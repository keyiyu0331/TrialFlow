"""Trial endpoints. STUB: returns placeholder data (see app/placeholders.py)."""

from typing import Literal

from fastapi import APIRouter, Query

from .. import placeholders as ph
from ..enums import ActivationStatus, DelayLevel, RecruitmentStatus
from ..schemas import Page, TrialDetail, TrialSiteSummary, TrialSummary
from .common import NOT_FOUND, limit_param, not_found, offset_param

router = APIRouter(prefix="/trials", tags=["trials"])


@router.get("", response_model=Page[TrialSummary], summary="List trials")
def list_trials(
    q: str | None = Query(None, description="Search title, acronym, NCT ID, or sponsor"),
    overall_status: RecruitmentStatus | None = None,
    limit: int = limit_param(),
    offset: int = offset_param(),
):
    items = [ph.TRIAL_SUMMARY]
    return Page(items=items, total=len(items), limit=limit, offset=offset)


@router.get("/{trial_id}", response_model=TrialDetail, responses=NOT_FOUND, summary="Get a trial")
def get_trial(trial_id: int):
    if trial_id != ph.TRIAL_ID:
        raise not_found("Trial", trial_id)
    return ph.TRIAL_DETAIL


@router.get(
    "/{trial_id}/sites",
    response_model=Page[TrialSiteSummary],
    responses=NOT_FOUND,
    summary="Trial dashboard: readiness, top blocker, and next-action owner per trial site",
)
def list_trial_sites(
    trial_id: int,
    activation_status: list[ActivationStatus] | None = Query(None),
    delay_level: list[DelayLevel] | None = Query(None),
    country: str | None = None,
    sort: Literal["readiness", "-readiness", "target_activation_date", "-delay"] = "-delay",
    limit: int = limit_param(),
    offset: int = offset_param(),
):
    if trial_id != ph.TRIAL_ID:
        raise not_found("Trial", trial_id)
    items = [
        row for row in [ph.TRIAL_SITE_SUMMARY]
        if (not activation_status or row.activation_status in activation_status)
        and (not delay_level or row.delay_level in delay_level)
        and (not country or row.site.country == country)
    ]
    return Page(items=items, total=len(items), limit=limit, offset=offset)
