# Rahgir release notes

**Release date:** 17 November 2026  
**Scope:** Local research prototype; functional UX improvements and reproducible verification.

## Product improvements

- Reworked the trip planner into an editorial, progressive-disclosure flow with travel-mood presets and explicit journey constraints.
- Added a discovery-versus-efficiency dial. It chooses the Balanced itinerary from the already-feasible Pareto pool; it does not change the optimizer's objectives or relax hard constraints.
- Added distinct route-personality cards when the computed Pareto set contains distinct options.
- Added single-stop road-matrix diagnostics for corridor candidates: additional driving time/distance, estimated arrival, supported opening-hours state, and reason codes.
- Added a candidate explorer with functioning category filters and a “Why this / Why not this?” explanation layer.
- Added a departure-time what-if. The API recomputes the plan and recalculates estimated arrival and supported opening-hours checks.
- Kept synthetic walkthroughs conspicuously labelled. No fictional POIs, risk scores or live data are presented as genuine.
- Improved mobile layout and explicit map-library/tile fallback states.

## Verified on this revision

- `pytest -q`: 44 passed, 0 failed, 0 skipped (11.18 seconds).
- `node --check backend/app/static/app.js`: passed.
- `python -m compileall -q backend/app research scripts/browser_smoke.py`: passed.
- `bash -n scripts/run_local.sh scripts/run_research.sh`: passed.
- Playwright Chromium smoke test: route form/result, synthetic-data disclosure, route selection, candidate filter, discovery dial, departure-time what-if, report modal, no page/console errors; 390 px viewport had no horizontal overflow.
- Research manuscript compiled with pdfLaTeX to a 5-page PDF and final pages were rendered and visually inspected.

## Boundaries

Live providers could not be reached from the build environment. There has been no on-ground route/POI verification, formal usability/accessibility study, validated safety dataset, or human-participant study. Weather, daylight, traffic and incidents are not simulated by the departure-time what-if. These limitations are detailed in `TEST_REPORT.md`, `UX_AND_PRODUCT_DESIGN.md`, and the research manuscript.


## Version 2 — Reference experience and trip companion

- Added an application-style journey workspace matching the supplied reference recordings: Dashboard, Routes, Saved, Journal and AI Assistant navigation, top-level Trips/Dashboard/Explore navigation, a route search field, and a responsive split itinerary/map layout.
- Added multi-select interests (Foodie, Heritage, Spiritual, Local markets, Nature and Photography) that feed the existing planner preference vector. Existing route-mood controls remain available.
- Added browser-local saved journey index and private browser-local travel journal. This is explicitly not account sync or durable server storage.
- Added trip Q&A at `POST /api/v1/trips/{trip_id}/ask`. With no key, it uses deterministic local rules over the stored trip record. Optional OpenRouter support is separate from planning/ranking and falls back locally on provider errors.
- Added optional article summaries and thumbnails when an OSM record explicitly provides `wikipedia=en:...`. No fuzzy name lookup, random photos or invented stories are used. Thumbnail hosts are restricted to `upload.wikimedia.org`; article links are shown for source context.
- Added a Google Maps directions deep link for non-synthetic/live-provider trips. Synthetic fixtures cannot open as real navigation.
- Kept road-matrix detour calculations, cumulative feasibility checks, Pareto optimization and uncertainty labels from the existing Rahgir planner.
- Added tests for the assistant fallback, untrusted prompt content, unknown trip IDs, request limits, Wikipedia tag gating and thumbnail host validation.

### Version 2 verification boundary

The optional OpenRouter conversation path requires the user's own key and was not tested against a live model during this build. The linked Wikipedia enrichment path was tested with mocked API responses; external article coverage and image availability were not validated live. Browser-local Saved and Journal data are not synced to a user account. Live road planning remains dependent on configured external services and a valid operator contact for public geocoding.


## Release 0.2.0 — workspace and trip companion

**Date:** 17 November 2026

- Added the team-reference workspace navigation and split itinerary/map view, alongside the existing public landing page.
- Connected multi-select travel interests to the existing planner preference vector.
- Added browser-local Saved and Journal views with open/remove and create/delete actions.
- Added trip-specific grounded Q&A with deterministic local fallback and optional OpenRouter configuration.
- Added article-linked POI summaries and Wikimedia-hosted thumbnails when an explicit OSM Wikipedia tag is available.
- Added Google Maps directions links for live-provider results only; synthetic fixtures do not present fake navigation.
- Incremented the API version to `0.2.0`.

### v2 verification

- Backend test suite: 49 passed (includes v2 Q&A and provider-enrichment regression tests).
- Chromium smoke run: landing form, synthetic trip, workspace/map, Pareto cards, save/open, journal, assistant, filters/search, and mobile width checks.
- Browser console errors: 0; uncaught page errors: 0; 390 px horizontal overflow: none.
- JavaScript syntax, Python compile and shell syntax checks passed.

### Explicit limitations

OpenRouter and live provider flows still require user-owned credentials and were not live-tested. Saved and journal entries are browser-local. Server trip records on the existing Render free preview use ephemeral SQLite under `/tmp`. There are no validated road-safety, traffic, weather or emergency feeds. The supplied team paper remains unchanged; no new experimental results are claimed. See `V2_FEATURE_MAP.md` and `research/v2_implementation_note.md`.
