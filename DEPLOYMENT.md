# Deploy Rahgir

Rahgir's Render service is a preview deployment. It is intentionally configured separately from other applications.

## Preview configuration

- Runtime: Python / FastAPI.
- Build: `python -m pip install --upgrade pip && pip install -r backend/requirements.txt`.
- Start: `PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.
- Routing: public OSRM demo adapter (best effort).
- Geocoding: Nominatim, explicit user-submitted searches only; no autocomplete.
- POI discovery: bounded Overpass route-corridor queries.
- Database: SQLite at `/tmp/rahgir.db` on the free preview. This is ephemeral.

The application identifies itself with `HTTP_USER_AGENT=RahgirRoadTripPlanner/0.3.0 (+https://github.com/shashankkumar8/rahgir)` and uses the configured public-provider request gate. Do not add autocomplete, batch geocoding, city-wide scraping or high-frequency polling. Preserve attribution and caching. Public providers can throttle, reject or be unavailable; errors must be shown as errors, never turned into synthetic live trips.

## Required environment

See `.env.example`. No API key is necessary for the current public Nominatim + OSRM + Overpass preview path. `ORS_API_KEY` is only required when you intentionally switch to OpenRouteService. Keep `ADMIN_TOKEN` generated/secret in Render; never add it to Git.

## Deploy from GitHub

1. Connect `shashankkumar8/rahgir`, branch `main`, to the existing dedicated Rahgir Render service.
2. Use the build and start commands above.
3. Ensure `GEOCODER_PROVIDER=nominatim`, `ROUTING_PROVIDER=osrm`, `HTTP_USER_AGENT` is set to the app-identifying value, `PUBLIC_PROVIDER_MIN_INTERVAL=1.05`, and `OVERPASS_URL` is configured.
4. Confirm the deploy is live in Render logs.
5. Open `/api/v1/health`. It reports app/provider configuration, not a successful external provider probe.
6. Perform one user-initiated live trip plan from the UI. A successful health response alone does not prove routing, geocoding or POI services are reachable.
7. Separately test an invalid/unknown location and provider outage; ensure the UI shows an actionable failure and does not change into the synthetic demo.

## Persistence limitation

The preview uses SQLite under `/tmp`, which is ephemeral on Render. Server-side trip records, community reports and share links may be lost on restart/redeploy. Browser Saved and Journal are stored in the current browser only and are not account-synced. Do not use this setup for durable user records.

Before a public production launch, provision a dedicated managed PostgreSQL database, migrate with a versioned migration tool, verify backups/restore, add authentication/authorization and per-user access controls, move uploads to object storage if introduced, configure contracted routing/geocoding/POI services, add observability and abuse controls, and conduct security/field validation. Do not reuse another application's database.

## Local run

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health: `/api/v1/health`  
OpenAPI: `/api/docs`
