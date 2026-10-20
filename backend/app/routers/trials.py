"""Trial endpoints: the trial list, trial detail, and the trial dashboard."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from .. import models as m
from ..db import get_session
from ..deps import get_today
from ..enums import ActivationStatus, DelayLevel, RecruitmentStatus, SiteHealth
from ..schemas import Page, TrialDetail, TrialSiteSummary, TrialSummary
from ..services import views
from .common import NOT_FOUND, limit_param, not_found, offset_param

router = APIRouter(prefix="/trials", tags=["trials"])


@router.get("", response_model=Page[TrialSummary], summary="List trials")
def list_trials(
    q: str | None = Query(None, description="Search title, acronym, NCT ID, or sponsor"),
    overall_status: RecruitmentStatus | None = None,
    limit: int = limit_param(),
    offset: int = offset_param(),
    session: Session = Depends(get_session),
):
    stmt = select(m.Trial)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(*(func.lower(func.coalesce(col, "")).like(like)
                  for col in (m.Trial.title, m.Trial.acronym, m.Trial.nct_id, m.Trial.sponsor_name)))
        )
    if overall_status:
        stmt = stmt.where(m.Trial.overall_status == overall_status)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    trials = session.scalars(stmt.order_by(m.Trial.id).limit(limit).offset(offset)).all()
    counts = views.activation_counts(session, [t.id for t in trials])
    return Page(items=[views.trial_summary(t, counts[t.id]) for t in trials], total=total, limit=limit, offset=offset)


@router.get("/{trial_id}", response_model=TrialDetail, responses=NOT_FOUND, summary="Get a trial")
def get_trial(trial_id: int, session: Session = Depends(get_session), today: date = Depends(get_today)):
    trial = session.get(m.Trial, trial_id)
    if trial is None:
        raise not_found("Trial", trial_id)
    counts = views.activation_counts(session, [trial.id])[trial.id]
    return views.trial_detail(session, trial, counts, today)


def _sort_key(sort: str):
    """Sort keys for the dashboard. Trial sites without milestones always go last."""

    def worst_first(row: TrialSiteSummary):
        blocker_days = row.top_blocker.days_overdue if row.top_blocker else 0
        return (row.milestones_total == 0, row.health == SiteHealth.activated,
                -views.DELAY_RANK[row.delay_level], -blocker_days, row.readiness_pct, row.id)

    return {
        "-delay": worst_first,
        "readiness": lambda r: (r.milestones_total == 0, r.readiness_pct, r.id),
        "-readiness": lambda r: (r.milestones_total == 0, -r.readiness_pct, r.id),
        "target_activation_date": lambda r: (r.target_activation_date is None, r.target_activation_date or date.max, r.id),
    }[sort]


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
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
):
    if session.get(m.Trial, trial_id) is None:
        raise not_found("Trial", trial_id)
    stmt = (
        select(m.TrialSite).join(m.Site).where(m.TrialSite.trial_id == trial_id)
        .options(joinedload(m.TrialSite.site))
    )
    if activation_status:
        stmt = stmt.where(m.TrialSite.activation_status.in_(activation_status))
    if country:
        stmt = stmt.where(m.Site.country == country)
    trial_sites = list(session.scalars(stmt).unique())
    bundles = views.load_bundles(session, trial_sites, today)
    rows = [views.trial_site_summary(bundles[ts.id], ts.site) for ts in trial_sites]
    if delay_level:
        rows = [r for r in rows if r.delay_level in delay_level]
    rows.sort(key=_sort_key(sort))
    return Page(items=rows[offset: offset + limit], total=len(rows), limit=limit, offset=offset)
