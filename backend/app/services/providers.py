from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from ..config import settings
from .poi_query import build_overpass_query


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"{provider}: {message}")


class RateGate:
    """Process-wide minimum interval guard for public OSMF/demo endpoints."""
    def __init__(self, interval: float):
        self.interval = max(0.0, interval)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self.interval - (time.monotonic() - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


# Public-provider controls and caches are process-wide: creating a new adapter for
# every HTTP request must not reset the shared endpoint rate limits or TTL cache.
_NOMINATIM_GATE = RateGate(settings.public_provider_min_interval)
_OSRM_GATE = RateGate(settings.public_provider_min_interval)
_OVERPASS_GATE = RateGate(10.0)
_GEOCODE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_POI_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_WIKIPEDIA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class ExternalProviders:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0), headers={"User-Agent": settings.http_user_agent})
        self._owns_client = client is None
        self._nominatim_gate = _NOMINATIM_GATE
        self._osrm_gate = _OSRM_GATE
        self._overpass_gate = _OVERPASS_GATE
        self._geocode_cache = _GEOCODE_CACHE
        self._poi_cache = _POI_CACHE

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _json(self, method: str, url: str, *, provider: str, **kwargs) -> dict[str, Any]:
        try:
            response = await self.client.request(method, url, **kwargs)
            if response.status_code == 429:
                raise ProviderError(provider, "rate limited; retry later", 429)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ProviderError(provider, "malformed response (expected JSON object)")
            return data
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(provider, "request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(provider, f"HTTP {exc.response.status_code}", exc.response.status_code) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(provider, f"request failed: {exc}") from exc

    async def geocode(self, query: str) -> dict[str, Any]:
        key = query.strip().casefold()
        cached = self._geocode_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return dict(cached[1])
        if settings.geocoder_provider != "nominatim":
            raise ProviderError("geocoder", f"unsupported GEOCODER_PROVIDER={settings.geocoder_provider!r}; use nominatim or provide a custom adapter")
        await self._nominatim_gate.wait()
        # Nominatim returns a JSON array, so it is decoded separately from the object helper.
        try:
            response = await self.client.get(
                f"{settings.geocoder_base_url.rstrip('/')}/search",
                params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "in"},
                headers={"Accept": "application/json", "User-Agent": settings.http_user_agent},
            )
            if response.status_code == 429:
                raise ProviderError("Nominatim", "rate limited; retry later", 429)
            response.raise_for_status()
            results = response.json()
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("Nominatim", "request timed out") from exc
        except Exception as exc:
            raise ProviderError("Nominatim", f"request failed: {exc}") from exc
        if not isinstance(results, list) or not results:
            raise ProviderError("Nominatim", f"could not resolve location: {query}")
        first = results[0]
        try:
            result = {
                "label": str(first.get("display_name", query)),
                "latitude": float(first["lat"]),
                "longitude": float(first["lon"]),
                "osm_type": first.get("osm_type"),
                "osm_id": first.get("osm_id"),
                "source": "OpenStreetMap Nominatim",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Nominatim", "location response omitted coordinates") from exc
        self._geocode_cache[key] = (time.monotonic() + 86_400, result)
        return result

    async def route(self, coordinates: list[tuple[float, float]]) -> dict[str, Any]:
        """Coordinates are (latitude, longitude); response geometry is GeoJSON coordinates."""
        if len(coordinates) < 2 or len(coordinates) > 10:
            raise ProviderError("routing", "route requires 2 to 10 waypoints")
        provider = settings.routing_provider.lower()
        if provider == "osrm":
            await self._osrm_gate.wait()
            joined = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coordinates)
            data = await self._json(
                "GET", f"{settings.osrm_base_url.rstrip('/')}/route/v1/{settings.osrm_profile}/{joined}",
                provider="OSRM", params={"overview": "full", "geometries": "geojson", "steps": "false", "alternatives": "false"},
            )
            routes = data.get("routes")
            if not routes:
                raise ProviderError("OSRM", "no road route found")
            route = routes[0]
            geometry = route.get("geometry", {}).get("coordinates")
            if not geometry or len(geometry) < 2:
                raise ProviderError("OSRM", "route geometry is missing")
            return {"distance_m": float(route["distance"]), "duration_s": float(route["duration"]), "geometry": geometry, "provider": "OSRM"}
        if provider == "ors":
            if not settings.ors_api_key:
                raise ProviderError("openrouteservice", "ORS_API_KEY is required when ROUTING_PROVIDER=ors")
            profile = "driving-car"
            body = {"coordinates": [[lon, lat] for lat, lon in coordinates], "instructions": False}
            data = await self._json(
                "POST", f"{settings.ors_base_url.rstrip('/')}/v2/directions/{profile}/geojson",
                provider="openrouteservice", json=body,
                headers={"Authorization": settings.ors_api_key, "Content-Type": "application/json"},
            )
            features = data.get("features") or []
            if not features:
                raise ProviderError("openrouteservice", "no road route found")
            feature = features[0]
            summary = feature.get("properties", {}).get("summary", {})
            geometry = feature.get("geometry", {}).get("coordinates")
            if not geometry or len(geometry) < 2:
                raise ProviderError("openrouteservice", "route geometry is missing")
            return {"distance_m": float(summary["distance"]), "duration_s": float(summary["duration"]), "geometry": geometry, "provider": "openrouteservice"}
        raise ProviderError("routing", f"unsupported ROUTING_PROVIDER={provider!r}")

    async def matrix(self, coordinates: list[tuple[float, float]]) -> dict[str, Any]:
        if len(coordinates) < 2 or len(coordinates) > 25:
            raise ProviderError("routing matrix", "matrix supports 2 to 25 locations in this application")
        provider = settings.routing_provider.lower()
        if provider == "osrm":
            await self._osrm_gate.wait()
            joined = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coordinates)
            data = await self._json(
                "GET", f"{settings.osrm_base_url.rstrip('/')}/table/v1/{settings.osrm_profile}/{joined}",
                provider="OSRM table", params={"annotations": "duration,distance"},
            )
            durations, distances = data.get("durations"), data.get("distances")
            if not durations or not distances or len(durations) != len(coordinates):
                raise ProviderError("OSRM table", "malformed or incomplete matrix")
            return {"durations": durations, "distances": distances, "provider": "OSRM"}
        if provider == "ors":
            if not settings.ors_api_key:
                raise ProviderError("openrouteservice", "ORS_API_KEY is required when ROUTING_PROVIDER=ors")
            body = {"locations": [[lon, lat] for lat, lon in coordinates], "metrics": ["duration", "distance"], "units": "m"}
            data = await self._json(
                "POST", f"{settings.ors_base_url.rstrip('/')}/v2/matrix/driving-car",
                provider="openrouteservice matrix", json=body,
                headers={"Authorization": settings.ors_api_key, "Content-Type": "application/json"},
            )
            return {"durations": data.get("durations"), "distances": data.get("distances"), "provider": "openrouteservice"}
        raise ProviderError("routing matrix", f"unsupported ROUTING_PROVIDER={provider!r}")

    async def discover_pois(self, route_latlon: list[tuple[float, float]], radius_m: int, categories: list[str] | None = None) -> list[dict[str, Any]]:
        from ..engine.geometry import sample_polyline
        samples = sample_polyline(route_latlon, max_samples=12, spacing_m=25_000)
        if not samples:
            return []
        selected_categories = sorted(set(categories or settings.default_poi_categories))
        cache_key = f"{tuple((round(a, 3), round(b, 3)) for a,b in samples)}:{radius_m}:{','.join(selected_categories)}"
        cached = self._poi_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return [dict(x) for x in cached[1]]
        query = build_overpass_query(samples, radius_m, selected_categories)
        await self._overpass_gate.wait()
        try:
            response = await self.client.post(
                settings.overpass_url, data={"data": query},
                headers={"User-Agent": settings.http_user_agent, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=35.0,
            )
            if response.status_code == 429:
                raise ProviderError("Overpass", "rate limited; wait before retrying", 429)
            response.raise_for_status()
            data = response.json()
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("Overpass", "request timed out") from exc
        except Exception as exc:
            raise ProviderError("Overpass", f"request failed: {exc}") from exc
        elements = data.get("elements", []) if isinstance(data, dict) else []
        seen: set[tuple[str, int]] = set()
        pois: list[dict[str, Any]] = []
        for element in elements:
            osm_type, osm_id = element.get("type"), element.get("id")
            if not osm_type or osm_id is None or (osm_type, int(osm_id)) in seen:
                continue
            seen.add((osm_type, int(osm_id)))
            tags = element.get("tags") or {}
            lat = element.get("lat")
            lon = element.get("lon")
            if lat is None or lon is None:
                center = element.get("center") or {}
                lat, lon = center.get("lat"), center.get("lon")
            try:
                lat, lon = float(lat), float(lon)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
            except (TypeError, ValueError):
                continue
            pois.append({
                "id": f"{osm_type}/{osm_id}", "osm_type": osm_type, "osm_id": int(osm_id),
                "name": tags.get("name") or tags.get("name:en") or "Unnamed mapped place",
                "latitude": lat, "longitude": lon, "tags": tags,
                "source": "OpenStreetMap", "source_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })
        self._poi_cache[cache_key] = (time.monotonic() + 900, pois)
        return pois

    async def enrich_pois(self, pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach optional context only when OSM explicitly names a Wikipedia page.

        This does not search by place name: ambiguous names and fuzzy matches are
        deliberately avoided. Provider failures leave the original OSM POI intact.
        """
        if not settings.wikipedia_enrichment or not pois:
            return pois

        semaphore = asyncio.Semaphore(3)

        async def enrich(poi: dict[str, Any]) -> dict[str, Any]:
            tags = poi.get("tags") if isinstance(poi.get("tags"), dict) else {}
            wikipedia_ref = str(tags.get("wikipedia") or "").strip()
            if not wikipedia_ref or ":" not in wikipedia_ref:
                return poi
            language, page = wikipedia_ref.split(":", 1)
            if language.casefold() != "en" or not page.strip() or len(page) > 180:
                return poi
            title = page.replace("_", " ").strip()
            cache_key = title.casefold()
            cached = _WIKIPEDIA_CACHE.get(cache_key)
            if cached and cached[0] > time.monotonic():
                return {**poi, **cached[1]}

            async with semaphore:
                try:
                    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page, safe='')}"
                    response = await self.client.get(
                        url,
                        headers={"Accept": "application/json", "User-Agent": settings.http_user_agent},
                        timeout=8.0,
                    )
                    if response.status_code != 200:
                        return poi
                    data = response.json()
                    extract = data.get("extract") if isinstance(data, dict) else None
                    if not isinstance(extract, str) or not extract.strip():
                        return poi
                    image = data.get("thumbnail") if isinstance(data, dict) else None
                    image_url = image.get("source") if isinstance(image, dict) else None
                    if image_url:
                        parsed = urlparse(image_url)
                        if parsed.scheme != "https" or parsed.hostname not in {"upload.wikimedia.org"}:
                            image_url = None
                    page_url = (((data.get("content_urls") or {}).get("desktop") or {}).get("page") if isinstance(data, dict) else None)
                    if not isinstance(page_url, str) or urlparse(page_url).scheme != "https" or urlparse(page_url).hostname not in {"en.wikipedia.org"}:
                        page_url = f"https://en.wikipedia.org/wiki/{quote(page.replace(' ', '_'), safe='') }"
                    enriched = {
                        "story_summary": extract.strip()[:900],
                        "wikipedia_url": page_url,
                        "image_url": image_url,
                        "image_attribution": "Image via Wikimedia Commons; open the linked article for source and licence details." if image_url else None,
                        "story_source": "Wikipedia REST summary (linked by OpenStreetMap tag)",
                    }
                    _WIKIPEDIA_CACHE[cache_key] = (time.monotonic() + 86_400, enriched)
                    return {**poi, **enriched}
                except (httpx.HTTPError, ValueError, TypeError, KeyError):
                    return poi

        enriched = await asyncio.gather(*(enrich(poi) for poi in pois), return_exceptions=True)
        return [item if isinstance(item, dict) else pois[index] for index, item in enumerate(enriched)]
