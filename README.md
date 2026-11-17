# RAHGIR — Road-trip planning with route feasibility

**Product promise:** Build a practical multi-stop road journey, inspect the road-network cost of every stop, and validate the complete sequence before relying on it.

Rahgir is not a chatbot or an LLM wrapper. Its core is a deterministic route-planning and decision system for intercity drivers. It combines provider-sourced road routing, route-corridor place/facility discovery, directed road-time matrices, cumulative detour and journey-time constraints, opening-hours uncertainty, a seeded multi-objective optimizer, and a final via-point route check.

## What a traveller can do

1. Enter an origin, destination and departure time; set a maximum journey duration, extra-driving budget and stop cap.
2. Choose the types of places or facilities that matter: heritage, food, nature, worship, shopping, fuel, EV charging, toilets, medical help, parking/rest areas or vehicle service.
3. Optionally enter their own vehicle efficiency and current unit price to calculate an indicative fuel/energy cost. Rahgir never guesses these values.
4. Compare deterministic route personalities from the feasible Pareto set.
5. Inspect each mapped candidate's source, category, distance from the route, directed single-stop assessment, opening-hours state and reasons it may or may not fit.
6. Add or remove stops and ask the route provider to validate the *complete ordered route*. The app only labels a sequence confirmed when the final provider check and hard constraints pass.
7. Change departure time, detour budget or discovery preference and recompute the plan.
8. Save a journey in the current browser, keep local notes, create a read-only share link, export a PDF, or open a provider-validated live route in an external navigation app.
9. Submit a road observation for moderation. A submitted report is not automatically verified and does not create a safety score.

## The engineering wedge

A point-to-point map route does not answer whether several stops, in a chosen order, are feasible together. Rahgir calculates the directed road legs for the whole sequence, propagates estimated arrivals, checks cumulative additional driving and total journey duration, applies supported opening-hours rules, and validates the selected via-point route with the routing provider. Straight-line distance and independent per-stop estimates are not used as substitutes for complete-route validation.

The main pipeline is:

```text
User trip + constraints
  -> explicit endpoint geocoding
  -> provider road route
  -> bounded route corridor sampling
  -> category-scoped mapped places/facilities
  -> candidate validation and provenance
  -> directed road-time/distance matrix
  -> temporal + cumulative constraint checks
  -> deterministic Pareto search
  -> selected via-point route recheck
  -> itinerary, candidate explorer, map, export/share
```

No LLM is used for routing, selection, feasibility, ranking or core UI actions.

## Data integrity and what is not claimed

- **Live mode:** only provider-returned route geometry, distances, durations and mapped POIs are used. A provider error returns an actionable error; it never silently changes into a synthetic journey.
- **Synthetic walkthrough:** opt-in, conspicuously labelled, and used only to exercise product interactions. It is not navigation, real place coverage or research outcome data.
- **Opening hours:** only a supported subset is interpreted. Missing or unsupported values remain `unknown`; they are not assumed open.
- **Safety, traffic and weather:** no validated road-safety, live traffic, forecast or emergency feed is connected. Absence of community reports is not evidence of safety.
- **Facility coverage:** fuel, EV, toilet, medical and vehicle-service discovery depends on what is actually mapped in OpenStreetMap. A mapped POI does not prove current stock, charger availability, opening or service quality.
- **Vehicle cost:** calculated only from user-entered efficiency and unit price. It is an estimate, not a live market quote.
- **Saved trips:** the local Saved and Journal views use browser storage. Server-side trip records currently use SQLite on Render's ephemeral filesystem; this is a preview limitation, not durable account storage.

## Provider configuration

See [`.env.example`](.env.example). The default preview adapters are:

| Setting | Purpose |
|---|---|
| `GEOCODER_PROVIDER=nominatim` | Explicit, user-submitted endpoint search; no autocomplete |
| `ROUTING_PROVIDER=osrm` | Public OSRM demo routing and matrix adapter; best-effort preview only |
| `OVERPASS_URL` | Bounded route-corridor POI queries |
| `HTTP_USER_AGENT` | Identifies Rahgir to public map providers |
| `PUBLIC_PROVIDER_MIN_INTERVAL=1.05` | Conservative per-process request gate for public services |
| `ORS_API_KEY` | Optional key when selecting OpenRouteService instead of public OSRM |
| `WIKIPEDIA_ENRICHMENT=true` | Article context only for an explicit OSM `wikipedia=en:...` tag |
| `DATABASE_URL` | SQLAlchemy database URL; local SQLite by default |
| `ADMIN_TOKEN` | Secret required for report moderation |
| `ALLOW_DEMO=true` | Enables the clearly labelled synthetic walkthrough |

Public Nominatim, OSRM and Overpass endpoints are shared services with their own usage terms and no production uptime guarantee. Requests are explicit, bounded and rate-limited. For sustained public use, configure dedicated or contracted routing, geocoding and POI infrastructure. See [data sources and provider limitations](docs/DATA_SOURCES.md).

## Local setup

Python 3.11+ is recommended. From the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
$env:PYTHONPATH = "backend"
uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000`; API docs are at `http://127.0.0.1:8000/api/docs`.

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
set -a && source .env && set +a
PYTHONPATH=backend uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --reload
```

## Verification

Run the backend and browser checks:

```bash
pytest -q
for f in backend/app/static/{core,map,workspace,results,route_actions,planner,app}.js; do node --check "$f"; done
python scripts/browser_smoke.py
```

The browser suite uses an isolated test database and a test-only synthetic walkthrough. It verifies actual browser actions and intercepted API behaviour, including provider-error UX. It does **not** claim that public route/geocoder providers were contacted successfully. The test report records the exact boundary.

## Source of truth

- [`SPEC.md`](SPEC.md) — product contract and acceptance criteria.
- [`AGENTS.md`](AGENTS.md) — implementation and verification rules.
- [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) — current test evidence and boundaries.
- [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) — this release's changes.
- [`research/`](research/) — reproducible synthetic algorithm experiments and the research manuscript draft. Synthetic benchmark numbers are not field evidence.
