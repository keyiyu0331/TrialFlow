"""Ask TrialFlow: chat answers from Claude, grounded in live status. Read-only."""

from datetime import UTC, date, datetime

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import get_today
from ..schemas import AskAnswer, AskRequest, DocumentAnalysis, ErrorResponse
from ..services import assistant, documents
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


@router.post(
    "/document",
    response_model=DocumentAnalysis,
    responses={
        413: {"model": ErrorResponse, "description": "file_too_large (over 2 MB)"},
        415: {"model": ErrorResponse, "description": "unsupported_file_type (PDF, .txt or .md only)"},
        422: {"model": ErrorResponse, "description": "empty_file, unreadable_pdf, or no_text (scanned PDF)"},
    },
    summary="Summarize and categorize an uploaded site document (never changes data, never stores the file)",
)
async def analyze_document(
    request: Request,
    filename: str = Query(
        min_length=1, max_length=200, description="Original file name; its extension picks the reader"
    ),
    client: anthropic.Anthropic | None = Depends(assistant.get_client),
):
    """The body is the raw file bytes. Uses Claude when configured and a rule-based analyzer otherwise."""
    data = await request.body()
    try:
        text = documents.extract_text(filename, data)
    except documents.DocumentError as e:
        raise HTTPException(e.status, detail={"detail": e.detail, "code": e.code}) from e
    return await run_in_threadpool(documents.analyze, client, filename, text)
