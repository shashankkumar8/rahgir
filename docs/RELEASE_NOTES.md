# Rahgir v0.3.0 — route-feasibility workbench

**Release scope:** replace the reference-style chat-centric surface with a deterministic, practical multi-stop road-trip planning workflow.

## Product changes

- The primary job is now explicit: plan a real road journey, discover mapped corridor places/facilities, build a stop sequence and validate the complete via-point route.
- Expanded corridor categories to practical traveller facilities: fuel, EV charging, toilets, medical help, vehicle service, parking and rest areas, alongside food, heritage, nature, worship and shopping.
- Split the client into small, single-purpose modules: core state/API, map, workspace, result views, route actions, planner actions and entrypoint.
- Removed the trip-chat concept from the primary product. No LLM dependency exists in route planning or ranking.
- Tightened the final route proof contract: an alternative is not labelled confirmed until its full via-point route check succeeds and its actual route metrics pass the constraints.
- Added user-entered vehicle efficiency and energy price cost estimates; no default market price or mileage is invented.
- Kept explicit synthetic walkthrough, provider-source provenance, structured provider failure states, local saved journeys/journal, what-if, reports, PDF export and read-only sharing.

## Verification on this source revision

- Backend: **66 passed**.
- JavaScript syntax: all seven client modules pass `node --check`.
- Chromium browser smoke: **21 end-to-end checks passed**.
- Browser console errors: 0.
- Uncaught page errors: 0.
- Mobile viewport: 390 px; no horizontal overflow.
- Browser checks include explicit synthetic disclosure, route options, full-route alternative recheck, facilities filter, map locate/fit, custom stop selection and validation, apply feasible route, search/category filters, what-if API, read-only share token creation, PDF response signature, saved/open/delete, journal create/delete, report submission, and explicit live-provider failure without demo fallback.

## Verification boundaries

- The browser route fixture is intentionally synthetic and test-only; it is not a real Delhi–Agra road observation.
- API tests mock external providers. Public provider success was not independently established from the build environment because outbound DNS/network access is not reliable here.
- Public OSM/OSRM/Overpass endpoints are best-effort shared services, not production guarantees.
- No field route validation, participant study, traffic/weather feed, verified road-safety dataset, emergency feed or live charger/fuel status is claimed.
- Saved and Journal remain browser-local. Render preview server records use SQLite under `/tmp` and are not durable across restarts.
