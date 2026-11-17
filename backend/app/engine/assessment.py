from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from .planner_utils import matrix_value
from .temporal import opening_status


class CandidateAssessmentMixin:
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
            outbound_s = matrix_value(durations, 0, matrix_index)
            inbound_s = matrix_value(durations, matrix_index, len(candidates) + 1)
            outbound_m = matrix_value(distances, 0, matrix_index)
            inbound_m = matrix_value(distances, matrix_index, len(candidates) + 1)
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
            "story_summary": poi.get("story_summary"),
            "wikipedia_url": poi.get("wikipedia_url"),
            "image_url": poi.get("image_url"),
            "image_attribution": poi.get("image_attribution"),
            "story_source": poi.get("story_source"),
        }
