# TrialFlow

Clinical trial site-activation tracker (CS 146S project, due Dec 10, 2026). For each **trial site** (one site in one trial; the unit we activate) it shows a study start-up manager readiness, the milestone blocking it, and who owns the next action. Trials and sites are real ClinicalTrials.gov data; milestones, owners, dependencies, and events are labeled synthetic. Terms: trial, site, trial site, milestone, dependency, blocker, green light.

## Architecture
- `backend/app/` (FastAPI + SQLAlchemy 2): `routers/` stay thin → `services/` → `models.py`. `schemas.py` is the API contract; `enums.py` is the only place enums live (shared by models, schemas, services).
- `services/readiness.py`: pure functions, no DB (readiness, blocking, top blocker, slip, health, `find_path` cycle check). `services/views.py`: `load_bundles()` loads milestones + dependencies and runs `analyze()` to build response shapes. `templates.py`, `registry_import.py`, `seeding.py` back the scripts.
- `scripts/import_registry.py` and `scripts/seed.py` fill the DB from `data/raw_25_studies.json` (the registry pull, source of truth).
- `frontend/` (Next.js 16 App Router, TS, plain CSS): `src/lib/api.ts` is the typed client; `src/lib/insights.ts` derives tasks and summaries from existing endpoints (no new endpoints).

Before changing an area, read its doc and update it in the same change: `docs/domain-rules.md` (rule definitions), `docs/schema.md` (tables), `docs/api-design.md` (endpoints), `docs/data-mapping.md` (registry JSON → columns), `docs/SYSTEM_OVERVIEW.md` (diagrams).

## Commands (from repo root)
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt`
- Tests: `cd backend && pytest` (in-memory SQLite, no setup). One file: `cd backend && pytest tests/test_readiness.py`
- Load data: `export DATABASE_URL=sqlite:///trialflow.db && python scripts/import_registry.py && python scripts/seed.py --reset` (`--as-of YYYY-MM-DD` pins the scenario dates)
- API: `uvicorn app.main:app --app-dir backend --reload` → http://localhost:8000/docs, `curl localhost:8000/health`
- Frontend: `cd frontend && npm install && npm run dev` (port 3000); check with `npm run typecheck && npm run build`
- No linter or formatter is configured.

## Conventions
- Errors: `HTTPException` with body `{"detail", "code"}` (e.g. `not_found`, `dependency_cycle`, `unsatisfied_dependencies`); `main.py` converts validation errors to `validation_error`.
- Never read the clock in services: take `as_of`/`today` (routers get it from `deps.get_today`). Tests pin it to `AS_OF = 2026-10-20` in `tests/conftest.py`.
- Fixtures: `client` (TestClient on a seeded DB copy), `seeded` (session on it), `session` + `world` (small hand-built world). API contract → `tests/test_api.py`, constraints → `test_models.py`, rules → `test_readiness.py`. Add a test with each rule or endpoint.
- Models must run on SQLite: JSON not ARRAY, no PG-only SQL in CHECKs; constraint names use `ck_`, `uq_`, `fk_`.
- Computed values (overdue, delay level, blocking, top blocker, readiness, next-action owner, projected activation) are derived in services, never stored as columns.
- Every status, owner, or due-date change writes a `milestone_events` row in the same transaction; completing GREEN_LIGHT activates the trial site. Dependencies stay acyclic and within one trial site; `not_applicable` counts as satisfied (`SATISFIED_STATUSES`).
- Every row and API object carries `source_type` (`public_registry` | `synthetic`); synthetic users use `example.org` emails.

## Guardrails
- Import from `data/raw_25_studies.json` only, never `data/*.csv` (they lack `phases`, and their `source_type`/`site_activation_status` columns are not from the API).
- Never infer activation from `reported_recruitment_status` (all 25 trials are RECRUITING; in-start-up trial sites are synthetic).
- Never import or display registry location contacts (real people). Never hand-edit `data/raw_25_studies.json`. Never write to ClinicalTrials.gov.
- API v2 has no stable location ID: keys are `ctgov_location_index` and `sites.dedup_key`; placeholder names ("Research Site") use `nct_id:index` and are never merged. Expect 25 trials / 1,662 sites / 1,715 trial sites.
- Without `DATABASE_URL`, everything targets `postgresql+psycopg://localhost/trialflow`. A relative SQLite URL resolves against the current directory, so don't `cd backend` before `uvicorn` or it opens an empty DB.
- Don't run `scripts/run_extraction.ps1`: the `extract_trials.py` it calls is missing.
- Secrets come from env vars only (`.env*` is gitignored). Planned LLM layer: send only structured status with no personal data; its output is a suggestion, never a status change.
