import asyncio

import pytest

from app.engine.planner import RoutePlanner
from app.schemas import PlanRequest
from app.services.demo import DEMO_CASES, DemoProviders


@pytest.mark.parametrize("case", DEMO_CASES, ids=lambda c: c["id"])
def test_all_indian_demo_pairs_produce_explicit_synthetic_itineraries(case):
    req = PlanRequest(origin=case["origin"], destination=case["destination"], detour_budget_minutes=90, max_journey_minutes=900, max_stops=3)
    result = asyncio.run(RoutePlanner(DemoProviders(case)).plan(req))
    assert result["mode"] == "synthetic_demo"
    assert result["route"]["provider"] == "SYNTHETIC DEMO"
    assert result["candidate_count"] > 0
    assert result["safety"]["status"] == "insufficient_evidence"
    assert "DEMO ONLY" in " ".join(result["limitations"])
    for alternative in result["alternatives"]:
        assert alternative["constraints"]["detour_budget_respected"]
        assert alternative["constraints"]["max_journey_time_respected"]


def test_tight_budget_returns_feasible_empty_route_instead_of_violating_budget():
    case = DEMO_CASES[1]
    req = PlanRequest(origin=case["origin"], destination=case["destination"], detour_budget_minutes=0, max_journey_minutes=600, max_stops=4)
    result = asyncio.run(RoutePlanner(DemoProviders(case)).plan(req))
    assert result["selected_alternative"] is not None
    assert result["selected_alternative"]["metrics"]["additional_driving_minutes"] <= 1e-6


def test_demo_does_not_claim_osm_sources():
    case = DEMO_CASES[0]
    req = PlanRequest(origin=case["origin"], destination=case["destination"])
    result = asyncio.run(RoutePlanner(DemoProviders(case)).plan(req))
    assert result["data_integrity"]["poi_source"] == "Synthetic demo fixtures"
    assert all(source["source"] != "OpenStreetMap" for source in result["sources"])


class ProviderWithMalformedPOIs:
    is_demo = False

    async def geocode(self, query):
        return {
            "label": query,
            "latitude": 28.6 if query == "Delhi" else 28.6,
            "longitude": 77.2 if query == "Delhi" else 77.3,
            "source": "Test fixture",
            "retrieved_at": "2026-11-17T00:00:00Z",
        }

    async def route(self, coordinates):
        if len(coordinates) == 2:
            return {"distance_m": 50000, "duration_s": 3600, "geometry": [[77.2, 28.6], [77.3, 28.6]], "provider": "TEST ROUTER"}
        return {"distance_m": 52000, "duration_s": 4000, "geometry": [[77.2, 28.6], [77.25, 28.6], [77.3, 28.6]], "provider": "TEST ROUTER"}

    async def discover_pois(self, route, radius, categories=None):
        return [
            {"id": "osm/node/1", "name": "On-route heritage", "latitude": 28.6, "longitude": 77.25, "tags": {"historic": "monument", "name": "On-route heritage"}, "source_url": "https://www.openstreetmap.org/node/1"},
            {"id": "osm/node/2", "name": "Far away", "latitude": 29.5, "longitude": 77.25, "tags": {"historic": "monument"}, "source_url": "https://www.openstreetmap.org/node/2"},
            {"id": "osm/node/3", "name": "Invalid coordinate", "latitude": 1000, "longitude": 77.2, "tags": {}, "source_url": "https://www.openstreetmap.org/node/3"},
            {"name": "Missing id", "latitude": 28.6, "longitude": 77.25, "tags": {}, "source_url": "https://example.org"},
        ]

    async def matrix(self, coordinates):
        return {
            "durations": [[0, 2000, 3600], [2000, 0, 2000], [3600, 2000, 0]],
            "distances": [[0, 26000, 50000], [26000, 0, 26000], [50000, 26000, 0]],
            "provider": "TEST ROUTER",
        }


def test_planner_filters_far_invalid_and_unidentified_places_and_rechecks_route(monkeypatch):
    import app.engine.planner as planner_module
    from dataclasses import replace

    monkeypatch.setattr(planner_module, "settings", replace(planner_module.settings, max_pois=10, corridor_radius_m=2500))
    request = PlanRequest(origin="Delhi", destination="Agra", detour_budget_minutes=30, max_journey_minutes=120, max_stops=2)
    result = asyncio.run(RoutePlanner(ProviderWithMalformedPOIs()).plan(request))
    assert result["candidate_count"] == 1
    selected = result["selected_alternative"]
    assert selected is not None
    assert selected["constraints"]["provider_route_recheck_completed"] is True
    assert selected["verified_route_duration_minutes"] == pytest.approx(66.7, abs=0.1)


def test_invalid_geocoder_coordinate_is_rejected():
    class BadGeocoder(ProviderWithMalformedPOIs):
        async def geocode(self, query):
            return {"label": query, "latitude": float("nan"), "longitude": 77.2}

    request = PlanRequest(origin="Delhi", destination="Agra")
    with pytest.raises(Exception, match="invalid coordinates"):
        asyncio.run(RoutePlanner(BadGeocoder()).plan(request))


def test_discovery_bias_changes_selected_pareto_persona_without_changing_feasibility():
    case = DEMO_CASES[1]
    common = dict(
        origin=case["origin"], destination=case["destination"],
        detour_budget_minutes=120, max_journey_minutes=600, max_stops=4, seed=42,
    )
    efficiency = asyncio.run(RoutePlanner(DemoProviders(case)).plan(PlanRequest(**common, discovery_bias=0.0)))
    discovery = asyncio.run(RoutePlanner(DemoProviders(case)).plan(PlanRequest(**common, discovery_bias=1.0)))
    assert efficiency["decision_policy"]["discovery_bias"] == 0.0
    assert discovery["decision_policy"]["discovery_bias"] == 1.0
    assert efficiency["selected_alternative"]["stop_ids"] != discovery["selected_alternative"]["stop_ids"]
    for result in (efficiency, discovery):
        assert result["selected_alternative"]["constraints"]["detour_budget_respected"] is True
        assert result["selected_alternative"]["constraints"]["max_journey_time_respected"] is True


def test_complete_route_validation_applies_cumulative_extra_driving_and_stop_time():
    from app.engine.route_validation import validate_route_sequence

    class SequenceProvider:
        async def route(self, coordinates):
            return {
                "distance_m": 130_000,
                "duration_s": 6_000,
                "geometry": [[77.2, 28.6], [77.4, 28.4], [77.6, 28.2]],
                "provider": "TEST ROUTER",
            }

        async def matrix(self, coordinates):
            return {
                "durations": [
                    [0, 1800, 3600, 6000],
                    [1800, 0, 1800, 4200],
                    [3600, 1800, 0, 2400],
                    [6000, 4200, 2400, 0],
                ],
                "distances": [
                    [0, 25_000, 50_000, 100_000],
                    [25_000, 0, 25_000, 75_000],
                    [50_000, 25_000, 0, 50_000],
                    [100_000, 75_000, 50_000, 0],
                ],
                "provider": "TEST MATRIX",
            }

    request = PlanRequest(
        origin="Delhi", destination="Agra", detour_budget_minutes=35,
        max_journey_minutes=150, max_stops=2, stop_duration_minutes=20,
    )
    stops = [
        {"id": "p1", "name": "Stop 1", "tags": {}, "latitude": 28.5, "longitude": 77.3},
        {"id": "p2", "name": "Stop 2", "tags": {}, "latitude": 28.4, "longitude": 77.4},
    ]
    result = asyncio.run(validate_route_sequence(
        SequenceProvider(), [(28.6, 77.2), (28.5, 77.3), (28.4, 77.4), (27.2, 78.0)],
        stops, request, baseline_distance_m=100_000, baseline_duration_s=3_600,
    ))
    assert result["additional_driving_minutes"] == pytest.approx(40)
    assert result["total_journey_minutes"] == pytest.approx(140)
    assert result["constraints"]["detour_budget_respected"] is False
    assert result["constraints"]["max_journey_time_respected"] is True
    assert result["constraints"]["stop_count"] == 2
    assert result["constraints"]["max_stops_respected"] is True
    assert result["feasible"] is False
    assert result["status"] == "constraints_not_met"
