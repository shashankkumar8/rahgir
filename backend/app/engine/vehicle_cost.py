from __future__ import annotations

from typing import Any

from ..schemas import PlanRequest


ENERGY_UNIT = {
    "petrol": "litre",
    "diesel": "litre",
    "cng": "kg",
    "electric": "kWh",
}


def estimate_energy_cost(distance_km: float, request: PlanRequest) -> dict[str, Any]:
    """Estimate energy use only from explicit traveller-entered consumption and price."""
    vehicle = request.vehicle_type
    if vehicle == "not_set":
        return {"status": "not_configured", "label": "Vehicle cost not configured"}

    consumption = request.consumption_per_100km
    unit_price = request.energy_price_per_unit
    if consumption is None or unit_price is None or consumption <= 0 or unit_price <= 0:
        return {"status": "invalid_configuration", "label": "Add valid efficiency and unit price"}

    units = max(0.0, float(distance_km)) * float(consumption) / 100.0
    cost = units * float(unit_price)
    unit = ENERGY_UNIT[vehicle]
    return {
        "status": "estimated",
        "vehicle_type": vehicle,
        "distance_km": round(max(0.0, float(distance_km)), 2),
        "consumption_per_100km": float(consumption),
        "unit": unit,
        "estimated_units": round(units, 3),
        "unit_price": float(unit_price),
        "estimated_cost_inr": round(cost, 2),
        "method": f"distance_km × consumption_per_100km ÷ 100 × user_entered_price_per_{unit}",
        "source": "Traveller-entered vehicle efficiency and energy price; not a live price feed.",
    }


def add_vehicle_cost_to_alternative(alternative: dict[str, Any], request: PlanRequest) -> dict[str, Any]:
    metrics = alternative.get("metrics") or {}
    distance = alternative.get("verified_route_distance_km")
    if distance is None:
        # Use the matrix-estimated total road distance where an actual recheck is unavailable.
        distance = metrics.get("total_route_distance_km")
    if distance is None:
        distance = alternative.get("base_route_distance_km")
    alternative["vehicle_cost"] = estimate_energy_cost(float(distance or 0), request)
    return alternative
