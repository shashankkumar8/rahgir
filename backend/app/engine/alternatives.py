from __future__ import annotations

from typing import Any


class AlternativeSelectionMixin:
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
