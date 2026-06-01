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
- `road_network_nodes.jsonl`: compact road graph node records exported from QGIS
  or another offline GIS/routing workflow.
- `road_network_edges.jsonl`: compact road graph edge records for car and
  rideshare routing; geometry is reviewed offline and not needed at runtime.
- `place_route_nodes.jsonl`: mode-aware reviewed snaps from canonical places to
  routable road graph nodes.
- `electricity_regions.jsonl`: maintained Australian electricity region aliases.
- `manifest.json`: artifact version, source notes, CRS, license notes, and open decisions.

These files are intentionally small fixtures for Ticket 12. Broader production
coverage should replace or extend them with source-noted exports generated from
authoritative datasets.

## Required QGIS Export Contract

Export these app-ready layers from QGIS into a local directory such as
`app/data/geospatial/qgis_exports/`:

- `places.geojson`
- optional `route_network_edges.geojson`
- optional `road_network_nodes.geojson`
- optional `road_network_edges.geojson`
- optional `place_route_nodes.csv`
- optional `electricity_regions.csv`
- optional `route_distances.csv`
- optional `qgis_export_manifest.json`

QGIS remains outside the FastAPI runtime. The importer reads exported files and
generates the compact JSONL artifacts consumed by the live app:

```powershell
..\venv\Scripts\python.exe -m app.pipeline_v2.qgis_geospatial_importer `
  --input-dir app\data\geospatial\qgis_exports `
  --output-dir app\data\geospatial
```

From the `app/` directory, the same command is:

```powershell
..\venv\Scripts\python.exe -m pipeline_v2.qgis_geospatial_importer `
  --input-dir data\geospatial\qgis_exports `
  --output-dir data\geospatial
```

### `places.geojson`

Each feature must have Point geometry, or `latitude` and `longitude`
properties. Required properties:

```text
place_id
name
aliases              pipe-delimited string or JSON array
place_type
region
source
source_version
```

If an alias is intentionally shared by more than one place, each affected
feature should also include `ambiguous_aliases` as a pipe-delimited string or
JSON array. The importer rejects duplicate aliases unless the ambiguity is
declared this way or in `qgis_export_manifest.json` under
`allowed_ambiguous_aliases`.

### `route_network_edges.geojson`

Each feature represents a place-to-place route edge used by the Ticket 12
provider-backed route-distance slice. This is not the Ticket 15 road graph.
Geometry is retained in QGIS for review, but runtime currently relies on the
exported properties:

```text
origin_place_id
destination_place_id
mode                 car_ride, rideshare, bus_ride, train_ride, etc.
distance_km          preferred, or distance + distance_unit
distance_source
confidence           0.0 to 1.0
source_version
bidirectional        true/false
```

The importer validates that every edge endpoint exists in `places.geojson`.

### `road_network_nodes.geojson`

Each feature represents a road graph node. Use Point geometry, or `latitude`
and `longitude` properties. Required properties:

```text
node_id
source
source_version
```

The generated `road_network_nodes.jsonl` intentionally omits GeoJSON geometry
and stores only stable node IDs, coordinates, source, and version metadata.

### `road_network_edges.geojson`

Each feature represents a routable road graph edge prepared offline. Geometry
is retained in QGIS for review, but runtime graph artifacts rely on properties:

```text
edge_id
from_node_id
to_node_id
distance_km
modes                car_ride, rideshare, or a pipe/JSON/list of those values
bidirectional        true/false
source
confidence           0.0 to 1.0
source_version
```

The importer validates that every edge references existing road nodes, that
`distance_km` is positive and numeric, and that modes are currently limited to
road modes `car_ride` and `rideshare`. One-way restrictions are preserved via
`bidirectional=false`; reverse travel is not inferred for those edges.

### Optional `place_route_nodes.csv`

Each row connects one canonical place to one reviewed road-network node for a
specific road mode. Required columns:

```text
place_id
mode                 car_ride or rideshare
node_id
snap_distance_m
snap_confidence      0.0 to 1.0
snap_source
source_version
```

Optional boolean columns `approximate`, `snap_approximate`, or `is_approximate`
can mark a reviewed long-distance snap. Without that explicit marker, the
importer rejects rows whose `snap_distance_m` exceeds the configured threshold
from `qgis_export_manifest.json` (`snap_distance_threshold_m` or
`place_route_node_snap_distance_threshold_m`, default `1000` metres).

The importer validates every `place_id` against `places.geojson`, every
`node_id` against `road_network_nodes.geojson`, and rejects duplicate
`place_id`/`mode` snap rows. Runtime routing uses these snaps before falling
back to place-centroid approximation.

### `electricity_regions.csv`

Required columns:

```text
region
region_name
country
factor_region
fallback_region
aliases              pipe-delimited string or JSON array
source
source_version
```

### Optional `route_distances.csv`

Use this only for audited exact origin/destination route cache rows. Required
columns match `route_network_edges.geojson` except geometry is absent:

```text
origin_place_id
destination_place_id
mode
distance_km          preferred, or distance + distance_unit
distance_source
confidence
source_version
bidirectional
```

## QGIS Regeneration Steps

1. Load raw place, station, locality, state, grid-region, and route datasets into
   a QGIS project dedicated to data prep.
2. Normalize all layers to `EPSG:4326` for exported centroids and metadata.
3. Run geometry validity checks and repair invalid geometries before joins.
4. Build canonical place records by joining localities/stations to Australian
   state or electricity-region layers.
5. Review aliases in an editable table. Keep ambiguous aliases as duplicate
   alias rows so the runtime returns `location.place_ambiguous`.
6. Generate any place-to-place route-network edge rows needed by the Ticket 12
   provider slice. Each row should contain `origin_place_id`,
   `destination_place_id`, `mode`, `distance`, `distance_unit`,
   `distance_source`, `confidence`, `source_version`, and `bidirectional`.
7. Generate road graph node and edge rows for Ticket 15. The edge layer should
   reference `from_node_id` and `to_node_id`, include positive `distance_km`,
   preserve `bidirectional`, and limit road modes to `car_ride` and
   `rideshare` until public-transport graph artifacts are explicitly scoped.
8. Generate reviewed place-to-road-node snap rows for Ticket 16. Keep snap
   points outside runtime; export only `place_id`, `mode`, `node_id`,
   `snap_distance_m`, confidence, source, and version metadata.
9. Optionally generate exact route-cache rows for audited high-value pairs.
   Runtime uses exact cache first, then shortest path over exported network
   edges, then centroid approximation as the lowest-confidence fallback.
10. Export app-ready JSONL files with UTF-8 encoding. Do not export QGIS project
   files into the runtime path.
11. Update `manifest.json` with source versions, license constraints, CRS,
   generation notes, road graph node/edge counts, connected component count,
   mode coverage, place-to-node snap counts, snap threshold, validation status,
   and unresolved data-source decisions.
12. Run the V2 geospatial tests without QGIS installed to confirm the runtime
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
