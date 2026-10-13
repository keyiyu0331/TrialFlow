"""Milestone and dependency endpoints. STUB: nothing is persisted."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status

from .. import placeholders as ph
from ..enums import (
    SATISFIED_STATUSES,
    ActivationStatus,
    DelayLevel,
    EventType,
    MilestoneStatus,
    SourceType,
)
from ..schemas import ErrorResponse, EventOut, MilestoneUpdate, MilestoneUpdateResult
from .common import NOT_FOUND, not_found

router = APIRouter(tags=["milestones"])


@router.patch(
    "/milestones/{milestone_id}",
    response_model=MilestoneUpdateResult,
    responses={**NOT_FOUND, 422: {"model": ErrorResponse, "description": "Invalid change"}},
    summary="Change status, owner, or due date; writes one event per changed field",
)
def update_milestone(milestone_id: int, body: MilestoneUpdate):
    current = ph.milestone(milestone_id)
    if current is None:
        raise not_found("Milestone", milestone_id)
    if body.owner_user_id is not None and ph.owner(body.owner_user_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"detail": "Unknown owner_user_id", "code": "unknown_user"})

    now = datetime.now(timezone.utc)
    changes = {}
    updated = current.model_copy()
    if "status" in body.model_fields_set and body.status != current.status:
        changes[EventType.status_change] = (current.status.value, body.status.value)
        updated.status = body.status
        updated.status_changed_at = now
        updated.completed_at = now if body.status == MilestoneStatus.complete else None
        updated.days_in_status = 0
        if body.status != MilestoneStatus.blocked:
            updated.blocked_reason = None
        if body.status in SATISFIED_STATUSES:
            updated.is_overdue, updated.days_overdue = False, 0
            updated.delay_level, updated.is_blocking = DelayLevel.on_time, False
    if "owner_user_id" in body.model_fields_set and body.owner_user_id != (
        current.owner.id if current.owner else None
    ):
        changes[EventType.owner_change] = (
            str(current.owner.id) if current.owner else None,
            str(body.owner_user_id) if body.owner_user_id is not None else None,
        )
        updated.owner = ph.owner(body.owner_user_id)
    if "due_date" in body.model_fields_set and body.due_date != current.due_date:
        changes[EventType.due_date_change] = (
            current.due_date.isoformat() if current.due_date else None,
            body.due_date.isoformat() if body.due_date else None,
        )
        updated.due_date = body.due_date
    if "blocked_reason" in body.model_fields_set:
        updated.blocked_reason = body.blocked_reason
    # TODO: recompute is_overdue / delay_level / is_blocking in the readiness service.

    events = [
        EventOut(id=9100 + i, milestone_id=milestone_id, milestone_name=current.name,
                 event_type=etype, old_value=old, new_value=new, note=body.note,
                 changed_by=ph.owner(body.changed_by_user_id), occurred_at=now,
                 source_type=SourceType.synthetic)
        for i, (etype, (old, new)) in enumerate(changes.items(), start=1)
    ]
    activation = (
        ActivationStatus.activated
        if current.template_code == "GREEN_LIGHT" and updated.status == MilestoneStatus.complete
        else ph.TRIAL_SITE_SUMMARY.activation_status
    )
    return MilestoneUpdateResult(milestone=updated, events=events,
                                 trial_site_activation_status=activation)


@router.delete(
    "/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    tags=["trial sites"],
    summary="Remove a milestone dependency",
)
def delete_dependency(dependency_id: int):
    if not any(d.id == dependency_id for d in ph.DEPENDENCIES):
        raise not_found("Dependency", dependency_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
