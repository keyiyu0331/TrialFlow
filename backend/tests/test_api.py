"""The REST API against the seeded database (real registry data + synthetic activation data).

"Today" is pinned to AS_OF, so overdue days and delay levels are exact.
"""

import pytest

SWOG = "NCT07578116"


def trial_id(client, nct=SWOG):
    items = client.get("/trials?limit=500").json()["items"]
    return next(t["id"] for t in items if t["nct_id"] == nct)


def dashboard(client, nct=SWOG, query=""):
    return client.get(f"/trials/{trial_id(client, nct)}/sites?{query}").json()


def site_by_scenario(client, scenario, nct=SWOG):
    return next(
        r
        for r in dashboard(
            client, nct, "activation_status=in_startup&activation_status=activated&activation_status=on_hold"
        )["items"]
        if r["scenario_label"] == scenario
    )


def milestone(detail, code):
    return next(ms for ms in detail["milestones"] if ms["template_code"] == code)


def test_openapi_lists_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/trials": {"get"},
        "/trials/{trial_id}": {"get"},
        "/trials/{trial_id}/sites": {"get"},
        "/trial-sites/{trial_site_id}": {"get"},
        "/trial-sites/{trial_site_id}/graph": {"get"},
        "/trial-sites/{trial_site_id}/events": {"get"},
        "/trial-sites/{trial_site_id}/dependencies": {"post"},
        "/dependencies/{dependency_id}": {"delete"},
        "/milestones/{milestone_id}": {"patch"},
        "/templates": {"get"},
        "/users": {"get"},
    }
    for path, methods in expected.items():
        assert methods <= set(paths[path]), path


def test_trial_list_counts_and_search(client):
    page = client.get("/trials?limit=500").json()
    assert page["total"] == 25
    swog = next(t for t in page["items"] if t["nct_id"] == SWOG)
    assert swog["activation_counts"]["in_startup"] == 11
    assert swog["activation_counts"]["activated"] == 1
    assert swog["activation_counts"]["on_hold"] == 0
    assert swog["site_count"] == 59 and swog["source_type"] == "public_registry"
    found = client.get("/trials?q=swog").json()
    assert [t["nct_id"] for t in found["items"]] == [SWOG]
    assert client.get("/trials?q=zzzz-no-match").json()["total"] == 0


def test_trial_detail(client):
    detail = client.get(f"/trials/{trial_id(client)}").json()
    assert detail["registry_url"] == f"https://clinicaltrials.gov/study/{SWOG}"
    assert 0 < detail["avg_readiness_pct"] < 100
    assert detail["target_site_count"] == 12


def test_dashboard_row_for_a_contract_stall(client):
    row = site_by_scenario(client, "contract_stall")
    assert row["health"] == "blocked"
    assert row["top_blocker"]["milestone_name"] == "Contract executed"
    assert row["top_blocker"]["days_overdue"] == 20 and row["top_blocker"]["delay_level"] == "8_30"
    assert row["top_blocker"]["blocked_reason"].startswith("Legal review")
    assert row["next_action_owner"]["role"] == "contracts"
    assert row["readiness_pct"] == 70.0 and row["milestones_satisfied"] == 7 and row["milestones_total"] == 10
    assert row["source_type"] == "synthetic" and row["site"]["source_type"] == "public_registry"


def test_dashboard_is_sorted_worst_first_and_activated_last(client):
    rows = dashboard(
        client, query="activation_status=in_startup&activation_status=activated&activation_status=on_hold"
    )["items"]
    assert rows[0]["delay_level"] == "over_30" and rows[0]["scenario_label"] == "training_gap"
    assert rows[-1]["health"] == "activated"
    assert [r["health"] for r in rows].count("activated") == 1


def test_dashboard_filters(client):
    only_activated = dashboard(client, query="activation_status=activated")
    assert only_activated["total"] == 1 and only_activated["items"][0]["scenario_label"] == "activated_a"
    over_30 = dashboard(client, query="delay_level=over_30&activation_status=in_startup")["items"]
    assert {r["scenario_label"] for r in over_30} == {"pharmacy_delay", "training_gap"}
    assert dashboard(client, query="country=United%20States&activation_status=in_startup")["total"] == 11
    assert dashboard(client, query="country=Nowhere")["total"] == 0
    by_readiness = dashboard(client, query="activation_status=in_startup&sort=readiness")["items"]
    assert [r["readiness_pct"] for r in by_readiness] == sorted(r["readiness_pct"] for r in by_readiness)


def test_dashboard_pagination_and_selected_sites_without_milestones(client):
    page = dashboard(client, query="limit=5&offset=0")
    assert page["total"] == 59 and len(page["items"]) == 5
    last = dashboard(client, query="limit=500")["items"][-1]
    assert last["activation_status"] == "selected" and last["milestones_total"] == 0 and last["top_blocker"] is None


def test_trial_site_detail_has_milestones_and_dependencies(client):
    row = site_by_scenario(client, "irb_delay")
    detail = client.get(f"/trial-sites/{row['id']}").json()
    assert len(detail["milestones"]) == 10 and detail["trial"]["nct_id"] == SWOG
    siv = milestone(detail, "SIV")
    assert len(siv["predecessor_ids"]) == 8 and not siv["is_ready"]
    irb = milestone(detail, "IRB_APPROVAL")
    assert irb["is_ready"] and irb["is_blocking"] and irb["days_overdue"] == 30 and irb["delay_level"] == "8_30"
    shipment = milestone(detail, "DRUG_SHIPMENT")
    assert shipment["is_overdue"] and not shipment["is_ready"] and shipment["is_impacted"]
    assert detail["projected_activation_date"] > detail["target_activation_date"]
    assert detail["site_slip_days"] > 0


def test_graph(client):
    row = site_by_scenario(client, "contract_stall")
    graph = client.get(f"/trial-sites/{row['id']}/graph").json()
    assert len(graph["nodes"]) == 10 and len(graph["edges"]) == 11
    names = {n["milestone_id"]: n["template_code"] for n in graph["nodes"]}
    assert names[graph["green_light_milestone_id"]] == "GREEN_LIGHT"
    assert [names[i] for i in graph["blocking_milestone_ids"]][0] == "CONTRACT_EXECUTED"
    contract_edges = [e for e in graph["edges"] if names[e["predecessor_id"]] == "CONTRACT_EXECUTED"]
    assert contract_edges and not any(e["is_satisfied"] for e in contract_edges)


def test_events_newest_first_and_filters(client):
    row = site_by_scenario(client, "contract_stall")
    events = client.get(f"/trial-sites/{row['id']}/events").json()
    stamps = [e["occurred_at"] for e in events["items"]]
    assert stamps == sorted(stamps, reverse=True) and events["total"] > 10
    blocked = client.get(f"/trial-sites/{row['id']}/events?event_type=status_change").json()["items"]
    assert any(e["new_value"] == "blocked" and e["note"].startswith("Legal review") for e in blocked)
    assert client.get(f"/trial-sites/{row['id']}/events?since=2999-01-01T00:00:00Z").json()["total"] == 0


def test_patch_completes_a_blocked_milestone_and_writes_events(client):
    row = site_by_scenario(client, "contract_stall")
    detail = client.get(f"/trial-sites/{row['id']}").json()
    contract = milestone(detail, "CONTRACT_EXECUTED")
    owner = contract["owner"]["id"]
    r = client.patch(
        f"/milestones/{contract['id']}",
        json={"status": "complete", "note": "Executed CTA received", "changed_by_user_id": owner},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["milestone"]["status"] == "complete" and not body["milestone"]["is_blocking"]
    assert body["milestone"]["blocked_reason"] is None
    assert [e["event_type"] for e in body["events"]] == ["status_change"]
    assert body["events"][0]["old_value"] == "blocked" and body["events"][0]["changed_by"]["id"] == owner
    after = site_by_scenario(client, "contract_stall")
    assert after["readiness_pct"] == 80.0
    # Clearing the contract exposes the next step: the SIV is overdue and now unblocked, owned by the CRA.
    assert after["top_blocker"]["milestone_name"] == "Site initiation visit"
    assert after["next_action_owner"]["role"] == "cra" and after["health"] == "blocked"


def test_patch_writes_one_event_per_changed_field(client):
    row = site_by_scenario(client, "on_track_early")
    detail = client.get(f"/trial-sites/{row['id']}").json()
    ms = milestone(detail, "IRB_APPROVAL")
    r = client.patch(
        f"/milestones/{ms['id']}",
        json={"status": "blocked", "blocked_reason": "IRB asked for revisions", "due_date": "2026-12-31"},
    )
    assert r.status_code == 200
    assert {e["event_type"] for e in r.json()["events"]} == {"status_change", "due_date_change"}
    assert r.json()["milestone"]["blocked_reason"] == "IRB asked for revisions"
    assert r.json()["milestone"]["is_blocking"]


def test_completing_green_light_activates_the_site(client):
    row = site_by_scenario(client, "green_light_pending", nct="NCT06312176")
    green = milestone(client.get(f"/trial-sites/{row['id']}").json(), "GREEN_LIGHT")
    r = client.patch(f"/milestones/{green['id']}", json={"status": "complete"})
    assert r.json()["trial_site_activation_status"] == "activated"
    after = client.get(f"/trial-sites/{row['id']}").json()
    assert after["activation_status"] == "activated" and after["actual_activation_date"] == "2026-10-20"
    assert after["health"] == "activated" and after["readiness_pct"] == 100.0 and after["is_ready"]
    # Reopening it undoes the activation.
    r = client.patch(f"/milestones/{green['id']}", json={"status": "in_progress"})
    assert r.json()["trial_site_activation_status"] == "in_startup"


def test_cannot_complete_a_milestone_with_open_predecessors(client):
    """Regression: GREEN_LIGHT used to be completable at 60% readiness, activating the site early."""
    row = site_by_scenario(client, "on_track_mid")
    detail = client.get(f"/trial-sites/{row['id']}").json()
    green = milestone(detail, "GREEN_LIGHT")
    open_ids = sorted(
        m["id"] for m in detail["milestones"] if m["template_code"] in ("SIV",) and m["status"] != "complete"
    )
    r = client.patch(f"/milestones/{green['id']}", json={"status": "complete"})
    assert r.status_code == 409 and r.json()["code"] == "unsatisfied_dependencies"
    assert r.json()["open_predecessor_ids"] == open_ids
    after = client.get(f"/trial-sites/{row['id']}").json()
    assert after["activation_status"] == "in_startup" and after["actual_activation_date"] is None
    assert milestone(after, "GREEN_LIGHT")["status"] == green["status"]


def test_not_applicable_predecessor_does_not_block_completion(client):
    row = site_by_scenario(client, "na_pharmacy", nct="NCT06312176")
    detail = client.get(f"/trial-sites/{row['id']}").json()
    pharmacy = milestone(detail, "PHARMACY_SETUP")
    assert pharmacy["status"] == "not_applicable"
    ship = milestone(detail, "DRUG_SHIPMENT")
    r = client.patch(f"/milestones/{ship['id']}", json={"status": "complete"})
    # Whatever else is open, a not_applicable predecessor counts as satisfied and is never reported.
    assert pharmacy["id"] not in r.json().get("open_predecessor_ids", [])


def test_blocked_reason_is_kept_in_the_event_note(client):
    row = site_by_scenario(client, "on_track_early")
    ms = milestone(client.get(f"/trial-sites/{row['id']}").json(), "IRB_APPROVAL")
    r = client.patch(f"/milestones/{ms['id']}", json={"status": "blocked", "blocked_reason": "Legal redlines"})
    event = r.json()["events"][0]
    assert event["event_type"] == "status_change" and event["note"] == "Legal redlines"
    # The reason survives unblocking, because it lives in history, not only on the row.
    r = client.patch(f"/milestones/{ms['id']}", json={"status": "in_progress"})
    assert r.json()["milestone"]["blocked_reason"] is None
    notes = [e["note"] for e in client.get(f"/trial-sites/{row['id']}/events").json()["items"]]
    assert "Legal redlines" in notes


def test_explicit_note_wins_over_blocked_reason(client):
    row = site_by_scenario(client, "on_track_early")
    ms = milestone(client.get(f"/trial-sites/{row['id']}").json(), "IRB_APPROVAL")
    r = client.patch(
        f"/milestones/{ms['id']}",
        json={"status": "blocked", "blocked_reason": "Legal redlines", "note": "Raised on Monday call"},
    )
    assert r.json()["events"][0]["note"] == "Raised on Monday call"
    assert r.json()["milestone"]["blocked_reason"] == "Legal redlines"


def test_patch_with_no_change_writes_no_events(client):
    row = site_by_scenario(client, "contract_stall")
    contract = milestone(client.get(f"/trial-sites/{row['id']}").json(), "CONTRACT_EXECUTED")
    r = client.patch(
        f"/milestones/{contract['id']}", json={"status": "blocked", "blocked_reason": contract["blocked_reason"]}
    )
    assert r.status_code == 200 and r.json()["events"] == []


def test_patch_errors(client):
    row = site_by_scenario(client, "contract_stall")
    contract = milestone(client.get(f"/trial-sites/{row['id']}").json(), "CONTRACT_EXECUTED")
    mid = contract["id"]
    assert client.patch(f"/milestones/{mid}", json={}).status_code == 422
    r = client.patch(f"/milestones/{mid}", json={"status": "blocked"})
    assert r.status_code == 422
    assert r.json() == {"detail": "blocked_reason is required when status is blocked", "code": "validation_error"}
    assert client.patch(f"/milestones/{mid}", json={"owner_user_id": 999999}).json()["code"] == "unknown_user"
    assert client.patch(f"/milestones/{mid}", json={"due_date": "2000-01-01"}).json()["code"] == "invalid_due_date"
    assert client.patch("/milestones/999999", json={"status": "complete"}).json()["code"] == "not_found"


def test_validation_errors_use_error_response_shape(client):
    r = client.get("/trials?limit=0")
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert r.json()["detail"].startswith("query.limit:")
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/trials"]["get"]["responses"]["422"]["content"]["application/json"]
    assert schema["schema"]["$ref"].endswith("/ErrorResponse")
    assert "HTTPValidationError" not in spec["components"]["schemas"]


def test_not_found_errors(client):
    for path in (
        "/trials/999999",
        "/trials/999999/sites",
        "/trial-sites/999999",
        "/trial-sites/999999/graph",
        "/trial-sites/999999/events",
    ):
        r = client.get(path)
        assert r.status_code == 404 and r.json()["code"] == "not_found", path


def test_dependency_errors_and_lifecycle(client):
    row = site_by_scenario(client, "contract_stall")
    graph = client.get(f"/trial-sites/{row['id']}/graph").json()
    code = {n["template_code"]: n["milestone_id"] for n in graph["nodes"]}
    url = f"/trial-sites/{row['id']}/dependencies"

    assert (
        client.post(
            url, json={"predecessor_id": code["IRB_APPROVAL"], "successor_id": code["IRB_APPROVAL"]}
        ).status_code
        == 422
    )
    dup = client.post(url, json={"predecessor_id": code["IRB_APPROVAL"], "successor_id": code["DRUG_SHIPMENT"]})
    assert dup.status_code == 409 and dup.json()["code"] == "duplicate_dependency"

    cycle = client.post(url, json={"predecessor_id": code["GREEN_LIGHT"], "successor_id": code["IRB_APPROVAL"]})
    assert cycle.status_code == 409 and cycle.json()["code"] == "dependency_cycle"
    path = cycle.json()["cycle_path"]
    assert path[0] == path[-1] == code["IRB_APPROVAL"] and code["GREEN_LIGHT"] in path

    other = site_by_scenario(client, "irb_delay")
    other_ids = {
        n["template_code"]: n["milestone_id"] for n in client.get(f"/trial-sites/{other['id']}/graph").json()["nodes"]
    }
    cross = client.post(url, json={"predecessor_id": other_ids["IRB_APPROVAL"], "successor_id": code["SIV"]})
    assert cross.status_code == 409 and cross.json()["code"] == "cross_trial_site"

    # A new valid dependency: the contract must now also precede shipment (the open schema question).
    created = client.post(
        url, json={"predecessor_id": code["CONTRACT_EXECUTED"], "successor_id": code["DRUG_SHIPMENT"]}
    )
    assert created.status_code == 201
    shipment = milestone(client.get(f"/trial-sites/{row['id']}").json(), "DRUG_SHIPMENT")
    assert code["CONTRACT_EXECUTED"] in shipment["predecessor_ids"]
    assert client.delete(f"/dependencies/{created.json()['id']}").status_code == 204
    assert client.delete(f"/dependencies/{created.json()['id']}").json()["code"] == "not_found"


def test_templates_and_users(client):
    templates = client.get("/templates").json()
    assert [t["code"] for t in templates][0] == "IRB_APPROVAL" and len(templates) == 10
    siv = next(t for t in templates if t["code"] == "SIV")
    assert len(siv["predecessor_codes"]) == 8 and siv["is_gate"]
    sponsor = client.get("/users?sponsor_only=true").json()
    assert {u["role"] for u in sponsor} == {"startup_manager", "cra", "sponsor_supply"}
    cras = client.get("/users?role=cra").json()
    assert len(cras) == 2 and all(u["site_id"] is None for u in cras)
    site_id = next(u["site_id"] for u in client.get("/users?role=regulatory").json())
    assert all(u["site_id"] == site_id for u in client.get(f"/users?site_id={site_id}").json())


def test_cors_allows_the_frontend_dev_server(client):
    r = client.options("/trials", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.parametrize("path", ["/health"])
def test_health(client, path):
    assert client.get(path).json() == {"status": "ok"}
