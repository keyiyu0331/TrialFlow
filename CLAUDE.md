# TrialFlow

Workflow platform for clinical trial site activation. CS 146S class project, due Dec 10, 2026.
- Keyi: schema, API, synthetic data, business context.
- Samhita: real data extraction, architecture, tech stack (done; see `docs/architecture.md`).

Primary user: a study start-up manager (sponsor/CRO) tracking many sites for one trial. Secondary: site staff updating their assigned milestones.

## Terminology (use consistently)
trial, site, **trial site** (one site in one trial; the unit we activate), milestone, dependency, blocker, green light.

## Source-of-truth docs
- `docs/schema.md`: final schema and rules
- `docs/api-design.md`: endpoint table and examples. Keep it concise; it feeds a 2-page technical spec.
- `docs/data-mapping.md`: API v2 JSON paths → columns, with data-quality flags
- `docs/site-activation-research.md`: milestones, dependencies, delay benchmarks
- `docs/architecture.md`: system architecture and tech stack; `docs/work-split.md`: team responsibilities
- Update these docs when you change models or endpoints.

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

## Stack and layout
Python, FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL, pytest. The frontend (Next.js/React/TypeScript) is not started.
- `backend/app/models.py` (tables), `enums.py`, `schemas.py` (API shapes), `routers/` (endpoints), `db.py`
- `backend/app/placeholders.py`: synthetic placeholder data the router stubs return. Replace it with DB queries.
- Tests run on SQLite in-memory with FK enforcement, so keep models portable: JSON, not ARRAY; no PG-only SQL in CHECKs.

## Commands
- Install: `pip install -r backend/requirements.txt`
- Test: `cd backend && pytest`
- Dev server: `cd backend && uvicorn app.main:app --reload`, then open http://localhost:8000/docs

## Status / next steps
- Done: schema, models, Pydantic schemas, router stubs, constraint tests.
- Next: seed script (synthetic milestones for 10–20 trial sites, scenarios such as `contract_stall` and `irb_delay`), importer, DB-backed routers, cycle detection, readiness/blocker service.
- Open: does drug shipment also need an executed contract? `scripts/extract_trials.py` is missing; the wrapper `scripts/run_extraction.ps1` calls it and writes outputs to its working directory, not `data/`.
