"""Pydantic request/response schemas for the TrialFlow REST API.

Fields marked "computed" are derived in the backend at query time and are never
stored. Every response object carries source_type so the UI can label real
registry data versus synthetic activation data.
"""

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    ActivationStatus,
    DelayLevel,
    EventType,
    MilestoneStatus,
    RecruitmentStatus,
    SiteHealth,
    SourceType,
    UserRole,
    Workstream,
)

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    detail: str
    code: str = Field(description="Machine-readable error code, e.g. dependency_cycle")
    cycle_path: list[int] | None = Field(
        default=None, description="Milestone IDs forming the cycle (409 dependency_cycle only)"
    )


# ---------- Users and owners ----------


class OwnerRef(ORMModel):
    """Compact owner reference embedded in milestones, blockers, and events."""

    id: int
    name: str
    role: UserRole
    team_name: str | None = None


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: UserRole
    site_id: int | None = Field(description="Null for sponsor or CRO staff")
    team_name: str | None = None
    source_type: SourceType


# ---------- Trials and sites ----------


class SiteOut(ORMModel):
    id: int
    name: str
    is_placeholder_name: bool = Field(description='True for registry placeholders like "Research Site"')
    city: str | None
    state: str | None
    country: str | None
    latitude: float | None = Field(default=None, description="City-level centroid")
    longitude: float | None = Field(default=None, description="City-level centroid")
    source_type: SourceType


class ActivationCounts(BaseModel):
    """Computed: trial sites per activation status."""

    selected: int = 0
    in_startup: int = 0
    activated: int = 0
    on_hold: int = 0
    dropped: int = 0


class TrialSummary(ORMModel):
    id: int
    nct_id: str | None
    title: str
    acronym: str | None
    phases: list[str]
    sponsor_name: str | None
    overall_status: RecruitmentStatus | None
    site_count: int = Field(description="Computed: number of trial sites")
    activation_counts: ActivationCounts
    source_type: SourceType


class TrialDetail(TrialSummary):
    study_type: str | None
    lead_sponsor_class: str | None
    start_date: date | None
    primary_completion_date: date | None
    completion_date: date | None
    last_update_posted_date: date | None
    last_registry_sync_at: datetime | None
    target_site_count: int | None
    target_fpi_date: date | None
    registry_url: str | None = Field(description="Computed from nct_id")
    avg_readiness_pct: float = Field(description="Computed: mean readiness across trial sites")


class TrialRef(ORMModel):
    id: int
    nct_id: str | None
    title: str


# ---------- Milestones ----------


class BlockerSummary(BaseModel):
    """Computed: the milestone currently holding up green light."""

    milestone_id: int
    milestone_name: str
    status: MilestoneStatus
    due_date: date | None
    days_overdue: int
    delay_level: DelayLevel
    owner: OwnerRef | None
    blocked_reason: str | None = None
    downstream_unsatisfied: int = Field(
        default=0, description="Computed: later milestones that cannot finish until this one does"
    )


class MilestoneOut(ORMModel):
    id: int
    template_code: str | None
    name: str
    workstream: Workstream
    status: MilestoneStatus
    owner: OwnerRef | None
    planned_start_date: date | None
    due_date: date | None
    started_at: datetime | None
    completed_at: datetime | None
    status_changed_at: datetime
    blocked_reason: str | None
    notes: str | None
    predecessor_ids: list[int] = Field(description="Milestones that must be satisfied first")
    # Computed at query time.
    is_overdue: bool
    days_overdue: int
    delay_level: DelayLevel
    days_in_status: int
    is_blocking: bool
    is_ready: bool = Field(default=False, description="Computed: unfinished, and every predecessor is satisfied")
    projected_finish: date | None = Field(default=None, description="Computed: null for not_applicable")
    slip_days: int = Field(default=0, description="Computed: days the projected finish is after the due date")
    is_impacted: bool = Field(default=False, description="Computed: unfinished and projected to slip")
    source_type: SourceType


class MilestoneUpdate(BaseModel):
    """PATCH body. Send only the fields to change; each change writes an event."""

    model_config = ConfigDict(extra="forbid")

    status: MilestoneStatus | None = None
    owner_user_id: int | None = None
    due_date: date | None = None
    blocked_reason: str | None = None
    note: str | None = Field(default=None, description="Optional comment stored on the events")
    changed_by_user_id: int | None = Field(default=None, description="Acting user (no auth in the MVP)")

    @model_validator(mode="after")
    def _require_a_change(self):
        if not self.model_fields_set & {"status", "owner_user_id", "due_date", "blocked_reason"}:
            raise ValueError("Provide at least one of status, owner_user_id, due_date, blocked_reason")
        if self.status == MilestoneStatus.blocked and not self.blocked_reason:
            raise ValueError("blocked_reason is required when status is blocked")
        return self


class EventOut(ORMModel):
    id: int
    milestone_id: int
    milestone_name: str
    event_type: EventType
    old_value: str | None
    new_value: str | None
    note: str | None
    changed_by: OwnerRef | None = Field(description="Null for system or seed-script changes")
    occurred_at: datetime
    source_type: SourceType


class MilestoneUpdateResult(BaseModel):
    milestone: MilestoneOut
    events: list[EventOut] = Field(description="Events written by this update")
    trial_site_activation_status: ActivationStatus = Field(
        description="May become activated when the green light milestone completes"
    )


# ---------- Trial sites ----------


class TrialSiteSummary(ORMModel):
    """One row of the trial dashboard (GET /trials/{id}/sites)."""

    id: int
    site: SiteOut
    reported_recruitment_status: RecruitmentStatus | None = Field(
        description="Real registry status; not an activation signal"
    )
    activation_status: ActivationStatus
    target_activation_date: date | None
    actual_activation_date: date | None
    scenario_label: str | None
    source_type: SourceType
    # Computed at query time.
    readiness_pct: float = Field(description="Satisfied (complete or n/a) / total milestones x 100")
    milestones_satisfied: int
    milestones_total: int
    is_ready: bool = Field(description="All milestones satisfied and no unresolved blocker")
    delay_level: DelayLevel = Field(description="Worst delay level among open milestones")
    top_blocker: BlockerSummary | None
    next_action_owner: OwnerRef | None
    health: SiteHealth = Field(description="Computed: activated, blocked, at_risk, or on_track")
    site_slip_days: int = Field(default=0, description="Computed: projected green light minus its due date")
    projected_activation_date: date | None = Field(
        default=None, description="Computed: projected green light date, from the dependency graph"
    )


class TrialSiteDetail(TrialSiteSummary):
    trial: TrialRef
    selected_date: date | None
    milestones: list[MilestoneOut]


# ---------- Dependency graph ----------


class GraphNode(BaseModel):
    milestone_id: int
    template_code: str | None
    name: str
    workstream: Workstream
    status: MilestoneStatus
    is_gate: bool
    owner: OwnerRef | None
    due_date: date | None
    # Computed.
    is_satisfied: bool
    is_overdue: bool
    is_blocking: bool
    is_ready: bool = False
    is_impacted: bool = False


class GraphEdge(BaseModel):
    id: int
    predecessor_id: int
    successor_id: int
    is_satisfied: bool = Field(description="Computed: predecessor is complete or not_applicable")
    source_type: SourceType


class TrialSiteGraph(BaseModel):
    trial_site_id: int
    green_light_milestone_id: int | None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    blocking_milestone_ids: list[int] = Field(description="Computed, most overdue first")


class DependencyCreate(BaseModel):
    predecessor_id: int
    successor_id: int

    @model_validator(mode="after")
    def _no_self_dependency(self):
        if self.predecessor_id == self.successor_id:
            raise ValueError("A milestone cannot depend on itself")
        return self


class DependencyOut(ORMModel):
    id: int
    trial_site_id: int
    predecessor_id: int
    successor_id: int
    source_type: SourceType


# ---------- Templates ----------


class TemplateOut(ORMModel):
    id: int
    code: str
    name: str
    workstream: Workstream
    default_owner_role: UserRole
    default_duration_days: int
    is_gate: bool
    sort_order: int
    predecessor_codes: list[str]
