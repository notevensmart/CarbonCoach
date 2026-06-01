from __future__ import annotations

from app.domain.assumptions import (
    place_fuzzy_match_assumption,
    route_cache_distance_assumption,
    route_centroid_distance_assumption,
    route_network_distance_assumption,
    user_supplied_energy_region_assumption,
)
from app.domain.geospatial import (
    ElectricityRegionResolver,
    LocalElectricityRegionResolver,
    LocalPlaceResolver,
    LocalRouteDistanceProvider,
    PlaceRecord,
    PlaceResolver,
    PlaceResolution,
    RouteDistanceProvider,
)
from app.domain.models import CarbonEvent, Issue, Quantity


class LocationEnricher:
    def __init__(
        self,
        place_resolver: PlaceResolver | None = None,
        route_distance_provider: RouteDistanceProvider | None = None,
        electricity_region_resolver: ElectricityRegionResolver | None = None,
    ) -> None:
        self.place_resolver = place_resolver or LocalPlaceResolver()
        self.route_distance_provider = route_distance_provider or LocalRouteDistanceProvider()
        self.electricity_region_resolver = (
            electricity_region_resolver or LocalElectricityRegionResolver()
        )

    def enrich(self, event: CarbonEvent) -> CarbonEvent:
        try:
            if event.category == "transport":
                return self._enrich_transport(event)
            if event.category == "energy":
                return self._enrich_energy(event)
            return event
        except Exception as exc:
            return event.model_copy(
                update={
                    "issues": [
                        *event.issues,
                        Issue(
                            code="location.provider_unavailable",
                            message=(
                                "Location enrichment was unavailable for this activity; "
                                f"continued without inferred location data. ({exc})"
                            ),
                            severity="warning",
                        ),
                    ]
                }
            )

    def _enrich_transport(self, event: CarbonEvent) -> CarbonEvent:
        origin_text = _entity_text(event.entities.get("origin"))
        destination_text = _entity_text(event.entities.get("destination"))
        if not origin_text or not destination_text:
            return event

        entities = dict(event.entities)
        assumptions = list(event.assumptions)
        issues = list(event.issues)

        origin = self._resolve_place(origin_text, "origin", entities, assumptions, issues)
        destination = self._resolve_place(
            destination_text,
            "destination",
            entities,
            assumptions,
            issues,
        )
        if _has_quantity(event, "distance"):
            return event.model_copy(
                update={
                    "entities": entities,
                    "assumptions": assumptions,
                    "issues": issues,
                }
            )
        if origin is None or destination is None:
            return event.model_copy(
                update={
                    "entities": entities,
                    "assumptions": assumptions,
                    "issues": issues,
                }
            )

        route = self.route_distance_provider.distance(
            origin,
            destination,
            event.activity_type,
        )
        if route.status == "mode_not_supported":
            issues.append(
                Issue(
                    code="route.mode_not_supported",
                    message=(
                        f"No maintained route-distance provider is configured for "
                        f"{event.activity_type} origin/destination enrichment."
                    ),
                    severity="warning",
                )
            )
            return event.model_copy(
                update={"entities": entities, "assumptions": assumptions, "issues": issues}
            )
        if route.status != "resolved" or route.distance is None:
            issues.append(
                Issue(
                    code="route.distance_unavailable",
                    message=(
                        f"No maintained route distance was available from {origin.name} "
                        f"to {destination.name} for {event.activity_type}."
                    ),
                    severity="warning",
                )
            )
            return event.model_copy(
                update={"entities": entities, "assumptions": assumptions, "issues": issues}
            )

        entities.update(
            {
                "distance_source": route.distance_source,
                "distance_confidence": route.confidence,
                "distance_inferred": True,
                "route_exact": route.exact,
                "route_source_version": route.source_version,
            }
        )
        if route.route_path_place_ids:
            entities["route_path_place_ids"] = "|".join(route.route_path_place_ids)
        if route.route_path_place_names:
            entities["route_path_place_names"] = " -> ".join(route.route_path_place_names)
        assumptions.append(
            _route_distance_assumption(
                origin.name,
                destination.name,
                event.activity_type,
                route.distance_source or "",
                route.exact,
            )
        )
        quantities = [
            *event.quantities,
            Quantity(
                value=float(route.distance),
                unit=route.distance_unit,
                dimension="distance",
                surface=f"{origin_text} to {destination_text}",
                confidence=route.confidence,
            ),
        ]
        return event.model_copy(
            update={
                "quantities": quantities,
                "entities": entities,
                "assumptions": assumptions,
                "issues": issues,
            }
        )

    def _resolve_place(
        self,
        query: str,
        role: str,
        entities: dict,
        assumptions: list,
        issues: list[Issue],
    ) -> PlaceRecord | None:
        resolution = self.place_resolver.resolve_place(query)
        if resolution.status == "resolved" and resolution.record is not None:
            _add_place_entities(entities, role, resolution)
            if resolution.match_type == "fuzzy_alias":
                assumptions.append(
                    place_fuzzy_match_assumption(
                        query,
                        resolution.record.name,
                        role,
                        resolution.confidence,
                    )
                )
            return resolution.record
        if resolution.status == "ambiguous":
            candidate_names = ", ".join(candidate.name for candidate in resolution.candidates)
            issues.append(
                Issue(
                    code="location.place_ambiguous",
                    message=(
                        f"The {role} place {query} matched multiple maintained places: "
                        f"{candidate_names}."
                    ),
                    severity="warning",
                )
            )
            return None
        issues.append(
            Issue(
                code="location.place_unresolved",
                message=f"Could not resolve the {role} place {query} from maintained aliases.",
                severity="warning",
            )
        )
        return None

    def _enrich_energy(self, event: CarbonEvent) -> CarbonEvent:
        resolution = self.electricity_region_resolver.resolve_region(event.raw_text)
        if resolution.status == "unknown":
            return event

        entities = dict(event.entities)
        assumptions = list(event.assumptions)
        issues = list(event.issues)
        if resolution.status == "ambiguous":
            candidate_names = ", ".join(
                candidate.region_name for candidate in resolution.candidates
            )
            issues.append(
                Issue(
                    code="energy.region_ambiguous",
                    message=(
                        "Multiple maintained electricity regions matched this activity: "
                        f"{candidate_names}."
                    ),
                    severity="warning",
                )
            )
            return event.model_copy(
                update={"entities": entities, "assumptions": assumptions, "issues": issues}
            )

        record = resolution.record
        if record is None:
            return event
        entities.update(
            {
                "region": record.region,
                "region_name": record.region_name,
                "factor_region": record.factor_region,
                "fallback_region": record.fallback_region,
                "region_source": record.source,
                "region_source_version": record.source_version,
                "region_confidence": resolution.confidence,
            }
        )
        if not any(assumption.code == "region.energy.user_supplied" for assumption in assumptions):
            assumptions.append(
                user_supplied_energy_region_assumption(
                    record.region,
                    record.region_name,
                )
            )
        return event.model_copy(
            update={
                "entities": entities,
                "assumptions": assumptions,
                "issues": issues,
            }
        )


def _add_place_entities(
    entities: dict,
    role: str,
    resolution: PlaceResolution,
) -> None:
    record = resolution.record
    if record is None:
        return
    entities.update(
        {
            f"{role}_place_id": record.place_id,
            f"{role}_place_name": record.name,
            f"{role}_place_type": record.place_type,
            f"{role}_region": record.region,
            f"{role}_latitude": record.latitude,
            f"{role}_longitude": record.longitude,
            f"{role}_source": record.source,
            f"{role}_source_version": record.source_version,
            f"{role}_confidence": resolution.confidence,
        }
    )
    if resolution.matched_alias:
        entities[f"{role}_matched_alias"] = resolution.matched_alias
    if resolution.match_type:
        entities[f"{role}_match_type"] = resolution.match_type


def _has_quantity(event: CarbonEvent, dimension: str) -> bool:
    return any(quantity.dimension == dimension for quantity in event.quantities)


def _route_distance_assumption(
    origin: str,
    destination: str,
    mode: str,
    distance_source: str,
    exact: bool,
):
    if not exact:
        return route_centroid_distance_assumption(origin, destination, mode)
    if "network" in distance_source:
        return route_network_distance_assumption(
            origin,
            destination,
            mode,
            distance_source,
        )
    return route_cache_distance_assumption(
        origin,
        destination,
        mode,
        distance_source or "route_cache",
    )


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""
