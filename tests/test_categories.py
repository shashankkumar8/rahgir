import pytest

from app.engine.planner_utils import classify_poi


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"amenity": "fuel"}, "fuel"),
        ({"amenity": "charging_station"}, "ev_charging"),
        ({"amenity": "toilets"}, "restroom"),
        ({"amenity": "hospital"}, "medical"),
        ({"shop": "car_repair"}, "vehicle_service"),
        ({"amenity": "parking"}, "parking"),
        ({"highway": "rest_area"}, "rest_area"),
        ({"amenity": "restaurant"}, "food"),
        ({"historic": "monument"}, "heritage"),
    ],
)
def test_osm_category_mapping_supports_travel_practicalities(tags, expected):
    category, _ = classify_poi(tags)
    assert category == expected
