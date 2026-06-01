# CarbonCoach V2 Ticket 12: QGIS-Backed Geospatial Enrichment

This document defines a vertical backend slice for using QGIS-prepared
geospatial data in the CarbonCoach V2 pipeline.

Ticket 12 assumes V2 already has structured extraction, quantity
normalization, entity enrichment, parameter builders, factor retrieval,
fallback behavior, and visible assumptions/issues. The gap addressed here is
location-aware activity data.

Agents implementing this ticket must also follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`
- `docs/carboncoach-v2-factor-intent-ticket.md`
- `docs/carboncoach-v2-common-factor-pathways-ticket.md`
- `docs/carboncoach-consumer-ui-ticket-plan.md`

## Why This Ticket Exists

The current V2 pipeline estimates transport when the user gives an explicit
distance and estimates electricity when the user gives an explicit energy
quantity. It also defaults electricity region to Australia when no region is
provided.

That is not enough for location-aware inputs such as:

```text
I drove from Parramatta to Bondi.
I used electricity at home in NSW.
I took the train from Redfern to Chatswood.
```

The system should understand:

```text
origin/destination place names
mode-specific route distance
state or grid-region hints
whether distance was explicit, routed, cached, or approximate
whether electricity quantity is missing versus region-only context
```

QGIS should improve the pipeline by preparing, validating, and exporting
reviewable geospatial lookup data. QGIS should not become a live runtime
dependency of the FastAPI request path.

## Goal

Add a geospatial enrichment layer so validated events can use location context
to build better parameters while preserving transparent uncertainty.

The engine should move from:

```text
event + normalized quantities
-> entity enrichment
-> parameter builder
```

to:

```text
event + normalized quantities
-> geospatial/location enrichment
-> entity enrichment
-> parameter builder
```

The location enrichment layer should:

- resolve maintained place aliases to canonical places and regions
- derive route distance for origin/destination transport inputs when no
  explicit distance was provided
- preserve explicit distance over inferred route distance
- detect Australian state or grid-region hints for energy events
- expose distance source, confidence, assumptions, and unresolved place issues
- keep tests deterministic with fixture-backed providers

## Vertical User Outcomes

### Route-Based Car Trip

Input:

```text
I drove from Parramatta to Bondi.
```

Expected behavior:

- extract a `transport` event with `activity_type: car_ride`
- preserve `origin: Parramatta` and `destination: Bondi`
- resolve both places through maintained geospatial data
- derive `distance` in kilometres using a route-distance provider
- estimate via the existing transport parameter/factor path
- expose a visible assumption if the distance is approximate rather than an
  exact routed distance

### NSW Electricity Region

Input:

```text
I used 5 kWh of electricity at home in NSW.
```

Expected behavior:

- extract an `energy` event with `activity_type: electricity_use`
- keep the explicit `energy: 5`, `energy_unit: kWh`
- detect `region: AU-NSW` or the selected provider's maintained NSW region key
- avoid adding `region.default_au_electricity`
- pass the region into the factor/estimate path where supported
- fall back visibly if only an Australia-wide factor is available

Input:

```text
I used electricity at home in NSW.
```

Expected behavior:

- preserve the NSW region context
- return `unresolved` because no energy quantity was supplied
- do not invent household electricity usage

### Route-Based Train Trip

Input:

```text
I took the train from Redfern to Chatswood.
```

Expected behavior:

- extract a `transport` event with `activity_type: train_ride`
- preserve `origin: Redfern` and `destination: Chatswood`
- resolve station/suburb aliases through maintained geospatial data
- derive passenger distance using a train-appropriate route provider or route
  cache
- estimate through the existing passenger-distance transport path
- expose route source and confidence

## Dependencies

- Ticket 10: semantic factor intent resolution
- Ticket 11: curated common factor pathway metadata overlay

Ticket 12 can be started before all route data is complete if the provider
interface, deterministic fixtures, and unresolved behavior are implemented
first.

## Non-Goals

Do not:

- install or launch QGIS inside the FastAPI runtime
- require QGIS for unit tests
- query Google Maps or other live map services during tests
- infer electricity consumption from "at home" without an explicit quantity or
  an approved profile feature
- silently replace explicit user distance with a routed distance
- treat centroid distance as exact routed distance
- hard-code only the three example routes in extraction logic
- weaken existing factor validation or confidence handling
- require live Climatiq, OpenRouter, Hugging Face, GCS, or external routing
  services in tests

## QGIS Role

Use QGIS as an offline data preparation and validation workbench.

Recommended QGIS workflow:

```text
raw GIS layers
-> CRS normalization
-> geometry repair and simplification where needed
-> suburb/station/place alias review
-> state/grid-region spatial joins
-> route-distance cache generation or route-layer validation
-> export compact app-ready JSONL/CSV/GeoJSON artifacts
```

The app should consume exported artifacts, not QGIS project files.

Suggested source families:

- Australian states and territories
- suburb/locality/place centroids
- public transport stops/stations and route shapes
- road or multimodal route-distance cache
- electricity region and factor applicability metadata

Every exported artifact must include source notes, version/date, CRS, license
or usage constraints, and generation script/tooling notes.

## Backend Scope

Create or extend primarily under:

```text
app/domain/
app/pipeline_v2/
app/data/
docs/
```

Suggested new files:

```text
app/domain/geospatial.py
app/pipeline_v2/location_enricher.py
app/data/geospatial/place_aliases.jsonl
app/data/geospatial/route_distances.jsonl
app/data/geospatial/electricity_regions.jsonl
app/data/geospatial/manifest.json
docs/qgis-geospatial-data-workflow.md
```

Expected existing files to touch:

```text
app/domain/models.py
app/domain/assumptions.py
app/pipeline_v2/event_extractor.py
app/pipeline_v2/quantity_normalizer.py
app/pipeline_v2/parameter_builders.py
app/pipeline_v2/emission_estimator.py
app/pipeline_v2/pipeline.py
app/pipeline_v2/retrieval_diagnostics.py
```

Keep edits scoped. The location layer should be a provider-backed enrichment
step, not a rewrite of extraction, retrieval, or fallback estimation.

## Data Contracts

Exact schemas may vary, but the runtime artifacts should support these
concepts.

### Place Alias Record

```json
{
  "place_id": "au-nsw-parramatta",
  "name": "Parramatta",
  "aliases": ["parramatta", "parramatta nsw"],
  "place_type": "suburb",
  "region": "AU-NSW",
  "latitude": -33.8136,
  "longitude": 151.0034,
  "source": "maintained geospatial export",
  "source_version": "YYYY-MM-DD"
}
```

### Route Distance Record

```json
{
  "origin_place_id": "au-nsw-redfern",
  "destination_place_id": "au-nsw-chatswood",
  "mode": "train_ride",
  "distance": 13.8,
  "distance_unit": "km",
  "distance_source": "gtfs_route_shape",
  "confidence": 0.85,
  "source_version": "YYYY-MM-DD"
}
```

### Electricity Region Record

```json
{
  "region": "AU-NSW",
  "region_name": "New South Wales",
  "country": "AU",
  "factor_region": "AU-NSW",
  "fallback_region": "AU",
  "source": "maintained electricity-region mapping",
  "source_version": "YYYY-MM-DD"
}
```

## Provider Interfaces

Add provider interfaces so production and tests can use different data sources:

```text
PlaceResolver
RouteDistanceProvider
ElectricityRegionResolver
```

Required behavior:

- return structured successes with confidence and source
- return typed misses for unknown or ambiguous places
- never throw through the main pipeline for normal missing data
- isolate provider failures to the affected event
- make all inferred values visible in parameters, assumptions, issues, or
  diagnostics

## Pipeline Behavior

### Transport

If a transport event has explicit distance:

- keep the explicit distance
- optionally enrich origin/destination metadata
- do not override the explicit quantity

If a transport event has origin and destination but no distance:

- resolve places
- request a route distance for the activity type
- add a `distance` quantity if a suitable route is found
- if only centroid approximation is available, mark lower confidence and add a
  visible assumption
- if no route is available, return unresolved with a place/route issue

Suggested parameter fields:

```json
{
  "distance": 31.2,
  "distance_unit": "km",
  "distance_source": "route_cache",
  "origin": "Parramatta",
  "destination": "Bondi",
  "origin_region": "AU-NSW",
  "destination_region": "AU-NSW"
}
```

### Energy

If an energy event includes a maintained region hint:

- preserve `region`
- include the region in parameters
- pass the region into selector filters or factor intent metadata where
  supported
- avoid default-Australia assumptions when the user gave a usable region

If no energy quantity exists:

- keep region context
- return unresolved with the existing missing-quantity issue
- do not infer household energy usage

## Assumptions And Issues

Add assumptions such as:

```text
route.distance.from_route_cache
route.distance.estimated_from_place_centroids
region.energy.user_supplied
region.energy.fallback_to_country
```

Add issues such as:

```text
location.place_unresolved
location.place_ambiguous
route.distance_unavailable
route.mode_not_supported
energy.region_factor_unavailable
```

Assumptions should explain how a value entered the calculation. Issues should
explain why a location-aware estimate could not be completed or why fallback
was needed.

## Test Scope

Add unit tests for:

- place alias resolution
- ambiguous and unknown place handling
- state/region detection for NSW and at least one other Australian state
- route provider exact-distance success
- route provider approximate-distance fallback
- provider failure isolation

Add pipeline tests for:

```text
I drove from Parramatta to Bondi.
I took the train from Redfern to Chatswood.
I used 5 kWh of electricity at home in NSW.
I used electricity at home in NSW.
I drove 10 km from Parramatta to Bondi.
I drove from Unknown Place to Bondi.
```

Expected test behavior:

- route-based car and train examples become estimated when fixture route data
  exists
- explicit `10 km` is preserved over any routed value
- region-aware electricity with `5 kWh` is estimated and carries NSW context
- region-only electricity remains unresolved because quantity is missing
- unknown place returns a visible issue instead of silently dropping the event

Tests must not require installed QGIS or live routing services.

## Frontend Visibility

Where result details are shown, expose:

- origin and destination when present
- distance source
- region source
- route/geospatial assumptions
- unresolved place or route issues

Do not add map UI in this ticket unless it is necessary to make the backend
behavior understandable. The primary slice is backend correctness and
transparency.

## Acceptance Criteria

This ticket is complete when:

- a `LocationEnricher` or equivalent provider-backed stage exists in V2
- QGIS-prepared app artifacts can be loaded from the repo
- route-origin/destination transport inputs can produce distance parameters
  through deterministic route fixtures
- NSW electricity context is preserved and used when an energy quantity exists
- missing quantities still remain unresolved
- explicit distances are never overwritten by inferred route distances
- assumptions/issues distinguish exact route cache, approximate route, unknown
  place, and missing quantity cases
- focused tests pass without QGIS, network, Climatiq, or external GIS services
- documentation explains how to regenerate the geospatial artifacts from QGIS

## Open Decisions

Resolve before broad rollout:

- authoritative place data source and license
- exact route-distance source: GTFS shapes, OSRM, pgRouting, maintained cache,
  or provider API
- whether electricity region should map to Climatiq region codes, local grid
  factor tables, or both
- how much geospatial data should ship in the repo versus blob storage
- privacy posture for user-entered places if future live routing is added
