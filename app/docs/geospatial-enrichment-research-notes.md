# Geospatial Enrichment Research Notes

Ticket 12 now follows common geospatial engineering patterns instead of relying
on a table of demonstration routes.

## Techniques Adopted

- **Gazetteer-style place resolution:** user place strings resolve through
  maintained aliases to canonical place IDs. Unknown and ambiguous aliases
  remain typed outcomes, matching how production geocoders separate candidate
  generation from ranking and disambiguation.
- **Mode-aware route graph:** QGIS exports compact route-network edges by mode.
  Runtime computes distance with Dijkstra shortest path over those edges.
- **Layered route sources:** exact audited cache first, network shortest path
  second, centroid approximation last.
- **Transit shape compatibility:** rail and bus edges can be generated from
  GTFS route shapes or stop-to-stop summaries, preserving a separate mode graph
  rather than treating public transport like road travel.
- **Spatial region context:** electricity regions are maintained records and can
  be regenerated from QGIS spatial joins or reviewed state/grid-region overlays.
- **Provenance in output:** distance source, confidence, route path, place IDs,
  source versions, assumptions, and unresolved issues stay visible.

## References Used

- OSRM: production road routing engines commonly pre-process road networks for
  efficient shortest-path queries.
  <https://project-osrm.org/docs/>
- pgRouting: PostGIS routing workflows expose Dijkstra-style shortest path over
  graph tables.
  <https://docs.pgrouting.org/>
- OpenTripPlanner: transit routing engines combine OpenStreetMap and GTFS-style
  transit data for multimodal route planning.
  <https://docs.opentripplanner.org/>
- GTFS static reference: `shapes.txt` and `shape_dist_traveled` support route
  geometry and distance along a shape.
  <https://gtfs.org/schedule/reference/>
- Pelias: open geocoder architecture built around maintained place records and
  search indexes.
  <https://github.com/pelias/pelias>
- GeoPandas spatial joins: QGIS-equivalent spatial join behavior for assigning
  points to polygons such as states or grid regions.
  <https://geopandas.org/en/stable/docs/reference/api/geopandas.sjoin.html>
- Shapely STRtree: spatial indexes are the standard way to keep geometry
  lookup scalable when datasets grow.
  <https://shapely.readthedocs.io/en/stable/strtree.html>

## How This Maps To CarbonCoach

The runtime still uses compact repo-bundled artifacts, not live QGIS. The key
difference is that route examples now exercise a generic graph algorithm:

```text
place aliases
-> canonical place IDs
-> exact route cache if available
-> Dijkstra over QGIS-exported mode-aware edges
-> centroid fallback only when graph data is absent
```

This lets a new maintained edge or place record improve route coverage without
adding a new branch for a complete journal sentence or a specific origin and
destination pair.
