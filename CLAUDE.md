# TrialFlow

Workflow platform for clinical trial site activation. For each site in a trial, it shows a study start-up manager the site's readiness, which milestone is blocking it, and who owns the next action. CS 146S class project, due Dec 10, 2026.
- Scope: prove the workflow works, using real registry trials and sites plus labeled synthetic activation data. There is no sponsor data.

Primary user: a study start-up manager (sponsor/CRO) tracking many sites for one trial. Secondary: site staff updating their assigned milestones.

## Terminology (use consistently)
trial, site, **trial site** (one site in one trial; the unit we activate), milestone, dependency, blocker, green light.

## Codebase map
Paths marked *(planned)* do not exist yet; they show where new code should go.
- `backend/app/`: `models.py` (tables), `enums.py`, `schemas.py` (API shapes), `routers/` (endpoints), `db.py`, `main.py`
- `backend/app/services/`: `readiness.py` (pure functions: ready, blocking, top blocker, slip, health, cycle check; see `docs/domain-rules.md`), `templates.py` (template instantiation), `registry_import.py`, `seeding.py` (scenarios), `views.py` (API shapes). Keep routers thin.
- `backend/tests/`: pytest; `conftest.py` provides the SQLite `session`, `world`, `seeded`, and `client` fixtures.
- `scripts/`: `import_registry.py`, `seed.py` (`--as-of`, `--reset`), `run_extraction.ps1` (wrapper; `extract_trials.py` is missing).
- `frontend/`: Next.js 16 App Router + TypeScript; `src/lib/api.ts` (typed client), `src/components/`, pages `/` (search, status/delay filters, trial summary, needs-attention), `/tasks` (My tasks), `/trials`, `/sites/[id]`; `src/lib/insights.ts` derives tasks and summaries from the API (no new endpoints). Plain CSS in `globals.css`.
- `data/raw_25_studies.json`: the real registry pull (source of truth).

## Source-of-truth docs
- `docs/schema.md`: final schema and rules
- `docs/domain-rules.md`: precise, testable definitions of blocking, top blocker, slip, and health *(proposed)*
- `docs/api-design.md`: endpoint table and examples. Keep it concise; it feeds a 2-page technical spec.
- `docs/data-mapping.md`: API v2 JSON paths → columns, with data-quality flags
- `docs/site-activation-research.md`: milestones, dependencies, delay benchmarks
- `docs/architecture.md`: system architecture and tech stack; `docs/work-split.md`: team responsibilities
- Update these docs when you change models or endpoints.

## Build and run
- Python 3.11+: `python -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt`
- Dev server: `cd backend && uvicorn app.main:app --reload`, then open http://localhost:8000/docs
- Database: `DATABASE_URL` (default `postgresql+psycopg://localhost/trialflow`). Then `python scripts/import_registry.py` and `python scripts/seed.py --reset` (use `DATABASE_URL=sqlite:///trialflow.db` locally).
- Frontend: `cd frontend && npm install && npm run dev` (http://localhost:3000; `npm run typecheck`, `npm run build`)

## Code style
- Type hints everywhere. SQLAlchemy 2 `Mapped[...]` / `mapped_column` style; Pydantic 2 models live in `schemas.py`.
- Enums live only in `enums.py` (str-valued) and are shared by models and schemas.
- Keep models portable, since tests run on SQLite: JSON, not ARRAY; no PG-only SQL in CHECKs. Name constraints with `ck_`, `uq_`, `fk_` prefixes.
- Errors: raise `HTTPException` with a `{"detail", "code"}` body (e.g. `not_found`, `dependency_cycle`). Pydantic validation failures are converted to the same shape (`validation_error`) in `main.py`.
- Computed values (see Domain rules) are derived in services, never added as columns.
- Short docstrings that state rules and rationale; match the surrounding comment density. No formatter or linter is configured yet.

## Testing
- `cd backend && pytest` runs on SQLite in-memory with FK enforcement; no database setup needed.
- Constraint tests are in `tests/test_models.py`; the API contract is in `tests/test_api.py`. Add a test with each new rule or endpoint.
- Smoke test: start the dev server, `curl localhost:8000/health`, then try `GET /trials/1/sites` and `PATCH /milestones/{id}` in `/docs`.
- *(planned)* Playwright e2e: dashboard → milestone update → dashboard reflects the change.

## Data rules
- **Real:** trials and sites from ClinicalTrials.gov API v2 (`data/raw_25_studies.json`: 25 trials, 1,715 locations). Importers read the JSON, not the CSVs (the CSVs lack `phases`, and their `source_type`/`site_activation_status` columns are not from the API).
- **Synthetic:** milestones, owners, dependencies, events. Every row and API object carries `source_type` (`public_registry` | `synthetic`).
- **Never infer activation from `reported_recruitment_status`.** The seed script may use it only as a scenario hint.
- The dataset has **no NOT_YET_RECRUITING sites** (all 25 trials are RECRUITING), so in-start-up trial sites are a labeled synthetic subset.
- **No stable location ID** in API v2. Use `trial_sites.ctgov_location_index` (1-based array position) and `sites.dedup_key` = normalized `name|city|state|country`. Placeholder names ("Research Site", "Research Facility") use `nct_id:index` and are never merged. Expect 1,662 sites and 1,715 trial sites.
- Do not import location contacts (real people). Owners are synthetic.
- geoPoint is a city centroid; partial dates (`YYYY-MM`) are stored as the 1st of the month.

## Domain rules
- Dependencies: no cycles (service layer), same trial site only (DB composite FKs), and `not_applicable` counts as satisfied (`SATISFIED_STATUSES` in `backend/app/enums.py`).
- Creating a trial site copies templates → milestones and template dependencies → milestone dependencies.
- Every status, owner, or due-date change writes a `milestone_events` row in the same transaction.
- Completing GREEN_LIGHT sets the trial site to `activated`.
- **Computed, never stored:** overdue, delay level, days in status, blocking, top blocker, next-action owner, readiness, projected activation.

## Security and data boundaries
- Never commit secrets. `.env*` is gitignored; read config (`DATABASE_URL`, future LLM keys) from environment variables only.
- Never import or display registry location contacts (real people). Synthetic users use `example.org` emails.
- Do not hand-edit `data/raw_25_studies.json`; regenerate it from the API.
- Never write to ClinicalTrials.gov; the registry is read-only input.
- Always label synthetic data `source_type = synthetic`; never present it as real.
- *(planned LLM)* Send only filtered, structured status with no personal data. LLM output is a suggestion, never a status change.

## Status / next steps
- Done: schema, models, readiness service, importer, seed (18 scenario trial sites), DB-backed API, frontend dashboard and trial site detail.
- Next: Playwright e2e, PostgreSQL run-through, trial-site creation endpoint use of templates from the UI, LLM suggestion layer (optional).
- Open: does drug shipment also need an executed contract? Top-blocker ordering and delay thresholds (`docs/domain-rules.md`) need team sign-off. `scripts/extract_trials.py` is missing; the wrapper `scripts/run_extraction.ps1` calls it and writes outputs to its working directory, not `data/`.
