# CarbonCoach V2 Ticket Plan

This document defines the minimal vertical-slice tickets for implementing CarbonCoach V2.

Agents must follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`

The V2 implementation must be built mostly in new files. Existing V1 code should be touched only for small integration points such as endpoint registration and frontend display.

## Shared Rules

### Product Goal

CarbonCoach V2 is for best-effort personal carbon awareness with transparent assumptions, not audit-grade accounting.

### Implementation Strategy

Build V2 in parallel behind:

```text
POST /api/estimate-v2
```

Keep V1 working:

```text
POST /api/estimate
```

### Ticket Shape

All tickets are vertical slices. Each ticket should improve backend behavior and frontend visibility where relevant.

Do not create architecture-only tickets unless the architecture is required by the vertical slice being implemented.

### Testing Standard

Each ticket must include:

1. Unit tests for deterministic logic.
2. Pipeline/API tests from journal input to response.
3. Frontend build verification if frontend changes.

Tests must not require live:

```text
Climatiq
OpenRouter
Hugging Face
Google Cloud Storage
```

Mock or fake external clients.

### Preferred New File Structure

Create V2 code mostly under:

```text
app/domain/
app/pipeline_v2/
```

Suggested structure:

```text
app/domain/
  __init__.py
  models.py
  confidence.py
  activity_taxonomy.py
  assumptions.py

app/pipeline_v2/
  __init__.py
  pipeline.py
  event_extractor.py
  quantity_normalizer.py
  entity_enricher.py
  parameter_builders.py
  factor_retriever.py
  validator.py
  response_builder.py
```

This exact split can evolve, but V2 should not be mixed deeply into V1 modules.

## Ticket 1: V2 Energy Slice, Heater And Electricity

### Goal

Create the V2 endpoint and final V2 response shape through an end-to-end energy slice.

This ticket proves the architecture using:

```text
I used a 2 kW heater for 3 hours.
I turned on the heater for 3 hours.
I used 5 kWh of electricity.
```

### Dependencies

None.

### Backend Scope

Add:

```text
POST /api/estimate-v2
```

Create the minimum V2 foundation needed for this slice:

- conservative journal preprocessing for unit formatting
- `Confidence`
- `Assumption`
- `Issue`
- `Quantity`
- `CarbonEvent`
- `EstimateDetail`
- `EstimateTotal`
- `CarbonEstimateResponse`
- energy taxonomy entries
- appliance assumptions for heater
- quantity normalization for energy/power/duration
- deterministic energy event extraction
- energy parameter builder
- fallback estimate path if Climatiq/factor retrieval is not ready

### Frontend Scope

Add minimal visibility for V2 response fields.

The frontend must be able to display:

- status
- confidence as `Medium (0.60)` style
- parameters used
- assumptions
- issues if present
- total/source breakdown if available

Do not redesign the full UI.

### Supported Inputs

#### Explicit Power And Duration

Input:

```text
I used a 2 kW heater for 3 hours.
```

Expected:

```text
category: energy
activity_type: space_heater_use
energy: 6 kWh
confidence: high, about 0.90
status: fallback_estimated or estimated
```

#### Duration Only

Input:

```text
I turned on the heater for 3 hours.
```

Expected:

```text
category: energy
activity_type: space_heater_use
duration: 3 hours
assumed power: 1.5 kW
energy: 4.5 kWh
confidence: medium, about 0.60
assumption: space_heater.default_power
assumption: region.default_au_electricity
status: fallback_estimated or estimated
```

#### Direct Electricity

Input:

```text
I used 5 kWh of electricity.
```

Expected:

```text
category: energy
activity_type: electricity_use
energy: 5 kWh
confidence: high, about 0.95
assumption: region.default_au_electricity if no region provided
status: fallback_estimated or estimated
```

### Required V2 Response Shape

Ticket 1 establishes the final V2 response shape. Later tickets may add fields, but should not break this contract.

Minimum shape:

```json
{
  "version": "v2",
  "total": {
    "co2e": 2.7,
    "unit": "kg",
    "confidence": {
      "score": 0.6,
      "level": "medium"
    },
    "source_breakdown": {
      "estimated": 0,
      "fallback_estimated": 2.7,
      "not_estimated": 0
    }
  },
  "details": [
    {
      "raw_text": "heater for 3 hours",
      "category": "energy",
      "activity_type": "space_heater_use",
      "status": "fallback_estimated",
      "parameters": {
        "energy": 4.5,
        "energy_unit": "kWh"
      },
      "confidence": {
        "score": 0.6,
        "level": "medium"
      },
      "assumptions": [
        {
          "code": "space_heater.default_power",
          "message": "Assumed heater power of 1.5 kW because wattage was not provided.",
          "source": "default",
          "confidence_impact": -0.25
        }
      ],
      "issues": []
    }
  ]
}
```

### Acceptance Criteria

- `/api/estimate-v2` exists.
- `/api/estimate` still works/imports.
- Raw journal text is preserved in V2 processing.
- Conservative preprocessing normalizes obvious unit formatting like `2kw`, `3hrs`, and `5kwh`.
- The three supported energy inputs return deterministic V2 responses.
- Confidence includes score and level.
- Assumptions are typed objects with stable codes.
- Australia is the default electricity region.
- Plain `heater` defaults to electric space heater.
- V2 response includes status, parameters, assumptions, issues, total, and source breakdown.
- Frontend can display the new fields.

### Tests

Add tests for:

- confidence score-to-level mapping
- Pydantic/domain model validation
- journal preprocessing preserves raw text and records corrections
- journal preprocessing normalizes `2kw`, `3hrs`, and `5kwh`
- quantity normalization for `2 kW`, `3 hours`, `5 kWh`
- `2 kW heater for 3 hours -> 6 kWh`
- `heater for 3 hours -> 4.5 kWh` with assumptions
- `5 kWh electricity -> 5 kWh`
- `/api/estimate-v2` response shape
- V1 pipeline or endpoint still imports

Run:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

If frontend changes:

```powershell
npm run build
```

from `app/frontend`.

### Do Not Do

- Do not implement transport yet.
- Do not add external vehicle APIs.
- Do not depend on live LLM/Climatiq/Hugging Face/GCS in tests.
- Do not replace `/api/estimate`.

## Ticket 2: V2 Transport Slice, Distance And Vehicle Defaults

### Goal

Add transport support for distance, compact `k`, vehicle/fuel details, and local vehicle defaults.

### Dependencies

Ticket 1.

### Backend Scope

Extend V2 with:

- transport taxonomy entries
- conservative domain typo correction for common vehicle terms
- distance quantity normalization
- compact `k` context rule
- transport event extraction
- transport entity enrichment
- vehicle defaults
- transport parameter builder
- contradiction handling through lowered confidence and issues

### Frontend Scope

Display transport-specific assumptions and issues, including:

- compact `k` interpretation
- vehicle default mapping
- explicit user override
- contradictions

### Supported Inputs

Must support:

```text
I drove 10 km in a petrol car.
I took a 7k ride.
I took a 7 km ride in a Toyota Camry.
I drove 12 km in a diesel SUV.
I drove 7 km in my electric Toyota Camry.
I drove my Tesla Model 3 for 8 km.
I drove my Tesla using diesel for 10 km.
```

### Required Behavior

#### Explicit Distance

```text
10 km -> distance 10 km, high confidence
```

#### Compact `k`

```text
7k ride -> distance 7 km, medium confidence
```

Add assumption:

```text
distance.compact_k_context_km
```

#### Toyota Camry Default

```text
Toyota Camry -> medium petrol car
```

Add assumption:

```text
vehicle.toyota_camry.default_petrol_medium
```

#### Explicit User Override

```text
electric Toyota Camry -> fuel_type electric
```

User input wins over defaults.

#### Tesla Model 3

```text
Tesla Model 3 -> electric medium car
```

#### Contradictions

```text
Tesla using diesel
```

Expected:

- produce an estimate if possible
- lower confidence
- add visible issue
- do not silently hide the contradiction

### Acceptance Criteria

- Transport events produce V2 response details.
- `7k` only becomes km when context supports distance.
- `7k` in purchase/money context does not become distance.
- Vehicle model defaults are centralized.
- Known typo corrections, such as `toytoa camery`, are recorded and slightly lower confidence.
- Explicit user fuel type overrides defaults.
- Contradictions lower confidence and add issues.
- Frontend displays transport assumptions/issues.

### Tests

Add tests for:

- explicit distance
- compact `k` with ride context
- compact `k` with purchase context rejected as distance
- Camry default
- typo-corrected Camry default with correction recorded
- electric Camry override
- Tesla Model 3 default
- diesel SUV
- Tesla/diesel contradiction lowers confidence
- pipeline/API responses for supported transport inputs

### Do Not Do

- Do not call external vehicle APIs.
- Do not require vehicle model year.
- Do not replace V1 matching.
- Do not add broad autocorrect that can change user meaning.

## Ticket 3: V2 Local-First Scored Factor Retrieval

### Goal

Improve V2 emission-factor search using local-first scored retrieval.

### Dependencies

Tickets 1 and 2.

### Backend Scope

Add or extend:

```text
app/pipeline_v2/factor_retriever.py
app/pipeline_v2/validator.py
```

Retrieval must use:

```text
1. metadata filter by category/sector/unit_type
2. keyword/entity scoring
3. semantic/vector score if available
4. optional Climatiq Search API fallback only when local retrieval is weak
```

### Scoring

Use or approximate:

```text
final_score =
  metadata_score * 0.35
+ semantic_score * 0.35
+ keyword_score * 0.20
+ source_quality_score * 0.10
```

### Thresholds

```text
score >= 0.75:
  accept normally

0.55 <= score < 0.75:
  accept with medium factor confidence

score < 0.55:
  reject and use fallback or unresolved
```

### Candidate Shape

Candidates must include:

```text
activity_id
name
sector
category
unit_type
score
match_reasons
```

### Hard Filters

- Energy events must not use distance factors.
- Transport events must not use waste factors.
- Wrong unit types must be rejected before Climatiq.

### Frontend Scope

Show factor match reasons in expanded/details view if available.

### Acceptance Criteria

- V2 retrieval returns scored candidates.
- Candidates include match reasons.
- Wrong unit type candidates are rejected.
- Low-score candidates are not used for Climatiq calls.
- Energy and transport V2 slices still pass.

### Tests

Use fake local factor records.

Test:

- heater/electricity query prefers energy factor
- car query prefers transport distance factor
- wrong unit type rejected
- low score becomes fallback/unresolved
- match reasons populated

### Do Not Do

- Do not depend on live Climatiq Search API in tests.
- Do not delete V1 Chroma retrieval.

## Ticket 4: V2 Climatiq Validation And Fallback Integration

### Goal

Safely connect V2 factor candidates and parameters to Climatiq.

### Dependencies

Ticket 3.

### Backend Scope

Add validation before every Climatiq call:

```text
factor unit_type matches parameter dimensions
required parameters exist
parameter units are valid
activity_id exists
```

Use the existing `ClimatiqClient` where possible, but keep V2 validation separate.

### Behavior

If validation fails:

```text
try next candidate
if no candidate remains, use fallback_estimated or unresolved
```

If Climatiq call fails:

```text
use fallback_estimated if local fallback exists
otherwise failed
```

### Frontend Scope

Display source clearly:

```text
estimated
fallback_estimated
unresolved
failed
```

Show fallback assumptions and API/factor issues when present.

### Acceptance Criteria

- V2 never calls Climatiq with missing required parameters.
- Invalid factor/parameter combinations are rejected before API call.
- Successful mocked Climatiq response yields `estimated`.
- Mocked API failure yields `fallback_estimated` where fallback exists.
- If no fallback exists, response is `failed` or `unresolved` with issues.
- Totals include fallback estimates.
- Source breakdown is correct.

### Tests

Mock Climatiq client.

Test:

- successful Climatiq estimate
- validation failure tries next candidate
- validation failure with no candidate becomes fallback/unresolved
- Climatiq error becomes fallback
- fallback counts toward total
- source breakdown is correct

### Do Not Do

- Do not use live Climatiq in tests.
- Do not remove fallback estimates from totals.

## Ticket 5: V2 Frontend Transparency And UX Pass

### Goal

Make V2 results understandable in the frontend.

### Dependencies

Tickets 1 through 4.

### Backend Scope

Only adjust response builder if the frontend needs a small field normalization.

Do not change core estimation behavior unless required by display correctness.

### Frontend Scope

Render V2 responses with:

- total kg CO2e
- total confidence as `Medium (0.72)`
- source breakdown
- per-event status
- per-event confidence
- parameters used
- assumptions
- issues
- factor match reasons if available
- fallback vs Climatiq source

Show `not_estimated` support only if present from Ticket 6; otherwise make the UI tolerant of it.

### Endpoint Strategy

Frontend should be able to target V2 without hardcoding production behavior.

Acceptable approaches:

- frontend env var for endpoint version
- simple local constant
- feature flag-style switch

Do not permanently remove V1 usage unless the user explicitly asks.

### Acceptance Criteria

- V2 response renders without crashing.
- Confidence appears as `Medium (0.72)` style.
- Assumptions and issues are visible.
- Source breakdown is visible.
- Frontend remains usable if an event has no assumptions/issues.
- Frontend build passes.

### Tests And Verification

Run:

```powershell
npm run build
```

If browser tooling is available, manually verify:

- heater duration response
- car ride response
- fallback response
- unresolved response if available

### Do Not Do

- Do not redesign the entire product UI.
- Do not remove V1 endpoint.

## Ticket 6: V2 Regression, Not Estimated, And Hardening

### Goal

Harden V2 with golden regressions, `not_estimated` behavior, unresolved behavior, and edge cases.

### Dependencies

Tickets 1 through 5.

### Backend Scope

Add robust handling for:

```text
not_estimated
unresolved
failed
```

`not_estimated` examples:

```text
I read a book for 2 hours.
I studied all afternoon.
```

`unresolved` examples:

```text
I used my thing for a while.
```

Do not force fake precision.

### Frontend Scope

Display `not_estimated` events in a secondary/collapsed section.

Do not include `not_estimated` events in totals.

### Golden Regression Suite

Create a fixture such as:

```text
tests/fixtures/v2_golden_inputs.jsonl
```

Include at least:

```json
{"input":"I used a 2 kW heater for 3 hours.","expected_category":"energy","expected_activity_type":"space_heater_use","expected_energy_kwh":6}
{"input":"I turned on the heater for 3 hours.","expected_category":"energy","expected_activity_type":"space_heater_use","expected_assumption_code":"space_heater.default_power"}
{"input":"I used 5 kWh of electricity.","expected_category":"energy","expected_activity_type":"electricity_use","expected_energy_kwh":5}
{"input":"I took a 7k ride.","expected_category":"transport","expected_activity_type":"car_ride","expected_distance_km":7,"expected_assumption_code":"distance.compact_k_context_km"}
{"input":"I took a 7 km ride in a Toyota Camry.","expected_category":"transport","expected_activity_type":"car_ride","expected_distance_km":7,"expected_assumption_code":"vehicle.toyota_camry.default_petrol_medium"}
{"input":"I drove 7 km in my electric Toyota Camry.","expected_category":"transport","expected_activity_type":"car_ride","expected_fuel_type":"electric"}
{"input":"I read a book for 2 hours.","expected_status":"not_estimated"}
```

### Acceptance Criteria

- Golden tests pass deterministically.
- `not_estimated` events are returned but excluded from totals.
- `unresolved` events include visible issues.
- Edge cases do not crash the API.
- V1 endpoint remains intact.
- Frontend build passes.

### Tests

Add tests for:

- golden fixture examples
- not estimated excluded from total
- unresolved visible in response
- empty/irrelevant input behavior
- malformed input does not crash endpoint
- existing V1 tests still pass

### Do Not Do

- Do not add telemetry.
- Do not add external vehicle APIs.
- Do not make tests depend on live services.

## Final Ticket Order

Implement in this order:

```text
1. V2 Energy Slice, Heater And Electricity
2. V2 Transport Slice, Distance And Vehicle Defaults
3. V2 Local-First Scored Factor Retrieval
4. V2 Climatiq Validation And Fallback Integration
5. V2 Frontend Transparency And UX Pass
6. V2 Regression, Not Estimated, And Hardening
```

## Overall Definition Of Done

V2 is complete when:

- `/api/estimate-v2` supports the energy and transport examples above.
- V2 responses include confidence, assumptions, statuses, issues, totals, and source breakdown.
- Factor retrieval is scored, local-first, and validates unit compatibility.
- Climatiq calls are made only with valid parameters.
- Fallback estimates count toward totals with transparent source breakdown.
- `not_estimated` and `unresolved` statuses are handled.
- Frontend can display V2 outputs clearly.
- Golden regression tests pass.
- Unit/API tests do not require live external services.
- V1 `/api/estimate` still works until the user explicitly migrates away from it.
