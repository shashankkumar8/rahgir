import math

from app.engine.geometry import haversine_m, point_to_polyline, sample_polyline


def test_haversine_same_point_is_zero():
    assert haversine_m((28.6139, 77.2090), (28.6139, 77.2090)) == 0


def test_haversine_delhi_agra_is_positive_and_reasonable():
    distance = haversine_m((28.6139, 77.2090), (27.1767, 78.0081))
    assert 150_000 < distance < 200_000


def test_point_to_polyline_progress_and_distance():
    line = [(0.0, 0.0), (0.0, 1.0)]
    distance, progress = point_to_polyline((0.01, 0.5), line)
    assert 900 < distance < 1200
    assert 0.45 < progress < 0.55


def test_empty_polyline_is_infinite_distance():
    distance, progress = point_to_polyline((1, 1), [])
    assert math.isinf(distance)
    assert progress == 0


def test_sample_polyline_caps_and_preserves_endpoints():
    line = [(0.0, i * 0.1) for i in range(21)]
    sampled = sample_polyline(line, max_samples=8, spacing_m=1)
    assert len(sampled) == 8
    assert sampled[0] == line[0]
    assert sampled[-1] == line[-1]


def test_antipodal_distance_remains_finite():
    distance = haversine_m((0, 0), (0, 180))
    assert math.isfinite(distance)
    assert 20_000_000 < distance < 20_100_000
