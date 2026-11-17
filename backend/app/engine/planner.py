from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..schemas import PlanRequest
from ..services.providers import ExternalProviders, ProviderError
from .evidence import evidence_completeness, evidence_record
from .geometry import point_to_polyline
from .nsga2 import Individual, nsga2
from .temporal import opening_status


CATEGORY_KEY = {
    "heritage": "history", "historic": "history", "museum": "history", "castle": "history",
    "attraction": "culture", "gallery": "culture", "artwork": "culture", "place_of_worship": "religion",
    "restaurant": "food", "cafe": "food", "bakery": "food", "marketplace": "shopping", "craft": "shopping",
    "park": "nature", "garden": "nature", "nature_reserve": "nature", "viewpoint": "photography",
    "zoo": "nature", "theme_park": "adventure",
}


def classify_poi(tags: dict[str, Any]) -> tuple[str, str]:
    if tags.get("historic") or tags.get("heritage"):
        return "heritage", "history"
    if tags.get("tourism") in {"museum", "gallery"}:
        return str(tags["tourism"]), "history" if tags["tourism"] == "museum" else "culture"
    if tags.get("tourism") in {"attraction", "artwork"}:
        return str(tags["tourism"]), "culture"
    if tags.get("tourism") == "viewpoint":
        return "viewpoint", "photography"
    if tags.get("amenity") == "place_of_worship":
        return "place_of_worship", "religion"
    if tags.get("amenity") in {"restaurant", "cafe"}:
        return str(tags["amenity"]), "food"
    if tags.get("amenity") == "marketplace":
        return "marketplace", "shopping"
    if tags.get("craft"):
        return "craft", "shopping"
    if tags.get("leisure") in {"park", "garden", "nature_reserve"}:
        return str(tags["leisure"]), "nature"
    if tags.get("tourism"):
        return str(tags["tourism"]), "culture"
    return "local_place", "culture"


def cultural_value(category: str, tags: dict[str, Any]) -> float:
    base = {
        "heritage": 1.00, "museum": 0.95, "gallery": 0.78, "attraction": 0.82,
        "place_of_worship": 0.88, "craft": 0.86, "marketplace": 0.68,
        "viewpoint": 0.72, "park": 0.58, "garden": 0.62, "nature_reserve": 0.72,
        "restaurant": 0.60, "cafe": 0.48, "bakery": 0.50, "artwork": 0.65,
        "zoo": 0.55, "theme_park": 0.42, "local_place": 0.35,
    }.get(category, 0.35)
    # Tag completeness affects evidence quality separately, not claimed cultural truth.
    if tags.get("heritage") or tags.get("historic"):
        base = max(base, 0.92)
    return min(1.0, base)


def _matrix_value(matrix: list[list[float | None]], i: int, j: int) -> float | None:
    try:
        value = matrix[i][j]
        if value is None:
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) and numeric >= 0 else None
    except (IndexError, TypeError, ValueError):
        return None


class RoutePlanner:
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

        raw_pois = await self.providers.discover_pois(route_latlon, settings.corridor_radius_m)
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
        selected = next((a for a in alternatives if a["label"] == "Balanced"), alternatives[0] if alternatives else None)
        selected_geometry = None
        selected_route_provider = None
        if selected and selected["stops"]:
            waypoints = [origin_xy] + [(s["latitude"], s["longitude"]) for s in selected["stops"]] + [destination_xy]
            try:
                routed = await self.providers.route(waypoints)
                selected_geometry = routed["geometry"]
                selected_route_provider = routed["provider"]
                actual_additional_minutes = max(0.0, (float(routed["duration_s"]) - route_duration) / 60.0)
                actual_additional_km = max(0.0, (float(routed["distance_m"]) - route_distance) / 1000.0)
                actual_total_minutes = float(routed["duration_s"]) / 60.0 + len(selected["stops"]) * request.stop_duration_minutes
                selected["verified_route_distance_km"] = round(float(routed["distance_m"]) / 1000, 2)
                selected["verified_route_duration_minutes"] = round(float(routed["duration_s"]) / 60, 1)
                selected["metrics"]["additional_driving_minutes"] = round(actual_additional_minutes, 1)
                selected["metrics"]["additional_distance_km"] = round(actual_additional_km, 2)
                selected["metrics"]["estimated_total_minutes_including_stops"] = round(actual_total_minutes, 1)
                detour_ok = actual_additional_minutes <= request.detour_budget_minutes + 1e-6
                total_ok = actual_total_minutes <= request.max_journey_minutes + 1e-6
                selected["constraints"]["provider_route_recheck_completed"] = True
                selected["constraints"]["provider_route_detour_budget_respected"] = detour_ok
                selected["constraints"]["provider_route_total_time_respected"] = total_ok
                selected["constraints"]["detour_budget_respected"] = selected["constraints"]["detour_budget_respected"] and detour_ok
                selected["constraints"]["max_journey_time_respected"] = selected["constraints"]["max_journey_time_respected"] and total_ok
                selected["actual_route_feasible"] = detour_ok and total_ok
            except (ProviderError, KeyError, TypeError, ValueError) as exc:
                selected["selected_route_geometry_status"] = f"Unavailable or invalid: {exc}"
                selected["constraints"]["provider_route_recheck_completed"] = False
                selected["actual_route_feasible"] = None
        elif selected:
            selected_geometry = baseline["geometry"]
            selected_route_provider = baseline["provider"]
            selected["verified_route_distance_km"] = round(route_distance / 1000, 2)
            selected["verified_route_duration_minutes"] = round(route_duration / 60, 1)
            selected["constraints"]["provider_route_recheck_completed"] = True
            selected["constraints"]["provider_route_detour_budget_respected"] = True
            selected["constraints"]["provider_route_total_time_respected"] = route_duration / 60 <= request.max_journey_minutes + 1e-6
            selected["actual_route_feasible"] = route_duration / 60 <= request.max_journey_minutes + 1e-6

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
            "candidates": [self._public_poi(p) for p in candidates],
            "candidate_assessments": candidate_assessments,
            "decision_policy": {
                "name": "Pareto-persona selection",
                "discovery_bias": request.discovery_bias,
                "explanation": "The discovery dial selects a preference-conditioned option from the feasible non-dominated set. It does not replace Pareto optimization or relax hard constraints.",
            },
            "alternatives": alternatives,
            "selected_alternative": selected,
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

    def _assess_candidates(self, candidates, durations, distances, request, base_duration_s, base_distance_m):
        """Explain each mapped candidate using its directed road-matrix legs.

        These are single-stop feasibility checks. They are not a claim that all
        individually feasible places fit together in one itinerary.
        """
        frequency: dict[str, int] = {}
        for poi in candidates:
            frequency[poi["category"]] = frequency.get(poi["category"], 0) + 1
        max_rarity = max((1 / math.sqrt(v) for v in frequency.values()), default=1.0)
        departure = request.departure_at
        if departure is not None and departure.tzinfo is None:
            from zoneinfo import ZoneInfo
            departure = departure.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        assessments = []
        for index, poi in enumerate(candidates):
            matrix_index = index + 1
            outbound_s = _matrix_value(durations, 0, matrix_index)
            inbound_s = _matrix_value(durations, matrix_index, len(candidates) + 1)
            outbound_m = _matrix_value(distances, 0, matrix_index)
            inbound_m = _matrix_value(distances, matrix_index, len(candidates) + 1)
            reasons: list[str] = []
            caveats: list[str] = []
            if None in (outbound_s, inbound_s, outbound_m, inbound_m):
                reasons.append("The routing provider did not return both directed road legs for this place.")
                added_minutes = None
                total_minutes = None
                added_km = None
                arrival = None
                hours_status = "unknown"
            else:
                via_seconds = float(outbound_s) + float(inbound_s)
                via_meters = float(outbound_m) + float(inbound_m)
                added_minutes = round(max(0.0, (via_seconds - base_duration_s) / 60.0), 1)
                added_km = round(max(0.0, (via_meters - base_distance_m) / 1000.0), 2)
                total_minutes = round(via_seconds / 60.0 + request.stop_duration_minutes, 1)
                arrival = departure + timedelta(seconds=float(outbound_s)) if departure else None
                hours_status = opening_status(poi.get("tags", {}).get("opening_hours"), arrival)
                if added_minutes > request.detour_budget_minutes + 1e-6:
                    reasons.append(f"Single-stop detour is {added_minutes:.0f} min, above your {request.detour_budget_minutes} min budget.")
                if total_minutes > request.max_journey_minutes + 1e-6:
                    reasons.append(f"Trip with this stop is {total_minutes:.0f} min, above your {request.max_journey_minutes} min limit.")
                if hours_status == "closed":
                    reasons.append("Supported opening-hours data indicates it is closed at the estimated arrival time.")
                elif hours_status == "unknown":
                    caveats.append("Opening hours are unknown or unsupported; verify directly before visiting.")
            if request.max_stops == 0:
                reasons.append("Your current plan allows zero stops.")

            preference = float(getattr(request.preferences, poi["preference_key"], 0.5))
            rarity = ((1 / math.sqrt(frequency.get(poi["category"], 1))) / max_rarity) if max_rarity else 0.0
            if added_minutes is not None:
                why = [f"Adds about {added_minutes:.0f} min of driving versus the base route", f"About {poi['corridor_distance_m']:.0f} m from the road geometry"]
                if hours_status == "open":
                    why.append("Mapped opening-hours rule indicates open at the estimated arrival")
                if hours_status == "unknown":
                    why.append("Opening-hours status is unknown")
            else:
                why = ["Road-network feasibility could not be calculated"]
            assessments.append({
                **self._public_poi(poi),
                "individual_status": "blocked" if reasons else "eligible",
                "individual_reasons": reasons,
                "caveats": caveats,
                "single_stop_detour_minutes": added_minutes,
                "single_stop_detour_km": added_km,
                "single_stop_total_minutes": total_minutes,
                "estimated_arrival_at": arrival.isoformat() if arrival else None,
                "hours_status": hours_status,
                "preference_match_input": round(preference, 3),
                "corridor_rarity_proxy": round(rarity, 3),
                "why_it_might_fit": why,
            })
        return assessments

    def _optimise(self, candidates, durations, distances, request, base_duration_s, base_distance_m):
        n = len(candidates)
        if n == 0 or request.max_stops == 0:
            return [self._evaluate(tuple(0 for _ in range(n)), candidates, durations, distances, request, base_duration_s, base_distance_m)]

        category_frequency: dict[str, int] = {}
        for poi in candidates:
            category_frequency[poi["category"]] = category_frequency.get(poi["category"], 0) + 1
        max_rarity = max((1 / math.sqrt(v) for v in category_frequency.values()), default=1.0)
        cache: dict[tuple[int, ...], tuple[tuple[float, ...], dict[str, Any] | None]] = {}

        def evaluate(genes):
            if genes not in cache:
                result = self._evaluate(genes, candidates, durations, distances, request, base_duration_s, base_distance_m, category_frequency, max_rarity)
                cache[genes] = (result["objectives"], result)
            return cache[genes]

        front = nsga2(evaluate, n, settings.nsga_population, settings.nsga_generations, request.seed)
        results = []
        seen = set()
        for individual in front:
            if individual.genes in seen:
                continue
            seen.add(individual.genes)
            result = evaluate(individual.genes)[1]
            if result:
                results.append(result)
        # Preserve an empty route as a valid fallback if every non-empty route violates constraints.
        empty = tuple(0 for _ in range(n))
        if not results:
            results.append(evaluate(empty)[1])
        return results

    def _evaluate(self, genes, candidates, durations, distances, request, base_duration_s, base_distance_m, category_frequency=None, max_rarity=1.0):
        selected_indices = [i for i, bit in enumerate(genes) if bit]
        if len(selected_indices) > request.max_stops:
            return {"objectives": (1e6, 1e6, 1e6, 1e6, 1e6, 1e6), "feasible": False, "stops": []}
        # Route progression order is fixed to the road corridor to avoid backtracking and unstable permutations.
        selected_indices.sort(key=lambda i: (candidates[i]["route_progress"], candidates[i]["id"]))
        matrix_indices = [0] + [i + 1 for i in selected_indices] + [len(candidates) + 1]
        travel_s = 0.0
        travel_m = 0.0
        elapsed_s = 0.0
        prev = matrix_indices[0]
        stop_rows = []
        departure = request.departure_at
        if departure is not None and departure.tzinfo is None:
            # India-focused product: naive departure values are interpreted as IST.
            from zoneinfo import ZoneInfo
            departure = departure.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        for idx in selected_indices:
            matrix_idx = idx + 1
            leg_s = _matrix_value(durations, prev, matrix_idx)
            leg_m = _matrix_value(distances, prev, matrix_idx)
            if leg_s is None or leg_m is None:
                return {"objectives": (1e6, 1e6, 1e6, 1e6, 1e6, 1e6), "feasible": False, "stops": []}
            travel_s += leg_s
            travel_m += leg_m
            elapsed_s += leg_s
            poi = candidates[idx]
            arrival = departure + timedelta(seconds=elapsed_s) if departure else None
            hours = poi.get("tags", {}).get("opening_hours")
            hours_status = opening_status(hours, arrival)
            if hours_status == "closed":
                return {"objectives": (1e6, 1e6, 1e6, 1e6, 1e6, 1e6), "feasible": False, "stops": []}
            stop_rows.append({**poi, "hours_status": hours_status, "arrival_at": arrival.isoformat() if arrival else None, "stop_duration_minutes": request.stop_duration_minutes})
            elapsed_s += request.stop_duration_minutes * 60
            prev = matrix_idx
        final_s = _matrix_value(durations, prev, matrix_indices[-1])
        final_m = _matrix_value(distances, prev, matrix_indices[-1])
        if final_s is None or final_m is None:
            return {"objectives": (1e6, 1e6, 1e6, 1e6, 1e6, 1e6), "feasible": False, "stops": []}
        travel_s += final_s
        travel_m += final_m
        additional_minutes = max(0.0, (travel_s - base_duration_s) / 60)
        additional_km = max(0.0, (travel_m - base_distance_m) / 1000)
        total_minutes = travel_s / 60 + len(selected_indices) * request.stop_duration_minutes
        if additional_minutes > request.detour_budget_minutes + 1e-6 or total_minutes > request.max_journey_minutes + 1e-6:
            return {"objectives": (1e6, 1e6, 1e6, 1e6, 1e6, 1e6), "feasible": False, "stops": []}

        if not selected_indices:
            value = diversity = novelty = metadata = 0.0
        else:
            pref_values = []
            culture_values = []
            novelties = []
            meta_values = []
            for idx in selected_indices:
                poi = candidates[idx]
                pref_key = poi["preference_key"]
                pref_weight = getattr(request.preferences, pref_key, 0.5)
                if request.traveler_mode == "culture": pref_weight = max(pref_weight, request.preferences.culture)
                if request.traveler_mode == "food" and pref_key == "food": pref_weight = max(pref_weight, 0.95)
                if request.traveler_mode == "nature" and pref_key == "nature": pref_weight = max(pref_weight, 0.95)
                if request.traveler_mode == "explorer": pref_weight = max(pref_weight, 0.75)
                if request.traveler_mode == "family": pref_weight = max(pref_weight, 0.65)
                pref_values.append(float(pref_weight))
                culture_values.append(float(poi["cultural_value"]))
                freq = (category_frequency or {}).get(poi["category"], 1)
                novelties.append((1 / math.sqrt(freq)) / max_rarity if max_rarity else 0.0)
                meta_values.append(float(poi["metadata_completeness"]))
            value = sum(c * p for c, p in zip(culture_values, pref_values)) / len(selected_indices)
            diversity = len({candidates[i]["category"] for i in selected_indices}) / len(selected_indices)
            novelty = sum(novelties) / len(novelties)
            metadata = sum(meta_values) / len(meta_values)

        # All objectives are minimised. No single arbitrary weighted score drives Pareto selection.
        objectives = (-value, -diversity, -novelty, additional_minutes, additional_km, -metadata)
        weighted_display = 0.48 * value + 0.20 * diversity + 0.16 * novelty + 0.16 * metadata
        return {
            "objectives": objectives,
            "feasible": True,
            "stop_ids": [candidates[i]["id"] for i in selected_indices],
            "stops": stop_rows,
            "metrics": {
                "personalised_cultural_relevance": round(value, 4),
                "category_diversity": round(diversity, 4),
                "corridor_category_novelty_proxy": round(novelty, 4),
                "metadata_completeness": round(metadata, 4),
                "additional_driving_minutes": round(additional_minutes, 1),
                "additional_distance_km": round(additional_km, 2),
                "estimated_total_minutes_including_stops": round(total_minutes, 1),
                "display_utility_for_balanced_label_only": round(weighted_display, 4),
            },
            "constraints": {
                "detour_budget_minutes": request.detour_budget_minutes,
                "detour_budget_respected": additional_minutes <= request.detour_budget_minutes + 1e-6,
                "max_journey_minutes": request.max_journey_minutes,
                "max_journey_time_respected": total_minutes <= request.max_journey_minutes + 1e-6,
                "max_stops": request.max_stops,
                "max_stops_respected": len(selected_indices) <= request.max_stops,
                "closed_places_excluded": True,
            },
        }

    def _named_alternatives(self, solutions: list[dict[str, Any]], discovery_bias: float = 0.55) -> list[dict[str, Any]]:
        feasible = [x for x in solutions if x.get("feasible")]
        if not feasible:
            return []
        # Unique itineraries from the non-dominated set.
        by_key = {tuple(x.get("stop_ids", [])): x for x in feasible}
        pool = list(by_key.values())
        def choose(key, reverse=False):
            return sorted(pool, key=key, reverse=reverse)[0]
        fastest = choose(lambda x: (x["metrics"]["additional_driving_minutes"], len(x["stops"])))
        cultural = choose(lambda x: (x["metrics"]["personalised_cultural_relevance"], x["metrics"]["category_diversity"], -x["metrics"]["additional_driving_minutes"]), True)
        explorer = choose(lambda x: (x["metrics"]["corridor_category_novelty_proxy"], x["metrics"]["category_diversity"], -x["metrics"]["additional_driving_minutes"]), True)
        foodie_pool = [x for x in pool if any(stop.get("preference_key") == "food" for stop in x.get("stops", []))]
        foodie = sorted(foodie_pool or pool, key=lambda x: (sum(1 for stop in x.get("stops", []) if stop.get("preference_key") == "food"), x["metrics"]["personalised_cultural_relevance"], -x["metrics"]["additional_driving_minutes"]), reverse=True)[0]

        # The dial is a visible preference selector over the feasible Pareto set.
        # It never changes feasibility or the objective vector used by NSGA-II.
        def normalized(value, values, lower_is_better=False):
            lo, hi = min(values), max(values)
            if abs(hi - lo) < 1e-12:
                return 1.0
            scaled = (value - lo) / (hi - lo)
            return 1.0 - scaled if lower_is_better else scaled

        detours = [float(x["metrics"]["additional_driving_minutes"]) for x in pool]
        distances_km = [float(x["metrics"]["additional_distance_km"]) for x in pool]
        raw_discovery = []
        for x in pool:
            m = x["metrics"]
            raw_discovery.append(
                0.36 * float(m["personalised_cultural_relevance"])
                + 0.22 * float(m["category_diversity"])
                + 0.26 * float(m["corridor_category_novelty_proxy"])
                + 0.16 * float(m["metadata_completeness"])
            )
        discovery_scores = []
        for index, x in enumerate(pool):
            m = x["metrics"]
            # Normalize both sides over the current feasible frontier. This makes
            # the dial interpretable as a preference between two comparable 0..1
            # axes. A valid discovery option is not overwhelmed by a zero-detour
            # empty itinerary merely because the raw discovery score is < 1.
            discovery = normalized(raw_discovery[index], raw_discovery)
            efficiency = (0.50 * normalized(float(m["additional_driving_minutes"]), detours, True)
                          + 0.50 * normalized(float(m["additional_distance_km"]), distances_km, True))
            score = float(discovery_bias) * discovery + (1.0 - float(discovery_bias)) * efficiency
            discovery_scores.append((score, x))
        balanced = max(discovery_scores, key=lambda pair: (pair[0], -pair[1]["metrics"]["additional_driving_minutes"]))[1]
        selected: list[tuple[str, dict[str, Any]]] = []
        # Keep Balanced first so de-duplication never removes the canonical
        # default selection when it coincides with another persona result.
        for label, item in [("Balanced", balanced), ("Fastest", fastest), ("Culture-rich", cultural), ("Explorer", explorer), ("Food trail", foodie)]:
            if all(item["stop_ids"] != existing[1]["stop_ids"] for existing in selected):
                selected.append((label, item))
        # Return at least one route even when all persona selectors converge.
        if not selected:
            selected = [("Balanced", balanced)]
        out = []
        for label, item in selected:
            stops = []
            for idx, stop in enumerate(item["stops"], start=1):
                source_label = "synthetic demonstration fixture" if getattr(self.providers, "is_demo", False) else "OpenStreetMap"
                why = [f"Classified as {stop['category'].replace('_', ' ')} from {source_label} tags"]
                why.append(f"{stop['corridor_distance_m']:.0f} m from the computed road geometry")
                if stop.get("hours_status") == "unknown":
                    why.append("Opening hours unknown or unsupported format; verify before visiting")
                else:
                    why.append("Opening hours indicate open at estimated arrival under supported parser")
                stops.append({
                    "id": stop["id"], "name": stop["name"], "category": stop["category"],
                    "latitude": stop["latitude"], "longitude": stop["longitude"],
                    "source_url": stop.get("source_url") or "",
                    "tags": stop["tags"],
                    "corridor_distance_m": stop["corridor_distance_m"],
                    "arrival_at": stop["arrival_at"], "hours_status": stop["hours_status"],
                    "stop_duration_minutes": stop["stop_duration_minutes"],
                    "metadata_completeness": stop["metadata_completeness"],
                    "preference_key": stop.get("preference_key", "culture"),
                    "cultural_value_heuristic": stop.get("cultural_value", 0.0),
                    "explanation": why,
                })
            out.append({
                "label": label,
                "feasible": item["feasible"],
                "stops": stops,
                "metrics": item["metrics"],
                "constraints": item["constraints"],
                "objectives_minimised": list(item["objectives"]),
                "stop_ids": item["stop_ids"],
                "algorithm": "NSGA-II (binary stop selection; route order follows route-corridor progress)",
            })
        return out

    @staticmethod
    def _public_poi(poi: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": poi["id"], "name": poi["name"], "category": poi["category"],
            "latitude": poi["latitude"], "longitude": poi["longitude"],
            "source_url": poi.get("source_url") or "", "tags": poi["tags"],
            "corridor_distance_m": poi["corridor_distance_m"],
            "route_progress": round(poi["route_progress"], 6),
            "metadata_completeness": poi["metadata_completeness"],
            "cultural_value_heuristic": poi["cultural_value"],
        }
