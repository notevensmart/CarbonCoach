# QGIS Geospatial Data Workflow

CarbonCoach uses QGIS as an offline data-preparation and review tool only.
The FastAPI runtime must not import QGIS, launch QGIS, or call live routing
services for the V2 request path.

## Runtime Artifacts

The app loads compact files from `app/data/geospatial/`:

- `place_aliases.jsonl`: canonical places, aliases, regions, and WGS84 centroids.
- `route_distances.jsonl`: optional exact mode-aware origin/destination route cache.
- `route_network_edges.jsonl`: mode-aware routable edges exported from QGIS and
  consumed by the runtime shortest-path provider.
- `electricity_regions.jsonl`: maintained Australian electricity region aliases.
- `manifest.json`: artifact version, source notes, CRS, license notes, and open decisions.

These files are intentionally small fixtures for Ticket 12. Broader production
coverage should replace or extend them with source-noted exports generated from
authoritative datasets.

## QGIS Regeneration Steps

1. Load raw place, station, locality, state, grid-region, and route datasets into
   a QGIS project dedicated to data prep.
2. Normalize all layers to `EPSG:4326` for exported centroids and metadata.
3. Run geometry validity checks and repair invalid geometries before joins.
4. Build canonical place records by joining localities/stations to Australian
   state or electricity-region layers.
5. Review aliases in an editable table. Keep ambiguous aliases as duplicate
   alias rows so the runtime returns `location.place_ambiguous`.
6. Generate route-network edge rows from validated road or transit route layers.
   Each row should contain `origin_place_id`, `destination_place_id`, `mode`,
   `distance`, `distance_unit`, `distance_source`, `confidence`,
   `source_version`, and `bidirectional`.
7. Optionally generate exact route-cache rows for audited high-value pairs.
   Runtime uses exact cache first, then shortest path over exported network
   edges, then centroid approximation as the lowest-confidence fallback.
8. Export app-ready JSONL files with UTF-8 encoding. Do not export QGIS project
   files into the runtime path.
9. Update `manifest.json` with source versions, license constraints, CRS,
   generation notes, and unresolved data-source decisions.
10. Run the V2 geospatial tests without QGIS installed to confirm the runtime
   remains fixture-backed and deterministic.

## Runtime Boundary

At runtime, the V2 pipeline uses provider interfaces:

- `PlaceResolver`
- `RouteDistanceProvider`
- `ElectricityRegionResolver`

Provider implementations may load repo-bundled JSONL/CSV/GeoJSON artifacts or
test fixtures. They should return typed misses for unknown or ambiguous data and
should not throw through the main pipeline for normal missing lookup results.

All inferred geospatial data must be visible through parameters, assumptions,
issues, or diagnostics. Explicit user quantities, such as a stated distance or
stated kWh, take precedence over any inferred route or regional default.
