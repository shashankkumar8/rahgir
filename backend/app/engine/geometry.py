from __future__ import annotations

import math
from typing import Iterable

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between (lat, lon) pairs in metres."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def _local_xy(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    lat, lon = point
    lat0, lon0 = origin
    x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_RADIUS_M
    return x, y


def project_point_to_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    """Return (distance_m, fraction_on_segment), using a local tangent plane."""
    px, py = _local_xy(point, start)
    ex, ey = _local_xy(end, start)
    denom = ex * ex + ey * ey
    if denom <= 1e-9:
        return math.hypot(px, py), 0.0
    t = max(0.0, min(1.0, (px * ex + py * ey) / denom))
    return math.hypot(px - t * ex, py - t * ey), t


def point_to_polyline(point: tuple[float, float], line: Iterable[tuple[float, float]]) -> tuple[float, float]:
    """Return (minimum corridor distance in metres, progress fraction in [0,1])."""
    coords = list(line)
    if not coords:
        return math.inf, 0.0
    if len(coords) == 1:
        return haversine_m(point, coords[0]), 0.0
    lengths = [haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    total = sum(lengths)
    best_distance, best_progress = math.inf, 0.0
    traversed = 0.0
    for i, (start, end) in enumerate(zip(coords, coords[1:])):
        distance, fraction = project_point_to_segment(point, start, end)
        if distance < best_distance:
            best_distance = distance
            best_progress = (traversed + lengths[i] * fraction) / total if total else 0.0
        traversed += lengths[i]
    return best_distance, best_progress


def sample_polyline(line: Iterable[tuple[float, float]], max_samples: int = 12, spacing_m: float = 25_000) -> list[tuple[float, float]]:
    """Distance-based route samples, capped to avoid excessive Overpass queries."""
    coords = list(line)
    if not coords:
        return []
    if len(coords) == 1:
        return coords
    lengths = [haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    total = sum(lengths)
    count = max(2, min(max_samples, int(math.ceil(total / max(spacing_m, 1))) + 1))
    targets = [total * i / (count - 1) for i in range(count)]
    samples: list[tuple[float, float]] = []
    seg, walked = 0, 0.0
    for target in targets:
        while seg < len(lengths) - 1 and walked + lengths[seg] < target:
            walked += lengths[seg]
            seg += 1
        length = lengths[seg]
        frac = 0.0 if length == 0 else max(0.0, min(1.0, (target - walked) / length))
        a, b = coords[seg], coords[seg + 1]
        samples.append((a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac))
    return samples
