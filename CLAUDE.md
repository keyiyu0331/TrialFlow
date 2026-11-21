# TrialFlow

Clinical trial site-activation tracker. For each **trial site** (one site in one trial; the unit we activate) it shows a study start-up manager readiness, the milestone blocking it, and who owns the next action. Trials and sites are real ClinicalTrials.gov data; milestones, owners, dependencies, and events are labeled synthetic. Terms: trial, site, trial site, milestone, dependency, blocker, green light.

## Architecture
- `backend/app/` (FastAPI + SQLAlchemy 2): `routers/` stay thin → `services/` → `models.py`. `schemas.py` is the API contract; `enums.py` is the only place enums live (shared by models, schemas, services).
- `services/readiness.py`: pure functions, no DB (readiness, blocking, top blocker, slip, health, `find_path` cycle check). `services/views.py`: `load_bundles()` loads milestones + dependencies and runs `analyze()` to build response shapes. `templates.py`, `registry_import.py`, `seeding.py` back the scripts. `tasks.py` (pure) is the Python port of `openTasks` in `frontend/src/lib/insights.ts`; change both together (rule D13).
- Assistant: `routers/assistant.py` (`POST /assistant/ask`) → `services/assistant.py` (Claude tool loop) → `services/assistant_tools.py` (`load_world()` applies scope once; tools are pure functions over that list). The Next route `frontend/src/app/api/ask/route.ts` calls it and falls back to rule-based `src/lib/ask.ts` on any non-200.
- Trial types (rule D14): `services/trial_types.py` (pure) derives drug / device / no product from `trials.intervention_types`; `services/templates.py` holds one checklist per type (`CHECKLISTS`). The registry pull has no device trial, so the device demo trial is synthetic.
- Document upload: `POST /assistant/document` → `services/documents.py` (extract text, `redact()`, Claude summary with quote-checked facts, rule-based fallback). Suggestion only; nothing is stored. Sample files: `data/sample_documents/`.
- `scripts/import_registry.py` and `scripts/seed.py` fill the DB from `data/raw_25_studies.json` (the registry pull, source of truth).
- `frontend/` (Next.js 16 App Router, TS, plain CSS): `src/lib/api.ts` is the typed client; `src/lib/insights.ts` derives tasks and summaries from existing endpoints (no new endpoints).

Before changing an area, read its doc and update it in the same change: `docs/domain-rules.md` (rule definitions), `docs/schema.md` (tables), `docs/api-design.md` (endpoints), `docs/data-mapping.md` (registry JSON → columns), `docs/SYSTEM_OVERVIEW.md` (diagrams).

## Commands (from repo root)
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt && pre-commit install`
- Tests: `cd backend && pytest` (in-memory SQLite, no setup). One file: `cd backend && pytest tests/test_readiness.py`
- Load data: `export DATABASE_URL=sqlite:///trialflow.db && python scripts/import_registry.py && python scripts/seed.py --reset` (`--as-of YYYY-MM-DD` pins the scenario dates)
- API: `uvicorn app.main:app --app-dir backend --reload` → http://localhost:8000/docs, `curl localhost:8000/health`
- Frontend: `cd frontend && npm install && npm run dev` (port 3000); check with `npm run typecheck && npm run build`
- Assistant: export `ANTHROPIC_API_KEY` before `uvicorn` to enable Claude (`TRIALFLOW_ASSISTANT_MODEL` overrides `claude-opus-5-5`). Tests never need it: they override `assistant.get_client` with a fake client. Real model calls cost money; ask before running them.
- Lint/format: `ruff check . && ruff format .` (Python, config in `ruff.toml`); `cd frontend && npm run lint` (`npm run format` to fix). Hooks in `.claude/settings.json` format each edit and block finishing while ruff, pytest, Biome, or typecheck fail; see `.claude/hooks/README.md`.

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
- API v2 has no stable location ID: keys are `ctgov_location_index` and `sites.dedup_key`; placeholder names ("Research Site") use `nct_id:index` and are never merged. Expect 25 registry trials / 1,662 registry sites / 1,715 registry trial sites (the seed adds one synthetic device trial with 6 fictional sites).
- Without `DATABASE_URL`, everything targets `postgresql+psycopg://localhost/trialflow`. A relative SQLite URL resolves against the current directory, so don't `cd backend` before `uvicorn`: it creates an empty `backend/trialflow.db` and every request fails with `no such table`.
- Don't run `scripts/run_extraction.ps1`: the `extract_trials.py` it calls is missing.
- Secrets come from env vars only (`.env*` is gitignored).
- LLM layer (`services/assistant*.py`): tools stay read-only and scoped through `load_world()`; they send structured status with owner name and role only (no emails, no contacts), and `redact()` strips emails and phone numbers from free text (`blocked_reason`, `notes`); output is a suggestion, never a status change; links come only from trial site ids the tools returned. Never add a tool that writes.
