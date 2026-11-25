# Domain rules: blockers, delay, and projected activation

**Status: proposed.** This makes the "computed at query time" values in `docs/schema.md` precise and testable, so `backend/app/services/` and its tests can be written from it. Where this differs from `schema.md`, `schema.md` wins until the team agrees; the differences are listed under Open questions.

All rules are pure functions of one trial site's milestones, its dependencies, and an `as_of` date. They never read the clock, so tests are deterministic. Nothing here is stored.

## Definitions

**D1. Satisfied.** `status` is in `SATISFIED_STATUSES` (`complete`, `not_applicable`).

**D2. Ready.** A milestone that is not satisfied and whose predecessors are all satisfied. Someone can act on it now.

**D3. Overdue.** Not satisfied and `due_date < as_of`. `days_overdue = (as_of - due_date).days`. A milestone due on `as_of` is not overdue.

**D4. Milestone delay level** (the `DelayLevel` enum, from `days_overdue`): `on_time` = 0, `1_7` = 1 to 7, `8_30` = 8 to 30, `over_30` = more than 30.

**D5. Blocking.** As in `schema.md`: not satisfied, and either overdue or `status = blocked`. GREEN_LIGHT is the thing being blocked, so it is never itself blocking.

**D6. Root blocker.** A blocking milestone that is also Ready. A blocking milestone that is not Ready is waiting on one or more root blockers, which the UI can show as "waiting on X".

**D7. Top blocker.** Among root blockers, pick by, in order:
1. most unsatisfied transitive successors (largest downstream impact),
2. most `days_overdue`,
3. earliest `due_date`,
4. lowest template `sort_order` (determinism).

Null when the trial site is activated or has no root blocker.

**D8. Next-action owner.** The top blocker's `owner_user_id`. If that is null, the template's `default_owner_role`.

**D9. Projected finish.** Recursive over the dependency DAG:
```
complete:        completed_at (date)
not_applicable:  contributes no constraint
otherwise:
  dur      = max(due_date - planned_start_date, 1 day)
  pred_max = max(projected_finish(p) for p in predecessors)   # none -> ignored
  projected_finish = max(due_date, as_of, pred_max + dur)
```
The `as_of` floor means an overdue milestone cannot finish before today.

**D10. Slip.** `slip_days(m) = max(0, projected_finish(m) - due_date(m))`. An unsatisfied milestone with `slip_days > 0` is **impacted**. This is how the UI shows which later steps a delay pushes back.

**D11. Trial site slip and delay level.** `site_slip = slip_days(GREEN_LIGHT)`, bucketed with the same `DelayLevel` thresholds as D4.

**D12. Health** (dashboard state):
- `activated`: GREEN_LIGHT is `complete`.
- `blocked`: at least one root blocker exists. A root blocker is by definition overdue or marked `blocked`, so a milestone someone flagged `blocked` counts even before its due date.
- `at_risk`: not blocked, but `site_slip > 0`.
- `on_track`: otherwise.

Readiness % and Ready stay as defined in `schema.md`.

**D13. Open tasks** (My tasks page and the assistant's `open_tasks` tool). Only trial sites `in_startup`; only milestones `not_started`, `in_progress`, or `blocked`. `until = due_date - as_of` in days (null without a due date). Kind, first match wins:
1. `blocked`: status `blocked`, or blocking (D5).
2. `overdue`: overdue (D3).
3. `due_soon`: in progress or Ready, and `until <= 7`.
4. `in_progress`, then `ready`, then `waiting`.

Sorted by kind in that order, then most days overdue, then soonest due. *Urgent* = blocked, overdue, or due soon. Implemented twice and kept in step: `frontend/src/lib/insights.ts` (`openTasks`) and `backend/app/services/tasks.py`; change both together.

**D14. Trial type** (decides which checklist a trial site gets). Computed from `trials.intervention_types`, never stored. Drug if any of DRUG, BIOLOGICAL, DIETARY_SUPPLEMENT, GENETIC, COMBINATION_PRODUCT, DIAGNOSTIC_TEST (registry diagnostic tests here are radiotracers, which the site pharmacy handles); else device if DEVICE; else no product (behavioral, procedure, radiation only, observational, none). A trial with both a drug and a device is a drug trial. Drug adds PHARMACY_SETUP and DRUG_SHIPMENT; device adds DEVICE_SAFETY_CHECK, DEVICE_SHIPMENT (after IRB_APPROVAL and the safety check) and DEVICE_TRAINING (after the shipment); no product adds nothing. SIV depends on every other non-gate step of the checklist. The registry pull has no device trial, so the device demo is a labeled synthetic trial (`TF-DEVICE-DEMO`) at fictional sites.

**D15. What-if projection** (planning card on the trial site page, `POST /trial-sites/{id}/what-if`). Re-runs D9 with up to five assumed finish dates: an assumed milestone's projected finish *is* the assumed date, and its successors follow through D9 as usual. Only projection-derived values change (projected finish, slip, impacted, site slip, and health where slip decides it, `at_risk` vs `on_track`). Status-based values (Ready, overdue, blocking, top blocker) do not: a what-if never completes anything, so a site with a root blocker stays `blocked`. The assumption wins over its predecessors' projected finish, with a warning when they finish later. Eligible: unsatisfied milestones of that trial site, dated on or after `as_of`. Never stored, never writes `milestone_events`. Note that D9 projects an overdue unfinished milestone to finish `as_of`, so for a late step a realistic future date shows how far go-live really slips; earlier dates help only steps that are not yet due.

## Required tests

Derive them from the rules above, not from the implementation. Fixtures should use the default template from `schema.md`.

1. Fresh trial site: the seven milestones with no predecessors are Ready; DRUG_SHIPMENT, SIV, and GREEN_LIGHT are not.
2. IRB complete, pharmacy not: DRUG_SHIPMENT is not Ready; PHARMACY_SETUP is the root blocker if overdue.
3. Overdue boundary: `due_date == as_of` is not overdue; one day earlier is overdue and `1_7`.
4. Delay level boundaries at 0, 1, 7, 8, 30, and 31 days.
5. Slip propagation: IRB incomplete and 20 days overdue pushes DRUG_SHIPMENT, SIV, and GREEN_LIGHT; all three are impacted.
6. `not_applicable` pharmacy does not hold up DRUG_SHIPMENT and adds no constraint to D9.
7. A milestone with `status = blocked` that is not yet overdue still counts as blocking.
8. Top blocker tie-break follows D7 order, including the `sort_order` fallback.
9. Activated trial site: health is `activated`, top blocker is null.
10. Dependency cycle is rejected with 409 `dependency_cycle` (already in `schema.md`).
11. Open tasks (D13): kind precedence, `due_soon` only for in-progress or Ready milestones, and sort order (`tests/test_tasks.py`).
12. Trial type (D14): classification of each intervention mix, one checklist per type, device dates and dependency counts, and a scenario for the wrong type is refused (`tests/test_trial_types.py`).
13. What-if (D15): earlier and later assumptions move the green light through two hops, status-based values and the top blocker do not change, a `not_applicable` branch is unaffected, an assumption earlier than its predecessors is honored, no assumptions equals the baseline (`tests/test_readiness.py`); the endpoint saves nothing and refuses unusable assumptions with 422 `invalid_assumption` (`tests/test_api.py`).

## Open questions

- **Top blocker definition.** `schema.md` says "most-overdue blocking milestone". D7 restricts the choice to Ready milestones and puts downstream impact first. Agree before the dashboard depends on it.
- **DRUG_SHIPMENT and CONTRACT_EXECUTED.** Still open in `schema.md`. If shipment needs an executed contract, add the template edge; D9 handles it with no change.
- **Delay thresholds.** D4 reuses the existing 1-7 / 8-30 / over-30 buckets for the site level too.
