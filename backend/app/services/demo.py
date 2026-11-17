from __future__ import annotations

from datetime import datetime, timezone

from ..engine.geometry import haversine_m

DEMO_CASES = [
    {"id": "ghaziabad-etawah", "origin": "Ghaziabad", "destination": "Etawah", "origin_coordinate": (28.6692, 77.4538), "destination_coordinate": (26.7773, 79.0239), "region": "Uttar Pradesh"},
    {"id": "delhi-agra", "origin": "Delhi", "destination": "Agra", "origin_coordinate": (28.6139, 77.2090), "destination_coordinate": (27.1767, 78.0081), "region": "Delhi / Uttar Pradesh"},
    {"id": "delhi-jaipur", "origin": "Delhi", "destination": "Jaipur", "origin_coordinate": (28.6139, 77.2090), "destination_coordinate": (26.9124, 75.7873), "region": "Delhi / Rajasthan"},
    {"id": "delhi-mathura", "origin": "Delhi", "destination": "Mathura", "origin_coordinate": (28.6139, 77.2090), "destination_coordinate": (27.4924, 77.6737), "region": "Delhi / Uttar Pradesh"},
    {"id": "mumbai-pune", "origin": "Mumbai", "destination": "Pune", "origin_coordinate": (19.0760, 72.8777), "destination_coordinate": (18.5204, 73.8567), "region": "Maharashtra"},
]

DEMO_TYPES = [
    ("heritage", {"historic": "monument", "heritage": "2", "name": "Illustrative heritage place"}),
    ("museum", {"tourism": "museum", "name": "Illustrative local museum"}),
    ("place_of_worship", {"amenity": "place_of_worship", "name": "Illustrative place of worship"}),
    ("craft", {"craft": "traditional", "name": "Illustrative craft workshop"}),
    ("restaurant", {"amenity": "restaurant", "name": "Illustrative regional food stop"}),
    ("viewpoint", {"tourism": "viewpoint", "name": "Illustrative viewpoint"}),
    ("park", {"leisure": "park", "name": "Illustrative green space"}),
    ("marketplace", {"amenity": "marketplace", "name": "Illustrative local market"}),
    ("fuel", {"amenity": "fuel", "name": "Illustrative fuel stop"}),
    ("ev_charging", {"amenity": "charging_station", "name": "Illustrative EV charger"}),
    ("restroom", {"amenity": "toilets", "name": "Illustrative public restroom"}),
    ("medical", {"amenity": "clinic", "name": "Illustrative clinic"}),
    ("vehicle_service", {"shop": "car_repair", "name": "Illustrative vehicle repair"}),
    ("parking", {"amenity": "parking", "name": "Illustrative parking area"}),
    ("rest_area", {"highway": "rest_area", "name": "Illustrative highway rest area"}),
]


def get_demo_case(case_id: str) -> dict:
    for case in DEMO_CASES:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


class DemoProviders:
    """Synthetic provider for product walkthroughs and deterministic tests only."""
    is_demo = True

    def __init__(self, case: dict):
        self.case = case
        self.origin = case["origin_coordinate"]
        self.destination = case["destination_coordinate"]
        self._pois = self._make_pois()

    async def geocode(self, query: str):
        if query.casefold() == self.case["origin"].casefold():
            lat, lon = self.origin
        elif query.casefold() == self.case["destination"].casefold():
            lat, lon = self.destination
        else:
            raise ValueError(f"Unknown demo endpoint {query}")
        return {"label": f"{query} (illustrative city-centre coordinate)", "latitude": lat, "longitude": lon, "source": "Synthetic demo fixture", "retrieved_at": datetime.now(timezone.utc).isoformat()}

    def _line(self, points, steps=30):
        coords = []
        for a, b in zip(points, points[1:]):
            for i in range(steps):
                t = i / steps
                coords.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        coords.append(points[-1])
        return coords

    async def route(self, coordinates):
        polyline = self._line(coordinates)
        distance = sum(haversine_m(a, b) for a, b in zip(coordinates, coordinates[1:])) * 1.25
        # Illustrative synthetic speed of 54 km/h; explicitly not real traffic or road routing.
        duration = distance / 15.0
        return {"distance_m": distance, "duration_s": duration, "geometry": [[lon, lat] for lat, lon in polyline], "provider": "SYNTHETIC DEMO"}

    def _make_pois(self):
        start, end = self.origin, self.destination
        dlat, dlon = end[0] - start[0], end[1] - start[1]
        points = []
        for i, (kind, tags) in enumerate(DEMO_TYPES, start=1):
            t = 0.12 + i * 0.095
            # Small perpendicular offset from the schematic route.
            lat = start[0] + dlat * t + (0.012 if i % 2 else -0.012)
            lon = start[1] + dlon * t + (0.010 if i % 3 else -0.010)
            points.append({
                "id": f"demo/{self.case['id']}/{i}", "osm_type": "demo", "osm_id": i,
                "name": f"{tags['name']} {i}", "latitude": lat, "longitude": lon,
                "tags": dict(tags), "source": "Synthetic demo fixture",
                "source_url": "fixture://rahgir/synthetic-demo-not-real-poi",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })
        return points

    async def discover_pois(self, route_latlon, radius_m, categories=None):
        from ..engine.planner_utils import classify_poi
        allowed = set(categories or ["heritage", "culture", "food", "nature", "religion", "shopping", "fuel", "ev_charging", "restroom", "medical", "vehicle_service", "parking", "rest_area"])
        return [dict(p) for p in self._pois if classify_poi(p["tags"])[0] in allowed]

    async def matrix(self, coordinates):
        n = len(coordinates)
        durations = [[0.0] * n for _ in range(n)]
        distances = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                distance = haversine_m(coordinates[i], coordinates[j]) * 1.25
                distances[i][j] = distance
                durations[i][j] = distance / 15.0
        return {"durations": durations, "distances": distances, "provider": "SYNTHETIC DEMO"}
