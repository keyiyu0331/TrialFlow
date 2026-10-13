"""SQLAlchemy models for TrialFlow. See docs/schema.md for the rationale.

Stored: facts (real registry fields, synthetic milestones, history).
Not stored: overdue, delay level, days in status, blocking, next-action owner,
readiness, projected activation. Those are computed in the backend.
"""

from datetime import date, datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import (
    ActivationStatus,
    EventType,
    MilestoneStatus,
    RecruitmentStatus,
    SourceType,
    UserRole,
    Workstream,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(enum_cls: type[PyEnum], name: str) -> Enum:
    """Native enum on PostgreSQL, CHECK constraint on SQLite; stores the values."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_constraint=True,
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class Trial(TimestampMixin, Base):
    """One clinical trial. Real rows come from ClinicalTrials.gov API v2."""

    __tablename__ = "trials"
    __table_args__ = (
        CheckConstraint(
            "source_type = 'synthetic' OR nct_id IS NOT NULL",
            name="ck_trials_registry_has_nct_id",
        ),
        CheckConstraint(
            "target_site_count IS NULL OR target_site_count >= 0",
            name="ck_trials_target_site_count_nonneg",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nct_id: Mapped[str | None] = mapped_column(String(11), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    acronym: Mapped[str | None] = mapped_column(String(64))
    # designModule.phases is an array (e.g. ["PHASE1", "PHASE2"]) and may be absent.
    phases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    study_type: Mapped[str | None] = mapped_column(String(32))
    sponsor_name: Mapped[str | None] = mapped_column(Text)
    lead_sponsor_class: Mapped[str | None] = mapped_column(String(32))
    overall_status: Mapped[RecruitmentStatus | None] = mapped_column(
        _enum(RecruitmentStatus, "recruitment_status")
    )
    # Registry dates may be partial (YYYY-MM); the importer stores the 1st of the month.
    start_date: Mapped[date | None] = mapped_column(Date)
    primary_completion_date: Mapped[date | None] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)
    last_update_posted_date: Mapped[date | None] = mapped_column(Date)
    last_registry_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Synthetic planning fields.
    target_site_count: Mapped[int | None] = mapped_column(Integer)
    target_fpi_date: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), nullable=False
    )

    trial_sites: Mapped[list["TrialSite"]] = relationship(back_populates="trial")


class Site(TimestampMixin, Base):
    """One research institution, shared across trials.

    API v2 locations have no stable ID, so the importer de-duplicates on
    dedup_key: normalized name|city|state|country, or nct_id:location_index for
    placeholder names such as "Research Site" that must never be merged.
    """

    __tablename__ = "sites"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="ck_sites_latitude"
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="ck_sites_longitude"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedup_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_placeholder_name: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    zip: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(Text)
    # geoPoint is a city-level centroid in API v2, not the facility location.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), nullable=False
    )

    trial_sites: Mapped[list["TrialSite"]] = relationship(back_populates="site")
    users: Mapped[list["User"]] = relationship(back_populates="site")


class TrialSite(TimestampMixin, Base):
    """One site in one trial: the unit TrialFlow activates."""

    __tablename__ = "trial_sites"
    __table_args__ = (
        UniqueConstraint("trial_id", "site_id", name="uq_trial_sites_trial_site"),
        CheckConstraint(
            "actual_activation_date IS NULL OR activation_status = 'activated'",
            name="ck_trial_sites_activation_date_only_when_activated",
        ),
        CheckConstraint(
            "ctgov_location_index IS NULL OR ctgov_location_index >= 1",
            name="ck_trial_sites_location_index_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trial_id: Mapped[int] = mapped_column(
        ForeignKey("trials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # 1-based position in contactsLocationsModule.locations; stable only within one pull.
    ctgov_location_index: Mapped[int | None] = mapped_column(Integer)
    # Real per-site registry status. Never used to infer activation.
    reported_recruitment_status: Mapped[RecruitmentStatus | None] = mapped_column(
        _enum(RecruitmentStatus, "recruitment_status")
    )
    activation_status: Mapped[ActivationStatus] = mapped_column(
        _enum(ActivationStatus, "activation_status"),
        default=ActivationStatus.selected,
        nullable=False,
    )
    selected_date: Mapped[date | None] = mapped_column(Date)
    target_activation_date: Mapped[date | None] = mapped_column(Date)
    actual_activation_date: Mapped[date | None] = mapped_column(Date)
    # Provenance of the activation data on this row (milestones are always synthetic in the MVP).
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), nullable=False
    )
    scenario_label: Mapped[str | None] = mapped_column(String(64))

    trial: Mapped[Trial] = relationship(back_populates="trial_sites")
    site: Mapped[Site] = relationship(back_populates="trial_sites")
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="trial_site", cascade="all, delete-orphan", passive_deletes=True
    )


class User(TimestampMixin, Base):
    """A milestone owner: a person or a team. site_id is null for sponsor/CRO staff."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False)
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), index=True
    )
    team_name: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), default=SourceType.synthetic, nullable=False
    )

    site: Mapped[Site | None] = relationship(back_populates="users")


class MilestoneTemplate(TimestampMixin, Base):
    """The standard checklist every new trial site starts from."""

    __tablename__ = "milestone_templates"
    __table_args__ = (
        CheckConstraint("default_duration_days >= 0", name="ck_templates_duration_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    workstream: Mapped[Workstream] = mapped_column(
        _enum(Workstream, "workstream"), nullable=False
    )
    default_owner_role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "user_role"), nullable=False
    )
    default_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_gate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)


class TemplateDependency(Base):
    """Default dependency graph between templates (predecessor must finish first)."""

    __tablename__ = "template_dependencies"
    __table_args__ = (
        CheckConstraint(
            "predecessor_template_id <> successor_template_id",
            name="ck_template_dependencies_no_self",
        ),
    )

    predecessor_template_id: Mapped[int] = mapped_column(
        ForeignKey("milestone_templates.id", ondelete="CASCADE"), primary_key=True
    )
    successor_template_id: Mapped[int] = mapped_column(
        ForeignKey("milestone_templates.id", ondelete="CASCADE"), primary_key=True
    )


class Milestone(TimestampMixin, Base):
    """One task for one trial site, copied from a template (or custom)."""

    __tablename__ = "milestones"
    __table_args__ = (
        # Target of the composite FKs that keep dependencies within one trial site.
        UniqueConstraint("id", "trial_site_id", name="uq_milestones_id_trial_site"),
        # A template is instantiated at most once per trial site.
        UniqueConstraint("trial_site_id", "template_id", name="uq_milestones_site_template"),
        CheckConstraint(
            "(status = 'complete' AND completed_at IS NOT NULL)"
            " OR (status <> 'complete' AND completed_at IS NULL)",
            name="ck_milestones_completed_at_matches_status",
        ),
        CheckConstraint(
            "planned_start_date IS NULL OR due_date IS NULL OR due_date >= planned_start_date",
            name="ck_milestones_due_after_start",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trial_site_id: Mapped[int] = mapped_column(
        ForeignKey("trial_sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("milestone_templates.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    workstream: Mapped[Workstream] = mapped_column(
        _enum(Workstream, "workstream"), nullable=False
    )
    status: Mapped[MilestoneStatus] = mapped_column(
        _enum(MilestoneStatus, "milestone_status"),
        default=MilestoneStatus.not_started,
        nullable=False,
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), default=SourceType.synthetic, nullable=False
    )

    trial_site: Mapped[TrialSite] = relationship(back_populates="milestones")
    template: Mapped[MilestoneTemplate | None] = relationship()
    owner: Mapped[User | None] = relationship()
    events: Mapped[list["MilestoneEvent"]] = relationship(
        back_populates="milestone", cascade="all, delete-orphan", passive_deletes=True
    )


class MilestoneDependency(TimestampMixin, Base):
    """A trial site's actual dependency graph (copied from templates, editable).

    trial_site_id is denormalized so the composite foreign keys guarantee both
    milestones belong to the same trial site. Cycle checks live in the service layer.
    """

    __tablename__ = "milestone_dependencies"
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_milestone_dependencies_pair"),
        CheckConstraint("predecessor_id <> successor_id", name="ck_milestone_dependencies_no_self"),
        ForeignKeyConstraint(
            ["predecessor_id", "trial_site_id"],
            ["milestones.id", "milestones.trial_site_id"],
            name="fk_milestone_dependencies_predecessor_same_site",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["successor_id", "trial_site_id"],
            ["milestones.id", "milestones.trial_site_id"],
            name="fk_milestone_dependencies_successor_same_site",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trial_site_id: Mapped[int] = mapped_column(
        ForeignKey("trial_sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    predecessor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    successor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), default=SourceType.synthetic, nullable=False
    )

    predecessor: Mapped[Milestone] = relationship(
        foreign_keys=[predecessor_id],
        primaryjoin="MilestoneDependency.predecessor_id == Milestone.id",
        viewonly=True,
    )
    successor: Mapped[Milestone] = relationship(
        foreign_keys=[successor_id],
        primaryjoin="MilestoneDependency.successor_id == Milestone.id",
        viewonly=True,
    )


class MilestoneEvent(Base):
    """Append-only change history: one row per status, owner, or due-date change."""

    __tablename__ = "milestone_events"
    __table_args__ = (
        CheckConstraint(
            "event_type = 'note' OR COALESCE(old_value, '') <> COALESCE(new_value, '')",
            name="ck_milestone_events_value_changed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    event_type: Mapped[EventType] = mapped_column(_enum(EventType, "event_type"), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    # Set explicitly by the seed script to backfill synthetic history.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type"), default=SourceType.synthetic, nullable=False
    )

    milestone: Mapped[Milestone] = relationship(back_populates="events")
    changed_by: Mapped[User | None] = relationship()
