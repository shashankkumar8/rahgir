import asyncio
from dataclasses import replace

import httpx
import pytest

import app.services.providers as provider_module
from app.services.providers import ExternalProviders, ProviderError


class ImmediateGate:
    async def wait(self):
        return None


def make_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://unit.test")


def test_nominatim_geocoder_parses_and_caches_response(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[{"display_name": "Delhi, India", "lat": "28.61", "lon": "77.20", "osm_type": "relation", "osm_id": 1}])

    monkeypatch.setattr(provider_module, "settings", replace(provider_module.settings, geocoder_provider="nominatim", geocoder_base_url="https://unit.test"))
    client = make_client(handler)
    adapter = ExternalProviders(client=client)
    adapter._nominatim_gate = ImmediateGate()
    try:
        async def run():
            first = await adapter.geocode("Delhi")
            second = await adapter.geocode("  DELHI  ")
            return first, second
        first, second = asyncio.run(run())
        assert first["latitude"] == 28.61
        assert first["longitude"] == 77.2
        assert second["label"] == first["label"]
        assert len(calls) == 1
    finally:
        asyncio.run(client.aclose())


def test_osrm_route_and_matrix_parse_provider_payloads(monkeypatch):
    def handler(request):
        if "/route/" in request.url.path:
            return httpx.Response(200, json={"routes": [{"distance": 12000, "duration": 900, "geometry": {"coordinates": [[77.2, 28.6], [77.3, 28.7]]}}]})
        if "/table/" in request.url.path:
            return httpx.Response(200, json={"durations": [[0, 900], [950, 0]], "distances": [[0, 12000], [12500, 0]]})
        return httpx.Response(404)

    monkeypatch.setattr(provider_module, "settings", replace(provider_module.settings, routing_provider="osrm", osrm_base_url="https://unit.test", osrm_profile="driving"))
    client = make_client(handler)
    adapter = ExternalProviders(client=client)
    adapter._osrm_gate = ImmediateGate()
    try:
        async def run():
            route = await adapter.route([(28.6, 77.2), (28.7, 77.3)])
            matrix = await adapter.matrix([(28.6, 77.2), (28.7, 77.3)])
            return route, matrix
        route, matrix = asyncio.run(run())
        assert route["provider"] == "OSRM"
        assert route["distance_m"] == 12000
        assert matrix["durations"][0][1] == 900
    finally:
        asyncio.run(client.aclose())


def test_provider_rate_limit_is_reported(monkeypatch):
    def handler(request):
        return httpx.Response(429, json={"message": "slow down"})

    monkeypatch.setattr(provider_module, "settings", replace(provider_module.settings, routing_provider="osrm", osrm_base_url="https://unit.test"))
    client = make_client(handler)
    adapter = ExternalProviders(client=client)
    adapter._osrm_gate = ImmediateGate()
    try:
        with pytest.raises(ProviderError, match="rate limited"):
            asyncio.run(adapter.route([(28.6, 77.2), (28.7, 77.3)]))
    finally:
        asyncio.run(client.aclose())
