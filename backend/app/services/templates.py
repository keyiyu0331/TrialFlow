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
from ..enums import SourceType, TrialType, UserRole, Workstream
from .trial_types import classify_trial_type


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


def _gates(parallel: tuple[str, ...]) -> tuple[TemplateSpec, ...]:
    """The two gate milestones every type ends with: SIV needs every other step, then green light."""
    return (
        TemplateSpec(
            "SIV",
            "Site initiation visit",
            Workstream.activation,
            UserRole.cra,
            7,
            90,
            predecessors=parallel,
            is_gate=True,
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


# Steps every trial site needs, whatever the trial ships.
_COMMON: tuple[TemplateSpec, ...] = (
    TemplateSpec("IRB_APPROVAL", "IRB approval", Workstream.regulatory, UserRole.regulatory, 45, 10),
    TemplateSpec("CONTRACT_EXECUTED", "Contract executed", Workstream.contracts, UserRole.contracts, 60, 20),
    TemplateSpec("BUDGET_FINALIZED", "Budget finalized", Workstream.contracts, UserRole.contracts, 45, 30),
    TemplateSpec("REGULATORY_DOCS", "Regulatory documents", Workstream.regulatory, UserRole.site_coordinator, 21, 40),
    TemplateSpec("STAFF_TRAINING", "Staff training", Workstream.training, UserRole.site_coordinator, 14, 50),
    TemplateSpec("LAB_SYSTEMS_ACCESS", "Lab and systems access", Workstream.operations, UserRole.lab_manager, 21, 70),
)

_DRUG_ONLY: tuple[TemplateSpec, ...] = (
    TemplateSpec("PHARMACY_SETUP", "Pharmacy setup", Workstream.pharmacy, UserRole.pharmacist, 21, 60),
    TemplateSpec(
        "DRUG_SHIPMENT",
        "Drug shipped and received",
        Workstream.operations,
        UserRole.sponsor_supply,
        14,
        80,
        predecessors=("IRB_APPROVAL", "PHARMACY_SETUP"),
    ),
)

# Devices skip the pharmacy. They need a biomedical safety check before shipment, and the
# site staff can only be trained on the device once it has arrived. These durations are
# synthetic assumptions: docs/site-activation-research.md benchmarks drug trials only.
_DEVICE_ONLY: tuple[TemplateSpec, ...] = (
    TemplateSpec("DEVICE_SAFETY_CHECK", "Device safety check", Workstream.operations, UserRole.lab_manager, 21, 65),
    TemplateSpec(
        "DEVICE_SHIPMENT",
        "Device shipped and received",
        Workstream.operations,
        UserRole.sponsor_supply,
        14,
        85,
        predecessors=("IRB_APPROVAL", "DEVICE_SAFETY_CHECK"),
    ),
    TemplateSpec(
        "DEVICE_TRAINING",
        "Device operator training",
        Workstream.training,
        UserRole.site_coordinator,
        10,
        87,
        predecessors=("DEVICE_SHIPMENT",),
    ),
)


def _checklist(extra: tuple[TemplateSpec, ...]) -> tuple[TemplateSpec, ...]:
    steps = tuple(sorted((*_COMMON, *extra), key=lambda s: s.sort_order))
    return (*steps, *_gates(tuple(s.code for s in steps)))


# The checklist per trial type (rule D14). Creating a trial site copies its type's checklist.
CHECKLISTS: dict[TrialType, tuple[TemplateSpec, ...]] = {
    TrialType.drug: _checklist(_DRUG_ONLY),
    TrialType.device: _checklist(_DEVICE_ONLY),
    TrialType.no_product: _checklist(()),
}
DEFAULT_TEMPLATES = CHECKLISTS[TrialType.drug]  # the original ten-step drug checklist

_ALL_SPECS: tuple[TemplateSpec, ...] = tuple(
    {spec.code: spec for checklist in CHECKLISTS.values() for spec in checklist}.values()
)


def checklist_for(trial_type: TrialType) -> tuple[TemplateSpec, ...]:
    return CHECKLISTS[trial_type]


def ensure_templates(session: Session) -> dict[str, m.MilestoneTemplate]:
    """Create any missing templates (for every trial type) and dependencies. Idempotent.

    SIV depends on a different set of steps in each type, so its template dependencies
    are the union; instantiation uses the per-type checklist, not these rows.
    """
    existing = {t.code: t for t in session.scalars(select(m.MilestoneTemplate))}
    for spec in sorted(_ALL_SPECS, key=lambda s: s.sort_order):
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
    for checklist in CHECKLISTS.values():
        for spec in checklist:
            for pred_code in spec.predecessors:
                pair = (existing[pred_code].id, existing[spec.code].id)
                if pair not in have:
                    session.add(m.TemplateDependency(predecessor_template_id=pair[0], successor_template_id=pair[1]))
                    have.add(pair)
    session.flush()
    return existing


def instantiate_trial_site(
    session: Session,
    trial_site: m.TrialSite,
    selected_date: date,
    owners_by_role: Mapping[UserRole, m.User] | None = None,
    trial_type: TrialType | None = None,
) -> dict[str, m.Milestone]:
    """Copy the trial type's checklist into milestones for one trial site, in one transaction.

    ``trial_type`` defaults to the type derived from the trial's intervention types.

    Dates are a forward pass from ``selected_date``: a milestone starts when its
    last predecessor is due (or on the selected date) and is due after its default
    duration. ``owners_by_role`` assigns the default owner by role when given.
    Raises ValueError if the trial site already has milestones.
    """
    if session.scalar(select(m.Milestone.id).where(m.Milestone.trial_site_id == trial_site.id).limit(1)):
        raise ValueError(f"trial site {trial_site.id} already has milestones")

    templates = ensure_templates(session)
    trial_type = trial_type or classify_trial_type(trial_site.trial.intervention_types)
    specs = sorted(checklist_for(trial_type), key=lambda s: s.sort_order)
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
