"""The default milestone checklist and how a new trial site gets its milestones.

The checklist and durations come from docs/schema.md (midpoints of the ranges in
docs/site-activation-research.md). Creating a trial site copies the templates
into milestones and the template dependencies into milestone dependencies.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..enums import SourceType, UserRole, Workstream


@dataclass(frozen=True)
class TemplateSpec:
    code: str
    name: str
    workstream: Workstream
    owner_role: UserRole
    days: int
    sort_order: int
    predecessors: tuple[str, ...] = ()
    is_gate: bool = False


_PARALLEL = (
    "IRB_APPROVAL",
    "CONTRACT_EXECUTED",
    "BUDGET_FINALIZED",
    "REGULATORY_DOCS",
    "STAFF_TRAINING",
    "PHARMACY_SETUP",
    "LAB_SYSTEMS_ACCESS",
    "DRUG_SHIPMENT",
)

DEFAULT_TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec("IRB_APPROVAL", "IRB approval", Workstream.regulatory, UserRole.regulatory, 45, 10),
    TemplateSpec("CONTRACT_EXECUTED", "Contract executed", Workstream.contracts, UserRole.contracts, 60, 20),
    TemplateSpec("BUDGET_FINALIZED", "Budget finalized", Workstream.contracts, UserRole.contracts, 45, 30),
    TemplateSpec("REGULATORY_DOCS", "Regulatory documents", Workstream.regulatory, UserRole.site_coordinator, 21, 40),
    TemplateSpec("STAFF_TRAINING", "Staff training", Workstream.training, UserRole.site_coordinator, 14, 50),
    TemplateSpec("PHARMACY_SETUP", "Pharmacy setup", Workstream.pharmacy, UserRole.pharmacist, 21, 60),
    TemplateSpec("LAB_SYSTEMS_ACCESS", "Lab and systems access", Workstream.operations, UserRole.lab_manager, 21, 70),
    TemplateSpec(
        "DRUG_SHIPMENT",
        "Drug shipped and received",
        Workstream.operations,
        UserRole.sponsor_supply,
        14,
        80,
        predecessors=("IRB_APPROVAL", "PHARMACY_SETUP"),
    ),
    TemplateSpec(
        "SIV", "Site initiation visit", Workstream.activation, UserRole.cra, 7, 90, predecessors=_PARALLEL, is_gate=True
    ),
    TemplateSpec(
        "GREEN_LIGHT",
        "Green light",
        Workstream.activation,
        UserRole.startup_manager,
        3,
        100,
        predecessors=("SIV",),
        is_gate=True,
    ),
)


def ensure_templates(session: Session) -> dict[str, m.MilestoneTemplate]:
    """Create any missing default templates and dependencies. Idempotent."""
    existing = {t.code: t for t in session.scalars(select(m.MilestoneTemplate))}
    for spec in DEFAULT_TEMPLATES:
        if spec.code in existing:
            continue
        existing[spec.code] = m.MilestoneTemplate(
            code=spec.code,
            name=spec.name,
            workstream=spec.workstream,
            default_owner_role=spec.owner_role,
            default_duration_days=spec.days,
            is_gate=spec.is_gate,
            sort_order=spec.sort_order,
        )
        session.add(existing[spec.code])
    session.flush()

    have = {(d.predecessor_template_id, d.successor_template_id) for d in session.scalars(select(m.TemplateDependency))}
    for spec in DEFAULT_TEMPLATES:
        for pred_code in spec.predecessors:
            pair = (existing[pred_code].id, existing[spec.code].id)
            if pair not in have:
                session.add(m.TemplateDependency(predecessor_template_id=pair[0], successor_template_id=pair[1]))
    session.flush()
    return existing


def instantiate_trial_site(
    session: Session,
    trial_site: m.TrialSite,
    selected_date: date,
    owners_by_role: Mapping[UserRole, m.User] | None = None,
) -> dict[str, m.Milestone]:
    """Copy the templates into milestones for one trial site, in one transaction.

    Dates are a forward pass from ``selected_date``: a milestone starts when its
    last predecessor is due (or on the selected date) and is due after its default
    duration. ``owners_by_role`` assigns the default owner by role when given.
    Raises ValueError if the trial site already has milestones.
    """
    if session.scalar(select(m.Milestone.id).where(m.Milestone.trial_site_id == trial_site.id).limit(1)):
        raise ValueError(f"trial site {trial_site.id} already has milestones")

    templates = ensure_templates(session)
    specs = sorted(DEFAULT_TEMPLATES, key=lambda s: s.sort_order)
    milestones: dict[str, m.Milestone] = {}
    for spec in specs:  # predecessors always have a lower sort_order
        start = max((milestones[p].due_date for p in spec.predecessors), default=selected_date)
        owner = (owners_by_role or {}).get(spec.owner_role)
        milestones[spec.code] = m.Milestone(
            trial_site_id=trial_site.id,
            template_id=templates[spec.code].id,
            name=spec.name,
            workstream=spec.workstream,
            owner_user_id=owner.id if owner else None,
            planned_start_date=start,
            due_date=start + timedelta(days=spec.days),
            source_type=SourceType.synthetic,
        )
        session.add(milestones[spec.code])
    session.flush()

    for spec in specs:
        for pred_code in spec.predecessors:
            session.add(
                m.MilestoneDependency(
                    trial_site_id=trial_site.id,
                    predecessor_id=milestones[pred_code].id,
                    successor_id=milestones[spec.code].id,
                    source_type=SourceType.synthetic,
                )
            )
    session.flush()
    return milestones
