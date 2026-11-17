from __future__ import annotations

import math
from typing import Any


def classify_poi(tags: dict[str, Any]) -> tuple[str, str]:
    """Map OSM tags to the product's fixed, user-visible stop categories."""
    amenity = str(tags.get("amenity") or "").casefold()
    tourism = str(tags.get("tourism") or "").casefold()
    leisure = str(tags.get("leisure") or "").casefold()
    shop = str(tags.get("shop") or "").casefold()
    highway = str(tags.get("highway") or "").casefold()

    if tags.get("historic") or tags.get("heritage"):
        return "heritage", "history"
    if tourism in {"museum", "gallery", "attraction", "artwork", "viewpoint", "zoo", "theme_park"}:
        return "culture", "culture"
    if amenity in {"restaurant", "cafe", "fast_food", "food_court", "ice_cream"} or shop in {"bakery", "confectionery", "deli"}:
        return "food", "food"
    if amenity == "place_of_worship":
        return "religion", "religion"
    if leisure in {"park", "garden", "nature_reserve"}:
        return "nature", "nature"
    if amenity == "fuel":
        return "fuel", "vehicle"
    if amenity == "charging_station":
        return "ev_charging", "vehicle"
    if amenity == "toilets":
        return "restroom", "facilities"
    if amenity in {"hospital", "clinic", "doctors", "pharmacy"}:
        return "medical", "facilities"
    if shop in {"car_repair", "tyres", "car_parts"} or tags.get("service:vehicle:repair"):
        return "vehicle_service", "vehicle"
    if amenity == "parking":
        return "parking", "facilities"
    if highway in {"rest_area", "services"} or tags.get("highway") == "services":
        return "rest_area", "facilities"
    if tags.get("craft") or amenity == "marketplace" or shop in {"market", "craft"}:
        return "shopping", "shopping"
    return "other", "culture"



def cultural_value(category: str, tags: dict[str, Any]) -> float:
    base = {
        "heritage": 1.00, "museum": 0.95, "gallery": 0.78, "attraction": 0.82,
        "place_of_worship": 0.88, "craft": 0.86, "marketplace": 0.68,
        "viewpoint": 0.72, "park": 0.58, "garden": 0.62, "nature_reserve": 0.72,
        "restaurant": 0.60, "cafe": 0.48, "bakery": 0.50, "artwork": 0.65,
        "zoo": 0.55, "theme_park": 0.42, "fuel": 0.20, "ev_charging": 0.22,
        "restroom": 0.18, "medical": 0.20, "vehicle_service": 0.18,
        "parking": 0.16, "rest_area": 0.25, "shopping": 0.52, "culture": 0.65,
        "nature": 0.58, "religion": 0.72, "local_place": 0.35,
    }.get(category, 0.35)
    # Tag completeness affects evidence quality separately, not claimed cultural truth.
    if tags.get("heritage") or tags.get("historic"):
        base = max(base, 0.92)
    return min(1.0, base)


def matrix_value(matrix: list[list[float | None]], i: int, j: int) -> float | None:
    try:
        value = matrix[i][j]
        if value is None:
            return None
        numeric = float(value)
        return numeric if math.isfinite(numeric) and numeric >= 0 else None
    except (IndexError, TypeError, ValueError):
        return None
