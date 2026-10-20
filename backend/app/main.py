import os

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import catalog, milestones, trial_sites, trials
from .routers.common import VALIDATION_ERROR

app = FastAPI(
    title="TrialFlow API",
    version="0.2.0",
    description=(
        "Clinical trial site activation tracking. Trials and sites are real "
        "ClinicalTrials.gov records; milestones, owners, and history are synthetic "
        "(see `source_type` on every object). Readiness, blockers, delay, and health "
        "are computed at request time from the dependency graph."
    ),
)

# The Next.js dev server runs on another origin. Override with CORS_ORIGINS (comma-separated).
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def _error_body(request, exc: HTTPException):
    # Flatten {"detail": {...}} into the ErrorResponse shape.
    body = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail, "code": "error"}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def _validation_error_body(request, exc: RequestValidationError):
    # Replace FastAPI's default {"detail": [...]} with the ErrorResponse shape.
    messages = []
    for err in exc.errors():
        msg = err["msg"].removeprefix("Value error, ")
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=422,
                        content={"detail": "; ".join(messages), "code": "validation_error"})


# VALIDATION_ERROR replaces the default HTTPValidationError schema in the OpenAPI spec.
for r in (trials.router, trial_sites.router, milestones.router, catalog.router):
    app.include_router(r, responses=VALIDATION_ERROR)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
