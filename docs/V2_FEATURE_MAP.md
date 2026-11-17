# Rahgir v2 feature traceability

**Release:** 0.2.0  
**Reference material:** the two team-provided WhatsApp recordings and *Rahgir: An AI-Powered Route-Aware Recommendation Framework for Detour-Constrained Road Trip Planning* (six-page team paper, supplied 17 November 2026).

This document distinguishes reference-visible behaviour, implemented behaviour, and work that remains. It is not a claim that the prototype has completed a field or user-study evaluation.

## Reference workflow → implementation

| Reference element | Rahgir v2 implementation | Verification / boundary |
|---|---|---|
| Branded landing page and trip entry form | Retained and polished public landing experience, trip form, swap endpoints, departure, detour budget and theme selection | Chromium browser smoke check |
| Multiple interest/theme selections | Food, heritage, spiritual, local markets, nature and photography chips map into the existing preference vector | Submitted values feed the planning request; no training model is implied |
| Route results with map and ordered stop list | Existing route/map experience is moved into a responsive application workspace without reinitialising the map | Chromium smoke check; external tiles remain provider/CDN-dependent |
| Dashboard / routes navigation | Dashboard, Routes and Explore top navigation plus Dashboard, Routes, Saved, Journal and AI Assistant workspace navigation | Chromium browser smoke check |
| Stop details and photos | Stop cards display a Wikipedia summary/thumbnail only when the OSM place explicitly carries an `wikipedia=en:...` tag | Mocked provider tests; no fuzzy place-name matching or stock images |
| Trip questions / conversation | `POST /api/v1/trips/{trip_id}/ask`; deterministic local grounded mode by default, optional OpenRouter mode | API tests cover local answer, missing trip, bounds and prompt-injection handling. Live model calls require a user key and remain unverified |
| Saved trips | Browser-local index stores trip ID, endpoint labels and save time; open and remove actions call the API/local storage | Browser smoke test. It is not a user account or synced database |
| Journal / trip notes | Browser-local per-trip journal supports create and delete | Browser smoke test. Notes are not uploaded or synced |
| Map-to-navigation action | Google Maps directions deep link is offered for live-provider results, not synthetic fixtures | Depends on a valid live plan and user device/browser |

## Improvements intentionally retained from the earlier Rahgir engine

- Directed road-network time/distance matrices for candidate and itinerary detour estimates; no straight-line detour substitute.
- Hard time, detour and stop constraints and a deterministic seeded NSGA-II Pareto search.
- Provider route recheck for the selected sequence where supported.
- Explanation and candidate filtering, including the distinction between a candidate's single-stop assessment and combined-itinerary feasibility.
- Evidence-aware handling: unknown opening hours remain unknown; missing incident data does not become a positive safety score; synthetic cases are labelled.

These design decisions deliberately avoid inheriting the team paper's stated approximations (fixed-speed straight-line detour estimate and independent per-stop budget semantics) as if they were stronger guarantees.

## Not completed in v2

- Account authentication, server-synced preferences, cloud-synced saved trips and journal, or durable database backups.
- Live OpenRouter verification; users must configure `OPENROUTER_API_KEY` in the deployment environment.
- Live geocoding in the deployed preview. It remains disabled until an operator supplies a genuine contact string for the configured public geocoding provider.
- Verified weather, traffic, daylight, road-incident, personal-security or emergency-response feeds.
- User study, field validation, comparative evaluation against commercial navigation systems, and new empirical effectiveness claims.
- The six-page team research paper has not been silently rewritten. It remains the team's supplied draft; this traceability note documents the software release only. Any paper revision should be team-reviewed and update authorship, methods, verified feature claims, citations and measured results together.

## Required configuration

| Variable | Required? | Why |
|---|---|---|
| `HTTP_USER_AGENT` | Required before enabling public Nominatim use | Identifies the operator/app and supplies a real contact. Do not retain the placeholder. |
| `GEOCODER_PROVIDER=nominatim` | Required to enable geocoding on the current provider adapter | Current Render preview sets this to `disabled` intentionally until the contact is configured. |
| `OPENROUTER_API_KEY` | Optional | Enables model-assisted phrasing in the trip assistant; local grounded answers work without it. |
| `OPENROUTER_MODEL` | Optional | Defaults to `openrouter/auto`. |
| `ORS_API_KEY` | Optional | Needed only when `ROUTING_PROVIDER=ors`; default OSRM path requires no key and is best-effort. |
| `ADMIN_TOKEN` | Required for moderation | Use a strong secret in the deployment environment; never commit it. |

## Verification performed for v2

- Backend pytest suite: 49 tests after the v2 prompt-context security regression test.
- `node --check backend/app/static/app.js`.
- `python -m compileall` for backend, tests and browser smoke harness.
- Shell syntax checks for local and research scripts.
- Chromium smoke path against the FastAPI test client with external network calls intercepted: landing form, synthetic result, disclaimer, workspace, map placement, Pareto cards, save/open, journal create, grounded assistant response, candidate filters/search, and mobile horizontal-overflow check at 390 px.

These are implementation and interaction checks, not evidence of live provider availability, recommendation quality, user satisfaction or road safety.
