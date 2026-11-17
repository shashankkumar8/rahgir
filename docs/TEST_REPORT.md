# Rahgir verification report

**Verification date:** 17 November 2026 (UX and what-if upgrade)  
**Build scope:** local development/research prototype  
**External network:** unavailable from the execution container; live provider calls not verified

## Automated tests

Command: `pytest -q`  
Result: **44 passed in 11.18 seconds; 0 failed; 0 skipped.**

Coverage includes API health and static page, synthetic trip planning across the supported case fixtures, persistence, what-if recomputation including departure-time propagation, discovery-bias bounds and preference-conditioned selection, share/revoke, PDF export, report submission and moderation rules, duplicate-report flagging, coordinate/geometry validation, route geometry calculations, temporal parsing, evidence abstention, NSGA-II dominance/determinism, provider adapter parsing and failure handling, malformed provider data, and request schema constraints.

The browser smoke script is reproducible with `pip install -r requirements-e2e.txt`, `python -m playwright install chromium`, and `python scripts/browser_smoke.py`. The research figure generator requires `requirements-research.txt`. The provider tests use mocked HTTP responses. They do not make requests to Nominatim, OSRM, OpenRouteService, or Overpass.

## Static checks

- `node --check backend/app/static/app.js` — passed.
- `python -m compileall -q backend/app research scripts/browser_smoke.py` — passed.
- `bash -n scripts/run_local.sh scripts/run_research.sh` — passed.
- Experiment CLI rejects candidate counts above 12 as configured — passed.
- LaTeX paper compiled with `pdflatex -interaction=nonstopmode -halt-on-error` — passed after adding the interactive decision-support method; final PDF contains 5 pages.
- PDF re-rendered to page images and visually inspected after the final compile — layout verified; see release artefact.

## Browser and HTTP workflow checks

Chromium headless smoke run used the actual HTML, CSS and JavaScript with frontend API calls routed to the FastAPI `TestClient` because the environment blocks Chromium navigation to local network addresses. Results:

- Landing page and trip form rendered.
- Synthetic Delhi–Agra walkthrough displayed results and its synthetic-data warning; 7 fixture candidates and 3 distinct Pareto alternatives were returned in this run.
- Selecting the Fastest persona changed the active itinerary and selected-state UI.
- Candidate category filter changed the visible result set and restoring “All” restored the full set.
- Discovery dial updated its label; what-if request carried `discovery_bias = 0.9`.
- What-if request carried a changed departure timestamp (`2026-11-19T10:00` in this run) and triggered backend itinerary recomputation.
- Community-report dialog opened and closed.
- No JavaScript page errors or console errors were recorded.
- At 390 px viewport width, `document.body.scrollWidth` was 390 px (no horizontal overflow).
- The map's external Leaflet library and tile requests were disabled in this smoke test; the explicit schematic map fallback was used. Its route title/status/freshness display was checked by the render path, but external tile rendering and live marker interactions are not verified here.
- PDF export is covered by the API integration test; the browser smoke script does not assert a new-tab download event.

An earlier separate Uvicorn process was queried over local HTTP before the current UI/persona expansion. Health, synthetic plan creation, what-if, share creation/read, and PDF export requests completed in that run. The sample plan created seven synthetic candidates and two alternatives at that earlier revision. PDF export returned an application/pdf response (2,890 bytes in that run). The current revision is covered by the 44-test API suite and the browser smoke run above. All these checks use synthetic fixtures; none is external-provider or field testing.

## Research experiment

Command (see README): `python research/run_experiments.py --seeds 5 --instances 8 --candidates 12 --population 64 --generations 60 --output research/results/paper_benchmark`

- 8 fixed synthetic instances.
- 5 NSGA-II seeds per instance.
- 4 algorithm variants (40 rows per algorithm; 160 CSV rows total).
- Exact reference Pareto front via exhaustive enumeration for each 12-candidate instance.
- Mean three-objective Monte-Carlo hypervolume: NSGA-II 0.255434; nearest-feasible 0.134135; weighted-greedy 0.096785; distance-only 0.054670.
- Mean six-objective IGD: NSGA-II 0.126492; nearest-feasible 0.441001; weighted-greedy 0.486873; distance-only 0.450815.

The raw CSV, JSON summary, textual summary and plotting script are checked in. These data are synthetic only; see `research/DATASET_CARD.md` and the paper's limitations.

## Not verified / remaining blockers

- No live route/POI data for Ghaziabad–Etawah, Delhi–Agra, Delhi–Jaipur, Delhi–Mathura or Mumbai–Pune; outbound DNS/network access was unavailable.
- No on-ground checks of road geometry, detour time, POI existence, cultural claims or opening hours.
- No external Leaflet CDN or OSM tile verification from the browser smoke environment.
- No production database, multi-worker deployment, cross-process provider throttling, load testing, security penetration test or formal accessibility audit.
- No validated road-segment safety dataset, weather/festival feeds or user-study dataset.
- Authentication, profile management, several roadmap features, and full permutation-aware itinerary sequencing remain out of scope for this version.

## How to reproduce

Run the automated test and benchmark commands from the root README. To verify live providers, configure the required routing credentials/provider endpoints and an identifying `HTTP_USER_AGENT` with contact information, then execute the five-route plan on an approved network and archive raw provider evidence with timestamps and licensing metadata. Do not replace unavailable live data with synthetic fixtures in any report or publication.
