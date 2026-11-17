"""Open tasks: unfinished milestones on trial sites in start-up, most urgent first.

Pure functions, no DB. This is a port of ``openTasks`` in ``frontend/src/lib/insights.ts``
(the My tasks page); keep the two in step. See docs/domain-rules.md, "Open tasks".
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from .. import schemas as s
from ..enums import ActivationStatus, MilestoneStatus

TaskKind = Literal["blocked", "overdue", "due_soon", "in_progress", "ready", "waiting"]

TASK_KINDS: tuple[TaskKind, ...] = ("blocked", "overdue", "due_soon", "in_progress", "ready", "waiting")
RANK: dict[str, int] = {kind: i for i, kind in enumerate(TASK_KINDS)}
URGENT: frozenset[str] = frozenset({"blocked", "overdue", "due_soon"})
OPEN_STATUSES = frozenset({MilestoneStatus.not_started, MilestoneStatus.in_progress, MilestoneStatus.blocked})
DUE_SOON_DAYS = 7


@dataclass(frozen=True)
class Task:
    kind: TaskKind
    milestone: s.MilestoneOut
    trial_site: s.TrialSiteDetail
    until: int | None  # days until due (negative when late); None without a due date


def classify(ms: s.MilestoneOut, until: int | None, soon_days: int = DUE_SOON_DAYS) -> TaskKind:
    if ms.status == MilestoneStatus.blocked or ms.is_blocking:
        return "blocked"
    if ms.is_overdue:
        return "overdue"
    active = ms.status == MilestoneStatus.in_progress or ms.is_ready
    if active and until is not None and until <= soon_days:
        return "due_soon"
    if ms.status == MilestoneStatus.in_progress:
        return "in_progress"
    if ms.is_ready:
        return "ready"
    return "waiting"


def open_tasks(details: list[s.TrialSiteDetail], as_of: date, soon_days: int = DUE_SOON_DAYS) -> list[Task]:
    """Open milestones on trial sites still in start-up: blocked, overdue, due soon, then the rest."""
    out: list[Task] = []
    for site in details:
        if site.activation_status != ActivationStatus.in_startup:
            continue
        for ms in site.milestones:
            if ms.status not in OPEN_STATUSES:
                continue
            until = (ms.due_date - as_of).days if ms.due_date else None
            out.append(Task(classify(ms, until, soon_days), ms, site, until))
    out.sort(key=lambda t: (RANK[t.kind], -t.milestone.days_overdue, t.until if t.until is not None else 9999))
    return out
