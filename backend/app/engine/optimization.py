from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from ..config import settings
from .nsga2 import nsga2
from .planner_utils import matrix_value
from .temporal import opening_status


class ItineraryOptimizationMixin:
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
            leg_s = matrix_value(durations, prev, matrix_idx)
            leg_m = matrix_value(distances, prev, matrix_idx)
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
        final_s = matrix_value(durations, prev, matrix_indices[-1])
        final_m = matrix_value(distances, prev, matrix_indices[-1])
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
                "total_route_distance_km": round(travel_m / 1000, 2),
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
