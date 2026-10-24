"""Trial site endpoints: detail, dependency graph, change history, and dependency edits."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import models as m
from ..db import get_session
from ..deps import get_today
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
from ..services import readiness, views
from .common import NOT_FOUND, limit_param, not_found, offset_param

router = APIRouter(prefix="/trial-sites", tags=["trial sites"])


def _bundle(session: Session, trial_site_id: int, today: date) -> views.SiteBundle:
    ts = session.get(m.TrialSite, trial_site_id, options=[joinedload(m.TrialSite.site), joinedload(m.TrialSite.trial)])
    if ts is None:
        raise not_found("Trial site", trial_site_id)
    return views.load_bundles(session, [ts], today)[ts.id]


@router.get("/{trial_site_id}", response_model=TrialSiteDetail, responses=NOT_FOUND,
            summary="Get a trial site with its milestones")
def get_trial_site(trial_site_id: int, session: Session = Depends(get_session), today: date = Depends(get_today)):
    bundle = _bundle(session, trial_site_id, today)
    ts = bundle.trial_site
    return views.trial_site_detail(bundle, ts.site, ts.trial, datetime.now(timezone.utc))


@router.get("/{trial_site_id}/graph", response_model=TrialSiteGraph, responses=NOT_FOUND,
            summary="Milestones, dependencies, and blocking flags")
def get_trial_site_graph(trial_site_id: int, session: Session = Depends(get_session),
                         today: date = Depends(get_today)):
    return views.graph(_bundle(session, trial_site_id, today))


@router.get("/{trial_site_id}/events", response_model=Page[EventOut], responses=NOT_FOUND,
            summary="Change history timeline, newest first")
def list_trial_site_events(
    trial_site_id: int,
    milestone_id: int | None = None,
    event_type: list[EventType] | None = Query(None),
    since: datetime | None = None,
    limit: int = limit_param(),
    offset: int = offset_param(),
    session: Session = Depends(get_session),
):
    if session.get(m.TrialSite, trial_site_id) is None:
        raise not_found("Trial site", trial_site_id)
    stmt = (
        select(m.MilestoneEvent).join(m.Milestone).where(m.Milestone.trial_site_id == trial_site_id)
        .options(joinedload(m.MilestoneEvent.milestone), joinedload(m.MilestoneEvent.changed_by))
    )
    if milestone_id is not None:
        stmt = stmt.where(m.MilestoneEvent.milestone_id == milestone_id)
    if event_type:
        stmt = stmt.where(m.MilestoneEvent.event_type.in_(event_type))
    events = [views.event_out(e) for e in session.scalars(stmt).unique()]
    if since is not None:
        cutoff = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        events = [e for e in events if e.occurred_at >= cutoff]
    events.sort(key=lambda e: (e.occurred_at, e.id), reverse=True)
    return Page(items=events[offset: offset + limit], total=len(events), limit=limit, offset=offset)


def _conflict(code: str, detail: str, **extra) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"detail": detail, "code": code, **extra})


@router.post(
    "/{trial_site_id}/dependencies",
    response_model=DependencyOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "dependency_cycle, cross_trial_site, or duplicate_dependency"},
    },
    summary="Add a dependency between two milestones of this trial site",
)
def create_dependency(trial_site_id: int, body: DependencyCreate, session: Session = Depends(get_session)):
    if session.get(m.TrialSite, trial_site_id) is None:
        raise not_found("Trial site", trial_site_id)
    for mid in (body.predecessor_id, body.successor_id):
        milestone = session.get(m.Milestone, mid)
        if milestone is None or milestone.trial_site_id != trial_site_id:
            raise _conflict("cross_trial_site", f"Milestone {mid} is not in trial site {trial_site_id}")

    existing = session.scalars(select(m.MilestoneDependency).where(m.MilestoneDependency.trial_site_id == trial_site_id)).all()
    if any(d.predecessor_id == body.predecessor_id and d.successor_id == body.successor_id for d in existing):
        raise _conflict("duplicate_dependency", "Dependency already exists")
    path = readiness.find_path([(d.predecessor_id, d.successor_id) for d in existing],
                               body.successor_id, body.predecessor_id)
    if path is not None:
        raise _conflict("dependency_cycle",
                        f"Adding {body.predecessor_id} → {body.successor_id} would create a cycle",
                        cycle_path=path + [body.successor_id])

    dep = m.MilestoneDependency(trial_site_id=trial_site_id, predecessor_id=body.predecessor_id,
                                successor_id=body.successor_id, source_type=SourceType.synthetic)
    session.add(dep)
    session.commit()
    return dep
