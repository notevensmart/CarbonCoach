# CarbonCoach V2 Tickets 13-22: Geospatial Routing Data Product

This document scopes the follow-on geospatial work after Ticket 12.

Ticket 12 adds the provider-backed enrichment slice: place resolution,
mode-aware route lookup, approximate fallback, electricity-region context,
and visible assumptions/issues.

Tickets 13-22 turn that slice into a more complete offline GIS data product
for casual location-aware transport entries such as:

```text
I took an Uber from Surry Hills to Newtown.
I drove from Melbourne CBD to Fitzroy.
I got a rideshare from Brisbane CBD to Brisbane Airport.
```

The goal is not to make the text preprocessor guess distances. The goal is:

```text
text route intent
-> maintained place resolution
-> snapped route-network nodes
-> mode-aware offline route/cache distance
-> visible confidence, assumptions, issues, and diagnostics
```

## Shared Scope Rules

All tickets in this document must follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`
- `docs/carboncoach-v2-qgis-geospatial-ticket.md`
- `docs/qgis-geospatial-data-workflow.md`

QGIS remains an offline data-preparation workflow only. Do not add QGIS,
GDAL, desktop GIS tools, Google Maps, or external routing services as live
FastAPI request dependencies.

Runtime should load compact repo-bundled or deployment-bundled artifacts such
as JSONL, CSV, or simplified GeoJSON.

Tests must not require live:

```text
QGIS
Climatiq
OpenRouter
Hugging Face
Google Cloud Storage
Google Maps
OSRM servers
external routing APIs
```

Use small deterministic fixture artifacts in tests.

## Shared Acceptance Rules

Every ticket must prove:

- explicit user quantities override inferred route distances
- unknown and ambiguous places fail safely with visible issues
- provider failures are isolated to the affected event
- mixed journals do not bleed origin, destination, region, mode, or distance
  context across events
- inferred values are visible through parameters, assumptions, issues, or
  diagnostics
- artifact imports validate schema, references, counts, source metadata, and
  manifest updates
- pipeline logic does not hard-code complete journal sentences or one-off
  city pairs

## Ticket 13: QGIS Gazetteer Import For Australian Places

### Goal

Replace hand-maintained city aliases with a QGIS-exported place gazetteer that
can support broad Australian place resolution.

### Dependencies

Ticket 12.

### Backend Scope

Add or extend importer support for:

```text
places.geojson
```

Supported place families:

- cities
- suburbs
- localities
- CBDs
- train stations
- airports
- common points of interest

Each imported place must support:

```text
place_id
name
aliases
place_type
region
latitude
longitude
source
source_version
```

Generated runtime artifact:

```text
app/data/geospatial/place_aliases.jsonl
```

### Non-Goals

- Do not implement road-network routing in this ticket.
- Do not add map UI.
- Do not add live geocoding.
- Do not silently invent aliases from user journals.

### Acceptance Criteria

- Given `places.geojson` with city, suburb, station, airport, and POI records,
  the importer writes deterministic `place_aliases.jsonl`.
- Importer rejects records missing `place_id`, `name`, `region`,
  coordinates, or aliases.
- Importer rejects duplicate `place_id`.
- Importer reports duplicate aliases that point to multiple places unless
  they are explicitly allowed as ambiguous.
- `Surry Hills`, `Newtown`, `Melbourne CBD`, `Brisbane Airport`,
  `Sydney Airport`, `Central Station`, `Parramatta`, and `Bondi` resolve.
- `Springfield` returns ambiguous when multiple records share that alias.
- `Springfield QLD` resolves specifically to the Queensland record.
- `Unknown Place` returns unresolved with `location.place_unresolved`.
- Runtime tests run without QGIS, network, GCS, or external routing.
- Manifest records artifact source, CRS, generated timestamp, counts, and
  validation status.

### Tests

Add importer tests for valid records, missing fields, duplicate `place_id`,
intentional ambiguous aliases, and accidental duplicate aliases.

Add resolver tests for the specific aliases above plus at least one unseen
city/suburb from the fixture.

Add one pipeline test proving a resolved origin/destination can reach the
existing distance-provider stage, even if the route remains approximate or
unavailable.

## Ticket 14: Alias, State Context, And Typo Resolution

### Goal

Make proper-noun resolution robust while preserving original user text.

### Dependencies

Tickets 12 and 13.

### Backend Scope

Extend `PlaceResolver` behavior for:

- casing and punctuation normalization
- abbreviation aliases such as `Melb` and `Bris`
- state hints such as `NSW`, `VIC`, and `QLD`
- conservative fuzzy matching for place aliases
- ambiguity handling

Fuzzy resolution belongs in the resolver, not in the broad journal
preprocessor.

### Non-Goals

- Do not globally autocorrect user text before extraction.
- Do not fuzzy-match very short administrative tokens such as `WA`, `SA`,
  `NT`, or `CBD`.
- Do not guess when multiple candidates are close.

### Acceptance Criteria

- `Melb to Bris` resolves to Melbourne and Brisbane using maintained aliases.
- `Surry Hils to Newtown` resolves `Surry Hils` to `Surry Hills` with
  `match_type=fuzzy_alias`.
- Original text remains visible as `origin="Surry Hils"` while resolved
  parameters include `origin_place_name="Surry Hills"`.
- `Springfield to Brisbane` remains ambiguous if no state context exists.
- `Springfield QLD to Brisbane` resolves to Springfield QLD.
- `Newcastle to Sydney` resolves to Newcastle NSW unless another maintained
  Newcastle record makes the alias ambiguous.
- Fuzzy matching does not rewrite short tokens such as `WA`, `SA`, `NT`, or
  `CBD`.
- Low-confidence typo matches return unresolved instead of guessing.
- Ambiguous fuzzy matches produce `location.place_ambiguous`.
- Fuzzy assumptions appear in output and UI.
- `I drove 8 km from Surry Hils to Newtown` keeps the explicit `8 km`.

### Tests

Add table-driven resolver tests for exact aliases, abbreviations, state-hinted
aliases, one clear typo, one ambiguous typo, and one rejected low-confidence
typo.

Add pipeline tests for explicit distance override, inferred distance, and
mixed journals that include fuzzy route plus unrelated energy.

## Ticket 15: QGIS Road Network Artifact Import

### Goal

Import a real routable road graph prepared offline in QGIS or another offline
GIS/routing workflow.

### Dependencies

Ticket 13.

### Backend Scope

Add importer support for:

```text
road_network_nodes.geojson
road_network_edges.geojson
```

Edge fields:

```text
edge_id
from_node_id
to_node_id
distance_km
modes
bidirectional
source
confidence
source_version
```

Generated runtime artifacts may be:

```text
road_network_nodes.jsonl
road_network_edges.jsonl
```

### Non-Goals

- Do not require a full national road graph in the repo.
- Do not implement place snapping yet.
- Do not use road graph edges for public transport in this ticket.

### Acceptance Criteria

- Importer accepts valid node and edge GeoJSON exports.
- Importer rejects edges whose nodes do not exist.
- Importer rejects negative, zero, or non-numeric distances.
- Importer rejects unsupported modes.
- Importer preserves one-way restrictions.
- Importer supports `car_ride` and `rideshare` as road modes without
  duplicating importer logic.
- Generated graph artifacts are compact and load at runtime without QGIS.
- Manifest includes node count, edge count, connected component count,
  mode coverage, source version, and validation status.
- Fixture graph includes at least one disconnected component and proves
  unreachable routes do not estimate silently.

### Tests

Add importer tests for valid graph import, unknown node references, invalid
distance, unsupported mode, and one-way/bidirectional semantics.

Add graph-loading tests that prove the runtime artifact can be parsed without
GeoJSON geometry.

## Ticket 16: Place-To-Road-Node Snapping

### Goal

Connect resolved places to routable road-network nodes.

### Dependencies

Tickets 13 and 15.

### Backend Scope

Add importer/runtime support for:

```text
place_route_nodes.csv
```

or equivalent GeoJSON/JSONL export with:

```text
place_id
mode
node_id
snap_distance_m
snap_confidence
snap_source
source_version
```

The runtime route provider should use snapped nodes before centroid fallback.

### Non-Goals

- Do not calculate snap points at runtime.
- Do not route arbitrary street addresses.
- Do not remove centroid fallback; make it a lower-confidence fallback.

### Acceptance Criteria

- Importer accepts valid place-to-node snap rows.
- Importer rejects snap rows for unknown places or unknown nodes.
- Importer rejects snap distances above the configured threshold unless the
  row is explicitly marked approximate.
- `Surry Hills` and `Newtown` resolve to road nodes for rideshare/car.
- Airports and CBDs can have different snapped nodes by mode if supplied.
- If origin snaps but destination does not, route is unresolved or approximate
  with a visible issue.
- If both places snap and graph path exists, centroid fallback is not used.
- Output includes `origin_route_node_id`, `destination_route_node_id`,
  `snap_confidence`, and `snap_source` in details or diagnostics.
- UI distinguishes `road network route` from `centroid approximation`.
- Explicit distance still bypasses routing even if snapped nodes exist.

### Tests

Add importer tests for valid snaps, unknown place, unknown node, excessive snap
distance, and mode-specific snaps.

Add pipeline tests for snapped route, one missing snap, and explicit distance
override.

## Ticket 17: Runtime Road Graph Routing For Car And Rideshare

### Goal

Calculate real offline road-network distances for casual car and rideshare
entries.

### Dependencies

Tickets 13, 15, and 16.

### Backend Scope

Extend `RouteDistanceProvider` to route between snapped road nodes using a
deterministic shortest-path algorithm over runtime graph artifacts.

The provider must be mode-aware for:

```text
car_ride
rideshare
```

### Non-Goals

- Do not add live routing APIs.
- Do not route train/bus here.
- Do not replace exact route cache priority.
- Do not estimate if no graph path exists unless the centroid fallback policy
  explicitly allows lower-confidence approximation.

### Acceptance Criteria

- `I took an Uber from Surry Hills to Newtown` estimates using graph-derived
  road distance.
- `I got a rideshare from Brisbane CBD to Brisbane Airport` estimates using a
  rideshare-compatible road graph.
- `I drove from Melbourne CBD to Fitzroy` estimates using a car-compatible
  road graph.
- `I drove 10 km from Melbourne CBD to Fitzroy` keeps `10 km` and does not
  override with graph distance.
- If no path exists between snapped nodes, output includes
  `route.distance_unavailable`.
- If provider raises an exception, only that event is affected.
- Mixed journal with route, electricity, and food keeps parameters isolated.
- Route output includes route source, route confidence, route exactness,
  graph/source version, and route path summary.
- One-way edge test proves route A to B can differ from B to A when the graph
  says so.
- Mode test proves train/bus routes do not use the car/rideshare graph.
- Performance test proves routing over the fixture graph stays below a
  deterministic threshold.

### Tests

Add provider tests for shortest path, one-way behavior, no-path behavior,
mode filtering, and provider exception isolation.

Add pipeline tests for the three named route families plus one unseen route
from the same fixture graph.

## Ticket 17B: Real Offline Road Data Layer Seed Build

### Goal

Replace the tiny hand-maintained road-routing fixtures with a reproducible
offline geospatial data build for Sydney, Melbourne, and Brisbane seed
coverage.

This ticket exists because Ticket 17 proves the runtime routing algorithm, but
offline routing is only useful when the app has a credible maintained data
layer. The output of this ticket is a source-noted, QA-checked, regenerated
artifact set that the existing `RouteDistanceProvider` can load without live
QGIS, live routing APIs, or manual row-by-row fixture authoring.

### Dependencies

Tickets 13, 15, 16, and 17.

Ticket 21 is not a dependency, but this ticket should implement enough local QA
checks to avoid importing obviously broken source data. Ticket 21 can later
promote those checks into a formal CLI/report command.

### Source Data Scope

Use real open geospatial sources, with licenses recorded in the manifest.

Preferred source families:

- OpenStreetMap road network extracts from Geofabrik or an equivalent
  reproducible OSM extract source.
- ABS ASGS Suburbs and Localities for Australian suburb/locality names,
  boundaries, and centroids.
- Maintained CBD, airport, station, and common POI records from official open
  data or reviewed OSM/Overture sources where ABS SAL alone is insufficient.
- Optional G-NAF only for future address-level work; do not require the large
  national address file for this seed road-routing ticket.
- Optional GTFS feeds only for station/stop gazetteer cross-checking; do not
  build train/bus routing here.

Candidate source URLs to evaluate and pin in the source manifest:

```text
OpenStreetMap / Geofabrik Australia:
https://download.geofabrik.de/australia-oceania/australia.html

ABS ASGS Suburbs and Localities:
https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/non-abs-structures/suburbs-and-localities

G-NAF on data.gov.au, optional for later address-level support:
https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf

Overture Maps, optional places/transportation cross-check:
https://docs.overturemaps.org/

Transport for NSW GTFS, optional future transit layer:
https://opendata.transport.nsw.gov.au/

Public Transport Victoria / Transport Victoria open data, optional future transit layer:
https://www.ptv.vic.gov.au/footer/data-and-reporting/datasets/

Queensland TransLink GTFS, optional future transit layer:
https://www.data.qld.gov.au/dataset/1c4c0295-135f-48d8-bc26-7391ffc5fd70
```

Minimum geographic scope:

```text
Sydney metro
Melbourne inner metro
Brisbane / South East Queensland airport corridor
```

The seed build should cover at least:

```text
Sydney CBD
Surry Hills
Newtown
Parramatta
Bondi
Sydney Airport
Melbourne CBD
Fitzroy
Brisbane CBD
Brisbane Airport
```

### Data Pipeline Scope

Add a reproducible offline data-build workflow under a scriptable path such as:

```text
scripts/geospatial/
data/geospatial/source_manifest.example.json
data/geospatial/qgis_exports/
```

The workflow should:

- download or accept pinned source extracts with dates and checksums
- clip source data to the scoped metro areas
- normalize CRS to `EPSG:4326`
- extract drivable road segments and preserve one-way metadata
- split or normalize road segments into stable graph nodes and edges
- calculate edge distance in kilometres from geometry
- create canonical place records and aliases from maintained source layers
- generate reviewed place-to-road-node snaps for `car_ride` and `rideshare`
- reject snap distances above threshold unless explicitly reviewed as
  approximate
- write compact runtime artifacts:

```text
place_aliases.jsonl
road_network_nodes.jsonl
road_network_edges.jsonl
place_route_nodes.jsonl
manifest.json
```

QGIS may be used as the review and export workbench, but the final build must
be reproducible enough that an agent can regenerate the runtime artifacts from
documented source inputs. Do not make the runtime depend on QGIS project files.

### Backend/Data Scope

Extend import/build tooling if needed so generated road artifacts are not
created by hand.

The importer or build script must validate:

- source files exist and match the manifest
- source license/attribution fields are present
- place IDs are stable and unique
- aliases are unique unless explicitly allowed as ambiguous
- graph node IDs are stable and unique
- road edges reference existing nodes
- edge distances are positive and numeric
- modes are limited to `car_ride` and `rideshare`
- one-way restrictions are preserved
- snaps reference known places and known nodes
- disconnected components are reported
- key seed places are snapped for both road modes
- key seed route pairs have either graph coverage or a visible no-path result

### Non-Goals

- Do not claim national Australian routing coverage.
- Do not ship full-size raw OSM, G-NAF, GTFS, or QGIS project files in the app
  runtime.
- Do not use Google Maps, live OSRM, live routing APIs, or live geocoding.
- Do not manually author individual route rows as the main data strategy.
- Do not add train/bus graph routing; that remains Ticket 19.
- Do not support arbitrary street-address routing in this ticket.
- Do not hide license obligations or source uncertainty.

### Acceptance Criteria

- A documented source manifest identifies every source dataset, URL or local
  source path, version/date, license, attribution text, checksum where
  practical, and processing notes.
- The generated runtime artifact set is created from real source extracts, not
  only from hand-authored fixture rows.
- The repo keeps compact generated artifacts only; large raw source extracts
  are ignored or documented as external inputs.
- The build produces at least one connected drivable graph component each for
  Sydney, Melbourne, and Brisbane seed coverage.
- `Surry Hills -> Newtown`, `Brisbane CBD -> Brisbane Airport`, and
  `Melbourne CBD -> Fitzroy` estimate end to end through the graph data.
- `Parramatta -> Bondi` has graph coverage or an explicitly documented no-path
  reason if the seed clip is intentionally smaller.
- A route whose places are snapped but disconnected returns
  `route.distance_unavailable` instead of falling through silently.
- Explicit user distance continues to override generated graph distance.
- The manifest records place count, road node count, road edge count, snap
  count, connected component count by mode, mode coverage, source versions,
  CRS, license notes, generated timestamp, and validation status.
- The build reports unsnapped seed places, duplicate aliases, unknown
  references, unsupported modes, and disconnected components.
- Tests do not require live QGIS, live downloads, live routing APIs, GCS,
  Climatiq, OpenRouter, or Hugging Face.
- Pipeline logic remains data-driven and does not hard-code complete journal
  sentences or one-off city pairs.

### Tests And Verification

Add fixture-backed tests for:

- source manifest parsing and required source metadata
- generated place aliases from a tiny ABS-like SAL fixture
- generated road graph nodes/edges from a tiny OSM-like road fixture
- one-way road handling from source tags
- place-to-node snap generation and threshold validation
- disconnected component reporting
- seed route checklist coverage
- explicit distance override
- snapped no-path unresolved behavior
- mixed journal isolation with generated graph route, electricity, and food

Run:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

If the build tooling includes optional download commands, keep networked source
download tests separate from CI and provide deterministic local fixtures for
normal test runs.

## Ticket 18: Offline OD Cache For Common Routes

### Goal

Use precomputed origin/destination route distances for common routes, while
keeping graph routing and approximation as fallbacks.

### Dependencies

Tickets 13 and 17.

### Backend Scope

Extend importer support for:

```text
route_distances.csv
```

Required fields:

```text
origin_place_id
destination_place_id
mode
distance
distance_unit
distance_source
confidence
source_version
bidirectional
```

Route resolution priority:

```text
explicit user distance
-> exact OD cache
-> snapped road graph
-> centroid approximation
-> unresolved
```

### Non-Goals

- Do not make the OD cache the only routing mechanism.
- Do not infer reverse routes unless the cache says they are bidirectional or
  a reverse record exists.

### Acceptance Criteria

- Importer accepts valid route cache rows.
- Importer rejects unknown places, unsupported modes, or non-positive
  distances.
- Exact cache wins over graph routing.
- Reverse route is used only if the record is marked bidirectional or reverse
  record exists.
- `Parramatta to Bondi` uses exact cache when available.
- `Bondi to Parramatta` uses reverse only if allowed.
- If cache exists for `car_ride` but user says `train`, cache is not used.
- If cache missing but graph path exists, graph route is used.
- If both cache and graph missing but places resolve, centroid fallback is
  used with lower confidence.
- Output clearly shows `distance_source=route_cache` or source-specific value.
- Tests prove no complete sentence is hard-coded in pipeline logic.

### Tests

Add importer tests for valid cache, unknown place, bad distance, unsupported
mode, and bidirectional behavior.

Add provider tests for cache priority, mode mismatch, graph fallback, centroid
fallback, and unresolved no-route behavior.

## Ticket 19: Public Transport Geospatial Layer

### Goal

Handle train and bus routes with transit-specific place and route artifacts
instead of road-distance approximations.

### Dependencies

Tickets 13 and 18.

### Backend Scope

Add importer/runtime support for:

- station and stop gazetteer records
- GTFS/QGIS-derived train route edges or exact station-to-station distances
- bus route edges or reviewed bus OD cache rows

Mode-aware support:

```text
train_ride
bus_ride
```

### Non-Goals

- Do not build a full timetable engine.
- Do not estimate wait time, transfers, or occupancy.
- Do not use train/bus artifacts for car/rideshare routes.

### Acceptance Criteria

- Importer accepts station/stop gazetteer records.
- Importer accepts GTFS/QGIS-derived train route edges.
- `Redfern to Chatswood by train` uses rail/GTFS path, not car road graph.
- `Central to Parramatta by train` resolves station aliases and estimates if a
  path exists.
- `Bus from Bondi to Sydney CBD` uses bus-compatible route artifact if
  available.
- If station exists but no transit path exists, route is unresolved with
  `route.distance_unavailable`.
- `I drove from Redfern to Chatswood` uses road mode, not rail mode.
- `I took the train 12 km from Redfern to Chatswood` keeps explicit `12 km`.
- Mixed car/train journal keeps route graphs separate.
- Output includes transit route source and confidence.
- UI shows a public transport route source label.

### Tests

Add importer tests for station/stop records and transit edges.

Add pipeline tests for train, bus, explicit distance override, wrong-mode
separation, no-path unresolved, and mixed car/train journals.

## Ticket 20: Location Confidence And UI Transparency

### Goal

Make location-derived estimates understandable in the product UI.

### Dependencies

Tickets 13-19, or any subset that adds new route provenance fields.

### Backend Scope

Normalize response fields if needed so frontend does not depend on provider
internals.

Do not change core geospatial behavior unless display correctness requires a
small response-shape adjustment.

### Frontend Scope

Activity cards and details should render:

- origin and destination when available
- resolved place names when different from user text
- distance source
- route exactness
- confidence/source labels
- fuzzy-match assumptions
- unresolved place/route issues

Source labels must distinguish:

```text
explicit user distance
exact route cache
road graph route
transit graph route
centroid approximation
unresolved place
```

### Non-Goals

- Do not add a map unless explicitly scoped in a later ticket.
- Do not expose internal IDs in the main card.
- Do not create per-city UI branches.

### Acceptance Criteria

- Activity card shows origin/destination when available.
- Estimated route distance source is visible.
- Approximate routes show an assumption in the card/details.
- Ambiguous or unresolved places show actionable Needs Attention messages.
- Internal IDs do not clutter the main activity card.
- Details tab includes IDs/source version for audit/debug.
- Fuzzy matches show original text and matched place.
- Explicit user distance does not show route-inference assumption.
- Mobile layout does not overlap or truncate key route text.
- Tests cover rendered output for resolved, approximate, ambiguous, and
  unresolved route states.

### Tests And Verification

Add frontend tests for resolved route, approximate route, fuzzy place match,
ambiguous place, unresolved place, and explicit distance override.

Run:

```powershell
npm run build
```

If browser tooling is available, verify the visible UI with at least one
resolved route, one approximate route, and one unresolved route.

## Ticket 21: Geospatial Artifact QA Command

### Goal

Make geospatial data quality measurable before deployment.

### Dependencies

Tickets 13-19.

### Backend Scope

Add a CLI/report command that inspects runtime geospatial artifacts and emits
JSON plus Markdown summaries.

The report should include:

- place counts by region and place type
- duplicate aliases
- intentionally ambiguous aliases
- accidental ambiguous aliases
- unsnapped places
- graph node/edge counts by mode
- disconnected components by mode
- route cache coverage
- common route checklist coverage
- manifest source/version validation

### Non-Goals

- Do not run QGIS in CI.
- Do not require live downloads.
- Do not block local development on warnings unless they are critical.

### Acceptance Criteria

- CLI reports place count by region and place type.
- CLI reports duplicate aliases.
- CLI reports intentionally ambiguous aliases separately from accidental
  duplicates.
- CLI reports unsnapped places.
- CLI reports graph node/edge counts by mode.
- CLI reports disconnected components by mode.
- CLI reports common route coverage from a maintained route checklist.
- CLI exits nonzero on critical validation failures.
- CLI writes JSON and Markdown reports.
- CI can run it without QGIS/network.
- Manifest records the QA report checksum/status.
- Test fixture includes intentional failures to prove the validator catches
  them.

### Tests

Add fixture-based CLI tests for passing artifacts, duplicate aliases, unknown
snap references, disconnected components, missing manifest metadata, and
critical exit status.

## Ticket 22: Route Coverage Seed Pack For Common Australian Journeys

### Goal

Add a useful starter pack of maintained, source-noted common Australian
routes, without pretending to have exhaustive national coverage.

### Dependencies

Tickets 13, 18, and 21. Ticket 17 is recommended if graph fallback is already
available.

### Backend/Data Scope

Add source-noted OD cache or graph coverage for common local journeys in
Sydney, Melbourne, and Brisbane.

Minimum seed set:

```text
Sydney CBD <-> Bondi
Sydney CBD <-> Parramatta
Surry Hills <-> Newtown
Melbourne CBD <-> Fitzroy
Melbourne CBD <-> St Kilda
Brisbane CBD <-> Brisbane Airport
Brisbane CBD <-> Fortitude Valley
```

Each route must include:

```text
origin_place_id
destination_place_id
mode
distance
distance_unit
distance_source
confidence
source_version
bidirectional
source notes
```

### Non-Goals

- Do not claim national coverage.
- Do not add unsupported route pairs as code branches.
- Do not mix car/rideshare route data with train/bus route data.

### Acceptance Criteria

- Adds maintained route cache or graph coverage for the minimum seed set.
- Each route has source, confidence, mode, and source version.
- Rideshare/car routes are separate from train/bus routes.
- Explicit distance still wins for every covered route.
- Unknown place still fails safely.
- Ambiguous place still fails safely unless context disambiguates.
- Tests verify each seed route estimates end to end.
- Tests include at least one unseen route that follows the same data path.
- Manifest states this is a seed pack, not exhaustive national coverage.
- QA command reports seed route coverage.

### Tests

Add one pipeline regression per seed route and one mixed journal containing a
covered route, region-aware electricity, and unrelated not-estimated activity.

Add explicit-distance override tests for at least two seed routes.

## Recommended Implementation Order

Implement in this order:

```text
13. QGIS Gazetteer Import For Australian Places
14. Alias, State Context, And Typo Resolution
15. QGIS Road Network Artifact Import
16. Place-To-Road-Node Snapping
17. Runtime Road Graph Routing For Car And Rideshare
17B. Real Offline Road Data Layer Seed Build
18. Offline OD Cache For Common Routes
19. Public Transport Geospatial Layer
20. Location Confidence And UI Transparency
21. Geospatial Artifact QA Command
22. Route Coverage Seed Pack For Common Australian Journeys
```

Tickets 15-17 are the key shift from place-name enrichment to real offline
road-distance calculation for casual Uber/rideshare and car entries. Ticket
17B is the data-product correction: it turns the proven routing machinery from
fixture-backed behavior into a reproducible seed road layer built from real
open geospatial sources.
