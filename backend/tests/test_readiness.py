"""Tests for app.services.readiness, written from docs/domain-rules.md.

They use plain values (no database) and the default template from docs/schema.md:
seven independent milestones, DRUG_SHIPMENT after IRB_APPROVAL and PHARMACY_SETUP,
SIV after all eight, GREEN_LIGHT after SIV.
"""

from datetime import date, timedelta

import pytest

from app.enums import DelayLevel, MilestoneStatus, SiteHealth
from app.services.readiness import (
    MilestoneInput,
    analyze,
    delay_level,
    would_create_cycle,
)

AS_OF = date(2026, 11, 1)
COMPLETE = MilestoneStatus.complete
NOT_STARTED = MilestoneStatus.not_started
IN_PROGRESS = MilestoneStatus.in_progress
BLOCKED = MilestoneStatus.blocked
NA = MilestoneStatus.not_applicable

IRB, CONTRACT, BUDGET, REGDOCS, TRAINING, PHARMACY, LAB, SHIPMENT, SIV, GREEN = range(1, 11)

# id -> (code, default duration in days, default due offset from AS_OF).
# The default schedule is exactly tight, so an untouched site has zero slip.
TEMPLATE = {
    IRB: ("IRB_APPROVAL", 45, 30),
    CONTRACT: ("CONTRACT_EXECUTED", 60, 30),
    BUDGET: ("BUDGET_FINALIZED", 45, 30),
    REGDOCS: ("REGULATORY_DOCS", 21, 30),
    TRAINING: ("STAFF_TRAINING", 14, 30),
    PHARMACY: ("PHARMACY_SETUP", 21, 30),
    LAB: ("LAB_SYSTEMS_ACCESS", 21, 30),
    SHIPMENT: ("DRUG_SHIPMENT", 14, 45),
    SIV: ("SIV", 7, 52),
    GREEN: ("GREEN_LIGHT", 3, 55),
}
EDGES = [(IRB, SHIPMENT), (PHARMACY, SHIPMENT)] + [(i, SIV) for i in range(1, 9)] + [(SIV, GREEN)]


def build(statuses=None, dues=None, sort_orders=None, completed_offset=-30):
    """Ten milestones. `dues` maps id -> days from AS_OF; unlisted ids use the default."""
    statuses = statuses or {}
    dues = dues or {}
    sort_orders = sort_orders or {}
    out = []
    for mid, (code, duration, default_due) in TEMPLATE.items():
        due = AS_OF + timedelta(days=dues.get(mid, default_due))
        status = statuses.get(mid, NOT_STARTED)
        out.append(
            MilestoneInput(
                id=mid,
                status=status,
                due_date=due,
                planned_start_date=due - timedelta(days=duration),
                completed_date=AS_OF + timedelta(days=completed_offset) if status == COMPLETE else None,
                code=code,
                sort_order=sort_orders.get(mid, mid),
            )
        )
    return out


def run(statuses=None, dues=None, sort_orders=None):
    return analyze(build(statuses, dues, sort_orders), EDGES, AS_OF)


def all_complete(**overrides):
    statuses = {mid: COMPLETE for mid in TEMPLATE}
    statuses.update(overrides)
    return statuses


def test_fresh_site_ready_set_and_no_blockers():
    result = run()
    ready = {mid for mid, s in result.milestones.items() if s.ready}
    assert ready == {IRB, CONTRACT, BUDGET, REGDOCS, TRAINING, PHARMACY, LAB}
    assert not result.milestones[SHIPMENT].ready
    assert not result.milestones[SIV].ready
    assert not result.milestones[GREEN].ready
    assert result.root_blocker_ids == []
    assert result.top_blocker_id is None
    assert result.site_slip_days == 0
    assert result.health == SiteHealth.on_track


def test_irb_complete_pharmacy_overdue_is_root_blocker():
    result = run({IRB: COMPLETE}, dues={PHARMACY: -3})
    assert not result.milestones[SHIPMENT].ready
    assert result.milestones[PHARMACY].root_blocker
    assert result.root_blocker_ids == [PHARMACY]
    assert result.top_blocker_id == PHARMACY
    assert result.health == SiteHealth.blocked


def test_overdue_boundary():
    on_due_date = run(dues={CONTRACT: 0}).milestones[CONTRACT]
    assert not on_due_date.overdue
    assert on_due_date.days_overdue == 0
    assert not on_due_date.blocking

    one_day_late = run(dues={CONTRACT: -1}).milestones[CONTRACT]
    assert one_day_late.overdue
    assert one_day_late.days_overdue == 1
    assert one_day_late.delay_level == DelayLevel.days_1_7


@pytest.mark.parametrize(
    "days, expected",
    [
        (0, DelayLevel.on_time),
        (1, DelayLevel.days_1_7),
        (7, DelayLevel.days_1_7),
        (8, DelayLevel.days_8_30),
        (30, DelayLevel.days_8_30),
        (31, DelayLevel.over_30),
    ],
)
def test_delay_level_boundaries(days, expected):
    assert delay_level(days) == expected


def test_slip_propagates_to_all_downstream_milestones():
    # Everything else is done; IRB is 20 days late and the planned schedule has no slack.
    statuses = all_complete()
    for mid in (IRB, SHIPMENT, SIV, GREEN):
        del statuses[mid]
    dues = {IRB: -20, SHIPMENT: -6, SIV: 1, GREEN: 4}
    result = run(statuses, dues)
    for mid in (IRB, SHIPMENT, SIV, GREEN):
        state = result.milestones[mid]
        assert state.impacted
        assert state.slip_days == 20
    assert result.milestones[IRB].projected_finish == AS_OF  # cannot finish before today
    assert result.site_slip_days == 20
    assert result.site_delay_level == DelayLevel.days_8_30
    assert result.root_blocker_ids == [IRB]  # SHIPMENT is overdue but still waiting on IRB
    assert result.milestones[SHIPMENT].blocking
    assert not result.milestones[SHIPMENT].root_blocker


def test_not_applicable_pharmacy_does_not_block_shipment():
    result = run({IRB: COMPLETE, PHARMACY: NA}, dues={PHARMACY: -10})
    pharmacy = result.milestones[PHARMACY]
    assert pharmacy.satisfied
    assert not pharmacy.overdue
    assert not pharmacy.blocking
    assert pharmacy.projected_finish is None
    assert result.milestones[SHIPMENT].ready


def test_blocked_status_counts_as_blocking_before_due_date():
    result = run({BUDGET: BLOCKED})
    budget = result.milestones[BUDGET]
    assert not budget.overdue
    assert budget.blocking
    assert budget.root_blocker
    assert result.top_blocker_id == BUDGET
    assert result.health == SiteHealth.blocked


def test_top_blocker_prefers_downstream_impact_over_days_overdue():
    # IRB gates 3 later milestones, CONTRACT only 2, although CONTRACT is far more overdue.
    result = run(dues={IRB: -1, CONTRACT: -10})
    assert result.root_blocker_ids == [IRB, CONTRACT]
    assert result.top_blocker_id == IRB


def test_top_blocker_tie_breaks_on_days_overdue():
    result = run({IRB: COMPLETE}, dues={CONTRACT: -10, BUDGET: -3})
    assert result.root_blocker_ids == [CONTRACT, BUDGET]


def test_top_blocker_tie_breaks_on_earliest_due_date():
    # Both flagged blocked and not yet overdue, so days overdue ties at 0.
    result = run({IRB: COMPLETE, CONTRACT: BLOCKED, BUDGET: BLOCKED}, dues={CONTRACT: 10, BUDGET: 5})
    assert result.root_blocker_ids == [BUDGET, CONTRACT]


def test_top_blocker_last_tie_break_is_sort_order():
    result = run(
        {IRB: COMPLETE},
        dues={CONTRACT: -5, BUDGET: -5},
        sort_orders={BUDGET: 1, CONTRACT: 2},
    )
    assert result.root_blocker_ids == [BUDGET, CONTRACT]


def test_activated_site():
    result = run(all_complete())
    assert result.health == SiteHealth.activated
    assert result.top_blocker_id is None
    assert result.root_blocker_ids == []
    assert result.site_slip_days == 0


def test_at_risk_when_slipping_without_any_blocker():
    # Nothing is overdue or blocked, but shipment is due before its predecessors allow.
    result = run(dues={SHIPMENT: 40, SIV: 45, GREEN: 48})
    assert result.root_blocker_ids == []
    assert result.site_slip_days == 6
    assert result.site_delay_level == DelayLevel.days_1_7
    assert result.health == SiteHealth.at_risk


def test_in_progress_milestone_is_still_unsatisfied():
    result = run({IRB: IN_PROGRESS})
    assert not result.milestones[IRB].satisfied
    assert not result.milestones[SHIPMENT].ready


def test_cycle_is_rejected():
    with pytest.raises(ValueError, match="cycle"):
        analyze(build(), EDGES + [(GREEN, IRB)], AS_OF)


def test_would_create_cycle():
    assert would_create_cycle(EDGES, GREEN, IRB)
    assert would_create_cycle(EDGES, IRB, IRB)
    assert not would_create_cycle(EDGES, IRB, GREEN)  # redundant but acyclic
    assert not would_create_cycle(EDGES, CONTRACT, SHIPMENT)  # the open schema question


def test_unknown_milestone_in_edge_is_rejected():
    with pytest.raises(ValueError, match="unknown"):
        analyze(build(), EDGES + [(IRB, 99)], AS_OF)
