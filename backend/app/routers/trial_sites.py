"""Trial site endpoints. STUB: returns placeholder data (see app/placeholders.py)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from .. import placeholders as ph
from ..enums import EventType, SourceType
from ..schemas import (
    DependencyCreate,
    DependencyOut,
    ErrorResponse,
    EventOut,
    Page,
    TrialSiteDetail,
    TrialSiteGraph,
)
from .common import NOT_FOUND, limit_param, not_found, offset_param

router = APIRouter(prefix="/trial-sites", tags=["trial sites"])


def _check(trial_site_id: int) -> None:
    if trial_site_id != ph.TRIAL_SITE_ID:
        raise not_found("Trial site", trial_site_id)


@router.get("/{trial_site_id}", response_model=TrialSiteDetail, responses=NOT_FOUND,
            summary="Get a trial site with its milestones")
def get_trial_site(trial_site_id: int):
    _check(trial_site_id)
    return ph.TRIAL_SITE_DETAIL


@router.get("/{trial_site_id}/graph", response_model=TrialSiteGraph, responses=NOT_FOUND,
            summary="Milestones, dependencies, and blocking flags")
def get_trial_site_graph(trial_site_id: int):
    _check(trial_site_id)
    return ph.GRAPH


@router.get("/{trial_site_id}/events", response_model=Page[EventOut], responses=NOT_FOUND,
            summary="Change history timeline, newest first")
def list_trial_site_events(
    trial_site_id: int,
    milestone_id: int | None = None,
    event_type: list[EventType] | None = Query(None),
    since: datetime | None = None,
    limit: int = limit_param(),
    offset: int = offset_param(),
):
    _check(trial_site_id)
    items = [
        e for e in ph.EVENTS
        if (milestone_id is None or e.milestone_id == milestone_id)
        and (not event_type or e.event_type in event_type)
        and (since is None or e.occurred_at >= since)
    ]
    return Page(items=items, total=len(items), limit=limit, offset=offset)


@router.post(
    "/{trial_site_id}/dependencies",
    response_model=DependencyOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse,
              "description": "dependency_cycle, cross_trial_site, or duplicate_dependency"},
    },
    summary="Add a dependency between two milestones of this trial site",
)
def create_dependency(trial_site_id: int, body: DependencyCreate):
    _check(trial_site_id)
    for mid in (body.predecessor_id, body.successor_id):
        if ph.milestone(mid) is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"detail": f"Milestone {mid} is not in trial site {trial_site_id}",
                        "code": "cross_trial_site"},
            )
    if any(d.predecessor_id == body.predecessor_id and d.successor_id == body.successor_id
           for d in ph.DEPENDENCIES):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"detail": "Dependency already exists", "code": "duplicate_dependency"},
        )
    # TODO: cycle detection (service layer) -> 409 dependency_cycle with cycle_path.
    return DependencyOut(id=5999, trial_site_id=trial_site_id, predecessor_id=body.predecessor_id,
                         successor_id=body.successor_id, source_type=SourceType.synthetic)
