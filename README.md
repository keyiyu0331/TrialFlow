# TrialFlow

**Clinical trial site activation tracker.** TrialFlow shows a study start-up manager how ready each site in a trial is: which unfinished milestone is blocking activation, and who owns the next action.

Before a site can enroll patients it must complete about ten milestones: IRB approval, contract, budget, regulatory documents, staff training, pharmacy setup, lab and systems access, drug shipment, site initiation visit (SIV), and the sponsor's green light. These steps are spread across several teams, and they stall at the handoffs. TrialFlow makes the blockers and their owners visible.

> CS 146S (Stanford, Autumn 2026) class project.

## Status

| Area | Status |
|---|---|
| Real trial and site data (ClinicalTrials.gov API v2) | ✅ 25 trials, 1,715 site records in `data/` |
| Architecture and tech stack | ✅ `docs/architecture.md` |
| Database schema (SQLAlchemy models + constraints) | ✅ `backend/app/models.py`, `docs/schema.md` |
| REST API design + stub endpoints | ✅ `docs/api-design.md`, browsable at `/docs` |
| Synthetic activation data (seed script) | ⏳ next |
| Readiness, blocker, and dependency-cycle logic | ⏳ planned |
| Frontend (Next.js / React / TypeScript) | ⏳ planned |

The API endpoints currently return **placeholder data**; they are not connected to a database yet.

## Real vs. synthetic data

- **Real:** trials and sites come from the public [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api).
- **Synthetic:** activation milestones, owners, dependencies, and change history are not public, so they are generated and clearly labeled.
- Every record and API object carries `source_type` (`public_registry` or `synthetic`).
- A site's registry recruitment status is shown as-is and **never** used to infer that it is activated.

## Repository layout

```
.
├── backend/                  FastAPI + SQLAlchemy backend
│   ├── app/
│   │   ├── main.py           FastAPI app
│   │   ├── models.py         Database tables and constraints
│   │   ├── schemas.py        API request/response shapes (Pydantic)
│   │   ├── enums.py          Shared status/role enums
│   │   ├── db.py             Engine and session setup
│   │   ├── placeholders.py   Sample data returned by the stub endpoints
│   │   └── routers/          Endpoint definitions
│   ├── tests/                pytest suite
│   └── requirements.txt
├── data/                     Real ClinicalTrials.gov extract
│   ├── raw_25_studies.json   Original API responses (source of truth)
│   ├── trials.csv            25 trials, flattened
│   ├── sites.csv             1,715 trial-site records, flattened
│   └── sample_metadata.json  Query, timestamp, and counts
├── docs/
│   ├── architecture.md       System architecture and technical stack
│   ├── schema.md             Final database schema and business rules
│   ├── api-design.md         Endpoint table and example requests/responses
│   ├── data-mapping.md       API v2 fields → database columns, data-quality notes
│   ├── site-activation-research.md  Milestones, dependencies, delay benchmarks
│   └── work-split.md         Team responsibilities and completed work
├── scripts/
│   └── run_extraction.ps1    Wrapper for the data extraction script
└── CLAUDE.md                 Context for AI-assisted development
```

## Getting started

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
pytest                          # run the test suite
uvicorn app.main:app --reload   # start the API
```

Then open http://localhost:8000/docs to browse the API.

The tests use an in-memory SQLite database, so they need no setup. The app targets PostgreSQL; set `DATABASE_URL` (default `postgresql+psycopg://localhost/trialflow`) once the database is connected.

## Architecture

```
ClinicalTrials.gov API v2 → Python ingestion → PostgreSQL ← synthetic seed data
                                                    ↕
                       FastAPI backend (readiness, blockers, dependencies)
                                                    ↕
                                 Next.js / React frontend
```

See `docs/architecture.md` for the full design, including planned LLM-generated explanations.

## Key API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/trials/{id}/sites` | Trial dashboard: readiness %, top blocker, and next-action owner per site |
| GET | `/trial-sites/{id}/graph` | Milestones, dependencies, and blocking flags |
| PATCH | `/milestones/{id}` | Update status, owner, or due date (recorded in history) |

See `docs/api-design.md` for all 11 endpoints with examples.

## Team

See `docs/work-split.md` for responsibilities and completed work.
