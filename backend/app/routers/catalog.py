"""Reference data: milestone templates and users."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_session
from ..enums import TrialType, UserRole
from ..schemas import TemplateOut, UserOut
from ..services.templates import checklist_for

router = APIRouter(tags=["reference"])


@router.get(
    "/templates",
    response_model=list[TemplateOut],
    summary="Milestone checklist for a trial type (default drug) with its dependencies",
)
def list_templates(trial_type: TrialType = TrialType.drug, session: Session = Depends(get_session)):
    checklist = checklist_for(trial_type)
    predecessors = {spec.code: sorted(spec.predecessors) for spec in checklist}
    templates = session.scalars(
        select(m.MilestoneTemplate)
        .where(m.MilestoneTemplate.code.in_(predecessors))
        .order_by(m.MilestoneTemplate.sort_order)
    ).all()
    return [
        TemplateOut(
            id=t.id,
            code=t.code,
            name=t.name,
            workstream=t.workstream,
            default_owner_role=t.default_owner_role,
            default_duration_days=t.default_duration_days,
            is_gate=t.is_gate,
            sort_order=t.sort_order,
            predecessor_codes=predecessors[t.code],
        )
        for t in templates
    ]


@router.get("/users", response_model=list[UserOut], summary="Milestone owners")
def list_users(
    site_id: int | None = None,
    role: UserRole | None = None,
    sponsor_only: bool = False,
    session: Session = Depends(get_session),
):
    stmt = select(m.User).order_by(m.User.id)
    if site_id is not None:
        stmt = stmt.where(m.User.site_id == site_id)
    if role is not None:
        stmt = stmt.where(m.User.role == role)
    if sponsor_only:
        stmt = stmt.where(m.User.site_id.is_(None))
    return session.scalars(stmt).all()
