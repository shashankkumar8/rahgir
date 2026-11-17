import pytest

from app.services.poi_query import build_overpass_query


def test_overpass_query_uses_bounded_multi_coordinate_corridor():
    query = build_overpass_query(
        [(28.61, 77.20), (28.20, 77.45), (27.90, 77.80)],
        2500,
        ["fuel", "ev_charging", "food"],
    )
    assert "[out:json][timeout:25]" in query
    assert "nwr(around:2500,28.61000,77.20000,28.20000,77.45000,27.90000,77.80000)" in query
    assert '["amenity"="fuel"]' in query
    assert '["amenity"="charging_station"]' in query
    assert '["amenity"~"restaurant|cafe|fast_food|food_court|ice_cream"]' in query
    assert query.count("nwr(") == 4


def test_overpass_query_rejects_unbounded_or_empty_requests():
    with pytest.raises(ValueError, match="between 1 and 12"):
        build_overpass_query([], 2500, ["fuel"])
    with pytest.raises(ValueError, match="between 100 and 10000"):
        build_overpass_query([(28.6, 77.2)], 50, ["fuel"])
    with pytest.raises(ValueError, match="at least one"):
        build_overpass_query([(28.6, 77.2)], 2500, ["not-a-category"])
