from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..schemas import PlanRequest
from ..services.providers import ExternalProviders, ProviderError
from .evidence import evidence_completeness, evidence_record
from .geometry import point_to_polyline
from .assessment import CandidateAssessmentMixin
from .optimization import ItineraryOptimizationMixin
from .alternatives import AlternativeSelectionMixin
from .planner_utils import classify_poi, cultural_value, matrix_value
from .vehicle_cost import estimate_energy_cost
from .route_validation import validate_route_sequence


class RoutePlanner(CandidateAssessmentMixin, ItineraryOptimizationMixin, AlternativeSelectionMixin):
    def __init__(self, providers: ExternalProviders):
        self.providers = providers

    @staticmethod
    def _valid_coordinate(point: tuple[float, float]) -> bool:
        lat, lon = point
        return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180

    @classmethod
    def _coordinate(cls, item: dict[str, Any], label: str) -> tuple[float, float]:
        try:
            point = (float(item["latitude"]), float(item["longitude"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("geocoder", f"{label} location response omitted valid coordinates") from exc
        if not cls._valid_coordinate(point):
            raise ProviderError("geocoder", f"{label} location response has invalid coordinates")
        return point

    async def plan(self, request: PlanRequest) -> dict[str, Any]:
        origin = await self.providers.geocode(request.origin)
        destination = await self.providers.geocode(request.destination)
        origin_xy = self._coordinate(origin, "origin")
        destination_xy = self._coordinate(destination, "destination")

        baseline = await self.providers.route([origin_xy, destination_xy])
        # Provider GeoJSON is [longitude, latitude]; internal geometry is (latitude, longitude).
        try:
            route_latlon = [(float(lat), float(lon)) for lon, lat in baseline["geometry"]]
            route_distance = float(baseline["distance_m"])
            route_duration = float(baseline["duration_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError(baseline.get("provider", "routing"), "provider returned malformed route metrics or geometry") from exc
        if len(route_latlon) < 2 or not all(self._valid_coordinate(p) for p in route_latlon):
            raise ProviderError(baseline["provider"], "provider returned invalid route geometry")
        if not math.isfinite(route_distance) or route_distance <= 0 or not math.isfinite(route_duration) or route_duration <= 0:
            raise ProviderError(baseline["provider"], "provider returned invalid route distance/duration")

        raw_pois = await self.providers.discover_pois(route_latlon, settings.corridor_radius_m, request.poi_categories)
        filtered: list[dict[str, Any]] = []
        for raw in raw_pois:
            if not isinstance(raw, dict):
                continue
            try:
                point = (float(raw["latitude"]), float(raw["longitude"]))
            except (KeyError, TypeError, ValueError):
                continue
            if not self._valid_coordinate(point):
                continue
            corridor_distance, progress = point_to_polyline(point, route_latlon)
            if corridor_distance > settings.corridor_radius_m:
                continue
            tags = raw.get("tags") if isinstance(raw.get("tags"), dict) else {}
            category, preference_key = classify_poi(tags)
            enriched = {
                **raw,
                "category": category,
                "preference_key": preference_key,
                "corridor_distance_m": round(corridor_distance, 1),
                "route_progress": progress,
                "name": str(raw.get("name") or "Unnamed mapped place")[:240],
                "tags": tags,
                "cultural_value": cultural_value(category, tags),
                "metadata_completeness": evidence_completeness(tags),
            }
            if not enriched.get("id"):
                continue
            filtered.append(enriched)
        # Prefer documented, close-corridor, culturally relevant mapped entries without asserting popularity.
        filtered.sort(key=lambda p: (-p["cultural_value"], -p["metadata_completeness"], p["corridor_distance_m"], p["id"]))
        candidates = filtered[: settings.max_pois]
        candidates.sort(key=lambda p: (p["route_progress"], p["id"]))
        # Optional article and thumbnail enrichment is strictly linked by an OSM
        # wikipedia tag; it never guesses an article from a place name.
        if candidates and hasattr(self.providers, "enrich_pois"):
            try:
                candidates = await self.providers.enrich_pois(candidates)
            except Exception:
                # Enrichment is additive only. A media/context outage cannot block
                # route calculation or change feasibility and ranking.
                pass

        coords = [origin_xy] + [(p["latitude"], p["longitude"]) for p in candidates] + [destination_xy]
        matrix_result = await self.providers.matrix(coords) if candidates else {
            "durations": [[route_duration, route_duration], [route_duration, route_duration]],
            "distances": [[route_distance, route_distance], [route_distance, route_distance]],
            "provider": baseline["provider"],
        }
        durations = matrix_result.get("durations")
        distances = matrix_result.get("distances")
        expected_size = len(candidates) + 2
        if not isinstance(durations, list) or len(durations) != expected_size or not isinstance(distances, list) or len(distances) != expected_size:
            raise ProviderError(matrix_result.get("provider", "routing matrix"), "incomplete road-network matrix")
        for row in durations:
            if not isinstance(row, list) or len(row) != expected_size:
                raise ProviderError(matrix_result.get("provider", "routing matrix"), "non-square duration matrix")
        for row in distances:
            if not isinstance(row, list) or len(row) != expected_size:
                raise ProviderError(matrix_result.get("provider", "routing matrix"), "non-square distance matrix")

        candidate_assessments = self._assess_candidates(candidates, durations, distances, request, route_duration, route_distance)
        solutions = self._optimise(candidates, durations, distances, request, route_duration, route_distance)
        alternatives = self._named_alternatives(solutions, request.discovery_bias)
        for alternative in alternatives:
            alternative["base_route_distance_km"] = round(route_distance / 1000, 2)
            alternative["vehicle_cost"] = estimate_energy_cost(float(alternative["metrics"].get("total_route_distance_km", route_distance / 1000)), request)
            alternative["actual_route_feasible"] = None
            alternative["route_validation_status"] = "not_checked"

        selected = None
        selected_geometry = None
        selected_route_provider = None
        validation_errors: list[str] = []
        checked_options = 0
        # Provider recheck is decisive: matrix-feasible plans are not called
        # feasible until the complete via-point route also respects hard limits.
        for alternative in alternatives[:3]:
            checked_options += 1
            stops = alternative["stops"]
            if not stops:
                actual_total_minutes = route_duration / 60
                feasible = actual_total_minutes <= request.max_journey_minutes + 1e-6
                alternative["verified_route_distance_km"] = round(route_distance / 1000, 2)
                alternative["vehicle_cost"] = estimate_energy_cost(route_distance / 1000, request)
                alternative["verified_route_duration_minutes"] = round(actual_total_minutes, 1)
                alternative["actual_route_feasible"] = feasible
                alternative["route_validation_status"] = "confirmed_feasible" if feasible else "constraints_not_met"
                alternative["constraints"].update({
                    "provider_route_recheck_completed": True,
                    "provider_route_detour_budget_respected": True,
                    "provider_route_total_time_respected": feasible,
                    "detour_budget_respected": True,
                    "max_journey_time_respected": feasible,
                })
                if feasible:
                    selected = alternative
                    selected_geometry = baseline["geometry"]
                    selected_route_provider = baseline["provider"]
                    break
                continue
            waypoints = [origin_xy] + [(stop["latitude"], stop["longitude"]) for stop in stops] + [destination_xy]
            try:
                validation = await validate_route_sequence(
                    self.providers, waypoints, stops, request, route_distance, route_duration,
                )
                alternative["route_validation"] = validation
                alternative["verified_route_distance_km"] = validation["distance_km"]
                alternative["verified_route_duration_minutes"] = validation["duration_minutes"]
                alternative["vehicle_cost"] = validation["vehicle_cost"]
                alternative["metrics"]["additional_driving_minutes"] = validation["additional_driving_minutes"]
                alternative["metrics"]["additional_distance_km"] = validation["additional_distance_km"]
                alternative["metrics"]["estimated_total_minutes_including_stops"] = validation["total_journey_minutes"]
                alternative["constraints"].update(validation["constraints"])
                alternative["actual_route_feasible"] = validation["feasible"]
                alternative["route_validation_status"] = validation["status"]
                if validation["feasible"]:
                    for stop, assessment in zip(alternative["stops"], validation["stop_assessments"]):
                        stop["arrival_at"] = assessment["arrival_at"]
                        stop["hours_status"] = assessment["hours_status"]
                    selected = alternative
                    selected_geometry = validation["geometry"]
                    selected_route_provider = validation["provider"]
                    break
                validation_errors.append(f"{alternative['label']}: selected stops exceed one or more hard limits")
            except (ProviderError, KeyError, TypeError, ValueError) as exc:
                alternative["route_validation_status"] = "unverified_provider_error"
                alternative["route_validation_error"] = str(exc)
                alternative["constraints"]["provider_route_recheck_completed"] = False
                validation_errors.append(f"{alternative['label']}: {exc}")

        is_demo = bool(getattr(self.providers, "is_demo", False))
        if is_demo:
            sources = [evidence_record("Synthetic demonstration fixtures", "fixture://rahgir/synthetic-demo-not-real-world-data", license_name="Test fixture")]
        else:
            sources = [
                evidence_record("OpenStreetMap", "https://www.openstreetmap.org/copyright"),
                evidence_record("OSRM" if baseline["provider"] == "OSRM" else baseline["provider"], "https://project-osrm.org/docs/" if baseline["provider"] == "OSRM" else "https://openrouteservice.org/"),
                evidence_record("Nominatim", "https://operations.osmfoundation.org/policies/nominatim/"),
                evidence_record("Overpass API", "https://wiki.openstreetmap.org/wiki/Overpass_API"),
            ]
        return {
            "mode": "synthetic_demo" if is_demo else "live",
            "origin": origin,
            "destination": destination,
            "route": {
                "provider": baseline["provider"],
                "distance_km": round(route_distance / 1000, 2),
                "duration_minutes": round(route_duration / 60, 1),
                "geometry": baseline["geometry"],
                "selected_geometry": selected_geometry,
                "selected_geometry_provider": selected_route_provider,
                "geometry_format": "GeoJSON coordinates [longitude, latitude]",
                "note": "Road-network geometry returned by the configured provider; never a straight-line route.",
            },
            "candidate_count": len(candidates),
            "selected_poi_categories": list(request.poi_categories),
            "vehicle_cost_baseline": estimate_energy_cost(route_distance / 1000, request),
            "candidates": [self._public_poi(p) for p in candidates],
            "candidate_assessments": candidate_assessments,
            "decision_policy": {
                "name": "Pareto-persona selection",
                "discovery_bias": request.discovery_bias,
                "explanation": "The discovery dial selects a preference-conditioned option from the feasible non-dominated set. It does not replace Pareto optimization or relax hard constraints.",
            },
            "alternatives": alternatives,
            "selected_alternative": selected,
            "route_validation_summary": {
                "status": "confirmed_feasible" if selected else "no_confirmed_option",
                "checked_options": checked_options,
                "message": "The selected option passed a complete provider via-point route check." if selected else "No option passed the final via-point route check. Review provider/constraint warnings or try a different budget.",
                "warnings": validation_errors,
            },
            "safety": {"status": "insufficient_evidence", "label": "Insufficient safety data", "explanation": "No authoritative, segment-level safety dataset is currently connected. OSM POIs and community reports are not a road-safety ground truth."},
            "weather": {"status": "not_integrated_in_this_build", "label": "Weather not used in ranking", "explanation": "No forecast has been fetched; recommendations are not weather-adjusted."},
            "sources": sources,
            "data_integrity": {
                "poi_source": "Synthetic demo fixtures" if is_demo else "OpenStreetMap Overpass API",
                "poi_license": "Test fixture; not real POI data" if is_demo else "ODbL; see OpenStreetMap attribution",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "candidate_filter": f"within {settings.corridor_radius_m} metres of provider road geometry",
                "novelty_definition": "Rarity of a category within this retrieved corridor candidate set; not a global popularity or hidden-gem truth label.",
                "evidence_score_definition": "Completeness of mapped metadata; not factual confidence.",
            },
            "limitations": ([
                "DEMO ONLY: line geometry, road costs, and POIs are synthetic and must not be used for navigation, field research, safety decisions, or paper results.",
                "The city-centre coordinates are illustrative starting points; this is not a real route for the named city pair.",
            ] if is_demo else [
                "Public OSM/OSRM services are best-effort and subject to their usage policies; switch to hosted/self-hosted providers for production scale.",
                "Mapped POI coverage and opening hours vary by location; missing fields are displayed as unknown.",
                "Safety scoring is intentionally withheld without validated road-segment ground truth.",
                "This build does not claim field validation or independently verified cultural descriptions.",
            ]),
        }
