import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

GETS = [
    "/trials",
    "/trials/1",
    "/trials/1/sites",
    "/trials/1/sites?activation_status=in_startup&delay_level=8_30",
    "/trial-sites/101",
    "/trial-sites/101/graph",
    "/trial-sites/101/events",
    "/templates",
    "/users?site_id=2",
]


@pytest.mark.parametrize("path", GETS)
def test_get_stubs_return_200(path):
    assert client.get(path).status_code == 200


def test_openapi_lists_every_endpoint():
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


def test_trial_sites_row_has_dashboard_fields():
    row = client.get("/trials/1/sites").json()["items"][0]
    assert row["top_blocker"]["milestone_name"] == "Contract executed"
    assert row["next_action_owner"]["name"] == "Site contracts office"
    assert row["source_type"] == "synthetic" and row["site"]["source_type"] == "public_registry"


def test_patch_writes_one_event_per_changed_field():
    r = client.patch("/milestones/1002", json={"status": "in_progress", "due_date": "2026-10-31",
                                               "changed_by_user_id": 12})
    assert r.status_code == 200
    assert {e["event_type"] for e in r.json()["events"]} == {"status_change", "due_date_change"}


def test_patch_rejects_empty_body_and_blocked_without_reason():
    assert client.patch("/milestones/1002", json={}).status_code == 422
    r = client.patch("/milestones/1003", json={"status": "blocked"})
    assert r.status_code == 422
    assert r.json() == {"detail": "blocked_reason is required when status is blocked",
                        "code": "validation_error"}


def test_validation_errors_use_error_response_shape():
    r = client.get("/trials?limit=0")
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert r.json()["detail"].startswith("query.limit:")
    spec = client.get("/openapi.json").json()
    schema = spec["paths"]["/trials"]["get"]["responses"]["422"]["content"]["application/json"]
    assert schema["schema"]["$ref"].endswith("/ErrorResponse")
    assert "HTTPValidationError" not in spec["components"]["schemas"]


def test_dependency_errors():
    assert client.post("/trial-sites/101/dependencies",
                       json={"predecessor_id": 1001, "successor_id": 1001}).status_code == 422
    dup = client.post("/trial-sites/101/dependencies",
                      json={"predecessor_id": 1001, "successor_id": 1008})
    assert dup.status_code == 409 and dup.json()["code"] == "duplicate_dependency"
    assert client.delete("/dependencies/5001").status_code == 204
    assert client.get("/trials/999").json()["code"] == "not_found"
