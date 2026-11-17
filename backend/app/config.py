from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Rahgir")
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'rahgir.db'}")
    routing_provider: str = os.getenv("ROUTING_PROVIDER", "osrm")
    osrm_base_url: str = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
    osrm_profile: str = os.getenv("OSRM_PROFILE", "driving")
    ors_base_url: str = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org")
    ors_api_key: str = os.getenv("ORS_API_KEY", "")
    geocoder_provider: str = os.getenv("GEOCODER_PROVIDER", "nominatim")
    geocoder_base_url: str = os.getenv("GEOCODER_BASE_URL", "https://nominatim.openstreetmap.org")
    overpass_url: str = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    http_user_agent: str = os.getenv("HTTP_USER_AGENT", "RahgirRoadTripResearch/0.1 (contact: configure-operator-email)")
    public_provider_min_interval: float = float(os.getenv("PUBLIC_PROVIDER_MIN_INTERVAL", "1.05"))
    corridor_radius_m: int = int(os.getenv("CORRIDOR_RADIUS_M", "2500"))
    max_pois: int = int(os.getenv("MAX_POIS", "14"))
    nsga_population: int = int(os.getenv("NSGA_POPULATION", "64"))
    nsga_generations: int = int(os.getenv("NSGA_GENERATIONS", "60"))
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    wikipedia_enrichment: bool = _bool("WIKIPEDIA_ENRICHMENT", True)
    cors_origins: tuple[str, ...] = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip())
    allow_demo: bool = _bool("ALLOW_DEMO", True)
    max_request_bytes: int = int(os.getenv("MAX_REQUEST_BYTES", "1048576"))


settings = Settings()
