from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .routers import catalog, milestones, trial_sites, trials

app = FastAPI(
    title="TrialFlow API",
    version="0.1.0",
    description=(
        "Clinical trial site activation tracking. Trials and sites are real "
        "ClinicalTrials.gov records; milestones, owners, and history are synthetic "
        "(see `source_type` on every object). **Endpoints are stubs returning placeholder data.**"
    ),
)


@app.exception_handler(HTTPException)
async def _error_body(request, exc: HTTPException):
    # Flatten {"detail": {...}} into the ErrorResponse shape.
    body = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail, "code": "error"}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


for r in (trials.router, trial_sites.router, milestones.router, catalog.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
