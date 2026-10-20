"""Enumerations shared by the SQLAlchemy models and the Pydantic schemas."""

from enum import Enum


class SourceType(str, Enum):
    """Provenance of a record: real ClinicalTrials.gov data or generated data."""

    public_registry = "public_registry"
    synthetic = "synthetic"


class RecruitmentStatus(str, Enum):
    """ClinicalTrials.gov API v2 location/overall status values (stored verbatim).

    This is the *reported* registry status. It never implies activation.
    """

    NOT_YET_RECRUITING = "NOT_YET_RECRUITING"
    RECRUITING = "RECRUITING"
    ENROLLING_BY_INVITATION = "ENROLLING_BY_INVITATION"
    ACTIVE_NOT_RECRUITING = "ACTIVE_NOT_RECRUITING"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"
    UNKNOWN = "UNKNOWN"


class ActivationStatus(str, Enum):
    selected = "selected"
    in_startup = "in_startup"
    activated = "activated"
    on_hold = "on_hold"
    dropped = "dropped"


class UserRole(str, Enum):
    startup_manager = "startup_manager"
    cra = "cra"
    site_coordinator = "site_coordinator"
    regulatory = "regulatory"
    contracts = "contracts"
    pharmacist = "pharmacist"
    lab_manager = "lab_manager"
    pi = "pi"
    sponsor_supply = "sponsor_supply"


class Workstream(str, Enum):
    regulatory = "regulatory"
    contracts = "contracts"
    pharmacy = "pharmacy"
    training = "training"
    operations = "operations"
    activation = "activation"


class MilestoneStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    blocked = "blocked"
    complete = "complete"
    not_applicable = "not_applicable"


# Statuses that satisfy a dependency (not_applicable counts as done).
SATISFIED_STATUSES = frozenset({MilestoneStatus.complete, MilestoneStatus.not_applicable})


class EventType(str, Enum):
    status_change = "status_change"
    owner_change = "owner_change"
    due_date_change = "due_date_change"
    note = "note"


class DelayLevel(str, Enum):
    """Computed at query time from days overdue; never stored."""

    on_time = "on_time"
    days_1_7 = "1_7"
    days_8_30 = "8_30"
    over_30 = "over_30"


class SiteHealth(str, Enum):
    """Dashboard state of one trial site. Computed from its milestones; never stored."""

    activated = "activated"
    blocked = "blocked"
    at_risk = "at_risk"
    on_track = "on_track"
