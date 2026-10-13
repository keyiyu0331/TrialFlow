"""Placeholder data for the router stubs so /docs shows realistic responses.

The trial and site are real (NCT07578116 and one of its registry locations);
every milestone, owner, date, and event below is SYNTHETIC. Computed fields are
hard-coded here; the real readiness/blocker logic is not implemented yet.
Replace this module with database queries once the seed script exists.
"""

from datetime import date, datetime, timezone

from .enums import (
    ActivationStatus,
    DelayLevel,
    EventType,
    MilestoneStatus as S,
    RecruitmentStatus,
    SourceType,
    UserRole,
    Workstream as W,
)
from .schemas import (
    ActivationCounts,
    BlockerSummary,
    DependencyOut,
    EventOut,
    GraphEdge,
    GraphNode,
    MilestoneOut,
    OwnerRef,
    SiteOut,
    TemplateOut,
    TrialDetail,
    TrialRef,
    TrialSiteDetail,
    TrialSiteGraph,
    TrialSiteSummary,
    TrialSummary,
    UserOut,
)

TODAY = date(2026, 10, 13)
SYN = SourceType.synthetic
REG = SourceType.public_registry


def _ts(d: str) -> datetime:
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


# ---------- Templates: (code, name, workstream, owner role, days, is_gate, predecessors) ----------

TEMPLATE_ROWS = [
    ("IRB_APPROVAL", "IRB approval", W.regulatory, UserRole.regulatory, 45, False, []),
    ("CONTRACT_EXECUTED", "Contract executed", W.contracts, UserRole.contracts, 60, False, []),
    ("BUDGET_FINALIZED", "Budget finalized", W.contracts, UserRole.contracts, 45, False, []),
    ("REGULATORY_DOCS", "Regulatory documents", W.regulatory, UserRole.site_coordinator, 21, False, []),
    ("STAFF_TRAINING", "Staff training", W.training, UserRole.site_coordinator, 14, False, []),
    ("PHARMACY_SETUP", "Pharmacy setup", W.pharmacy, UserRole.pharmacist, 21, False, []),
    ("LAB_SYSTEMS_ACCESS", "Lab and systems access", W.operations, UserRole.lab_manager, 21, False, []),
    ("DRUG_SHIPMENT", "Drug shipped and received", W.pharmacy, UserRole.sponsor_supply, 14, False,
     ["IRB_APPROVAL", "PHARMACY_SETUP"]),
    ("SIV", "Site initiation visit", W.activation, UserRole.cra, 7, True,
     ["IRB_APPROVAL", "CONTRACT_EXECUTED", "BUDGET_FINALIZED", "REGULATORY_DOCS",
      "STAFF_TRAINING", "PHARMACY_SETUP", "LAB_SYSTEMS_ACCESS", "DRUG_SHIPMENT"]),
    ("GREEN_LIGHT", "Green light", W.activation, UserRole.startup_manager, 3, True, ["SIV"]),
]

TEMPLATES = [
    TemplateOut(id=i, code=c, name=n, workstream=w, default_owner_role=r,
                default_duration_days=d, is_gate=g, sort_order=i * 10, predecessor_codes=p)
    for i, (c, n, w, r, d, g, p) in enumerate(TEMPLATE_ROWS, start=1)
]

# ---------- Users (synthetic) ----------

SITE_ID = 2
USERS = [
    UserOut(id=1, name="Dana Whitfield", email="dana.whitfield@example.org",
            role=UserRole.startup_manager, site_id=None, team_name=None, source_type=SYN),
    UserOut(id=2, name="Marco Ruiz", email="marco.ruiz@example.org",
            role=UserRole.cra, site_id=None, team_name=None, source_type=SYN),
    UserOut(id=3, name="Sponsor supply team", email="supply@example.org",
            role=UserRole.sponsor_supply, site_id=None, team_name="Sponsor supply team",
            source_type=SYN),
    UserOut(id=11, name="Priya Natarajan", email="priya.natarajan@example.org",
            role=UserRole.site_coordinator, site_id=SITE_ID, team_name=None, source_type=SYN),
    UserOut(id=12, name="Site contracts office", email="contracts.derby@example.org",
            role=UserRole.contracts, site_id=SITE_ID, team_name="Site contracts office",
            source_type=SYN),
    UserOut(id=13, name="Grace Okafor", email="grace.okafor@example.org",
            role=UserRole.regulatory, site_id=SITE_ID, team_name=None, source_type=SYN),
    UserOut(id=14, name="Tom Becker", email="tom.becker@example.org",
            role=UserRole.pharmacist, site_id=SITE_ID, team_name=None, source_type=SYN),
    UserOut(id=15, name="Lena Park", email="lena.park@example.org",
            role=UserRole.lab_manager, site_id=SITE_ID, team_name=None, source_type=SYN),
]
_USER_BY_ID = {u.id: u for u in USERS}


def owner(user_id: int | None) -> OwnerRef | None:
    if user_id is None:
        return None
    u = _USER_BY_ID[user_id]
    return OwnerRef(id=u.id, name=u.name, role=u.role, team_name=u.team_name)


# ---------- Trial, site, trial site ----------

TRIAL_ID = 1
TRIAL_SITE_ID = 101

SITE = SiteOut(id=SITE_ID, name="Smilow Cancer Hospital-Derby Care Center",
               is_placeholder_name=False, city="Derby", state="Connecticut",
               country="United States", latitude=41.32065, longitude=-73.089, source_type=REG)

TRIAL_DETAIL = TrialDetail(
    id=TRIAL_ID, nct_id="NCT07578116",
    title="Adding Surgery and Radiation to the Usual Treatment for HER2-Positive Breast "
          "Cancer That Had Already Spread at Diagnosis",
    acronym=None, phases=["PHASE3"], sponsor_name="SWOG Cancer Research Network",
    overall_status=RecruitmentStatus.RECRUITING, site_count=59,
    activation_counts=ActivationCounts(in_startup=12, activated=47),
    source_type=REG, study_type="INTERVENTIONAL", lead_sponsor_class="NETWORK",
    start_date=date(2027, 3, 9), primary_completion_date=date(2032, 5, 31),
    completion_date=date(2033, 5, 31), last_update_posted_date=date(2026, 10, 13),
    last_registry_sync_at=_ts("2026-10-13T16:00:45"), target_site_count=60,
    target_fpi_date=date(2027, 3, 9),
    registry_url="https://clinicaltrials.gov/study/NCT07578116", avg_readiness_pct=86.3,
)
TRIAL_SUMMARY = TrialSummary(**TRIAL_DETAIL.model_dump(include=set(TrialSummary.model_fields)))

# ---------- Milestones for trial site 101 (synthetic "contract_stall" scenario) ----------
# (code, status, owner, due, started, completed, status_changed, blocked_reason)
_M = [
    ("IRB_APPROVAL", S.complete, 13, "2026-09-01", "2026-07-20", "2026-08-28", "2026-08-28", None),
    ("CONTRACT_EXECUTED", S.blocked, 12, "2026-10-01", "2026-08-01", None, "2026-09-15",
     "Indemnification clause under sponsor legal review"),
    ("BUDGET_FINALIZED", S.in_progress, 12, "2026-10-20", "2026-08-15", None, "2026-08-15", None),
    ("REGULATORY_DOCS", S.complete, 11, "2026-08-25", "2026-08-01", "2026-08-22", "2026-08-22", None),
    ("STAFF_TRAINING", S.in_progress, 11, "2026-10-25", "2026-10-01", None, "2026-10-01", None),
    ("PHARMACY_SETUP", S.complete, 14, "2026-09-10", "2026-08-10", "2026-09-08", "2026-09-08", None),
    ("LAB_SYSTEMS_ACCESS", S.not_started, 15, "2026-10-30", None, None, "2026-07-15", None),
    ("DRUG_SHIPMENT", S.not_started, 3, "2026-11-05", None, None, "2026-07-15", None),
    ("SIV", S.not_started, 2, "2026-11-15", None, None, "2026-07-15", None),
    ("GREEN_LIGHT", S.not_started, 1, "2026-11-20", None, None, "2026-07-15", None),
]
_TPL = {t.code: t for t in TEMPLATES}
_MID = {code: 1000 + i for i, (code, *_rest) in enumerate(_M, start=1)}
_BLOCKING = {_MID["CONTRACT_EXECUTED"]}


def _days_overdue(due: date, status: S) -> int:
    if status in (S.complete, S.not_applicable):
        return 0
    return max((TODAY - due).days, 0)


def _delay(days: int) -> DelayLevel:
    if days == 0:
        return DelayLevel.on_time
    if days <= 7:
        return DelayLevel.days_1_7
    if days <= 30:
        return DelayLevel.days_8_30
    return DelayLevel.over_30


MILESTONES: list[MilestoneOut] = []
for code, status, uid, due, started, completed, changed, reason in _M:
    t = _TPL[code]
    due_d = date.fromisoformat(due)
    od = _days_overdue(due_d, status)
    MILESTONES.append(MilestoneOut(
        id=_MID[code], template_code=code, name=t.name, workstream=t.workstream, status=status,
        owner=owner(uid), planned_start_date=date(2026, 7, 15), due_date=due_d,
        started_at=_ts(started) if started else None,
        completed_at=_ts(completed) if completed else None,
        status_changed_at=_ts(changed), blocked_reason=reason, notes=None,
        predecessor_ids=[_MID[p] for p in t.predecessor_codes],
        is_overdue=od > 0, days_overdue=od, delay_level=_delay(od),
        days_in_status=(TODAY - date.fromisoformat(changed)).days,
        is_blocking=_MID[code] in _BLOCKING, source_type=SYN,
    ))
_MILESTONE_BY_ID = {m.id: m for m in MILESTONES}

_contract = _MILESTONE_BY_ID[_MID["CONTRACT_EXECUTED"]]
TOP_BLOCKER = BlockerSummary(
    milestone_id=_contract.id, milestone_name=_contract.name, status=_contract.status,
    due_date=_contract.due_date, days_overdue=_contract.days_overdue,
    delay_level=_contract.delay_level, owner=_contract.owner,
)

_satisfied = sum(m.status in (S.complete, S.not_applicable) for m in MILESTONES)
TRIAL_SITE_SUMMARY = TrialSiteSummary(
    id=TRIAL_SITE_ID, site=SITE, reported_recruitment_status=RecruitmentStatus.RECRUITING,
    activation_status=ActivationStatus.in_startup, target_activation_date=date(2026, 11, 20),
    actual_activation_date=None, scenario_label="contract_stall", source_type=SYN,
    readiness_pct=round(100 * _satisfied / len(MILESTONES), 1),
    milestones_satisfied=_satisfied, milestones_total=len(MILESTONES), is_ready=False,
    delay_level=TOP_BLOCKER.delay_level, top_blocker=TOP_BLOCKER,
    next_action_owner=TOP_BLOCKER.owner,
)
TRIAL_SITE_DETAIL = TrialSiteDetail(
    **TRIAL_SITE_SUMMARY.model_dump(),
    trial=TrialRef(id=TRIAL_ID, nct_id=TRIAL_DETAIL.nct_id, title=TRIAL_DETAIL.title),
    selected_date=date(2026, 7, 15), milestones=MILESTONES,
)

# ---------- Graph ----------

DEPENDENCIES = [
    DependencyOut(id=5000 + i, trial_site_id=TRIAL_SITE_ID, predecessor_id=pred, successor_id=m.id,
                  source_type=SYN)
    for i, (m, pred) in enumerate(((m, p) for m in MILESTONES for p in m.predecessor_ids), start=1)
]

GRAPH = TrialSiteGraph(
    trial_site_id=TRIAL_SITE_ID,
    green_light_milestone_id=_MID["GREEN_LIGHT"],
    nodes=[
        GraphNode(milestone_id=m.id, template_code=m.template_code, name=m.name,
                  workstream=m.workstream, status=m.status, is_gate=_TPL[m.template_code].is_gate,
                  owner=m.owner, due_date=m.due_date,
                  is_satisfied=m.status in (S.complete, S.not_applicable),
                  is_overdue=m.is_overdue, is_blocking=m.is_blocking)
        for m in MILESTONES
    ],
    edges=[
        GraphEdge(id=d.id, predecessor_id=d.predecessor_id, successor_id=d.successor_id,
                  is_satisfied=_MILESTONE_BY_ID[d.predecessor_id].status in (S.complete, S.not_applicable),
                  source_type=SYN)
        for d in DEPENDENCIES
    ],
    blocking_milestone_ids=sorted(_BLOCKING),
)

# ---------- Events ----------

EVENTS = [
    EventOut(id=9003, milestone_id=_contract.id, milestone_name=_contract.name,
             event_type=EventType.status_change, old_value="in_progress", new_value="blocked",
             note="Indemnification clause under sponsor legal review", changed_by=owner(12),
             occurred_at=_ts("2026-09-15T14:05:00"), source_type=SYN),
    EventOut(id=9002, milestone_id=_MID["PHARMACY_SETUP"], milestone_name="Pharmacy setup",
             event_type=EventType.status_change, old_value="in_progress", new_value="complete",
             note=None, changed_by=owner(14), occurred_at=_ts("2026-09-08T10:30:00"), source_type=SYN),
    EventOut(id=9001, milestone_id=_contract.id, milestone_name=_contract.name,
             event_type=EventType.due_date_change, old_value="2026-09-15", new_value="2026-10-01",
             note="Redline round 2", changed_by=owner(1), occurred_at=_ts("2026-09-02T09:00:00"),
             source_type=SYN),
]


def milestone(milestone_id: int) -> MilestoneOut | None:
    return _MILESTONE_BY_ID.get(milestone_id)
