from __future__ import annotations

from collections.abc import Iterable


CATEGORY_FILTERS = {
    "heritage": ['["historic"]', '["heritage"]'],
    "culture": ['["tourism"~"attraction|museum|gallery|viewpoint|artwork|zoo|theme_park"]'],
    "food": ['["amenity"~"restaurant|cafe|fast_food|food_court|ice_cream"]', '["shop"~"bakery|confectionery|deli"]'],
    "nature": ['["leisure"~"park|garden|nature_reserve"]'],
    "religion": ['["amenity"="place_of_worship"]'],
    "shopping": ['["craft"]', '["amenity"="marketplace"]', '["shop"~"market|craft"]'],
    "fuel": ['["amenity"="fuel"]'],
    "ev_charging": ['["amenity"="charging_station"]'],
    "restroom": ['["amenity"="toilets"]'],
    "medical": ['["amenity"~"hospital|clinic|doctors|pharmacy"]'],
    "vehicle_service": ['["shop"~"car_repair|tyres|car_parts"]', '["service:vehicle:repair"]'],
    "parking": ['["amenity"="parking"]'],
    "rest_area": ['["highway"~"rest_area|services"]'],
}


def build_overpass_query(samples: Iterable[tuple[float, float]], radius_m: int, categories: Iterable[str]) -> str:
    """Build a bounded corridor-only Overpass query with one selector per tag filter."""
    points = list(samples)
    if not points or len(points) > 12:
        raise ValueError("Route sampling must contain between 1 and 12 points")
    if radius_m < 100 or radius_m > 10_000:
        raise ValueError("Corridor radius must be between 100 and 10000 metres")
    selected = [category for category in dict.fromkeys(categories) if category in CATEGORY_FILTERS]
    filters = list(dict.fromkeys(filter_text for category in selected for filter_text in CATEGORY_FILTERS[category]))
    if not filters:
        raise ValueError("Select at least one supported place category")
    around_points = ",".join(f"{latitude:.5f},{longitude:.5f}" for latitude, longitude in points)
    clauses = [f"nwr(around:{int(radius_m)},{around_points}){filter_text};" for filter_text in filters]
    return "[out:json][timeout:25];(\n" + "\n".join(clauses) + "\n);out center tags;"
