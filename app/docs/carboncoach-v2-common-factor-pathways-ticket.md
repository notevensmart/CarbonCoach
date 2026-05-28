# CarbonCoach V2 Ticket 11: Curated Common Factor Pathway Metadata Overlay

This document defines a follow-on data quality ticket after Ticket 10.

Ticket 10 gives the backend a semantic factor-intent layer. Ticket 11 gives
that layer better searchable metadata for the common personal pathways users
actually describe in daily journals.

Agents implementing this ticket must also follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`
- `docs/carboncoach-v2-everyday-coverage-ticket.md`
- `docs/carboncoach-v2-llm-extraction-tickets.md`
- `docs/carboncoach-v2-factor-intent-ticket.md`
- `docs/carboncoach-consumer-ui-ticket-plan.md`

## Why This Ticket Exists

The raw factor database is rich, but its rows are often too shallow for the
engine to connect ordinary user language to the right activity ID.

Raw metadata may include fields such as:

```text
activity_id
name
category
sector
source
unit_type
```

That is not always enough for queries like:

```text
Threw away 2 kg of plastic.
Bought two coffees.
Ordered a beef burrito.
Ran the heater while gaming.
```

Ticket 10 should resolve a structured intent, but retrieval still benefits
from curated metadata that says what each useful factor is actually for:

```text
allowed activity types
materials
methods
product classes
unit boundary
included/excluded terms
source quality
human-readable description
```

This ticket applies the 80/20 rule: enrich a focused set of common personal
pathways instead of trying to describe every database row.

## Goal

Create a source-noted, schema-validated metadata overlay for common personal
carbon pathways across the four supported categories:

```text
transport
energy
goods_services
waste
```

The overlay should improve factor search and selection without changing raw
Climatiq metadata files, weakening validation, or requiring manual Google
Cloud Storage updates.

## Dependencies

- Ticket 10: semantic factor intent resolution

Ticket 11 assumes that the pipeline can already generate structured factor
intents and pass them into retrieval. If Ticket 10 is incomplete, implement
only the overlay schema and tests that can run against fake metadata records,
then integrate after the intent resolver exists.

## Non-Goals

Do not:

- enrich every row in the database
- edit raw Climatiq CSV files directly
- require a GCS blob update for normal implementation
- add a new top-level `food` category
- let an LLM choose final activity IDs at runtime
- replace deterministic validation with search-score confidence
- estimate missing quantities only because an enriched row exists
- use live Climatiq, OpenRouter, Hugging Face, or GCS in tests

## GCP And Blob Storage Decision

Default implementation must be repo-bundled.

Create the overlay in the repository, for example:

```text
app/data/enriched_factor_metadata.jsonl
```

At runtime, load and merge the overlay with the existing local or GCS-loaded
raw factor metadata. The overlay must not require the user to manually update
blob storage on GCP.

Expected behavior:

- raw factor metadata may still come from local CSVs or GCS, as today
- the enriched overlay ships with the app code
- Docker or Cloud Run deployment includes the overlay because it is in the repo
- the loader merges overlay fields by `activity_id` or an explicit pathway key
- missing overlay data never breaks startup; it only reduces enriched retrieval

Only move this overlay to GCS later if the project intentionally chooses
centralized runtime data management. That is outside this ticket's default
scope.

## Overlay Shape

Create a reviewed schema for enriched factor metadata. Exact field names may
vary, but each overlay row should represent:

```json
{
  "activity_id": "example_activity_id",
  "description": "Plastic waste sent to landfill, measured by weight.",
  "carboncoach_category": "waste",
  "allowed_activity_types": ["landfill_waste"],
  "unit_type": "Weight",
  "preferred_terms": ["plastic waste", "landfill", "disposal", "end of life"],
  "excluded_terms": ["recycling", "compost", "purchase"],
  "semantic_dimensions": {
    "material_classes": ["plastic"],
    "disposal_methods": ["landfill"]
  },
  "calculation_boundary": "Disposal or treatment of plastic waste by mass.",
  "source_note": "Curated from factor name/category metadata and reviewed pathway taxonomy.",
  "source_quality_score": 0.85
}
```

The overlay may also support category-specific fields:

```text
transport_modes
fuel_types
vehicle_classes
energy_end_uses
product_classes
purchase_contexts
material_classes
disposal_methods
region_hints
fallback_pathway_key
```

Use controlled vocabularies. Unknown values should fail schema validation
rather than silently becoming search terms.

## Source-Backed Research Requirement

The implementation agent must not build the overlay only from examples in
this chat.

Create a small source-noted research artifact, for example:

```text
docs/carboncoach-v2-common-pathway-research.md
```

The research should identify common personal carbon pathways within the four
supported categories. It may use official or reputable public references such
as household emissions category guidance, transport/residential energy/waste
category references, and the database's own factor naming conventions.

The research artifact must:

- stay within `transport`, `energy`, `goods_services`, and `waste`
- explain why each pathway family is included
- document boundaries and exclusions
- avoid inventing unsupported categories
- note where local factor availability is required before estimation is safe

If the implementing agent uses web research, it must cite sources in the
research artifact. Automated tests must still be local and deterministic.

## Initial Pathway Coverage

Start with about 30-60 curated pathways. Prefer quality over volume.

Prioritize goods/services and waste first because those currently need the
most help connecting to useful factor IDs.

### Transport

Include common personal transport pathways:

```text
car ride by distance
petrol car by distance
diesel car by distance
electric car by distance
hybrid car by distance, if compatible factors exist
bus ride by passenger distance
train ride by passenger distance
taxi or rideshare by distance
flight by passenger distance, only if already supported safely
walking or cycling as no operational-emissions estimate boundary
```

Do not infer distance if missing.

### Energy

Include common household energy pathways:

```text
electricity use by kWh
space heater use from kWh or power x duration
air conditioning or cooling by kWh, if supported safely
hot water by energy, if supported safely
cooking appliance electricity by kWh, if supported safely
generic device electricity by kWh
PC, laptop, TV, console, and appliance use as unresolved unless sufficient
energy or maintained assumptions exist
```

Do not convert vague duration such as `all evening` into hours unless a
separate maintained assumption rule exists and is visible.

### Goods Services

Use `goods_services` for food, drinks, purchases, and services. Do not create
a top-level `food` category.

Include common goods/services pathways:

```text
coffee by serving/item, if compatible factor exists
beef by weight
meat or meal by serving, only with maintained compatible factor
restaurant meal by serving, if compatible factor exists
takeaway meal by serving, if compatible factor exists
groceries by spend or weight only when compatible factor exists
clothing by item or spend only when compatible factor exists
electronics purchase by item or spend only when compatible factor exists
generic purchase as unresolved unless a compatible broad factor is maintained
```

Do not convert money into item count. A spend input can only use a Money factor.

### Waste

Model material and disposal method independently.

Include common waste pathways:

```text
general landfill waste by weight
mixed packaging landfill waste by weight
plastic landfill waste by weight
cardboard or paper landfill waste by weight, if compatible factors exist
plastic recycling by weight
cardboard recycling by weight
paper recycling by weight
glass recycling by weight
metal recycling by weight
food waste composting by weight
food waste landfill by weight, if compatible factors exist
```

Do not infer recycling from recyclable-looking material. The user must
describe recycling, composting, landfill, rubbish, general waste, throwing
away, or an equivalent disposal context.

## Runtime Integration

Add a loader/merger around factor metadata.

Suggested files:

```text
app/domain/factor_metadata_overlay.py
app/pipeline_v2/factor_metadata_provider.py
app/data/enriched_factor_metadata.jsonl
```

The loader must:

- parse JSONL deterministically
- validate every row against a strict schema
- reject unknown categories and controlled-vocabulary values
- merge rows into raw metadata records by `activity_id`
- support pathway-key rows only when explicitly marked as local fallback or
  bootstrap metadata
- never mutate the raw CSV/GCS-loaded metadata in place
- expose enriched fields to Ticket 10 retrieval and diagnostics
- degrade gracefully if an activity ID from the overlay is not present in the
  local fake test records

## Retrieval Behavior

When Ticket 10 factor intents are available, enriched metadata should improve:

- candidate discovery
- ranking
- candidate rejection explanations
- specific-versus-generic fallback choice
- developer diagnostics

Expected behavior:

```text
intent semantic dimensions
+ enriched metadata preferred/excluded terms
+ hard unit/category validation
-> better candidate ranking
```

Enriched metadata must never override hard validation.

Examples:

```text
Threw away 2kg plastic
-> prefer plastic landfill Weight factor over general landfill factor
-> reject plastic recycling factor because method conflicts

Bought two coffees
-> prefer coffee serving/item factor if compatible
-> do not use spend-based factor unless the input is money and factor unit is Money

Ordered a beef burrito
-> prefer maintained meal/food-serving factor if available
-> unresolved or documented fallback if no safe factor exists
```

## Tests

Tests must not require live external services.

Add schema tests for:

- overlay JSONL parses successfully
- every row has a description and source note
- category is one of `transport`, `energy`, `goods_services`, `waste`
- no row uses top-level `food`
- unit type values are known
- activity types are controlled
- preferred and excluded terms are non-empty where useful
- semantic dimensions use controlled vocabularies
- source quality scores are bounded between 0 and 1
- duplicate `activity_id` overlay rows are rejected unless explicitly allowed

Add metadata merge tests for:

- overlay fields merge into fake raw metadata by `activity_id`
- raw records without overlay still work
- missing overlay file degrades safely in tests where optional
- invalid overlay rows fail fast in schema validation tests
- raw CSV/GCS metadata is not mutated in place

Add retrieval tests using fake local factor records for:

```text
Threw away 2kg of plastic.
Discarded 2 kg of plastic packaging.
Recycled 500 g of plastic bottles.
Composted 2 kg of food scraps.
Bought 1 kg of beef.
Bought two coffees.
Spent $6 on coffee.
Ordered a beef burrito.
Ran a 2 kW heater for 3 hours.
Drove 12 km in a petrol car.
```

Retrieval tests must prove:

- enriched metadata improves selected candidate ranking over shallow raw records
- specific compatible factors beat generic factors
- generic fallback requires a visible assumption
- wrong-method candidates are rejected
- wrong-unit candidates are rejected
- money factors are used only for money inputs
- goods and waste do not cross-select each other's factors
- unresolved remains visible when no safe factor path exists

Add at least one multi-activity stress test:

```text
I drove 12 km, bought two coffees, ordered a beef burrito, recycled 500 g of plastic bottles, and threw away 1 kg of food waste.
```

Expected:

- all supported categories remain represented
- unsupported or unresolved events remain visible
- one weak or missing factor does not suppress other events
- impact comparison remains suppressed if represented result is partial

## Acceptance Criteria

- A repo-bundled enriched factor metadata overlay exists.
- Overlay rows are schema validated with controlled vocabularies.
- A source-noted research artifact documents included pathway families.
- The overlay stays within the four supported categories.
- Runtime metadata loading merges overlay fields with raw database records.
- No manual GCS/blob update is required by default.
- Ticket 10 factor retrieval uses enriched metadata when available.
- Waste and goods/services factor linking improve on fake database records.
- The system still rejects wrong unit, wrong method, and wrong category factors.
- Missing quantities still produce unresolved or assumption-backed behavior, not
  fabricated precision.
- Developer diagnostics can show enriched metadata reasons without exposing
  raw provider payloads.
- Existing V2 energy, transport, goods/services, waste, extraction, confidence,
  coverage, and UI tests pass.
- V1 `/api/estimate` remains intact.

## Verification

Run backend tests:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

If frontend files change, run from `app/frontend`:

```powershell
npm test -- --watchAll=false
npm run build
```

If deployment files change, verify the overlay is included in the production
image or deployment package. For the default repo-bundled implementation, this
should be handled by normal source inclusion rather than a GCS upload.

## Do Not Do

- Do not require the user to manually update GCP blob storage.
- Do not modify raw Climatiq CSVs as the source of truth.
- Do not make a broad unsupervised LLM pass over every database row and trust
  the output without schema validation and reviewable source notes.
- Do not add categories outside `transport`, `energy`, `goods_services`, and
  `waste`.
- Do not treat enriched metadata as permission to bypass parameter validation.
- Do not use recyclable material as proof of recycling.
- Do not convert spend into servings or weight.
- Do not hide unresolved events to make the UI look cleaner.
- Do not run live external services in automated tests.

## Completion Definition

Ticket 11 is complete when the V2 backend can use a small, reviewed,
repo-bundled metadata overlay to connect common personal activities to
compatible factor records more reliably, while preserving deterministic
validation, transparent assumptions, and no manual GCP data maintenance.
