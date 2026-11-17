# Deploy Rahgir to Render

This repository includes a Render Blueprint at `render.yaml`.

## Important deployment behaviour

- The Blueprint targets a **free** Singapore web service for a demo deployment. Free services can sleep when idle.
- The current application uses SQLite. The Blueprint stores it under `/tmp`, which is ephemeral. **Trips, reports and share links can be lost on restart/redeploy.** This is acceptable only for a preview; it is not durable production storage.
- The application is a research prototype. The current safety subsystem intentionally reports `insufficient_evidence`; it must not be marketed as a safe-navigation product.
- The live provider adapters use public OSM/Nominatim/Overpass and OSRM defaults. These are not a production SLA. Set a valid identifying `HTTP_USER_AGENT` with an operator contact before enabling live geocoding. Follow the providers' usage policies and attribution requirements. Do not add autocomplete or bulk geocoding to public Nominatim.
- Do not add API keys or secrets to Git. Configure them in the Render environment.

## Deploy steps

1. Push this repository to a GitHub repository you control.
2. In Render, choose **New → Blueprint** and connect that repository.
3. Render reads `render.yaml` and previews a single `rahgir` web service. Review the plan/region before applying.
4. During the first setup, provide `HTTP_USER_AGENT` with a real project/operator contact. Render generates `ADMIN_TOKEN`; retrieve it securely from the service's environment settings when moderation is needed. Never publish it.
5. Apply the Blueprint and wait for the service deploy to finish.
6. Check `https://<your-service>.onrender.com/api/v1/health`. A successful response confirms process readiness only; it does not probe OSRM, Nominatim or Overpass.
7. Open the root URL and use **Try synthetic walkthrough** to verify the product UI. Synthetic route/POI values are clearly labelled and must never be used for real navigation or research outcome data.

## Before production use

1. Replace SQLite with managed PostgreSQL and add the matching SQLAlchemy driver. Run migrations and verify backup/restore.
2. Move persistent user uploads to object storage if uploads are introduced.
3. Configure a production routing/geocoding/POI provider with appropriate quotas, caching and attribution.
4. Set a real operator contact in `HTTP_USER_AGENT`; keep secrets only in Render environment variables.
5. Add authentication and per-user authorization before exposing personal saved trips. The current read-only share token is not a user-account system.
6. Conduct live route validation, monitor provider failures, add observability and security review.
7. Do not claim validated safety, traffic, weather or incident intelligence until those evidence feeds and validations exist.

## Local equivalent

```bash
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health endpoint: `/api/v1/health`  
OpenAPI: `/api/docs`
