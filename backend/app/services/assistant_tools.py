"""Read-only tools the Ask TrialFlow assistant can call.

``load_world`` is the only place that touches the DB and the only place scope is applied:
site staff see their own site's trial sites, sponsor/CRO staff see every tracked one.
Every tool is a pure function over that already-filtered list, so no tool can reach
data outside the caller's scope. Tools return compact JSON-able dicts with owner
name and role only (never email or other contact details) and never change anything.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import models as m
from .. import schemas as s
from ..enums import ActivationStatus, SiteHealth, UserRole
from . import tasks as tk
from . import views

SPONSOR_ROLES = frozenset({UserRole.startup_manager, UserRole.cra, UserRole.sponsor_supply})
TRACKED = (ActivationStatus.in_startup, ActivationStatus.on_hold, ActivationStatus.activated)


@dataclass(frozen=True)
class Scope:
    role: UserRole
    site_id: int | None = None

    @property
    def is_sponsor(self) -> bool:
        return self.role in SPONSOR_ROLES


def load_world(session: Session, scope: Scope, today: date, now: datetime) -> list[s.TrialSiteDetail]:
    """Every tracked trial site the caller may see, with milestones and computed status."""
    stmt = (
        select(m.TrialSite)
        .where(m.TrialSite.activation_status.in_(TRACKED))
        .options(joinedload(m.TrialSite.site), joinedload(m.TrialSite.trial))
        .order_by(m.TrialSite.id)
    )
    if not scope.is_sponsor:
        if scope.site_id is None:
            return []
        stmt = stmt.where(m.TrialSite.site_id == scope.site_id)
    trial_sites = list(session.scalars(stmt).unique())
    bundles = views.load_bundles(session, trial_sites, today)
    return [views.trial_site_detail(bundles[ts.id], ts.site, ts.trial, now) for ts in trial_sites]


# ---------- Shapes sent to the model ----------


def _owner(o: s.OwnerRef | None) -> dict | None:
    return {"name": o.name, "role": o.role.value} if o else None


def _d(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _site_row(d: s.TrialSiteDetail) -> dict:
    b = d.top_blocker
    return {
        "trial_site_id": d.id,
        "site": d.site.name,
        "city": d.site.city,
        "state": d.site.state,
        "country": d.site.country,
        "trial": d.trial.nct_id or d.trial.title,
        "activation_status": d.activation_status.value,
        "health": d.health.value,
        "readiness_pct": d.readiness_pct,
        "steps_done": f"{d.milestones_satisfied} of {d.milestones_total}",
        "top_blocker": (
            {
                "milestone": b.milestone_name,
                "status": b.status.value,
                "days_overdue": b.days_overdue,
                "blocked_reason": b.blocked_reason,
                "owner": _owner(b.owner),
                "later_steps_waiting": b.downstream_unsatisfied,
            }
            if b
            else None
        ),
        "target_go_live": _d(d.target_activation_date),
        "expected_go_live": _d(d.projected_activation_date),
        "activated_on": _d(d.actual_activation_date),
        "days_past_target": d.site_slip_days,
    }


def _task_row(t: tk.Task) -> dict:
    ms = t.milestone
    return {
        "kind": t.kind,
        "milestone": ms.name,
        "status": ms.status.value,
        "trial_site_id": t.trial_site.id,
        "site": t.trial_site.site.name,
        "trial": t.trial_site.trial.nct_id or t.trial_site.trial.title,
        "owner": _owner(ms.owner),
        "due_date": _d(ms.due_date),
        "days_until_due": t.until,
        "days_overdue": ms.days_overdue,
        "blocked_reason": ms.blocked_reason,
    }


# ---------- Tools ----------


def _matches(text: str | None, needle: str | None) -> bool:
    return not needle or (text is not None and needle.strip().lower() in text.lower())


def list_trial_sites(
    world: list[s.TrialSiteDetail], as_of: date, health: str | None = None, query: str | None = None
) -> dict:
    rows = [
        d
        for d in world
        if (not health or d.health.value == health)
        and (
            not query
            or any(_matches(v, query) for v in (d.site.name, d.site.city, d.site.state, d.trial.nct_id, d.trial.title))
        )
    ]
    return {"count": len(rows), "trial_sites": [_site_row(d) for d in rows]}


def get_trial_site(world: list[s.TrialSiteDetail], as_of: date, trial_site_id: int) -> dict:
    d = next((x for x in world if x.id == trial_site_id), None)
    if d is None:
        raise ToolError(f"Trial site {trial_site_id} does not exist or is not visible to this user.")
    names = {ms.id: ms.name for ms in d.milestones}
    return {
        **_site_row(d),
        "milestones": [
            {
                "milestone": ms.name,
                "status": ms.status.value,
                "owner": _owner(ms.owner),
                "due_date": _d(ms.due_date),
                "days_overdue": ms.days_overdue,
                "is_blocking": ms.is_blocking,
                "is_ready_to_start": ms.is_ready,
                "waits_on": [names[p] for p in ms.predecessor_ids if p in names],
                "expected_finish": _d(ms.projected_finish),
                "blocked_reason": ms.blocked_reason,
                "notes": ms.notes,
            }
            for ms in d.milestones
        ],
    }


def open_tasks(
    world: list[s.TrialSiteDetail],
    as_of: date,
    kind: str | None = None,
    owner_name: str | None = None,
    milestone: str | None = None,
    limit: int = 15,
) -> dict:
    tasks = [
        t
        for t in tk.open_tasks(world, as_of)
        if (not kind or (t.kind in tk.URGENT if kind == "urgent" else t.kind == kind))
        and (not owner_name or (t.milestone.owner is not None and _matches(t.milestone.owner.name, owner_name)))
        and _matches(t.milestone.name, milestone)
    ]
    limit = max(1, min(limit, 50))
    return {"total": len(tasks), "shown": min(limit, len(tasks)), "tasks": [_task_row(t) for t in tasks[:limit]]}


def portfolio_summary(world: list[s.TrialSiteDetail], as_of: date) -> dict:
    live = [d for d in world if d.activation_status == ActivationStatus.in_startup]
    tasks = tk.open_tasks(world, as_of)
    by_kind = {k: sum(1 for t in tasks if t.kind == k) for k in tk.TASK_KINDS}
    blocked = [d for d in live if d.top_blocker]
    blocked.sort(key=lambda d: (-d.top_blocker.downstream_unsatisfied, -d.top_blocker.days_overdue))
    projected = sorted(d.projected_activation_date for d in live if d.projected_activation_date)
    return {
        "trial_sites_tracked": len(world),
        "by_activation_status": {st.value: sum(1 for d in world if d.activation_status == st) for st in TRACKED},
        "in_startup_by_health": {
            h.value: sum(1 for d in live if d.health == h) for h in SiteHealth if h.value != "activated"
        },
        "average_readiness_pct": round(sum(d.readiness_pct for d in live) / len(live), 1) if live else None,
        "open_tasks_by_kind": by_kind,
        "projected_to_miss_target": sum(1 for d in live if d.site_slip_days > 0),
        "latest_expected_go_live": _d(projected[-1]) if projected else None,
        "chase_first": [_site_row(d) for d in blocked[:5]],
    }


class ToolError(Exception):
    """A tool call the model can recover from (bad id, out of scope); returned as an error result."""


_HEALTH = [h.value for h in SiteHealth]

TOOLS: list[dict[str, Any]] = [
    {
        "name": "portfolio_summary",
        "description": (
            "Overview of every trial site the user can see: counts by activation status and health, "
            "average readiness, open tasks by kind, how many will miss their target go-live, and the "
            "top blockers to chase first (ranked by how many later steps wait on them). "
            "Use for summaries, 'how are we doing', and 'what should I chase today'."
        ),
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "list_trial_sites",
        "description": (
            "List trial sites (one site in one trial) with readiness, health, top blocker and its owner, "
            "and target vs expected go-live. Filter by health and/or a text query matched against site "
            "name, city, state, trial NCT id or title. Use it to find a site's trial_site_id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "health": {"type": "string", "enum": _HEALTH, "description": "Only sites with this health"},
                "query": {"type": "string", "description": "Text to match, e.g. 'Oxford' or 'NCT06312176'"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_trial_site",
        "description": (
            "Full status of one trial site: every milestone with status, owner, due date, days overdue, "
            "whether it is blocking, what it waits on, expected finish, and any blocked reason or notes. "
            "Use to explain why a site is stuck or what happens next there."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"trial_site_id": {"type": "integer"}},
            "required": ["trial_site_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "open_tasks",
        "description": (
            "Open milestones on trial sites in start-up, most urgent first (blocked, overdue, due within 7 "
            "days, in progress, ready, waiting). Filter by kind ('urgent' = blocked + overdue + due soon), "
            "owner name (e.g. what does Nadia have open), and/or milestone name (e.g. 'contract', 'IRB')."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["urgent", *tk.TASK_KINDS]},
                "owner_name": {"type": "string", "description": "Part of the owner's name"},
                "milestone": {"type": "string", "description": "Part of the milestone name"},
                "limit": {"type": "integer", "description": "Max tasks to return, 1-50 (default 15)"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]

_FUNCS = {
    "portfolio_summary": portfolio_summary,
    "list_trial_sites": list_trial_sites,
    "get_trial_site": get_trial_site,
    "open_tasks": open_tasks,
}


@dataclass
class ToolRun:
    """Result of one tool call, plus the trial site ids it showed the model."""

    result: dict
    trial_site_ids: set[int] = field(default_factory=set)
    is_error: bool = False


def _ids(value: Any) -> set[int]:
    """Every trial_site_id anywhere in a tool result."""
    if isinstance(value, dict):
        found = {value["trial_site_id"]} if isinstance(value.get("trial_site_id"), int) else set()
        return found.union(*(_ids(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_ids(v) for v in value))
    return set()


def run_tool(name: str, args: dict, world: list[s.TrialSiteDetail], as_of: date) -> ToolRun:
    func = _FUNCS.get(name)
    if func is None:
        return ToolRun({"error": f"Unknown tool {name!r}"}, is_error=True)
    try:
        result = func(world, as_of, **(args or {}))
    except ToolError as e:
        return ToolRun({"error": str(e)}, is_error=True)
    except TypeError as e:  # unexpected arguments
        return ToolRun({"error": f"Bad arguments for {name}: {e}"}, is_error=True)
    return ToolRun(result, _ids(result))
