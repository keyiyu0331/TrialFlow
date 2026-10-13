# TrialFlow REST API Design

FastAPI, JSON. Interactive docs are at `/docs`. Stubs live in `backend/app/routers/`, and the schemas in `backend/app/schemas.py`. Every object carries `source_type` (`public_registry` or `synthetic`). Fields such as readiness, delay level, blocking, top blocker, and next-action owner are **computed at request time**, never stored. List endpoints return `{items, total, limit, offset}`. Errors return `{detail, code}`.

## Endpoints

| Method | Path | Purpose | Main query params / body |
|---|---|---|---|
| GET | `/trials` | List trials with site counts by activation status | `q`, `overall_status`, `limit`, `offset` |
| GET | `/trials/{id}` | Trial detail, registry fields, average readiness | — |
| GET | `/trials/{id}/sites` | **Trial dashboard:** one row per trial site with readiness %, top blocker, next-action owner | `activation_status`*, `delay_level`*, `country`, `sort` (`-delay`, `readiness`, `target_activation_date`), `limit`, `offset` |
| GET | `/trial-sites/{id}` | One trial site with all its milestones | — |
| GET | `/trial-sites/{id}/graph` | **Dependency graph:** nodes, edges, blocking flags | — |
| GET | `/trial-sites/{id}/events` | Change-history timeline, newest first | `milestone_id`, `event_type`*, `since`, `limit`, `offset` |
| PATCH | `/milestones/{id}` | **Update status, owner, or due date;** writes one event per changed field | body: `status`, `owner_user_id`, `due_date`, `blocked_reason`, `note`, `changed_by_user_id` |
| POST | `/trial-sites/{id}/dependencies` | Add a dependency. **409** for `dependency_cycle`, `cross_trial_site`, or `duplicate_dependency` | body: `predecessor_id`, `successor_id` |
| DELETE | `/dependencies/{id}` | Remove a dependency (204) | — |
| GET | `/templates` | Default milestone checklist with predecessor codes | — |
| GET | `/users` | Milestone owners | `site_id`, `role`, `sponsor_only` |

\* can be repeated, e.g. `?delay_level=8_30&delay_level=over_30`.

**Status codes:** 200/201/204 on success; 404 `not_found`; 409 on dependency conflicts; 422 for an invalid body (e.g. an empty PATCH, `blocked` without `blocked_reason`, or a self-dependency).

## Key examples
These are trimmed versions of the stub output. The trial and site are real (NCT07578116, Smilow Derby); the milestones and owners are synthetic.

### 1. `GET /trials/1/sites?activation_status=in_startup`
The start-up manager's main view: where each site stands, what is blocking it, and who acts next.
```json
{
  "items": [{
    "id": 101,
    "site": {"id": 2, "name": "Smilow Cancer Hospital-Derby Care Center", "city": "Derby",
             "state": "Connecticut", "country": "United States",
             "is_placeholder_name": false, "source_type": "public_registry"},
    "reported_recruitment_status": "RECRUITING",
    "activation_status": "in_startup",
    "target_activation_date": "2026-11-20",
    "scenario_label": "contract_stall",
    "source_type": "synthetic",
    "readiness_pct": 30.0, "milestones_satisfied": 3, "milestones_total": 10,
    "is_ready": false,
    "delay_level": "8_30",
    "top_blocker": {"milestone_id": 1002, "milestone_name": "Contract executed",
                    "status": "blocked", "due_date": "2026-10-01",
                    "days_overdue": 12, "delay_level": "8_30",
                    "owner": {"id": 12, "name": "Site contracts office", "role": "contracts"}},
    "next_action_owner": {"id": 12, "name": "Site contracts office", "role": "contracts"}
  }],
  "total": 1, "limit": 50, "offset": 0
}
```

### 2. `GET /trial-sites/101/graph`
Feeds the dependency view. `is_satisfied` on an edge means the predecessor is complete or not applicable.
```json
{
  "trial_site_id": 101,
  "green_light_milestone_id": 1010,
  "nodes": [
    {"milestone_id": 1002, "template_code": "CONTRACT_EXECUTED", "name": "Contract executed",
     "workstream": "contracts", "status": "blocked", "is_gate": false,
     "owner": {"id": 12, "name": "Site contracts office", "role": "contracts"},
     "due_date": "2026-10-01", "is_satisfied": false, "is_overdue": true, "is_blocking": true},
    {"milestone_id": 1009, "template_code": "SIV", "name": "Site initiation visit",
     "workstream": "activation", "status": "not_started", "is_gate": true,
     "owner": {"id": 2, "name": "Marco Ruiz", "role": "cra"},
     "due_date": "2026-11-15", "is_satisfied": false, "is_overdue": false, "is_blocking": false}
  ],
  "edges": [
    {"id": 5004, "predecessor_id": 1002, "successor_id": 1009,
     "is_satisfied": false, "source_type": "synthetic"}
  ],
  "blocking_milestone_ids": [1002]
}
```

### 3. `PATCH /milestones/1002`
Site staff close their milestone. The response returns the updated milestone, the events written, and the trial site's activation status. Completing GREEN_LIGHT would change it to `activated`.
```json
// request
{"status": "complete", "note": "Fully executed CTA received", "changed_by_user_id": 12}
// 200 response
{
  "milestone": {"id": 1002, "name": "Contract executed", "status": "complete",
                "completed_at": "2026-10-13T21:22:10Z", "status_changed_at": "2026-10-13T21:22:10Z",
                "blocked_reason": null, "is_overdue": false, "delay_level": "on_time",
                "days_in_status": 0, "is_blocking": false, "source_type": "synthetic"},
  "events": [{"id": 9101, "milestone_id": 1002, "event_type": "status_change",
              "old_value": "blocked", "new_value": "complete",
              "note": "Fully executed CTA received",
              "changed_by": {"id": 12, "name": "Site contracts office", "role": "contracts"},
              "occurred_at": "2026-10-13T21:22:10Z", "source_type": "synthetic"}],
  "trial_site_activation_status": "in_startup"
}
```
A dependency conflict on POST returns:
`409 {"detail": "Adding 1010 → 1002 would create a cycle", "code": "dependency_cycle", "cycle_path": [1002, 1009, 1010, 1002]}`

## Not yet implemented
The stubs return data from `backend/app/placeholders.py`. Still to build: the DB-backed queries, blocker and next-action computation, cycle detection, transactional event writes, template instantiation, and authentication (none in the MVP; `changed_by_user_id` is passed in the body).
