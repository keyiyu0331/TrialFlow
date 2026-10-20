"""Reference data: milestone templates and users."""

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_session
from ..enums import UserRole
from ..schemas import TemplateOut, UserOut

router = APIRouter(tags=["reference"])


@router.get("/templates", response_model=list[TemplateOut],
            summary="Standard milestone checklist with default dependencies")
def list_templates(session: Session = Depends(get_session)):
    templates = session.scalars(select(m.MilestoneTemplate).order_by(m.MilestoneTemplate.sort_order)).all()
    code_by_id = {t.id: t.code for t in templates}
    predecessors: dict[int, list[str]] = defaultdict(list)
    for dep in session.scalars(select(m.TemplateDependency)):
        predecessors[dep.successor_template_id].append(code_by_id[dep.predecessor_template_id])
    return [
        TemplateOut(id=t.id, code=t.code, name=t.name, workstream=t.workstream,
                    default_owner_role=t.default_owner_role, default_duration_days=t.default_duration_days,
                    is_gate=t.is_gate, sort_order=t.sort_order, predecessor_codes=sorted(predecessors[t.id]))
        for t in templates
    ]


@router.get("/users", response_model=list[UserOut], summary="Milestone owners")
def list_users(site_id: int | None = None, role: UserRole | None = None, sponsor_only: bool = False,
               session: Session = Depends(get_session)):
    stmt = select(m.User).order_by(m.User.id)
    if site_id is not None:
        stmt = stmt.where(m.User.site_id == site_id)
    if role is not None:
        stmt = stmt.where(m.User.role == role)
    if sponsor_only:
        stmt = stmt.where(m.User.site_id.is_(None))
    return session.scalars(stmt).all()
