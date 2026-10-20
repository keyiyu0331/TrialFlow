"""Readiness and blocker rules for one trial site.

Implements docs/domain-rules.md. Everything here is a pure function of the
milestones, the dependency edges, and an ``as_of`` date: no database, no clock,
so results are deterministic and tests need no fixtures beyond plain values.

Callers load a trial site's milestones and dependencies, convert them to
``MilestoneInput`` and ``(predecessor_id, successor_id)`` pairs, and call
``analyze``. Nothing computed here is ever stored.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, timedelta

from ..enums import SATISFIED_STATUSES, DelayLevel, MilestoneStatus, SiteHealth

GREEN_LIGHT_CODE = "GREEN_LIGHT"

Edge = tuple[int, int]  # (predecessor_id, successor_id)


@dataclass(frozen=True)
class MilestoneInput:
    """The fields of a milestone the rules need."""

    id: int
    status: MilestoneStatus
    due_date: date | None = None
    planned_start_date: date | None = None
    completed_date: date | None = None
    code: str | None = None
    # Template sort_order; the last tie-break for choosing the top blocker.
    sort_order: int = 0


@dataclass(frozen=True)
class MilestoneState:
    """Computed state of one milestone."""

    id: int
    satisfied: bool
    ready: bool
    overdue: bool
    days_overdue: int
    delay_level: DelayLevel
    blocking: bool
    root_blocker: bool
    # Unsatisfied milestones that transitively depend on this one.
    downstream_unsatisfied: int
    # None for not_applicable milestones, which add no constraint.
    projected_finish: date | None
    slip_days: int
    impacted: bool


@dataclass(frozen=True)
class SiteAnalysis:
    milestones: dict[int, MilestoneState]
    # Root blockers, best first (the first one is the top blocker).
    root_blocker_ids: list[int]
    top_blocker_id: int | None
    site_slip_days: int
    site_delay_level: DelayLevel
    health: SiteHealth


def delay_level(days_overdue: int) -> DelayLevel:
    """Bucket a number of days into the DelayLevel thresholds (0, 1-7, 8-30, over 30)."""
    if days_overdue <= 0:
        return DelayLevel.on_time
    if days_overdue <= 7:
        return DelayLevel.days_1_7
    if days_overdue <= 30:
        return DelayLevel.days_8_30
    return DelayLevel.over_30


def would_create_cycle(edges: list[Edge], predecessor_id: int, successor_id: int) -> bool:
    """True if adding predecessor -> successor closes a cycle.

    That happens when the successor can already reach the predecessor. A DB
    constraint cannot express this, so the service layer checks before insert.
    """
    if predecessor_id == successor_id:
        return True
    successors: dict[int, list[int]] = defaultdict(list)
    for pred, succ in edges:
        successors[pred].append(succ)
    seen: set[int] = set()
    stack = [successor_id]
    while stack:
        node = stack.pop()
        if node == predecessor_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(successors[node])
    return False


def analyze(milestones: list[MilestoneInput], edges: list[Edge], as_of: date) -> SiteAnalysis:
    """Compute readiness, blockers, slip, and health for one trial site.

    Raises ValueError for unknown milestone ids in ``edges`` or for a cycle.
    Milestones without a due date are never overdue and never slip, but they
    still wait on their predecessors.
    """
    by_id = {m.id: m for m in milestones}
    preds: dict[int, list[int]] = {m.id: [] for m in milestones}
    succs: dict[int, list[int]] = {m.id: [] for m in milestones}
    for pred, succ in edges:
        if pred not in by_id or succ not in by_id:
            raise ValueError(f"dependency {pred}->{succ} references an unknown milestone")
        preds[succ].append(pred)
        succs[pred].append(succ)

    order = _topological_order(by_id, preds, succs)
    satisfied = {m.id: m.status in SATISFIED_STATUSES for m in milestones}

    # D9: projected finish, predecessors first.
    finish: dict[int, date | None] = {}
    for mid in order:
        finish[mid] = _projected_finish(by_id[mid], [finish[p] for p in preds[mid]], as_of)

    states: dict[int, MilestoneState] = {}
    for m in milestones:
        mid = m.id
        is_satisfied = satisfied[mid]
        ready = not is_satisfied and all(satisfied[p] for p in preds[mid])
        overdue = not is_satisfied and m.due_date is not None and m.due_date < as_of
        days_overdue = (as_of - m.due_date).days if overdue else 0
        blocking = (
            not is_satisfied
            and m.code != GREEN_LIGHT_CODE
            and (overdue or m.status == MilestoneStatus.blocked)
        )
        slip = 0
        if not is_satisfied and m.due_date is not None and finish[mid] is not None:
            slip = max(0, (finish[mid] - m.due_date).days)
        states[mid] = MilestoneState(
            id=mid,
            satisfied=is_satisfied,
            ready=ready,
            overdue=overdue,
            days_overdue=days_overdue,
            delay_level=delay_level(days_overdue),
            blocking=blocking,
            root_blocker=blocking and ready,
            downstream_unsatisfied=_count_unsatisfied_downstream(mid, succs, satisfied),
            projected_finish=finish[mid],
            slip_days=slip,
            impacted=not is_satisfied and slip > 0,
        )

    # D7: best root blocker first.
    root_ids = sorted(
        (mid for mid, s in states.items() if s.root_blocker),
        key=lambda mid: (
            -states[mid].downstream_unsatisfied,
            -states[mid].days_overdue,
            by_id[mid].due_date or date.max,
            by_id[mid].sort_order,
            mid,
        ),
    )

    green = next((m for m in milestones if m.code == GREEN_LIGHT_CODE), None)
    if green is not None:
        site_slip = states[green.id].slip_days
    else:
        site_slip = max((s.slip_days for s in states.values()), default=0)

    if green is not None and green.status == MilestoneStatus.complete:
        health = SiteHealth.activated
    elif root_ids:
        health = SiteHealth.blocked
    elif site_slip > 0:
        health = SiteHealth.at_risk
    else:
        health = SiteHealth.on_track

    return SiteAnalysis(
        milestones=states,
        root_blocker_ids=root_ids,
        top_blocker_id=root_ids[0] if root_ids else None,
        site_slip_days=site_slip,
        site_delay_level=delay_level(site_slip),
        health=health,
    )


def _projected_finish(m: MilestoneInput, pred_finishes: list[date | None], as_of: date) -> date | None:
    if m.status == MilestoneStatus.complete:
        return m.completed_date or as_of
    if m.status == MilestoneStatus.not_applicable:
        return None  # adds no constraint to its successors
    if m.planned_start_date is not None and m.due_date is not None:
        duration = max((m.due_date - m.planned_start_date).days, 1)
    else:
        duration = 1
    candidates = [as_of]  # an unfinished milestone cannot finish before today
    if m.due_date is not None:
        candidates.append(m.due_date)
    constraints = [f for f in pred_finishes if f is not None]
    if constraints:
        candidates.append(max(constraints) + timedelta(days=duration))
    return max(candidates)


def _count_unsatisfied_downstream(start: int, succs: dict[int, list[int]], satisfied: dict[int, bool]) -> int:
    seen: set[int] = set()
    stack = list(succs[start])
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(succs[node])
    return sum(1 for node in seen if not satisfied[node])


def _topological_order(by_id: dict[int, MilestoneInput], preds: dict[int, list[int]],
                       succs: dict[int, list[int]]) -> list[int]:
    indegree = {mid: len(p) for mid, p in preds.items()}
    queue = deque(mid for mid, d in indegree.items() if d == 0)
    order: list[int] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in succs[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(by_id):
        raise ValueError("dependency cycle")
    return order
