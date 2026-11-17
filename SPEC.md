# Rahgir v0.3 — Product and Engineering Specification

**Product category:** Route-aware road-trip decision and feasibility tool  
**Primary user:** A driver planning an intercity journey in India who wants useful stops without losing control of time, extra driving or fuel/energy cost.  
**Core product promise:** Build and validate a practical stop sequence along a real road route; show the exact road, time, cost and evidence trade-offs before the traveller leaves.

## 1. Ground-truth problem and wedge

A driver can obtain a point-to-point route from a navigation app, and can search for places near a city. The harder decision is whether a combination of stops along the entire route is practical: how much extra road time it adds, whether the stop is likely to be open at the estimated arrival, whether the full journey still fits the driver's time limit, and where useful facilities (fuel, EV charging, toilets, medical help and vehicle service) exist.

Rahgir's wedge is **route-network verified multi-stop feasibility**, including cumulative detour and time-window propagation. It is not a chat interface that paraphrases a map API.

## 2. Golden path

1. Traveller enters start and destination, departure time, maximum total trip time, cumulative extra-driving budget and desired stop types.
2. Traveller optionally enters their vehicle energy efficiency and current fuel/electricity unit price.
3. Backend geocodes the endpoints, obtains an actual road route, samples the route corridor, retrieves mapped places and facilities, validates their coordinates, and obtains a directed road-time/distance matrix.
4. A deterministic multi-objective optimizer chooses feasible combinations. Each combination is checked against cumulative extra driving, full journey duration, stop count, and supported opening-hours rules.
5. The chosen itinerary is sent back through the route provider as a via-point route. A route that fails this final check is not presented as confirmed feasible; the system tries the next candidate or reports that validation failed.
6. Traveller can inspect evidence for every candidate, add/remove stops and validate a custom sequence, compare options, save locally, share a read-only trip, export a PDF, or open the selected via-point route in an external navigation service.

## 3. Must-have product capabilities

- **Live route planning:** real endpoint coordinates, provider road geometry, distance and duration. No silent synthetic fallback.
- **Corridor discovery:** OSM-mapped attractions, heritage, food, nature, worship, fuel, EV charging, toilets, parking/rest areas, medical services and vehicle service, subject to actual mapped coverage.
- **Road-matrix detour calculation:** directed road legs, not straight-line distance. Cumulative route detour is computed for the entire stop sequence.
- **Time-window handling:** supported opening-hours syntax can produce open/closed; missing or unsupported syntax stays unknown and is shown as a caveat.
- **Deterministic options:** efficient, balanced and discovery-led Pareto alternatives with their objective trade-offs visible.
- **Custom itinerary builder:** traveller can select any discovered candidates and validate the full via-point route against their own time and detour budgets.
- **Vehicle cost estimate:** uses only the efficiency and unit price entered by the traveller. No guessed fuel price or vehicle mileage.
- **Map and action:** route geometry, candidate and selected-stop markers, source links, OSM attribution, Google Maps directions link for a validated live route, PDF export and read-only sharing.
- **Local saved journeys:** explicitly browser-local. No claim of account sync.
- **Operational readiness:** visible provider status and precise, recoverable errors. Missing credentials or unavailable public services must not render fake route results.

## 4. Not in this release

- No LLM-based route planning or ranking. The AI chat is removed from the primary journey.
- No claims about traffic, road safety, weather, crowd levels, fuel availability, EV charger working status, hospital capacity or real-time operating status unless an authoritative feed is separately connected and validated.
- No user accounts or cloud sync; browser-local saved journeys remain local.
- No automated Nominatim autocomplete. User-submitted search happens only on explicit plan submission.
- No fake POIs, fabricated photos, synthetic coordinates or generated opening hours in live mode. Synthetic walkthrough is opt-in, bannered and isolated from live planning.

## 5. Data and provider rules

- Nominatim is end-user search only, cached, rate-limited to no more than one request per second for the application, with a custom app-identifying User-Agent and visible attribution. Do not add autocomplete or bulk search.
- Public OSRM demo is best-effort, rate-limited to one request per second, identified with a custom User-Agent and attributed. It is a development/preview provider, not a commercial uptime guarantee.
- Overpass queries are bounded to route samples and chosen categories; no city-wide scraping or repeated broad queries. Cache successful corridor queries and surface provider failures.
- OpenStreetMap attribution is displayed. Preserve source URL, OSM element ID, retrieval timestamp and raw tags for each candidate.
- ORS may be selected by configuration where a user supplies a key; no credential is committed to Git.

## 6. Locked architecture

- FastAPI application; Pydantic request contracts; SQLAlchemy persistence.
- Provider adapters: Nominatim geocoding, OSRM or ORS routing/matrix, Overpass POI discovery, optional Wikipedia context only for explicit OSM Wikipedia tags.
- Deterministic engine: route sampling, geometry filtering, road-matrix evaluation, feasibility checks, Pareto selection, schedule propagation and cost estimation.
- Thin static web client: accessible responsive trip form, results workbench, map, candidate inspector, custom itinerary validation and action/export surfaces.
- No LLM in the core route or ranking path. No added dependency unless justified by a required capability.
- New and refactored modules should remain small and single-purpose (target under 250 lines); no monolithic source files.

## 7. Acceptance criteria / definition of done

### Route pipeline
- A valid live request either returns a provider-sourced road route plus mapped candidates or a structured actionable provider error.
- No live request can return a synthetic fixture.
- Matrix dimensions, coordinates, timestamps, sources and route geometry are validated.
- Every reported itinerary obeys the cumulative detour, total journey-time and max-stop constraints.
- The selected via-point route is rechecked. If it fails or cannot be checked, the UI must say so and must not label it confirmed.

### Candidate and facility explorer
- Filters change the actual visible result list.
- Every candidate has a source, category, route-corridor distance, individual road-matrix assessment and clear eligibility reasons.
- A selected set can be validated as a complete route. Add/remove actions update the selected set; the validate action calls the backend and reports exact extra time, extra distance, total duration, estimated arrivals, opening-hours unknowns and budget pass/fail.

### Vehicle cost
- With no vehicle inputs, cost is labelled not configured.
- With valid inputs, baseline and planned-route energy/fuel use and cost are calculated deterministically and covered by unit tests.
- Invalid or zero efficiencies/prices are rejected; no default market price is invented.

### User actions
- Save/open/delete local trip, add/delete local note, select Pareto option, custom itinerary check, what-if recompute, read-only share, PDF export and navigation link all have a real action and error state.
- No visible button is inert or a decorative success.

### Verification
- Unit tests for route geometry, provider parsing, corridor filters, candidate category mapping, hours parsing, optimizer feasibility, cost estimation and custom route validation.
- API integration tests for live-provider mock success/failure, provider-disabled state, no synthetic live fallback, persistence, sharing, PDF and reports.
- Browser tests for a complete synthetic test-only golden path, real provider-error UX, candidate filtering, custom itinerary selection/validation, alternative switching, save/open/delete, journal, export/share affordances, and narrow mobile layout.
- External provider success is reported separately from mocked functional tests. No claim of field validation without field data.

## 8. Telemetry

The UI shows distinct states for: configuration missing, provider request in progress, provider success (with source and retrieval time), rate-limited, provider unavailable, incomplete response, route feasibility pass/fail, and custom validation status. It never hides a failed request behind a synthetic fallback.
