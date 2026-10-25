# TrialFlow System Overview

How the frontend, backend, and database fit together; how the backend files connect; and one request traced end to end. Diagrams are Mermaid and render on GitHub and in VS Code's Markdown preview.

**Legend:** ⏳ = planned, not built yet. Dashed grey boxes are planned. `DATABASE_URL` picks the database: PostgreSQL by default, SQLite for local runs and tests (in-memory).

## 1. System overview

```mermaid
flowchart LR
    CTG["ClinicalTrials.gov API v2"]
    RAW[("data/raw_25_studies.json<br/>25 real trials, 1,715 locations")]
    IMP["scripts/import_registry.py<br/>real trials and sites"]
    SEED["scripts/seed.py --reset --as-of<br/>synthetic milestones, owners, events<br/>(18 scenario trial sites)"]
    DB[("PostgreSQL or SQLite<br/>(DATABASE_URL)<br/>stores facts only")]
    BE["FastAPI backend<br/>backend/app/<br/>validates, applies rules,<br/>computes readiness and blockers"]
    FE["Next.js frontend<br/>/ dashboard, /tasks, /trials,<br/>/sites/[id] checklist + updates"]
    USER(["Start-up manager / site staff"])
    LLM["LLM suggestions ⏳"]

    CTG -- "one-time pull (offline)" --> RAW
    RAW --> IMP --> DB
    SEED --> DB
    USER <--> FE
    FE -- "HTTP request (JSON)" --> BE
    BE -- "JSON response" --> FE
    BE <-- "SQL via SQLAlchemy" --> DB
    BE -.-> LLM

    classDef planned stroke-dasharray: 5 5,fill:#f2f2f2,color:#555
    class LLM planned
```

- **Frontend:** shows data and sends user changes. Pages fetch on the server (`API_URL`); milestone updates go from the browser (`NEXT_PUBLIC_API_URL`). `src/lib/insights.ts` derives My tasks and trial summaries from existing endpoints; it adds no business rules.
- **Backend:** validates every request, enforces the rules, and computes readiness, delays, blockers, and next-action owners on each request.
- **Database:** stores facts only (statuses, dates, owners, history), never computed values.
- **Scripts:** load the database before the app runs. The app never calls ClinicalTrials.gov while serving a request.

## 2. Backend file map

```mermaid
flowchart TD
    MAIN["main.py<br/>creates the app, error handlers,<br/>mounts routers"]
    subgraph ROUTERS["routers/ (one file per URL group)"]
        TR["trials.py<br/>/trials"]
        TS["trial_sites.py<br/>/trial-sites"]
        MI["milestones.py<br/>/milestones, /dependencies"]
        CA["catalog.py<br/>/templates, /users"]
    end
    COMMON["routers/common.py<br/>not_found, paging, error docs"]
    DEPS["deps.py<br/>get_today (pinned in tests)"]
    subgraph SERVICES["services/"]
        VIEWS["views.py<br/>load bundles, build API shapes"]
        RD["readiness.py<br/>pure rules: blocking, top blocker,<br/>slip, health, cycle check"]
        TPL["templates.py<br/>templates → milestones + deps"]
        IMPS["registry_import.py"]
        SEEDS["seeding.py<br/>scenarios"]
    end
    SCRIPTS["scripts/import_registry.py<br/>scripts/seed.py"]
    MODELS["models.py<br/>database tables + constraints"]
    DBPY["db.py<br/>engine, get_session"]
    DB[("PostgreSQL / SQLite")]
    SCHEMAS["schemas.py<br/>API contract: request and<br/>response shapes, validation"]
    ENUMS["enums.py<br/>shared vocabulary:<br/>statuses, roles, workstreams"]

    MAIN --> ROUTERS
    ROUTERS --> COMMON
    ROUTERS --> DEPS
    ROUTERS --> VIEWS --> RD
    MI --> RD
    TS --> RD
    VIEWS --> SCHEMAS
    ROUTERS -- "queries via session" --> MODELS
    MODELS --> DBPY --> DB
    SCRIPTS --> IMPS
    SCRIPTS --> SEEDS --> TPL
    IMPS --> MODELS
    SEEDS --> MODELS
    ENUMS --> MODELS
    ENUMS --> SCHEMAS
    ENUMS --> RD
```

| File | Main job |
|---|---|
| `main.py` | Starts the app, mounts the routers, and converts every error to `{detail, code}` |
| `routers/*.py` | Define the URLs; query the database, call services, return a schema object |
| `routers/common.py` | Shared helpers: `not_found()`, paging limits, error docs |
| `deps.py` | `get_today()`: the date computed values are measured against; tests override it |
| `services/readiness.py` | Pure functions (no database): `analyze()` for readiness, blocking, top blocker, slip, health; `find_path()` for cycle checks. See `docs/domain-rules.md` |
| `services/views.py` | `load_bundles()` loads milestones and dependencies for many trial sites in two queries, runs `analyze()`, and builds response schemas |
| `services/templates.py` | Copies milestone templates and template dependencies into a new trial site |
| `services/registry_import.py` | Parses the registry JSON into trials, sites, and trial sites (dedup keys, partial dates) |
| `services/seeding.py` | Synthetic owners, milestones, and events for the scenario trial sites |
| `schemas.py` | What goes over the wire: validates input, shapes output, generates `/docs` |
| `models.py` | What is stored: tables and constraints (e.g. one row per trial and site pair) |
| `db.py` | Engine and `get_session`; turns on foreign keys for SQLite |
| `enums.py` | Allowed values, shared by models, schemas, and services so they never disagree |

Dependency direction: **routers → services → models → database**, with **schemas** shaping what goes back out. `readiness.py` never touches the database, so its rules are tested with plain inputs.

## 3. Sample data flow: "Show activation status for trial 1"

A start-up manager opens trial 1 and filters to sites still in start-up.

```mermaid
sequenceDiagram
    autonumber
    actor U as Start-up manager
    participant FE as Next.js page (server)
    participant M as main.py
    participant R as routers/trials.py
    participant DB as models.py + database
    participant V as services/views.py
    participant RD as services/readiness.py
    participant SC as schemas.py

    U->>FE: Open trial 1, filter "In start-up"
    FE->>M: GET /trials/1/sites?activation_status=in_startup
    M->>R: route to list_trial_sites()
    Note over M,R: FastAPI validates inputs first:<br/>trial_id is an int, in_startup is an ActivationStatus
    alt invalid input (e.g. activation_status=in_progress)
        M-->>FE: 422 validation_error
    end
    R->>DB: does trial 1 exist?
    alt trial does not exist (e.g. trial 99)
        R-->>FE: 404 not_found
    end
    R->>DB: SELECT trial_sites JOIN sites<br/>WHERE trial_id = 1 AND activation_status = in_startup
    DB-->>R: trial sites (facts only)
    R->>V: load_bundles(trial_sites, today)
    V->>DB: milestones + dependencies (two queries)
    V->>RD: analyze(milestones, edges, today) per trial site
    RD-->>V: readiness %, overdue days, delay level,<br/>top blocker, next-action owner
    V-->>R: TrialSiteSummary per trial site
    R->>R: filter by delay_level, sort (default -delay), page
    R->>SC: wrap in Page[TrialSiteSummary]
    SC-->>M: validated, serialized JSON
    M-->>FE: 200 items, total, limit, offset
    FE-->>U: e.g. 30% ready, blocked by Contract executed<br/>(12 days late), chase Site contracts office
```

**Only the totals?** `GET /trials/1` follows the same path and returns a `TrialDetail` whose `activation_counts` (e.g. 12 in start-up, 47 activated) are computed by counting trial sites by status.

**The write path** goes the other way. Site staff mark a milestone complete in the browser, which sends `PATCH /milestones/{id}` to `routers/milestones.py`. In one transaction, it:
- rejects the change with 409 `unsatisfied_dependencies` if a predecessor is still open;
- updates the milestone row and writes one `milestone_events` row per changed field (status, owner, due date);
- sets the trial site to `activated` when GREEN_LIGHT is completed, and back to `in_startup` if it is reopened;
- returns the updated milestone, its events, and the trial site's activation status.

Adding a dependency (`POST /trial-sites/{id}/dependencies`) runs `readiness.find_path()` first and returns 409 `dependency_cycle` with the cycle path if the new edge would close a loop.

The next dashboard request then shows the new readiness.

**Try it** (local SQLite, all from the repo root so every step opens the same `trialflow.db`):
```bash
export DATABASE_URL=sqlite:///trialflow.db
python scripts/import_registry.py && python scripts/seed.py --reset
uvicorn app.main:app --app-dir backend --reload
curl "localhost:8000/trials/1/sites?activation_status=in_startup"
cd frontend && npm install && npm run dev   # second terminal; http://localhost:3000
```

Keep this file up to date when the structure changes (e.g. when the LLM layer or new services are added).
