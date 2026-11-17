# Rahgir architecture and data flow

## Component boundaries

| Component | Responsibility | Current implementation |
|---|---|---|
| Browser client | Progressive trip form, travel-mood chips, discovery dial, candidate filters, Pareto selection, itinerary timeline, report form, share/export | Plain JavaScript + HTML/CSS; Leaflet CDN when online |
| API | Validation, orchestration, persistence, reports, share links, PDF | FastAPI + Pydantic + SQLAlchemy |
| Geocoder | Resolve human-readable endpoints | Nominatim adapter |
| Router | Baseline and via-stop routes; route matrix | OSRM or ORS adapter |
| POI search | Candidate discovery around route samples | Overpass adapter |
| Geo engine | Polyline projection, corridor distance, sampling | Haversine + local tangent-plane segment projection |
| Temporal engine | Supported OSM hours subset | Deterministic parser; unknown for unsupported syntax |
| Optimizer | Select a feasible POI subset and Pareto alternatives | Binary NSGA-II |
| Evidence layer | Sources, metadata coverage, uncertainty state | Source metadata + strict insufficient-safety fallback |
| Persistence | Trips, reports and hashed share tokens | SQLite local prototype |
| Research | Synthetic algorithm benchmarks and methodology | Python runner + CSV/JSON/Markdown/LaTeX |

## Live planning sequence

1. Validate origin/destination and constraints.
2. Resolve both endpoints.
3. Request a baseline road route and geometry.
4. Sample geometry at a bounded spacing/count and query mapped attractions, culture, food, craft and nature tags around those sample points.
5. Reject malformed POI coordinates, remove duplicate source objects, project valid POIs onto the full provider route and keep only candidates inside the configured corridor radius.
6. Request a directed road-time and road-distance matrix for origin, candidate POIs and destination.
7. Sort selected POIs by along-route progress (current search approximation); calculate arrival estimates and exclude only definitely-closed POIs.
8. Evaluate each binary stop selection under hard stop-count, incremental driving-time and total journey-time constraints.
9. Approximate a six-objective Pareto front with seeded binary NSGA-II.
10. Choose a Balanced persona result from the feasible Pareto set using the user's discovery-bias preference; preserve other distinct persona alternatives.
11. Expose single-stop route-fit diagnostics for every mapped candidate, while keeping combined-itinerary feasibility separate.
12. Request the selected via-stop route again and re-check provider-reported detour and total journey time. Mark unavailable/failed verification explicitly.
13. Persist the trip and return provenance, sources, limitations and calculated alternatives.

## Optimisation objectives

The current six minimisation objectives are:

1. Negative preference-weighted cultural relevance (hand-authored category-value heuristic × explicit user weights).
2. Negative category diversity ratio.
3. Negative route-corridor category rarity proxy.
4. Additional road driving minutes.
5. Additional road distance kilometres.
6. Negative mapped metadata completeness.

The latter two positive-value terms are proxies only. Neither metadata completeness nor category rarity is a probability of truth, global popularity, or proof of a hidden gem. Safety is not an objective because no validated road-segment safety dataset is connected.

## Constraint model

For a selected sequence `π`, the backend sums directed provider matrix legs from origin through selected POIs to destination:

- `delta_drive = max(0, via_stop_drive_time - baseline_drive_time)`
- `total_journey = via_stop_drive_time + selected_stop_count × planned_stop_duration`
- hard constraints: `selected_stop_count <= max_stops`, `delta_drive <= detour_budget`, `total_journey <= max_journey_time`
- only a definite `closed` value from the supported hours parser excludes a POI; unknown opening hours remain unknown.

This is a bounded subset-selection model with a fixed route-progress order. It is not a general vehicle-routing solver and can miss better sequences requiring backtracking.

## Safety and trust boundaries

- Community report states are workflow states, not a calibrated incident confidence score.
- A source URL is required before the moderator can set `verified`.
- Reports do not change route ranking or safety status.
- `insufficient_evidence` is the default safety result.
- Retrieved POI tags, external response strings and community descriptions are untrusted data; the frontend escapes text before HTML insertion.
- The API does not store continuous GPS traces.

## Deployment boundary

SQLite is suitable for local/demo and small evaluation workloads only. A production deployment needs PostgreSQL/PostGIS, multi-process distributed cache/rate gates, authenticated users/roles, structured job queue, monitoring, backup and data-retention policy. The current process-global rate gate/cache does not coordinate multiple application workers or multiple hosts.

## Interactive Pareto decision policy

The discovery dial is a post-optimisation choice mechanism over the feasible non-dominated pool. For each Pareto candidate, the UI computes a normalized discovery utility from the current cultural-relevance, category-diversity, corridor-category-rarity proxy and metadata-completeness metrics. It separately computes normalized efficiency from lower additional driving time and distance. With user preference $\alpha\in[0,1]$, the Balanced persona is selected by maximizing $\alpha D_i + (1-\alpha)E_i$. The dial does not alter NSGA-II's six objectives, bypass opening-hours checks, or relax detour/time/stop constraints. Its values are stored in the trip request and returned as `decision_policy`.

Candidate-level explanations are one-stop diagnostics from directed origin-to-candidate and candidate-to-destination matrix legs. They do not certify that multiple individually feasible stops are jointly feasible. The optimizer checks the combined route-progress-ordered sequence, and the selected itinerary is sent through a second route-provider recheck.

The what-if endpoint accepts an optional departure timestamp. When provided, the full planning request is rebuilt; estimated candidate arrivals and supported opening-hours checks are recalculated. Traffic, weather, daylight, crowding and incidents remain unmodelled unless connected to verified providers.
