# CarbonCoach V2 Design Spec

## Purpose

CarbonCoach should estimate emissions from natural-language journal entries by extracting carbon-relevant activity data, matching it to appropriate emission factors, validating calculation parameters, and returning transparent assumptions.

The current architecture improved basic distance parsing, but it still treats a journal entry mostly as:

```text
journal text -> activity label -> activity_id -> generic parameters
```

That is not enough for inputs such as:

- "I turned on a heater for 3 hours."
- "I used a 2 kW heater for 3 hours."
- "I took a 7k ride in a Toyota Camry."
- "I drove 12 km in a diesel SUV."

The V2 architecture should treat journal parsing as structured information extraction into carbon-specific event schemas.

## Design Principles

1. LLMs extract structured facts; deterministic code validates, normalizes, and calculates.
2. Activity data is the first-class object, not the activity label.
3. Emission-factor retrieval should happen after event extraction, not before.
4. Assumptions must be explicit in the API response.
5. Every estimate should expose source, confidence, parameters, factor match, and fallback behavior.
6. Domain-specific logic beats one generic parser for transport, energy, waste, and goods.

## Research Basis

Carbon accounting generally follows:

```text
emissions = activity data x emission factor
```

EPA and WRI both describe this pattern: activity data represents the magnitude of an activity, and emission factors convert that activity into greenhouse gas emissions.

For the NLP side, this is closer to semantic parsing / structured information extraction than simple classification. Modern LLM extraction systems are usually schema-first: define the expected JSON contract, force or validate model output against that contract, then repair/retry invalid responses.

For measurement-heavy inputs, quantity extraction is not enough by itself. The system must link the quantity to the measured entity and property:

```text
"heater for 3 hours"
quantity: 3
unit: hours
measured entity: heater
property: duration
derived quantity: kWh, if power is known or assumed
```

Relevant references:

- EPA inventory guidance: https://archive.epa.gov/epa/statelocalclimate/develop-greenhouse-gas-inventory.html
- WRI methodology: https://www.wri.org/sustainability-wri/dashboard/methodology
- Climatiq docs: https://www.climatiq.io/docs
- Climatiq search API: https://www.climatiq.io/docs/api-reference/search
- RAG paper, Lewis et al. 2020: https://arxiv.org/abs/2005.11401
- Measurement extraction review: https://aclanthology.org/2022.findings-emnlp.161.pdf
- Comprehensive Quantity Extractor paper: https://arxiv.org/abs/2305.08853
- Quantulum quantity extraction library: https://github.com/marcolagi/quantulum
- Pint units library: https://pint.readthedocs.io/en/0.18/
- NHTSA vPIC vehicle API: https://vpic.nhtsa.dot.gov/api/Home/Index

## Target Architecture

```text
FastAPI endpoint
  -> CarbonPipeline
    -> JournalPreprocessor
    -> JournalEventExtractor
    -> QuantityNormalizer
    -> EntityEnricher
    -> DomainParameterBuilder
    -> FactorRetriever
    -> EstimateValidator
    -> ClimatiqClient
    -> FallbackEstimator
    -> ResponseBuilder
```

### Module Responsibilities

#### JournalPreprocessor

Conservatively cleans the journal entry before event extraction while preserving the raw input.

Purpose:

- reduce obvious typos and formatting issues
- improve downstream extraction and retrieval
- preserve enough provenance to explain corrections

This module should not reinterpret the user's meaning.

Allowed examples:

```text
5km -> 5 km
500g -> 500 g
3hrs -> 3 hours
2kw -> 2 kW
kwh -> kWh
toytoa -> toyota
camery -> camry
```

Forbidden examples:

```text
do not paraphrase the journal
do not remove quantities
do not turn 7k into 7 km here
do not hide ambiguity
do not silently replace entities without recording corrections
```

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
    }
  ]
}
```

Downstream modules may use `cleaned_journal`, but response details should preserve raw spans where possible.

#### CarbonPipeline

Orchestrates the full flow. It should not contain domain-specific parsing or fallback math.

Input:

```python
journal_entry: str
```

Output:

```python
CarbonEstimateResponse
```

Responsibilities:

- call event extraction
- build parameters per event
- retrieve and validate emission factor
- call Climatiq
- fallback when necessary
- aggregate totals

#### JournalEventExtractor

Extracts structured carbon events from text.

Current output:

```python
[("car trip", "transport")]
```

Target output:

```json
[
  {
    "raw_text": "took a 7 km ride in a Toyota Camry",
    "category": "transport",
    "activity_type": "car_ride",
    "quantities": [
      {
        "value": 7,
        "unit": "km",
        "dimension": "distance",
        "surface": "7 km"
      }
    ],
    "entities": {
      "vehicle_make": "Toyota",
      "vehicle_model": "Camry"
    },
    "confidence": 0.86
  }
]
```

Implementation options:

- Phase 1: LLM prompt returning strict JSON plus Pydantic validation.
- Phase 2: provider-native structured output or tool calling if available.
- Phase 3: add retry/repair path for invalid JSON.

The schema should remain fairly flat. Deep schemas are harder for LLMs to fill reliably.

Extraction must be additive across the journal. The extractor should not return immediately after the first matching keyword if later text may contain another supported activity. Each slice should expand the set of supported event patterns while preserving previously supported patterns.

Robustness expectations:

- handle multiple supported activities in one journal entry
- preserve supported events when surrounded by irrelevant text
- record unsupported carbon-relevant activities as `unresolved` or `not_estimated` where possible
- include tests for wording variations near the ticket examples
- avoid making the listed ticket examples the only phrases that work

#### QuantityNormalizer

Extracts, normalizes, and canonicalizes quantities.

Examples:

```text
7k -> 7 km, if transport context is present
7 km -> 7 km
500g -> 0.5 kg
3 hrs -> 3 hours
2 kW -> 2 kW
$20 -> 20 USD
```

Recommended stack:

- keep current regex parser for common user phrasing
- evaluate `quantulum3` for measurement extraction
- evaluate `pint` for unit conversion and dimensional validation

This module should preserve the original surface string for debugging.

#### EntityEnricher

Turns extracted entities into calculation-relevant properties.

Transport examples:

```text
Toyota Camry -> passenger car, medium, petrol by default unless hybrid/electric is stated
Tesla Model 3 -> passenger car, electric
Prius -> passenger car, hybrid
SUV -> passenger car, large
bus -> bus
train -> rail
```

Energy examples:

```text
heater -> space heater, assumed 1.5 kW
AC -> air conditioner, assumed 2.0 kW
oven -> oven, assumed 2.4 kW
```

Potential vehicle enrichment sources:

- local rules table for common models
- optional NHTSA vPIC API for make/model/body metadata
- optional fuel economy API later if model/year is available

#### DomainParameterBuilder

Builds Climatiq-ready parameters from a `CarbonEvent`.

There should be separate builders by category.

```text
TransportParameterBuilder
EnergyParameterBuilder
WasteParameterBuilder
GoodsServicesParameterBuilder
```

##### TransportParameterBuilder

Inputs:

- distance
- vehicle type
- fuel type
- passenger count
- route type if available

Examples:

```text
"I drove 10 km"
-> distance = 10 km
-> vehicle = passenger car
-> fuel = unknown/petrol assumption
```

```text
"I took a 7k ride in a Toyota Camry"
-> distance = 7 km
-> vehicle_make = Toyota
-> vehicle_model = Camry
-> vehicle_class = medium passenger car
-> fuel = petrol assumption
```

##### EnergyParameterBuilder

Inputs:

- direct kWh, or
- device + duration + power

Examples:

```text
"used 5 kWh of electricity"
-> energy = 5 kWh
```

```text
"turned on heater for 3 hours"
-> device = heater
-> duration = 3 hours
-> assumed_power_kw = 1.5
-> energy = 4.5 kWh
```

```text
"used a 2 kW heater for 3 hours"
-> power = 2 kW
-> duration = 3 hours
-> energy = 6 kWh
```

##### WasteParameterBuilder

Inputs:

- weight
- material
- disposal method

Examples:

```text
"recycled 500g plastic"
-> material = plastic
-> method = recycling
-> weight = 0.5 kg
```

##### GoodsServicesParameterBuilder

Inputs:

- item count
- item type
- spend
- weight if available

Examples:

```text
"bought two shirts"
-> item = shirts
-> number = 2
```

```text
"spent $20 on coffee"
-> activity = coffee purchase
-> money = 20 USD
```

#### FactorRetriever

Finds candidate Climatiq emission factors.

Current matching uses vector similarity over activity names. V2 should use a hybrid strategy:

1. Filter by category/sector and unit type.
2. Semantic search on activity names.
3. Keyword/entity boosts.
4. Data quality/source preference.
5. Reject candidates below threshold.

Example query for car:

```text
medium petrol passenger car Toyota Camry distance
```

Example query for heater:

```text
electricity grid mix residential energy kWh
```

This module should return multiple candidates with scores and reasons, not only one winner.

#### EstimateValidator

Validates that a selected factor and parameter set are compatible.

Examples:

```text
factor unit_type = Energy
parameters must include energy + energy_unit
```

```text
factor unit_type = Distance
parameters must include distance + distance_unit
```

If validation fails, the pipeline should either:

- try the next factor candidate
- convert parameters if possible
- fallback with assumptions
- return a structured unresolved estimate

#### ClimatiqClient

Owns API concerns only:

- request building
- auth
- timeouts
- response parsing
- error reporting

It should not infer parameters or choose fallback factors.

#### FallbackEstimator

Provides deterministic fallback estimates when Climatiq is unavailable or no compatible factor exists.

Fallbacks should be explicit and low-confidence:

```json
{
  "source": "fallback",
  "confidence": "low",
  "assumptions": [
    "Used local fallback factor for medium petrol car."
  ]
}
```

#### ResponseBuilder

Builds user-facing structured response:

```json
{
  "result": {
    "co2e": 4.25,
    "unit": "kg",
    "details": [
      {
        "raw_text": "turned on heater for 3 hours",
        "category": "energy",
        "activity_type": "space_heater_use",
        "parameters": {
          "energy": 4.5,
          "energy_unit": "kWh"
        },
        "activity_id": "electricity-supply_grid-source_residual_mix",
        "co2e": 2.1,
        "unit": "kg",
        "source": "climatiq",
        "confidence": "medium",
        "assumptions": [
          "Assumed heater power of 1.5 kW because wattage was not provided."
        ]
      }
    ]
  }
}
```

## Proposed Data Models

Use Pydantic models for validation.

```python
class Quantity(BaseModel):
    value: float
    unit: str
    dimension: Literal[
        "distance",
        "energy",
        "power",
        "duration",
        "weight",
        "money",
        "number",
        "volume",
        "area",
    ]
    surface: str | None = None
    confidence: float = 1.0
```

```python
class CarbonEvent(BaseModel):
    raw_text: str
    category: Literal["transport", "energy", "waste", "goods_services"]
    activity_type: str
    quantities: list[Quantity] = []
    entities: dict[str, str | float | int | bool | None] = {}
    assumptions: list[str] = []
    confidence: float = 0.0
```

```python
class FactorCandidate(BaseModel):
    activity_id: str
    name: str
    sector: str | None = None
    category: str | None = None
    unit_type: str
    score: float
    match_reasons: list[str] = []
```

```python
class EstimateDetail(BaseModel):
    event: CarbonEvent
    activity_id: str | None = None
    activity_name: str | None = None
    parameters: dict
    co2e: float | None = None
    unit: str = "kg"
    source: Literal["climatiq", "fallback", "unresolved"]
    confidence: Literal["high", "medium", "low"]
    assumptions: list[str] = []
    errors: list[str] = []
```

## Example Flows

### Heater With Duration Only

Input:

```text
I turned on the heater for 3 hours.
```

Event:

```json
{
  "category": "energy",
  "activity_type": "space_heater_use",
  "quantities": [
    {"value": 3, "unit": "hour", "dimension": "duration", "surface": "3 hours"}
  ],
  "entities": {"device": "heater"}
}
```

Parameter build:

```text
duration = 3 h
assumed_power = 1.5 kW
energy = 4.5 kWh
```

Assumption:

```text
Assumed heater power of 1.5 kW because wattage was not provided.
```

### Heater With Power And Duration

Input:

```text
I used a 2 kW heater for 3 hours.
```

Parameter build:

```text
power = 2 kW
duration = 3 h
energy = 6 kWh
```

No power assumption needed.

### Car Ride With Model

Input:

```text
I took a 7 km ride in a Toyota Camry.
```

Event:

```json
{
  "category": "transport",
  "activity_type": "car_ride",
  "quantities": [
    {"value": 7, "unit": "km", "dimension": "distance", "surface": "7 km"}
  ],
  "entities": {
    "vehicle_make": "Toyota",
    "vehicle_model": "Camry"
  }
}
```

Entity enrichment:

```text
Toyota Camry -> medium passenger car, petrol by default
```

Assumption:

```text
Mapped Toyota Camry to medium petrol passenger car because model year/fuel type were not provided.
```

### Compact Unit

Input:

```text
I took a 7k ride.
```

Normalization:

```text
7k -> 7 km because context is transport and "ride" implies distance
```

Assumption:

```text
Interpreted "7k" as 7 km based on transport context.
```

## Tests And Evaluation

### Unit Tests

Quantity normalization:

- `7k ride` -> `7 km`
- `500g plastic` -> `0.5 kg`
- `3hrs heater` -> `3 hours`
- `2 kW heater for 3 hours` -> power and duration
- `$20 coffee` -> money

Event extraction:

- heater duration
- heater power + duration
- car ride with make/model
- bus/train/flight
- recycling with material and weight

Parameter builders:

- energy direct kWh
- energy duration + power
- energy duration + assumed power
- transport distance + generic car
- transport distance + enriched vehicle

Factor retrieval:

- retrieves distance-compatible factor for car ride
- retrieves energy-compatible factor for heater/electricity
- rejects wrong unit type

Pipeline regressions:

- no quantity -> explicit low-confidence default
- API fails -> fallback with assumptions
- ambiguous input -> unresolved or low confidence, not silent nonsense

### Golden Test Set

Create `tests/fixtures/carbon_events.jsonl` with examples:

```json
{"input":"I drove 10 km in a petrol car","expected_category":"transport","expected_dimension":"distance","expected_value":10}
{"input":"I used a 2 kW heater for 3 hours","expected_category":"energy","expected_energy_kwh":6}
{"input":"I turned on the heater for 3 hours","expected_category":"energy","expected_assumption":"heater power"}
{"input":"I recycled 500g of plastic","expected_category":"waste","expected_weight_kg":0.5}
{"input":"I bought two shirts","expected_category":"goods_services","expected_number":2}
```

## Rollout Plan

V2 must be delivered through vertical slices, not pure architecture-layer tickets.

Each slice should improve backend behavior and expose the new behavior in the frontend with enough UI to verify it. Shared architecture should emerge inside slices as needed.

Every slice must include:

- unit tests for deterministic logic
- pipeline/API tests from journal input to response
- frontend build verification when frontend changes
- production-like deployment verification when frontend changes
- robustness tests for wording variation and mixed multi-event journals when extraction changes
- mocks/fakes for external services

Tests must not require live Climatiq, OpenRouter, Hugging Face, or Google Cloud Storage.

Frontend visibility must be verified through the same deployment path users open. For the current single-service Cloud Run target, the production container must include the React production build and FastAPI must serve it at `/`; otherwise UI tickets can pass locally while deployed users still see the legacy inline FastAPI form.

### Phase 1: First Vertical Slice

Implement the first user-visible V2 slice behind `/api/estimate-v2`.

Recommended first slice:

```text
Energy duration-to-kWh for heater/electricity inputs.
```

This slice should introduce only the shared foundation needed for that behavior:

- `Quantity`
- `CarbonEvent`
- `Confidence`
- `Assumption`
- energy taxonomy entries
- energy parameter builder
- V2 response shape
- frontend display for confidence/assumptions/status

### Phase 1A: Deployment Visibility

Before adding more UI-dependent slices, fix the deployment path so frontend changes are visible after deployment.

Required outcome:

- the deployed root page serves the React app, or a separate frontend host is documented and configured
- the backend image no longer hides React changes behind the old inline FastAPI form
- `/api/estimate` and `/api/estimate-v2` stay reachable after the frontend routing change
- a production-like build/run is verified before marking UI tickets done

### Phase 2: Quantity And Domain Builders

Add further vertical slices for:

- transport distance and vehicle defaults
- waste material and weight
- goods/services count and money

### Phase 3: Better Retrieval

- Replace one-shot vector match with hybrid retrieval.
- Store Climatiq metadata including `sector`, `category`, `unit_type`, `source`.
- Add candidate scoring and rejection threshold.

### Phase 4: Transparency And UX

- Update frontend details panel to show:
  - extracted event
  - parameters used
  - assumptions
  - confidence
  - source: Climatiq or fallback

### Phase 5: External Enrichment

- Optional vehicle model lookup through NHTSA vPIC.
- Optional appliance/fuel economy data source.
- Optional user profile defaults, such as region and electricity grid.

## Open Questions

1. Should ambiguous estimates return low-confidence fallback, or ask the user a follow-up?
2. Should the app optimize for personal journaling speed or emissions accounting rigor?
3. What geography should defaults assume: Australia, US, or user-selected region?
4. Should exact vehicle model support be limited to common models first?
5. Should V2 keep Climatiq as the only authoritative factor source, or add local factor tables for common personal activities?

## Recommended Immediate Next Step

Start with Phase 1 and Phase 2 for transport and energy only.

These are the current pain points:

- messy natural language and typos can degrade extraction/matching
- distances partly work, but vehicle details are ignored
- duration-based energy use does not work

A focused milestone should support:

- `7k ride`
- `7 km ride in a Toyota Camry`
- `drove 12 km in a diesel SUV`
- `heater for 3 hours`
- `2 kW heater for 3 hours`
- `used 5 kWh electricity`

Once those are solid, waste and goods can follow the same pattern.
