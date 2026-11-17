# Data sources, attribution, and provider policies

## OpenStreetMap ecosystem

- **Data:** OpenStreetMap contributors, queried through Nominatim (geocoding) and Overpass (POI tags).
- **Attribution:** display `© OpenStreetMap contributors` and link to https://www.openstreetmap.org/copyright.
- **Licence:** OpenStreetMap database is available under ODbL. Review attribution and share-alike obligations before redistributing a derived database. A project's own source code licence does not replace ODbL obligations for OSM-derived data.
- **Nominatim public endpoint:** follow https://operations.osmfoundation.org/policies/nominatim/. The policy includes a maximum of one request per second, an identifying User-Agent/Referer, caching, attribution, and restrictions on autocomplete and bulk use. The prototype only uses explicit submitted origin/destination lookups, not autocomplete.
- **Overpass:** use shared public instances sparingly. Cache results, keep query sizes modest, handle 429/timeouts, and use a paid or self-hosted service for sustained/product traffic. Endpoint choice is configurable.

## Routing

- **OSRM:** the adapter uses the public HTTP Route and Table service interface. The public demo service is best-effort and has no production SLA; check its usage terms before use. Do not rely on it for a commercial launch or high request volume.
- **OpenRouteService:** the application supports directions and matrix calls. Set `ROUTING_PROVIDER=ors` and supply `ORS_API_KEY`. Verify current plan quotas, terms, supported profiles, and matrix limits before production deployment.

## Provider response integrity

- Route geometry is expected as GeoJSON `[longitude, latitude]` and is converted internally to `(latitude, longitude)`.
- Route distance/time and matrix leg costs are provider-derived. NaN, infinite, negative, malformed or missing values are rejected as unavailable.
- POI records preserve OSM object type/id, tags, source URL and retrieval timestamp.
- If the provider is unavailable, the live flow returns an error. It does not silently fall back to synthetic fixture output.
- Synthetic demo data is explicitly partitioned and never reported as OSM content.

## Future source additions

Before adding a source, record the dataset/API owner, access method, licence, attribution, geographic/temporal coverage, update cadence, known bias, missingness, and permitted retention/redistribution. Road-incident, police/hospital facility, traffic, weather and festival data require separate authority/source validation; no such dataset is silently inferred from OSM tags.
