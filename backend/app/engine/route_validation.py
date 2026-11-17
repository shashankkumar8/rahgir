from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..schemas import PlanRequest
from ..services.providers import ProviderError
from .planner_utils import matrix_value
from .temporal import opening_status
from .vehicle_cost import estimate_energy_cost


IST = ZoneInfo("Asia/Kolkata")


def _departure(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=IST) if value.tzinfo is None else value


def _validate_matrix(matrix: dict[str, Any], size: int) -> tuple[list[list[Any]], list[list[Any]]]:
    durations, distances = matrix.get("durations"), matrix.get("distances")
    for name, value in (("duration", durations), ("distance", distances)):
        if not isinstance(value, list) or len(value) != size or any(not isinstance(row, list) or len(row) != size for row in value):
            raise ProviderError("routing matrix", f"provider returned an incomplete {name} matrix")
    return durations, distances


async def validate_route_sequence(
    providers: Any,
    coordinates: list[tuple[float, float]],
    stops: list[dict[str, Any]],
    request: PlanRequest,
    baseline_distance_m: float,
    baseline_duration_s: float,
) -> dict[str, Any]:
    """Re-route a complete candidate sequence and verify the traveller's hard limits."""
    if len(coordinates) != len(stops) + 2:
        raise ProviderError("route validation", "stop coordinates do not match the submitted itinerary")
    route = await providers.route(coordinates)
    matrix_result = await providers.matrix(coordinates)
    durations, distances = _validate_matrix(matrix_result, len(coordinates))
    try:
        route_distance_m = float(route["distance_m"])
        route_duration_s = float(route["duration_s"])
        geometry = route["geometry"]
        if not isinstance(geometry, list) or len(geometry) < 2:
            raise ValueError("route geometry is missing")
        if not (0 < route_distance_m < float("inf") and 0 < route_duration_s < float("inf")):
            raise ValueError("route metrics are invalid")
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError(route.get("provider", "routing"), "provider returned incomplete via-point route data") from exc

    elapsed_seconds = 0.0
    departure = _departure(request.departure_at)
    assessments = []
    warnings = []

    for index, stop in enumerate(stops, start=1):
        leg_seconds = matrix_value(durations, index - 1, index)
        leg_distance = matrix_value(distances, index - 1, index)
        if leg_seconds is None or leg_distance is None:
            raise ProviderError("routing matrix", f"missing road leg from waypoint {index - 1} to {index}")
        elapsed_seconds += leg_seconds
        arrival = departure + timedelta(seconds=elapsed_seconds) if departure else None
        hours = opening_status((stop.get("tags") or {}).get("opening_hours"), arrival)
        item = {
            "id": stop["id"],
            "name": stop["name"],
            "order": index,
            "arrival_at": arrival.isoformat() if arrival else None,
            "hours_status": hours,
        }
        if hours == "closed":
            warnings.append(f"{stop['name']} is marked closed at the estimated arrival time by supported OSM hours data.")
        elif hours == "unknown":
            warnings.append(f"Opening hours for {stop['name']} are unknown or use an unsupported format.")
        assessments.append(item)
        elapsed_seconds += request.stop_duration_minutes * 60

    final_index = len(coordinates) - 1
    final_seconds = matrix_value(durations, final_index - 1, final_index)
    final_distance = matrix_value(distances, final_index - 1, final_index)
    if final_seconds is None or final_distance is None:
        raise ProviderError("routing matrix", "missing final road leg to destination")
    route_distance_km = route_distance_m / 1000
    route_duration_minutes = route_duration_s / 60
    extra_drive_minutes = max(0.0, (route_duration_s - baseline_duration_s) / 60)
    extra_distance_km = max(0.0, (route_distance_m - baseline_distance_m) / 1000)
    total_minutes = route_duration_minutes + len(stops) * request.stop_duration_minutes
    detour_ok = extra_drive_minutes <= request.detour_budget_minutes + 1e-6
    total_time_ok = total_minutes <= request.max_journey_minutes + 1e-6
    stop_count_ok = len(stops) <= request.max_stops
    hours_ok = not any(item["hours_status"] == "closed" for item in assessments)
    feasible = detour_ok and total_time_ok and stop_count_ok and hours_ok

    return {
        "provider": route.get("provider"),
        "matrix_provider": matrix_result.get("provider"),
        "geometry": route.get("geometry"),
        "distance_km": round(route_distance_km, 2),
        "duration_minutes": round(route_duration_minutes, 1),
        "additional_driving_minutes": round(extra_drive_minutes, 1),
        "additional_distance_km": round(extra_distance_km, 2),
        "total_journey_minutes": round(total_minutes, 1),
        "stop_ids": [stop["id"] for stop in stops],
        "stop_assessments": assessments,
        "constraints": {
            "detour_budget_minutes": request.detour_budget_minutes,
            "detour_budget_respected": detour_ok,
            "max_journey_minutes": request.max_journey_minutes,
            "max_journey_time_respected": total_time_ok,
            "max_stops": request.max_stops,
            "stop_count": len(stops),
            "max_stops_respected": stop_count_ok,
            "known_closed_stops_excluded": hours_ok,
            "provider_route_recheck_completed": True,
        },
        "feasible": feasible,
        "status": "confirmed_feasible" if feasible else "constraints_not_met",
        "warnings": warnings,
        "vehicle_cost": estimate_energy_cost(route_distance_km, request),
        "verification": "Complete via-point route was recalculated by the configured routing provider; opening-hour states use only supported mapped rules.",
    }
