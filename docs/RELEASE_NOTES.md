# Rahgir UX and decision-support upgrade

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
