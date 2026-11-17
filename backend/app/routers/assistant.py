"""Ask TrialFlow: chat answers from Claude, grounded in live status. Read-only."""

from datetime import UTC, date, datetime

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import get_today
from ..schemas import AskAnswer, AskRequest, ErrorResponse
from ..services import assistant
from ..services.assistant_tools import Scope, load_world

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE, detail={"detail": detail, "code": "assistant_unavailable"}
    )


@router.post(
    "/ask",
    response_model=AskAnswer,
    responses={503: {"model": ErrorResponse, "description": "assistant_unavailable: no API key, API error, timeout"}},
    summary="Answer a question about the caller's trial sites (never changes data)",
)
def ask(
    body: AskRequest,
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
    client: anthropic.Anthropic | None = Depends(assistant.get_client),
):
    if client is None:
        raise _unavailable("The assistant is not configured (ANTHROPIC_API_KEY is not set)")
    world = load_world(session, Scope(body.role, body.site_id), today, datetime.now(UTC))
    try:
        return assistant.ask(client, body.question, body.history, world, today)
    except assistant.AssistantUnavailable as e:
        raise _unavailable(str(e)) from e
