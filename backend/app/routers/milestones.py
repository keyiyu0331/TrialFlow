"""Milestone and dependency edits. Every status, owner, or due-date change writes an event."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import models as m
from ..db import get_session
from ..deps import get_today
from ..enums import ActivationStatus, EventType, MilestoneStatus
from ..schemas import ErrorResponse, MilestoneUpdate, MilestoneUpdateResult
from ..services import readiness, views
from .common import NOT_FOUND, not_found

router = APIRouter(tags=["milestones"])


def _unprocessable(code: str, detail: str) -> HTTPException:
    return HTTPException(422, detail={"detail": detail, "code": code})


@router.patch(
    "/milestones/{milestone_id}",
    response_model=MilestoneUpdateResult,
    responses={**NOT_FOUND, 422: {"model": ErrorResponse, "description": "Invalid change"}},
    summary="Change status, owner, or due date; writes one event per changed field",
)
def update_milestone(milestone_id: int, body: MilestoneUpdate, session: Session = Depends(get_session),
                     today: date = Depends(get_today)):
    ms = session.get(m.Milestone, milestone_id,
                     options=[joinedload(m.Milestone.template), joinedload(m.Milestone.owner)])
    if ms is None:
        raise not_found("Milestone", milestone_id)
    fields = body.model_fields_set
    if body.owner_user_id is not None and session.get(m.User, body.owner_user_id) is None:
        raise _unprocessable("unknown_user", "Unknown owner_user_id")
    if body.changed_by_user_id is not None and session.get(m.User, body.changed_by_user_id) is None:
        raise _unprocessable("unknown_user", "Unknown changed_by_user_id")
    if body.due_date and ms.planned_start_date and body.due_date < ms.planned_start_date:
        raise _unprocessable("invalid_due_date", "due_date cannot be before the planned start date")

    now = datetime.now(timezone.utc)
    changes: list[tuple[EventType, str | None, str | None]] = []
    was_complete = ms.status == MilestoneStatus.complete

    if "status" in fields and body.status is not None and body.status != ms.status:
        changes.append((EventType.status_change, ms.status.value, body.status.value))
        ms.status, ms.status_changed_at = body.status, now
        ms.completed_at = now if body.status == MilestoneStatus.complete else None
        if ms.started_at is None and body.status in (MilestoneStatus.in_progress, MilestoneStatus.blocked,
                                                    MilestoneStatus.complete):
            ms.started_at = now
        if body.status != MilestoneStatus.blocked:
            ms.blocked_reason = None
    reason_changed = False
    if "blocked_reason" in fields and ms.status == MilestoneStatus.blocked and body.blocked_reason != ms.blocked_reason:
        ms.blocked_reason, reason_changed = body.blocked_reason, True
    if "owner_user_id" in fields and body.owner_user_id != ms.owner_user_id:
        changes.append((EventType.owner_change,
                        str(ms.owner_user_id) if ms.owner_user_id is not None else None,
                        str(body.owner_user_id) if body.owner_user_id is not None else None))
        ms.owner_user_id = body.owner_user_id
    if "due_date" in fields and body.due_date != ms.due_date:
        changes.append((EventType.due_date_change,
                        ms.due_date.isoformat() if ms.due_date else None,
                        body.due_date.isoformat() if body.due_date else None))
        ms.due_date = body.due_date

    events = [
        m.MilestoneEvent(milestone_id=ms.id, changed_by_user_id=body.changed_by_user_id, event_type=kind,
                         old_value=old, new_value=new, note=body.note, occurred_at=now,
                         source_type=ms.source_type)
        for kind, old, new in changes
    ]
    if not events and (body.note or reason_changed):
        events.append(m.MilestoneEvent(milestone_id=ms.id, changed_by_user_id=body.changed_by_user_id,
                                       event_type=EventType.note, new_value=ms.blocked_reason if reason_changed else None,
                                       note=body.note, occurred_at=now, source_type=ms.source_type))
    session.add_all(events)

    trial_site = session.get(m.TrialSite, ms.trial_site_id)
    if ms.template and ms.template.code == readiness.GREEN_LIGHT_CODE:
        if ms.status == MilestoneStatus.complete and not was_complete:
            trial_site.activation_status, trial_site.actual_activation_date = ActivationStatus.activated, today
        elif was_complete and ms.status != MilestoneStatus.complete and trial_site.activation_status == ActivationStatus.activated:
            trial_site.activation_status, trial_site.actual_activation_date = ActivationStatus.in_startup, None
    session.commit()

    bundle = views.load_bundles(session, [trial_site], today)[trial_site.id]
    session.refresh(ms)
    return MilestoneUpdateResult(
        milestone=views.milestone_out(bundle.by_id[ms.id], bundle, now),
        events=[views.event_out(e) for e in events],
        trial_site_activation_status=trial_site.activation_status,
    )


@router.delete(
    "/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    tags=["trial sites"],
    summary="Remove a milestone dependency",
)
def delete_dependency(dependency_id: int, session: Session = Depends(get_session)):
    dep = session.get(m.MilestoneDependency, dependency_id)
    if dep is None:
        raise not_found("Dependency", dependency_id)
    session.delete(dep)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
