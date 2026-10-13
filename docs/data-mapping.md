# ClinicalTrials.gov API v2 → TrialFlow field mapping

Verified against `data/raw_25_studies.json` (25 studies, 1,715 locations, pulled 2026-10-13; see `data/sample_metadata.json`). All paths are relative to `protocolSection`. `data/trials.csv` and `data/sites.csv` match the JSON exactly (0 mismatches). The importer should read the JSON, not the CSVs.

**Flags:** **A** = array, **M** = missing in some records, **U** = unreliable or needs normalizing.

## Trials (25 records)

| API v2 path | TrialFlow column | Flags | Observed |
|---|---|---|---|
| `identificationModule.nctId` | `trials.nct_id` | | 25/25, unique |
| `identificationModule.briefTitle` | `trials.title` | | 25/25 |
| `identificationModule.acronym` | `trials.acronym` | M | 6/25 present |
| `designModule.phases` | `trials.phases` (JSON list) | A, M | 4 trials `["PHASE1","PHASE2"]`; 6 `["NA"]`; 3 absent (observational) → `[]` |
| `designModule.studyType` | `trials.study_type` | | 22 INTERVENTIONAL, 3 OBSERVATIONAL |
| `sponsorCollaboratorsModule.leadSponsor.name` | `trials.sponsor_name` | | 25/25 |
| `sponsorCollaboratorsModule.leadSponsor.class` | `trials.lead_sponsor_class` | | INDUSTRY 9, OTHER 9, NIH 4, OTHER_GOV 2, NETWORK 1 |
| `statusModule.overallStatus` | `trials.overall_status` | U | **All 25 are RECRUITING**, even though the query also asked for NOT_YET_RECRUITING |
| `statusModule.startDateStruct.date` | `trials.start_date` | U | 3 of 25 are `ESTIMATED` (future) |
| `statusModule.primaryCompletionDateStruct.date` | `trials.primary_completion_date` | U | Partial dates such as `2027-08` → stored as the 1st of the month |
| `statusModule.completionDateStruct.date` | `trials.completion_date` | U | 6 partial (`YYYY-MM`) |
| `statusModule.lastUpdatePostDateStruct.date` | `trials.last_update_posted_date` | U | The same date (2026-10-13) for all 25, because the sample was sorted by this field |
| *(import time)* | `trials.last_registry_sync_at` | | `retrieved_at_utc` from the metadata |
| *(constant)* | `trials.source_type` | | `public_registry` |

Not imported: eligibility, outcomes, arms, `designModule.enrollmentInfo` (planned enrollment, not site-level), and `armsInterventionsModule.interventions` (A, missing in 1 trial). Interventions could later decide whether a trial needs the pharmacy and drug-shipment milestones (15 of 25 trials have a DRUG or BIOLOGICAL intervention).

## Sites and trial sites (1,715 locations)

Each element of `contactsLocationsModule.locations[]` (A) becomes one **trial site**, linked to a de-duplicated **site**.

| API v2 path | TrialFlow column | Flags | Observed |
|---|---|---|---|
| `locations[].facility` | `sites.name` | U | 1,715/1,715 present. **715 are placeholders:** 709 "Research Site" (all of CAMBRIA-1, NCT05774951) and 6 "Research Facility" → `is_placeholder_name = true` |
| `locations[].city` | `sites.city` | | 1,715/1,715 |
| `locations[].state` | `sites.state` | M | missing in 688 rows (mostly outside the US) |
| `locations[].zip` | `sites.zip` | M | missing in 42 |
| `locations[].country` | `sites.country` | | 1,715/1,715 |
| `locations[].geoPoint.lat/lon` | `sites.latitude/longitude` | M, U | missing in 43. These are **city centroids, not facilities**: Milan resolves to the centre of Italy, and 13 Seoul sites share one point |
| `locations[].status` | `trial_sites.reported_recruitment_status` | U | RECRUITING 925, ACTIVE_NOT_RECRUITING 609, WITHDRAWN 132, TERMINATED 19, SUSPENDED 16, COMPLETED 14. **No NOT_YET_RECRUITING.** This is the registry's label, not activation |
| *(array position, 1-based)* | `trial_sites.ctgov_location_index` | U | Equals `site_number` in `sites.csv`. Stable only within one pull |
| `locations[].contacts[]` | — | A, M | 870 rows have contacts (PI names, emails). **Not imported**: real people. Owners are synthetic |

### Location identity and de-duplication
API v2 locations have **no stable ID**; the only keys are those listed above. The importer builds `sites.dedup_key`:

- Normal name: `lower(trim(facility)) | city | state | country` (whitespace collapsed). `state` is included so that two cities with the same name in different states stay separate.
- Placeholder name: `{nct_id}:{location_index}`. These are never merged. Merging by name + city + country would wrongly combine 100 groups of different CAMBRIA-1 sites in the same city (e.g. two "Research Site" rows in Chicago).

Result: **1,662 sites**, 53 of them in more than one trial, and **1,715 trial sites** with no duplicate (trial, site) pairs.

### CSV-only columns (ignored)
`sites.csv` adds `source_type` (always `public_registry`) and `site_activation_status` (always `unknown`). Neither comes from the API. `trials.csv` lacks `phases`, so it cannot replace the JSON.

## Activation data: not public
IRB approval, contract, budget, training, pharmacy, drug shipment, SIV and green light are not in the registry. All of them are **synthetic** (`source_type = synthetic`), as Samhita's spec describes. **TrialFlow never infers activation from `reported_recruitment_status`.** The seed script may use it only as a scenario hint, e.g. RECRUITING → a fully complete synthetic history. Because the pull has no NOT_YET_RECRUITING sites, in-start-up trial sites are a labeled synthetic subset.
