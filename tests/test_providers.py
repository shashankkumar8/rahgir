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


def test_wikipedia_enrichment_requires_explicit_osm_tag_and_validates_thumbnail(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={
            "title": "Test Heritage Site",
            "extract": "A source-linked short context paragraph.",
            "thumbnail": {"source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Test.jpg/320px-Test.jpg"},
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Test_Heritage_Site"}},
        })

    monkeypatch.setattr(provider_module, "settings", replace(provider_module.settings, wikipedia_enrichment=True, http_user_agent="Rahgir tests"))
    client = make_client(handler)
    adapter = ExternalProviders(client=client)
    pois = [
        {"id": "node/1", "name": "Test Heritage Site", "tags": {"wikipedia": "en:Test_Heritage_Site"}},
        {"id": "node/2", "name": "Another Site", "tags": {}},
    ]
    try:
        enriched = asyncio.run(adapter.enrich_pois(pois))
        assert enriched[0]["story_summary"] == "A source-linked short context paragraph."
        assert enriched[0]["image_url"].startswith("https://upload.wikimedia.org/")
        assert enriched[0]["wikipedia_url"] == "https://en.wikipedia.org/wiki/Test_Heritage_Site"
        assert "story_summary" not in enriched[1]
        assert len(calls) == 1
    finally:
        asyncio.run(client.aclose())


def test_wikipedia_enrichment_rejects_non_wikimedia_thumbnail(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "extract": "Grounded article summary.",
            "thumbnail": {"source": "https://untrusted.example/tracker.jpg"},
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Another_Test_Page"}},
        })

    monkeypatch.setattr(provider_module, "settings", replace(provider_module.settings, wikipedia_enrichment=True))
    client = make_client(handler)
    adapter = ExternalProviders(client=client)
    try:
        result = asyncio.run(adapter.enrich_pois([{"id": "node/3", "name": "Another test", "tags": {"wikipedia": "en:Another_Test_Page"}}]))[0]
        assert result["story_summary"] == "Grounded article summary."
        assert result["image_url"] is None
    finally:
        asyncio.run(client.aclose())
