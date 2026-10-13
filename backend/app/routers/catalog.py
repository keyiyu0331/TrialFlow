"""Reference data: milestone templates and users. STUB: placeholder data."""

from fastapi import APIRouter

from .. import placeholders as ph
from ..enums import UserRole
from ..schemas import TemplateOut, UserOut

router = APIRouter(tags=["reference"])


@router.get("/templates", response_model=list[TemplateOut],
            summary="Standard milestone checklist with default dependencies")
def list_templates():
    return ph.TEMPLATES


@router.get("/users", response_model=list[UserOut], summary="Milestone owners")
def list_users(site_id: int | None = None, role: UserRole | None = None, sponsor_only: bool = False):
    return [
        u for u in ph.USERS
        if (site_id is None or u.site_id == site_id)
        and (role is None or u.role == role)
        and (not sponsor_only or u.site_id is None)
    ]
