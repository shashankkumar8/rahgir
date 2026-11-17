from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.demo import DEMO_CASES

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_static_homepage(client):
    health = client.get("/api/v1/health").json()
    assert health["status"] == "ok"
    assert health["version"] == "0.3.0"
    home = client.get("/")
    assert home.status_code == 200
    assert "Rahgir" in home.text


def test_demo_workflow_share_export_and_what_if(client):
    case = DEMO_CASES[1]
    response = client.post("/api/v1/demo/plan?case_id=delhi-agra", json={
        "origin": case["origin"], "destination": case["destination"],
        "detour_budget_minutes": 90, "max_journey_minutes": 800, "max_stops": 3, "discovery_bias": 0.8,
    })
    assert response.status_code == 200, response.text
    assert response.json()["result"]["decision_policy"]["discovery_bias"] == 0.8
    trip_id = response.json()["trip_id"]
    result = response.json()["result"]

    # The custom route endpoint must call the same full via-point route and
    # matrix validator used by the selected optimizer alternatives.
    assert result["candidates"]
    custom = client.post(f"/api/v1/trips/{trip_id}/route-preview", json={
        "stop_ids": [result["candidates"][0]["id"]],
    })
    assert custom.status_code == 200, custom.text
    custom_result = custom.json()
    assert custom_result["provider"] == "SYNTHETIC DEMO"
    assert custom_result["constraints"]["provider_route_recheck_completed"] is True
    assert custom_result["constraints"]["stop_count"] == 1
    assert custom_result["status"] in {"confirmed_feasible", "constraints_not_met"}

    duplicate = client.post(f"/api/v1/trips/{trip_id}/route-preview", json={
        "stop_ids": [result["candidates"][0]["id"]] * 2,
    })
    assert duplicate.status_code == 422
    unknown = client.post(f"/api/v1/trips/{trip_id}/route-preview", json={"stop_ids": ["not-a-candidate"]})
    assert unknown.status_code == 422
    too_many = client.post(f"/api/v1/trips/{trip_id}/route-preview", json={
        "stop_ids": [item["id"] for item in result["candidates"][:5]],
    })
    assert too_many.status_code == 422

    trip = client.get(f"/api/v1/trips/{trip_id}")
    assert trip.status_code == 200
    assert trip.json()["result"]["mode"] == "synthetic_demo"

    share = client.post(f"/api/v1/trips/{trip_id}/share").json()
    token = share["token"]
    public = client.get(f"/api/v1/shared/{token}")
    assert public.status_code == 200
    assert public.json()["access"] == "read_only"

    pdf = client.get(f"/api/v1/trips/{trip_id}/export.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"

    from datetime import datetime, timedelta
    departure = (datetime.now().astimezone() + timedelta(days=2)).replace(second=0, microsecond=0).isoformat()
    what_if = client.post(f"/api/v1/trips/{trip_id}/what-if", json={"detour_budget_minutes": 0, "discovery_bias": 0.2, "departure_at": departure})
    assert what_if.status_code == 200, what_if.text
    assert what_if.json()["result"]["decision_policy"]["discovery_bias"] == 0.2
    assert what_if.json()["result"]["selected_alternative"]["metrics"]["additional_driving_minutes"] <= 1e-6
    assert any(x["estimated_arrival_at"] for x in what_if.json()["result"]["candidate_assessments"])

    revoked = client.delete(f"/api/v1/trips/{trip_id}/share/{token}")
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/shared/{token}").status_code == 404


def test_demo_requires_matching_endpoints(client):
    response = client.post("/api/v1/demo/plan?case_id=delhi-agra", json={"origin": "Mumbai", "destination": "Pune"})
    assert response.status_code == 422


def test_report_submission_and_moderation_require_evidence_and_admin(client):
    report = client.post("/api/v1/reports", json={
        "category": "road_damage", "description": "A large pothole is visible near the shoulder.",
        "latitude": 28.6, "longitude": 77.2,
    })
    assert report.status_code == 200
    report_id = report.json()["id"]
    unverified = client.get("/api/v1/reports").json()["reports"]
    assert any(x["id"] == report_id and x["status"] == "submitted" for x in unverified)
    assert client.post(f"/api/v1/reports/{report_id}/moderate", json={"status": "verified"}).status_code == 403


def test_report_verified_state_requires_evidence_url(client, monkeypatch):
    # Settings are immutable; replace the settings object in the module for this test.
    import app.main as main_module
    monkeypatch.setattr(main_module, "settings", replace(main_module.settings, admin_token="test-secret"))
    
    report = client.post("/api/v1/reports", json={
        "category": "flooding", "description": "Water is covering the left travel lane.",
        "latitude": 28.61, "longitude": 77.21,
    })
    assert report.status_code == 200
    rid = report.json()["id"]
    no_source = client.post(f"/api/v1/reports/{rid}/moderate", headers={"X-Admin-Token": "test-secret"}, json={"status": "verified"})
    assert no_source.status_code == 422


def test_possible_duplicate_report_is_flagged_without_auto_verification(client):
    payload = {
        "category": "obstruction",
        "description": "A fallen tree blocks the left side of the carriageway.",
        "latitude": 28.6000,
        "longitude": 77.2000,
    }
    first = client.post("/api/v1/reports", json=payload)
    second = client.post("/api/v1/reports", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["possible_duplicate"] is True
    assert second.json()["duplicate_of"] == first.json()["id"]
    assert second.json()["status"] == "submitted"


def test_live_provider_failure_is_not_replaced_with_synthetic_demo(client, monkeypatch):
    import app.main as main_module
    from app.services.providers import ProviderError

    async def unavailable(_request):
        raise ProviderError("routing", "test provider unavailable", status_code=503)

    monkeypatch.setattr(main_module, "_run_live_plan", unavailable)
    response = client.post("/api/v1/trips/plan", json={"origin": "Delhi", "destination": "Agra"})
    assert response.status_code == 502
    assert response.json()["detail"]["provider"] == "routing"
    assert "synthetic_demo" not in response.text


def test_health_reports_missing_live_provider_configuration(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "settings", replace(
        main_module.settings,
        geocoder_provider="disabled",
        routing_provider="osrm",
        overpass_url="https://overpass.example/api/interpreter",
    ))
    health = client.get("/api/v1/health").json()
    assert health["live_planning_ready"] is False
    assert health["planning_state"] == "configuration_missing"
    assert health["providers"]["geocoder"]["configured"] is False
    assert health["synthetic_walkthrough"] is True
