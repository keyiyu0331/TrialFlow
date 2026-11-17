"""Open-task rules (services/tasks.py), the Python port of openTasks in frontend/src/lib/insights.ts."""

from datetime import UTC, datetime

from app import schemas as s
from app.enums import ActivationStatus, MilestoneStatus, UserRole
from app.services import tasks as tk
from app.services.assistant_tools import Scope, load_world
from conftest import AS_OF


def _ms(**kw) -> s.MilestoneOut:
    base = dict(status=MilestoneStatus.not_started, is_blocking=False, is_overdue=False, is_ready=False)
    return s.MilestoneOut.model_construct(**{**base, **kw})


def test_classify_order_of_precedence():
    assert tk.classify(_ms(status=MilestoneStatus.blocked), None) == "blocked"
    assert tk.classify(_ms(is_blocking=True, is_overdue=True), -5) == "blocked"
    assert tk.classify(_ms(is_overdue=True, status=MilestoneStatus.in_progress), -3) == "overdue"
    assert tk.classify(_ms(status=MilestoneStatus.in_progress), 7) == "due_soon"
    assert tk.classify(_ms(is_ready=True), 2) == "due_soon"
    assert tk.classify(_ms(status=MilestoneStatus.in_progress), 8) == "in_progress"
    assert tk.classify(_ms(status=MilestoneStatus.in_progress), None) == "in_progress"
    assert tk.classify(_ms(is_ready=True), 30) == "ready"
    # Not started and not ready: due dates don't make it urgent until it can start.
    assert tk.classify(_ms(), 1) == "waiting"


def test_open_tasks_on_seeded_world(seeded):
    world = load_world(seeded, Scope(UserRole.startup_manager), AS_OF, datetime.now(UTC))
    tasks = tk.open_tasks(world, AS_OF)
    assert tasks
    assert all(t.trial_site.activation_status == ActivationStatus.in_startup for t in tasks)
    assert all(t.milestone.status in tk.OPEN_STATUSES for t in tasks)
    ranks = [tk.RANK[t.kind] for t in tasks]
    assert ranks == sorted(ranks)
    blocked = [t for t in tasks if t.kind == "blocked"]
    late = [t.milestone.days_overdue for t in blocked]
    assert late == sorted(late, reverse=True)
    for t in tasks:
        if t.milestone.due_date:
            assert t.until == (t.milestone.due_date - AS_OF).days
