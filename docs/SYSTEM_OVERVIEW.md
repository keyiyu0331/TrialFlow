# TrialFlow System Overview

How the frontend, backend, and database fit together; how the backend files connect; and one request traced end to end. Diagrams are Mermaid and render on GitHub and in VS Code's Markdown preview.

**Legend:** ⏳ = planned, not built yet. Dashed grey boxes are planned. Today the backend serves hard-coded data from `placeholders.py` instead of a database.

## 1. System overview

```mermaid
flowchart LR
    CTG["ClinicalTrials.gov API v2"]
    RAW[("data/raw_25_studies.json<br/>25 real trials, 1,715 locations")]
    IMP["scripts/import_registry.py ⏳<br/>real trials and sites"]
    SEED["scripts/seed.py ⏳<br/>synthetic milestones, owners, events"]
    DB[("PostgreSQL ⏳<br/>stores facts only")]
    BE["FastAPI backend<br/>backend/app/<br/>validates, applies rules,<br/>computes readiness and blockers"]
    PH["placeholders.py<br/>hard-coded sample data (today)"]
    FE["Next.js frontend ⏳<br/>dashboard, site checklist,<br/>update buttons"]
    USER(["Start-up manager / site staff"])

    CTG -- "one-time pull (offline)" --> RAW
    RAW --> IMP --> DB
    SEED --> DB
    USER <--> FE
    FE -- "HTTP request (JSON)" --> BE
    BE -- "JSON response" --> FE
    BE <-- "SQL via SQLAlchemy ⏳" --> DB
    BE -. "today" .-> PH

    classDef planned stroke-dasharray: 5 5,fill:#f2f2f2,color:#555
    class IMP,SEED,DB,FE planned
```

- **Frontend:** shows data and sends user changes. No business logic.
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
    PH["placeholders.py<br/>fake data (today, delete later)"]
    SVC["services/ ⏳<br/>readiness, blockers,<br/>cycle check, event writes"]
    MODELS["models.py<br/>database tables + constraints"]
    DBPY["db.py<br/>engine and session"]
    PG[("PostgreSQL ⏳")]
    SCHEMAS["schemas.py<br/>API contract: request and<br/>response shapes, validation"]
    ENUMS["enums.py<br/>shared vocabulary:<br/>statuses, roles, workstreams"]

    MAIN --> ROUTERS
    ROUTERS --> COMMON
    ROUTERS -. "today" .-> PH
    ROUTERS -- "planned" --> SVC
    SVC --> MODELS --> DBPY --> PG
    ROUTERS -- "return objects shaped as" --> SCHEMAS
    PH --> SCHEMAS
    ENUMS --> MODELS
    ENUMS --> SCHEMAS

    classDef planned stroke-dasharray: 5 5,fill:#f2f2f2,color:#555
    class SVC,PG planned
```

| File | Main job |
|---|---|
| `main.py` | Starts the app, mounts the routers, and converts every error to `{detail, code}` |
| `routers/*.py` | Define the URLs; take a request, get data, return a schema object |
| `routers/common.py` | Shared helpers: `not_found()`, paging limits, error docs |
| `schemas.py` | What goes over the wire: validates input, shapes output, generates `/docs` |
| `models.py` | What is stored: tables and constraints (e.g. one row per trial and site pair) |
| `db.py` | Database connection setup; turns on foreign keys for SQLite in tests |
| `enums.py` | Allowed values, shared by models and schemas so they never disagree |
| `placeholders.py` | Temporary fake data in schema shape; replaced by services and the database |
| `services/` ⏳ | Business logic: readiness, blockers, cycle detection, event writes |

Dependency direction: **routers → services → models → database**, with **schemas** shaping what goes back out.

## 3. Sample data flow: "Show activation status for trial 1"

A start-up manager opens trial 1 and filters to sites still in start-up.

```mermaid
sequenceDiagram
    autonumber
    actor U as Start-up manager
    participant FE as Frontend ⏳
    participant M as main.py
    participant R as routers/trials.py
    participant S as services/ ⏳
    participant DB as models.py + PostgreSQL ⏳
    participant SC as schemas.py

    U->>FE: Open trial 1, filter "In start-up"
    FE->>M: GET /trials/1/sites?activation_status=in_startup
    M->>R: route to list_trial_sites()
    Note over M,R: FastAPI validates inputs first:<br/>trial_id is an int, in_startup is an ActivationStatus
    alt invalid input (e.g. activation_status=in_progress)
        M-->>FE: 422 validation_error
    end
    R->>S: dashboard(trial_id=1, filters)
    Note over R,S: Today: R reads placeholders.py instead
    S->>DB: SELECT trial_sites JOIN sites JOIN milestones<br/>WHERE trial_id = 1 AND activation_status = in_startup
    alt trial does not exist (e.g. trial 99)
        R-->>FE: 404 not_found
    end
    DB-->>S: rows (facts only)
    S->>S: compute readiness %, overdue days,<br/>top blocker, next-action owner
    S-->>R: per-site results
    R->>SC: wrap in Page[TrialSiteSummary]
    SC-->>M: validated, serialized JSON
    M-->>FE: 200 items, total, limit, offset
    FE-->>U: Smilow Derby: 30% ready,<br/>blocked by Contract executed (12 days late),<br/>chase Site contracts office
```

**Only the totals?** `GET /trials/1` follows the same path and returns a `TrialDetail` whose `activation_counts` (e.g. 12 in start-up, 47 activated) are computed by counting trial sites by status.

**The write path** goes the other way. Site staff mark a milestone complete, so the frontend sends `PATCH /milestones/{id}` to `routers/milestones.py`. The planned service then:
- updates the milestone row;
- writes a `milestone_events` row in the same transaction;
- sets the trial site to `activated` if the milestone is GREEN_LIGHT.

The next dashboard request then shows the new readiness.

**Try it today** (steps 2–12 run on placeholder data):
```bash
cd backend && uvicorn app.main:app --reload
curl "localhost:8000/trials/1/sites?activation_status=in_startup"
```

Keep this file up to date when the structure changes (e.g. when `services/`, the database, or the frontend is built).
