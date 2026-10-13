# TrialFlow Database Schema (final)

Supersedes the earlier AACT-based draft. Implemented in `backend/app/models.py`, with enums in `backend/app/enums.py`. The field-level source mapping is in `docs/data-mapping.md`.

## At a glance
The schema centers on **trial sites**: one site's participation in one trial, the unit TrialFlow activates. Each trial site owns about 10 **milestones** linked by **dependencies**, which converge on the SIV and the **green light**. Trials and sites are real ClinicalTrials.gov API v2 records. Milestones, owners, dependencies, and history are synthetic.

```
trials 1─* trial_sites *─1 sites 1─* users
              │1
              *
          milestones ─* milestone_events
              │ (predecessor / successor, same trial site)
       milestone_dependencies
milestone_templates 1─* template_dependencies   (copied into milestones / milestone_dependencies)
```

**Provenance.** Every table except the templates has `source_type` ∈ {`public_registry`, `synthetic`} (Samhita's term). It replaces the draft's `data_source` and `is_synthetic`, and every API object carries it so the UI can label synthetic data.

**Conventions.** PostgreSQL, integer primary keys, and `created_at`/`updated_at` on every table except `template_dependencies` and `milestone_events` (append-only, uses `occurred_at`). Enums are native PG enums. On SQLite, which the tests use, they become CHECK constraints. `phases` is a JSON list for portability.

## Tables
Only the key columns are listed; `models.py` is the source of truth.

**trials**: `nct_id` (unique; required unless synthetic), `title`, `acronym`, `phases` (JSON list), `study_type`, `sponsor_name`, `lead_sponsor_class`, `overall_status`, `start_date`, `primary_completion_date`, `completion_date`, `last_update_posted_date`, `last_registry_sync_at`, `target_site_count` (≥ 0), `target_fpi_date`, `source_type`.

**sites**: `dedup_key` (unique), `name`, `is_placeholder_name`, `city`, `state`, `zip`, `country`, `latitude`/`longitude` (city-level centroid, range-checked), `source_type`.

**trial_sites**: `trial_id` FK, `site_id` FK, **UNIQUE(trial_id, site_id)**, `ctgov_location_index` (≥ 1), `reported_recruitment_status` (CT.gov enum), `activation_status` (`selected | in_startup | activated | on_hold | dropped`), `selected_date`, `target_activation_date`, `actual_activation_date` (**CHECK** only set when activated), `scenario_label`, `source_type`.

**users**: `name`, `email` (unique), `role` (`startup_manager | cra | site_coordinator | regulatory | contracts | pharmacist | lab_manager | pi | sponsor_supply`), `site_id` FK (null for sponsor or CRO staff), `team_name` (set when the owner is a team).

**milestone_templates**: `code` (unique), `name`, `workstream`, `default_owner_role`, `default_duration_days` (≥ 0), `is_gate`, `sort_order` (unique).

**template_dependencies**: PK (`predecessor_template_id`, `successor_template_id`), **CHECK** predecessor ≠ successor.

**milestones**: `trial_site_id` FK, `template_id` FK (null for custom milestones), `name`, `workstream`, `status` (`not_started | in_progress | blocked | complete | not_applicable`), `owner_user_id` FK, `planned_start_date`, `due_date` (**CHECK** ≥ planned start), `started_at`, `completed_at` (**CHECK** set if and only if status = complete), `status_changed_at`, `blocked_reason`, `notes`, `source_type`. **UNIQUE(trial_site_id, template_id)**, plus UNIQUE(id, trial_site_id), the target of the composite FKs below.

**milestone_dependencies**: `id`, `trial_site_id`, `predecessor_id`, `successor_id`, **UNIQUE(predecessor_id, successor_id)**, **CHECK** predecessor ≠ successor, and **composite FKs** (`predecessor_id`, `trial_site_id`) and (`successor_id`, `trial_site_id`) → milestones(`id`, `trial_site_id`).

**milestone_events**: `milestone_id` FK, `changed_by_user_id` FK (null for system or seed changes), `event_type` (`status_change | owner_change | due_date_change | note`), `old_value`, `new_value`, `note`, `occurred_at`, `source_type`. **CHECK**: a change event must actually change the value.

## Default template
Ten milestones, as listed in the brief. Feasibility and selection happen before a trial site exists, so they are recorded as `trial_sites.selected_date` rather than as a milestone.

| Code | Owner role | Days | Depends on |
|---|---|---|---|
| IRB_APPROVAL | regulatory | 45 | — |
| CONTRACT_EXECUTED | contracts | 60 | — |
| BUDGET_FINALIZED | contracts | 45 | — |
| REGULATORY_DOCS | site_coordinator | 21 | — |
| STAFF_TRAINING | site_coordinator | 14 | — |
| PHARMACY_SETUP | pharmacist | 21 | — |
| LAB_SYSTEMS_ACCESS | lab_manager | 21 | — |
| DRUG_SHIPMENT | sponsor_supply | 14 | IRB_APPROVAL, PHARMACY_SETUP |
| SIV (gate) | cra | 7 | all eight above |
| GREEN_LIGHT (gate) | startup_manager | 3 | SIV |

Durations are midpoints of the ranges in `docs/site-activation-research.md`. Whether DRUG_SHIPMENT also needs CONTRACT_EXECUTED is still an open question for a domain expert.

## Rules
| Rule | Where enforced |
|---|---|
| No self-dependency; no duplicate edge | DB (CHECK, UNIQUE) |
| **Dependencies stay within one trial site** | **DB** (composite FKs), and the API returns 409 `cross_trial_site` |
| No cycles | Service layer (reachability check before insert), API 409 `dependency_cycle`. A DB constraint cannot express this |
| `not_applicable` satisfies successors | Service layer (`SATISFIED_STATUSES` in `enums.py`) |
| Creating a trial site copies templates → milestones and template deps → milestone deps, with due dates from `default_duration_days` | Service layer (one transaction); UNIQUE(trial_site_id, template_id) prevents copying twice |
| Every status, owner, or due-date change writes a `milestone_events` row and, for status changes, updates `status_changed_at` | Service layer (same transaction as the change) |
| Completing GREEN_LIGHT sets `activation_status = activated` and `actual_activation_date` | Service layer; DB CHECK keeps the date consistent |
| **Recruitment status ≠ activation** | Convention: `reported_recruitment_status` is display-only and never drives readiness |

## Computed at query time (never stored)
| Value | Definition |
|---|---|
| Overdue | `due_date` < today and status not in {complete, not_applicable} |
| Delay level | Days overdue: `on_time`, `1_7`, `8_30`, `over_30` |
| Days in status | today − `status_changed_at` |
| Blocking | An unsatisfied milestone that is overdue or `blocked`, with an unsatisfied path to GREEN_LIGHT |
| Top blocker / next-action owner | The most-overdue blocking milestone, and its owner |
| Readiness % | (complete + not_applicable) ÷ all milestones × 100. This matches Samhita's "complete ÷ required" because not_applicable = not required |
| Ready | All milestones satisfied and no unresolved blocker (Samhita's definition) |
| Projected activation (stretch) | Longest remaining path to GREEN_LIGHT |
