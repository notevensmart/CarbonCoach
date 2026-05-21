# CarbonCoach V2 Agent README

This README records the design decisions from the V2 planning session. Future agents must treat this as the source of truth unless the user explicitly changes a decision.

## Product Goal

CarbonCoach V2 is for best-effort personal carbon awareness, not audit-grade accounting.

The app should:

- estimate from natural-language journal entries
- use realistic assumptions when information is missing
- expose assumptions and confidence clearly
- avoid pretending estimates are exact
- keep the journaling flow fast by estimating first, not blocking on follow-up questions

## Core Architecture Rule

Do not treat journal parsing as simple label classification.

Use this architecture:

```text
journal text
-> conservative journal preprocessing
-> structured carbon events
-> quantity and entity normalization
-> domain-specific parameter builders
-> improved local-first factor retrieval
-> validation
-> Climatiq or fallback estimate
-> response with assumptions, confidence, status, and source breakdown
```

LLMs may help extract structured facts, but deterministic code must validate, normalize, calculate, and score confidence.

## Journal Preprocessing

V2 should include a conservative `JournalPreprocessor` before event extraction.

The goal is to reduce avoidable typos and formatting mistakes before matching, without changing the user's meaning.

Core rule:

```text
Normalize surface mess, do not reinterpret meaning.
```

The preprocessor must always preserve the original raw journal text.

Recommended output:

```json
{
  "raw_journal": "i drove 7k in a toytoa camery",
  "cleaned_journal": "i drove 7k in a toyota camry",
  "corrections": [
    {
      "from": "toytoa",
      "to": "toyota",
      "type": "spelling",
      "confidence": 0.95
    },
    {
      "from": "camery",
      "to": "camry",
      "type": "spelling",
      "confidence": 0.90
    }
  ]
}
```

Allowed preprocessing:

```text
normalize whitespace
normalize casing where safe
normalize obvious unit formatting, e.g. 5km -> 5 km
normalize unit casing, e.g. kwh -> kWh, kw -> kW
expand common unit abbreviations, e.g. hrs -> hours
correct known domain typos, e.g. toytoa -> toyota, camery -> camry
```

Forbidden preprocessing:

```text
do not paraphrase the full journal
do not remove ambiguity
do not delete quantities
do not convert compact k to km here
do not silently replace entities without recording a correction
do not use broad autocorrect that can change carbon meaning
```

The event extractor may use both raw and cleaned text. Response details should preserve raw event spans where possible.

Preprocessing corrections should affect confidence. For example, a vehicle model identified after typo correction should be slightly less confident than an exact user-provided match.

## Event Boundary Rule

One event equals one activity that maps to one emission calculation pathway.

Example:

```text
I drove 10 km to the shops, bought two shirts, then drove home and used the heater for 3 hours.
```

Expected events:

```text
1. drove 10 km to the shops -> transport / car_ride
2. bought two shirts -> goods_services / clothing_purchase
3. drove home -> transport / car_ride
4. used the heater for 3 hours -> energy / space_heater_use
```

Return trips may inherit distance only when strongly implied.

Example assumption:

```text
Assumed return trip distance matched outbound trip: 10 km.
```

## Categories

Use the existing four top-level categories:

```text
transport
energy
waste
goods_services
```

Do not add `food` as a top-level category in V2. Food belongs under `goods_services` with specific activity types such as `food_purchase`, `restaurant_meal`, or `coffee_purchase`.

## Activity Types

`activity_type` must be controlled and enum-like, not free-form.

Initial activity types:

```text
transport:
- car_ride
- bus_ride
- train_ride
- flight
- rideshare
- bicycle_ride
- walking

energy:
- electricity_use
- space_heater_use
- air_conditioner_use
- cooking_appliance_use
- hot_water_use
- natural_gas_use

waste:
- landfill_waste
- recycling
- composting

goods_services:
- clothing_purchase
- electronics_purchase
- food_purchase
- coffee_purchase
- restaurant_meal
- generic_purchase
```

Unknown activity types should map to a controlled generic type, not an invented string.

## Taxonomy Storage

Store the V2 activity taxonomy in Python config/constants first, for example:

```text
app/domain/activity_taxonomy.py
```

Do not introduce a database or external config service for taxonomy yet.

The taxonomy should include:

- category
- activity_type
- keywords
- required quantity dimensions
- supporting quantity dimensions
- derivation rules
- parameter builder key
- fallback factor key
- default assumptions if relevant

## Strict Validation

All LLM output must pass strict schema validation before entering the pipeline.

Use Pydantic models for:

- `Quantity`
- `CarbonEvent`
- `Confidence`
- `Assumption`
- `FactorCandidate`
- `EstimateDetail`

Invalid LLM output must not flow into Climatiq requests.

Recommended failure path:

```text
LLM output
-> parse JSON
-> Pydantic validation
-> one repair retry if needed
-> deterministic heuristic fallback
-> low confidence if fallback is used
```

## Determinism

Make extraction as deterministic as possible:

- temperature `0`
- strict JSON-only output
- controlled enums
- Pydantic validation
- deterministic quantity normalization
- rule-based confidence scoring
- golden regression tests

The model can assist, but validation decides what the rest of the app can use.

## Quantity Extraction

Use hybrid extraction:

```text
LLM extracts candidate event structure
deterministic QuantityNormalizer scans raw text again
normalizer adds/fixes quantities
Pydantic validates final event
parameter builders use normalized quantities
```

Deterministic normalization is the source of truth.

Support at least:

```text
7k -> 7 km when context strongly implies distance
7 km -> 7 km
500g -> 0.5 kg
3 hrs -> 3 hours
2 kW -> 2 kW
5 kWh -> 5 kWh
$20 -> 20 USD
```

## Compact `k` Rule

Interpret compact `k` as kilometers only when context strongly supports distance.

Examples:

```text
took a 7k ride -> 7 km
ran a 5k -> 5 km
spent 7k on furniture -> do not convert to km
bought a 7k TV -> do not convert to km
```

When context is used, add an assumption and reduce confidence.

Example:

```text
Interpreted "7k" as 7 km based on transport context.
```

## Confidence

Expose both numeric score and string level.

```json
{
  "score": 0.72,
  "level": "medium"
}
```

Mapping:

```text
0.80 - 1.00 -> high
0.50 - 0.79 -> medium
0.00 - 0.49 -> low
```

The UI may display:

```text
Confidence: Medium (0.72)
```

Use separate confidence fields where useful:

- event confidence
- parameter confidence
- factor confidence
- total confidence

## Confidence Scoring

Confidence must be rule/evidence-based, not blindly copied from the LLM.

Recommended parameter confidence examples:

```text
explicit value + explicit unit -> 0.95
context-inferred unit, e.g. 7k ride -> 0.72
power + duration converted to energy -> 0.90
duration + assumed appliance power -> 0.60
default parameter with no quantity -> 0.35
```

Recommended event confidence principles:

```text
validated LLM structured event -> starts around 0.75
exact enum activity type -> add confidence
specific raw text span -> add confidence
heuristic fallback -> cap confidence around 0.60
generic/unknown activity -> cap confidence around 0.55
contradiction -> lower confidence
```

## Assumptions

Assumptions must be standardized typed objects, not random strings.

Recommended shape:

```json
{
  "code": "space_heater.default_power",
  "message": "Assumed heater power of 1.5 kW because wattage was not provided.",
  "source": "default",
  "confidence_impact": -0.25
}
```

Use realistic, statistically rooted defaults. Do not build assumption telemetry yet.

Defaults should live centrally, for example:

```text
app/domain/assumptions.py
```

## Default Region

Use Australia as the V2 default region.

```text
DEFAULT_REGION = "AU"
DEFAULT_ELECTRICITY_REGION = "AU"
```

If no region is provided for electricity-related estimates, assume Australia and expose that assumption.

## Heater Defaults

Plain `heater` defaults to electric space heater in V2.

If the user says:

```text
heater for 3 hours
```

Assume:

```text
electric space heater
1.5 kW default power
Australia electricity grid
```

If the user explicitly says gas heater, do not force electric.

Keep fuel/power source in normalized entities:

```json
{
  "device": "heater",
  "power_source": "electricity"
}
```

## Assumption Selection Priority

When making assumptions, maximize confidence honestly by choosing the best-supported realistic default.

Priority:

```text
1. Explicit user input
2. Strong context inference
3. Known entity-specific default
4. Category-level default
5. Generic low-confidence fallback
```

Do not inflate confidence just because the system selected a default.

## Fuel And Power Source Normalization

Normalize fuel and power source as controlled entity fields.

Transport uses:

```text
fuel_type
```

Energy/appliances use:

```text
power_source
```

Controlled values:

```text
petrol
diesel
hybrid
electric
electricity
natural_gas
unknown
```

Avoid ambiguous values like `gas`; normalize to `petrol` or `natural_gas` based on context.

## Vehicle Defaults

V2 should start with local vehicle defaults, not external vehicle APIs.

Example:

```python
VEHICLE_MODEL_DEFAULTS = {
    ("toyota", "camry"): {
        "vehicle_type": "car",
        "vehicle_size": "medium",
        "fuel_type": "petrol",
        "confidence": 0.65,
        "assumption_code": "vehicle.toyota_camry.default_petrol_medium",
    },
    ("tesla", "model 3"): {
        "vehicle_type": "car",
        "vehicle_size": "medium",
        "fuel_type": "electric",
        "confidence": 0.85,
        "assumption_code": "vehicle.tesla_model_3.default_electric",
    },
}
```

External vehicle APIs may be added later.

## Explicit User Input Wins

Explicit user details always override defaults.

Example:

```text
electric Toyota Camry
```

User-provided `electric` wins over a local Camry default of petrol.

Precedence:

```text
1. explicit user input
2. strong context inference
3. known model default
4. category default
5. generic fallback
```

## Contradictions

Do not silently fix contradictory inputs.

Contradictions should:

- lower confidence
- appear as visible issues
- still produce an estimate when a reasonable path exists

Example:

```text
I drove my Tesla using diesel for 10 km.
```

Preferred behavior:

```text
Use Tesla -> electric if that is the strongest known entity.
Add issue: input mentioned diesel, but Tesla is mapped to electric.
Lower confidence.
```

If no safe path exists, return `unresolved` or low-confidence fallback.

## Quantity Roles

Each activity type must define quantity roles:

```text
required
supporting
derivable
```

Example:

```text
car_ride:
  required: distance
  supporting: duration, passengers

space_heater_use:
  required: energy
  derivable:
    power + duration -> energy
    duration + default_power -> energy
```

Parameter builders must choose required dimensions first. Supporting dimensions should not override required dimensions.

## Retrieval Timing

Do not retrieve an emission factor immediately after label classification.

Use this order:

```text
CarbonEvent
-> normalize quantities/entities
-> build candidate parameter intent
-> retrieve factor candidates using event + entities + required unit type
-> validate candidate factor against built parameters
-> call Climatiq
```

## Factor Retrieval

Use local-first hybrid retrieval.

Recommended order:

```text
1. local metadata filter by sector/category/unit_type
2. keyword/entity scoring
3. vector similarity within filtered candidates
4. optional Climatiq Search API fallback if local retrieval is weak
```

Improved search should use weighted scoring:

```text
final_score =
  metadata_score * 0.35
+ semantic_score * 0.35
+ keyword_score * 0.20
+ source_quality_score * 0.10
```

Candidate results should include match reasons:

```json
{
  "activity_id": "...",
  "score": 0.87,
  "match_reasons": [
    "unit_type matched distance",
    "sector matched transport",
    "matched fuel type petrol",
    "matched vehicle class passenger car"
  ]
}
```

## Retrieval Thresholds

Use thresholds:

```text
score >= 0.75:
  accept normally

0.55 <= score < 0.75:
  accept with medium factor confidence

score < 0.55:
  do not call Climatiq with that factor
  use fallback or unresolved
```

Hard filters:

- energy events must not use distance factors
- transport events must not use waste factors
- incompatible fuel/material/device terms should be penalized heavily

## Event Statuses

Use this controlled status enum:

```text
estimated
fallback_estimated
not_estimated
unresolved
failed
```

Definitions:

```text
estimated:
  Climatiq estimate succeeded with compatible factor and parameters.

fallback_estimated:
  Local fallback estimate used because Climatiq/factor retrieval failed or was unavailable.

not_estimated:
  Event understood, but no meaningful carbon pathway should be estimated.

unresolved:
  Event likely carbon-relevant, but required data/factor could not be built safely.

failed:
  Unexpected system error while processing the event.
```

## Not Estimated Events

Do not force every activity into an estimate.

Examples:

```text
read a book for 2 hours -> not_estimated
studied all afternoon -> not_estimated
watched TV for 2 hours -> estimated if TV appliance default exists
```

Return `not_estimated` events in the API response. Do not include them in the total.

The frontend should show them in a secondary or collapsed section.

## Totals

Fallback estimates count toward total emissions.

The total response should include source breakdown:

```json
{
  "total": {
    "co2e": 4.5,
    "unit": "kg",
    "confidence": {"score": 0.68, "level": "medium"},
    "source_breakdown": {
      "estimated": 1.8,
      "fallback_estimated": 2.7,
      "not_estimated": 0
    }
  }
}
```

## Implementation Strategy

Do not rewrite the working endpoint in one large change.

Build V2 as a parallel pipeline:

```text
POST /api/estimate-v2
```

Keep V1 working:

```text
POST /api/estimate
```

Suggested file structure:

```text
app/
  domain/
    models.py
    activity_taxonomy.py
    assumptions.py

  pipeline_v2/
    event_extractor.py
    quantity_normalizer.py
    entity_enricher.py
    parameter_builders.py
    factor_retriever.py
    validator.py
    response_builder.py
    pipeline.py
```

Build V2 through vertical slice tickets.

The first recommended slice is:

```text
Energy duration-to-kWh for heater/electricity inputs.
```

Acceptance examples:

```text
I used a 2 kW heater for 3 hours.
-> energy = 6 kWh, high confidence

I turned on the heater for 3 hours.
-> assumes electric heater and default power, medium confidence

I used 5 kWh of electricity.
-> energy = 5 kWh, high confidence
```

V1 endpoint must continue to work while V2 is built.

## Ticket Strategy

All implementation tickets must be vertical slices that gradually improve both backend and frontend behavior.

Do not split tickets purely by architecture layer, such as:

```text
models only
taxonomy only
parser only
retriever only
```

Instead, each ticket should deliver a user-visible capability end to end.

Example:

```text
Energy heater slice:
  backend extracts heater events, normalizes duration/power, derives kWh,
  returns assumptions/confidence/status,
  frontend displays those new fields,
  tests cover the full behavior.
```

Shared architecture may be introduced inside a vertical slice, but only the pieces needed for that slice should be built.

## Testing Standard For Every Ticket

Every vertical slice must be tested thoroughly.

Use three layers of testing unless a layer genuinely does not apply.

### 1. Unit Tests

Test deterministic pieces directly.

Examples:

```text
2 kW + 3 hours -> 6 kWh
3 hours + default heater power -> 4.5 kWh
7k ride -> 7 km with context assumption
500g plastic -> 0.5 kg
Toyota Camry -> medium petrol default
```

### 2. Pipeline Or API Tests

Test journal input to V2 response.

Examples:

```text
POST /api/estimate-v2 with "heater for 3 hours"
assert activity_type, parameters, assumptions, confidence, status, and total
```

### 3. Frontend Verification

At minimum, run:

```powershell
npm run build
```

If the ticket changes meaningful UI behavior, verify that the page renders the new response fields locally or with browser/screenshot testing.

### External Service Rule

Unit and pipeline tests must not require live:

```text
Climatiq
OpenRouter
Hugging Face
Google Cloud Storage
```

External clients must be mocked, faked, or bypassed in tests.

### Definition Of Done For A Ticket

A ticket is not done unless:

```text
backend tests pass
new slice tests pass
frontend build passes if frontend changed
existing V1 behavior is not broken
assumptions/confidence/status are visible where relevant
no live external service is required for tests
```
