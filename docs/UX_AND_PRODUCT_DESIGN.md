# Rahgir — user experience and product design specification

**Status:** implemented local prototype UI; browser-verified with synthetic fixtures. This document distinguishes functional interactions from roadmap concepts and unverified real-world services.

## Experience principles

1. **Curiosity without pressure:** discovery is optional and constrained by the user's time and detour budget.
2. **Show the trade-off, not one magic answer:** the user sees distinct feasible Pareto alternatives and chooses the route personality that suits the day.
3. **Evidence before certainty:** source links, retrieval context, unknown hours and unavailable safety/weather data remain visible.
4. **Progressive disclosure:** start/destination, travel mood and two key limits are prominent; stop count, total journey time, stop duration and individual preference weights live under advanced settings.
5. **Every control has a consequence:** mode chips update the request, the discovery dial changes Pareto selection preference, candidate chips filter the mapped list, alternative cards reselect the itinerary, and what-if controls call the recomputation endpoint.

## Screen structure

### 1. Landing and route planner
- Editorial brand treatment and concise explanation of Rahgir's purpose.
- Origin and destination with swap control.
- Departure date/time.
- Travel-mood presets: Balanced, Culture, Food trail, Nature, Explorer and Family. These alter the explicit preference mode; they are not accessibility/safety guarantees.
- Detour budget slider and discovery/efficiency dial.
- Progressive advanced settings for total journey time, stop count, stop duration and preference weights.
- Offline walkthrough is clearly named and uses the conspicuous synthetic-data notice.

### 2. Map and route status
- Road geometry and mapped candidates when a map library/provider is available.
- Leaflet/OSM attribution is shown when the tiled map loads.
- If external map tiles or the map library are unavailable, a schematic geometry view is used with an explicit warning; it is not presented as a navigational basemap.
- Candidate markers can be opened on the map from the candidate explorer when the interactive map is active.

### 3. Results and decision support
- Route recipe summarises the selected alternative using returned route/itinerary metrics.
- Metric strip separates base distance, base drive, additional drive and total time including planned stops.
- Pareto shortlist shows distinct Balanced, Fastest, Culture-rich, Explorer and Food trail options only when they are non-duplicate choices in the computed set.
- Journey Pulse shows start, selected stops and destination in itinerary order, with estimated arrivals where departure time is provided.
- Selected itinerary contains mapped-place sources, opening-hours state and “Why this place?” reasoning.
- Candidate Explorer filters by category and exposes single-stop detour, route distance, individual status, caveats and source link.
- “Why not these other places?” separates hard single-stop blockers from places that pass individual checks but were not selected in the full stop combination.

### 4. What-if interaction
The user can change the detour budget, discovery preference and (optionally) departure timestamp. The browser sends those values to `/api/v1/trips/{trip_id}/what-if`; the backend rebuilds the plan and returns new alternatives and candidate arrival estimates. The interface does not fabricate traffic, weather, daylight or incident changes.

### 5. Community contribution
The report dialog accepts a category, description and coordinates. A submitted report is not verified. Near-identical reports can be flagged for review but are not treated as independent corroboration. Moderation requires a source URL before assigning the `verified` workflow state; this still does not create a road-safety probability.

### 6. Share and export
The app supports read-only share links, token revocation and a PDF itinerary export. Share links should be treated as bearer links: anyone with the link can view the read-only result. The UI does not publish continuous location history.

## Decision semantics (must remain stable)

| UI concept | Actual semantics | What it must not imply |
|---|---|---|
| Discovery dial | Post-Pareto selection preference between normalized discovery and efficiency terms | It is not an additional optimizer objective or an evidence-quality score |
| Culture-rich | Higher hand-authored preference-weighted relevance among feasible Pareto options | A verified judgement of cultural importance |
| Explorer | Higher category-rarity/variety proxy within the current retrieved corridor | Globally lesser-known or validated “hidden gem” status |
| Metadata coverage | Fraction of mapped fields present | Truth probability or recommendation confidence |
| Individually feasible | One POI's directed single-stop matrix detour fits current constraints | That it fits jointly with every other stop |
| Unknown opening hours | Provider data or parser support is insufficient | That a place is open |
| Insufficient safety data | No validated segment-level safety ground truth is connected | That a road is safe or dangerous |
| Synthetic walkthrough | Local artificial route/cost/POI fixtures for testing interactions | A real route, live POIs, travel advice or research evidence |

## Browser verification

The reproducible Playwright script `scripts/browser_smoke.py` runs the actual HTML/CSS/JavaScript with API calls routed to FastAPI's in-process test client. The current run checks page/form rendering, synthetic-data labelling, route-persona selection, category filtering, discovery-dial copy, what-if recomputation with a changed discovery bias and departure timestamp, report-dialog open/close, no browser console/page errors, and mobile width overflow at 390 px. The external Leaflet CDN and map tiles are deliberately intercepted, so the test covers the explicit schematic fallback rather than the external basemap. It is a functional smoke test, not a formal accessibility or usability study.

## Deliberately deferred (not present as working features)

- Live weather/festival/crowd adaptation and time-dependent traffic estimates.
- Validated road-segment incident/risk datasets, safety heatmaps, safe-haven/emergency facility lookup.
- User accounts, persistent preference profiles and learning from behaviour.
- Verified cultural knowledge graph, source-ranked cultural claims and RAG/LLM Q&A.
- Photo upload/vision analysis, voice and regional-language interaction.
- Full permutation-aware stop ordering and a map provider's complete alternative-route set.
- Production accessibility audit and consented comparative user study.

These are not hidden behind fake buttons or simulated values. They require data, authorization, research validation or infrastructure that is not available in this build.
