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

### Robustness Ratchet

Each ticket must make the system more robust than the previous ticket. Do not implement a slice as a single narrow keyword branch that only handles the listed happy-path examples.

Every extraction ticket must consider:

- multiple carbon-relevant events in one journal entry
- common wording variations for the supported activity
- irrelevant text before, between, and after supported activities
- ambiguous or missing quantities with visible assumptions or issues
- unsupported activities returned as `not_estimated` or `unresolved` instead of being silently dropped when they are carbon-relevant

The supported examples in a ticket are minimum regression cases, not the full boundary of expected behavior.

### Generalization And Engineering Gate

Agents must implement input families, not memorize examples.

Before completing a slice, identify the variation dimensions it is meant to
handle, such as:

```text
activity or mode
quantity spelling and unit formatting
explicit versus inferred properties
known, unknown, and ambiguous entities
missing data
contradictory data
multiple events in one journal
unsupported near-neighbor inputs
```

Implementation rules:

- put controlled vocabulary, synonyms, defaults, and fallback keys in taxonomy
  or maintained metadata rather than distributing phrase checks through the pipeline
- make normalizers, enrichers, parameter builders, retrieval, and validation
  operate on structured dimensions, not ticket-example strings
- preserve meaningful user-provided entities that are not recognized; expose
  assumptions or issues rather than dropping them or pretending they were absent
- use explicit user evidence before inference, verified metadata before
  defaults, and defaults before low-confidence fallback
- introduce provider interfaces for external or broad reference data, with
  deterministic fixture/cache-backed test implementations and failure behavior
- avoid activity IDs, product/model names, or complete journal sentences in
  decision logic unless they are entries in reviewable domain metadata
- document the supported family and the honest fallback boundary in each ticket

Hard-coded rules are acceptable only for controlled grammar/unit normalization,
controlled taxonomy synonyms, safety validation, or small reviewed bootstrap
metadata. They are not acceptable as the primary strategy for broad real-world
entity coverage.

### User-Visible Parity Gate

Once the production frontend defaults to V2, common inputs that already
produced an estimate in V1 must not silently regress to zero or `unresolved`
without a deliberate product decision visible to the user.

Before a V2-default UI is treated as complete:

- audit representative working V1 pathways against V2
- implement parity for common pathways, or keep a deliberate routing/fallback
  strategy while V2 coverage is incomplete
- add regressions for any user-observed loss of behavior, including common
  public-transport inputs

### Deployment Visibility Gate

Frontend changes are not complete until they are visible through the same deployment path users open in production.

For the current Cloud Run deployment, that means one of these must be true:

- FastAPI serves the built React app from the deployed container.
- The React app is deployed separately and points at the deployed FastAPI API base URL.

Do not count `npm run build` alone as deployment-ready. The ticket must also verify that:

- the Docker build context includes the frontend source or build artifacts when the backend image serves the UI
- the Dockerfile builds or copies the frontend assets needed by production
- FastAPI no longer serves the old inline HTML form at `/` when the React app is meant to be the production UI
- `/api/estimate-v2` is reachable from the deployed UI without relying on localhost-only configuration

### Testing Standard

Each ticket must include:

1. Unit tests for deterministic logic.
2. Pipeline/API tests from journal input to response.
3. Frontend build verification if frontend changes.
4. Deployment visibility verification if frontend changes.
5. Robustness tests for wording variation, irrelevant surrounding text, and multi-event behavior when extraction changes.
6. A coverage-matrix test set for each new supported family.
7. V1-to-V2 visible parity regressions when the production UI targets V2.

A coverage matrix must include, where applicable:

- at least one example not named in the ticket's supported-input list
- unit/spacing or wording variation
- an explicit-property override
- an unknown or ambiguous entity
- a missing-data or contradictory-data path
- a nearby negative example that must not be converted into an estimate
- a mixed multi-event journal
- an invariance test, such as unrelated surrounding prose not changing the
  normalized parameters or factor selection

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
- `/api/estimate-v2` uses the same readiness guard as `/api/estimate` so startup failures are visible.
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
- If Ticket 1 changes the visible UI, the deployed app path is updated so those fields are visible after Cloud Run deployment.
- Energy extraction is not implemented as an early-return single-event detector; it can coexist with other events in the same journal entry.
- Unsupported or irrelevant text around the heater/electricity event does not prevent the supported energy event from being estimated.

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
- journal with unrelated surrounding text plus heater event still estimates the heater event
- journal with heater and another carbon-relevant activity returns more than one event or clearly marks the unsupported event as `unresolved`/`not_estimated`
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

## Ticket 1A: Deployment Visibility Fix For V2 UI

### Goal

Make frontend changes visible in the deployed app.

This ticket exists because a React build can pass locally while Cloud Run still serves the old FastAPI inline HTML page.

### Dependencies

Ticket 1.

### Current Problem To Fix

The production image currently:

- excludes `app/frontend/` from the Docker build context
- runs only `uvicorn app.app:app`
- serves a hard-coded FastAPI HTML form at `/`
- does not serve the React build from the deployed container

### Required Decision

Choose one deployment model and document it in the ticket PR or commit message:

```text
Option A: single Cloud Run service
  Docker builds React and FastAPI serves the React build.

Option B: split deployment
  Frontend is deployed separately and calls the Cloud Run API URL.
```

Prefer Option A unless the project already has a separate frontend host configured.

### Backend/Deployment Scope For Option A

Update the deployment path so the Cloud Run image includes and serves the React app:

- remove the Docker ignore rule that excludes `app/frontend/`
- use a Node build stage or equivalent install/build step for `app/frontend`
- copy the React production build into the final image
- mount the React build with FastAPI static serving
- keep `/api/estimate` and `/api/estimate-v2` available as API routes
- remove or move the old inline root form so `/` returns the React app

### Frontend Scope

Ensure the deployed React app calls the deployed backend correctly:

- same-origin `/api/estimate-v2` for Option A
- configurable production API base URL for Option B
- no localhost-only endpoint assumptions
- while V2 coverage is narrower than V1, expose V2 deliberately as a
  selectable/clearly identified path or keep the general default on a path
  that does not remove already-working estimates

### Acceptance Criteria

- The deployed root page shows the React UI, not the old `Enter Your Daily Journal` inline FastAPI form.
- A production Docker build contains the frontend assets needed to render the UI.
- `GET /` returns the React app shell.
- `POST /api/estimate-v2` still returns the V2 response shape.
- `POST /api/estimate` still works until V1 is intentionally retired.
- The visible default estimation workflow does not silently turn common
  V1-estimated journal inputs into zero/unresolved V2 responses; if V2 remains
  incomplete, its reduced scope is explicitly selected or signposted.
- Browser verification confirms a heater journal can be submitted through the visible deployed UI.
- Frontend build passes.
- Backend/API tests pass.

### Tests And Verification

Run:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

from `app`.

Run:

```powershell
npm run build
```

from `app/frontend`.

Also verify one production-like path:

```powershell
docker build -t carboncoach-v2-ui .
docker run --rm -p 8080:8080 carboncoach-v2-ui
```

Then open:

```text
http://localhost:8080/
```

and confirm the React UI submits to `/api/estimate-v2`.

### Do Not Do

- Do not leave the production root path serving the old inline FastAPI form.
- Do not require users to open a separate local React dev server to see deployed UI changes.
- Do not hardcode localhost as the production API URL.

## Ticket 2: V2 Transport Slice, Distance And Transparent Vehicle Defaults

### Goal

Add transport support for distance, compact `k`, vehicle/fuel details, local
verified defaults, and honest fallback behavior for arbitrary named vehicles.

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
- explicit vehicle class/fuel enrichment independent of named-model support
- preservation of arbitrary named vehicle descriptions
- local verified vehicle defaults
- transport parameter builder
- contradiction handling through lowered confidence and issues

### Frontend Scope

Display transport-specific assumptions and issues, including:

- compact `k` interpretation
- vehicle default mapping
- unknown named-vehicle fallback mapping
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
I took a 5 km ride in a BMW X5.
I took a 5 km ride in a BMW X5 SUV.
I drove 5 km in an electric BMW iX SUV.
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

#### Arbitrary Named Vehicles

```text
BMW X5 -> preserve vehicle_description; generic class/fuel fallback with an explicit issue
BMW X5 SUV -> preserve vehicle_description; use the explicit large/SUV class; assume only fuel
electric BMW iX SUV -> preserve vehicle_description; use explicit electric and large/SUV traits
```

Do not alter emissions merely because an unverified model name sounds more
specific. Model-specific emissions require maintained vehicle metadata.

### Acceptance Criteria

- Transport events produce V2 response details.
- Transport extraction can return transport events alongside existing energy events from the same journal.
- `7k` only becomes km when context supports distance.
- `7k` in purchase/money context does not become distance.
- Vehicle model defaults are centralized.
- Arbitrary supplied vehicle descriptions are preserved in response parameters.
- Unknown named vehicles expose `vehicle.named_model.unmapped` rather than
  silently collapsing to a generic car with a misleading assumption.
- Explicit body class and fuel attributes affect estimates for any vehicle name.
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
- unknown named vehicle is retained with a visible fallback assumption and issue
- explicit SUV/fuel traits work with an unmapped vehicle name
- pipeline/API responses for supported transport inputs
- mixed journal containing transport and energy activities
- transport wording variations with extra non-carbon journal text

### Do Not Do

- Do not call external vehicle APIs.
- Do not require vehicle model year.
- Do not grow hand-written model regexes as the primary coverage strategy.
- Do not replace V1 matching.
- Do not add broad autocorrect that can change user meaning.

## Ticket 2A: Common Transport Mode Parity

### Goal

Restore and improve the common transport pathways a user reasonably expects
when the visible frontend submits to V2, including inputs already estimated by
V1 such as bus journeys.

### Dependencies

Ticket 2.

### Backend Scope

- Drive mode recognition from transport taxonomy/synonym metadata rather than
  separate sentence-specific branches.
- Support distance-based estimation or explicit zero-operational-emissions
  handling for the controlled transport families appropriate to available factors:
  `bus_ride`, `train_ride`, `rideshare`, `bicycle_ride`, and `walking`.
- Handle `flight` only where a defensible distance/factor path exists; otherwise
  keep it visible as unresolved with a useful issue.
- Keep unknown transport wording visible when carbon-relevant, and record the
  unsupported normalized mode or raw description rather than silently dropping it.
- Use reusable distance normalization and transport parameter construction
  across transport modes.
- Maintain mode fallback-factor metadata centrally with source/provenance notes.

### Required Behavior

Minimum cases:

```text
took a 5km bus ride -> estimated or fallback_estimated, not unresolved
caught the train for 12 km -> estimated or fallback_estimated
rode my bike 6 km -> not_estimated with zero operational emissions or estimated only if a documented boundary applies
walked 2 km -> not_estimated with zero operational emissions
took a rideshare 8 km -> estimate with a visible vehicle/default assumption
```

Mode synonyms such as `bus`, `coach`, `train`, `rail`, `bike`, `bicycle`,
`walked`, `taxi`, and `rideshare` should be maintained as data associated with
the activity taxonomy, not scattered one-off code paths.

### Acceptance Criteria

- The bus input reported by users no longer shows `0.00 kg CO2e` solely
  because the frontend uses V2.
- Common modes use one data-driven transport pipeline and centralized factor defaults.
- Unsupported modes are visible and produce one meaningful issue, not duplicated issues.
- Existing car and energy behavior remains intact in mixed journals.
- The frontend can keep rendering the existing V2 detail contract without mode-specific markup.

### Tests

- Add a table-driven matrix for mode synonyms, distance formatting, and expected statuses.
- Include `took a 5km bus ride` as a V1-visible-parity regression.
- Test bus/train mixed with heater and car events.
- Test walking/bicycle zero-operational-emissions behavior.
- Test an unknown transport mode and issue de-duplication.

### Do Not Do

- Do not solve public transport by adding a conditional for only the reported bus phrase.
- Do not claim full lifecycle emissions for walking/bicycling without a defined methodology.
- Do not depend on live external services in tests.

## Ticket 2B: Data-Backed Vehicle Specificity

### Goal

Provide broad make/model/version accuracy through maintained vehicle metadata,
instead of adding individual model branches whenever a user encounters one.

### Dependencies

Ticket 2.

### Backend Scope

- Add a vehicle metadata provider abstraction with a deterministic local/cache-backed test path.
- Query and normalize arbitrary makes/models/variants through the provider
  contract; do not introduce a new source-code branch per recognized model.
- Evaluate a suitable body/fuel metadata source and an emissions/fuel-economy
  source; body metadata alone must not be treated as precise emissions data.
- Enrich known make/model/year or variant information only when supported by
  verified metadata.
- Keep explicit user fuel/class inputs higher priority than provider defaults.
- Keep the current transparent named-vehicle fallback when metadata is missing
  or ambiguous.

### Required Behavior

- `BMW X5` is retained today with fallback assumptions; with verified variant
  metadata it may use a more specific class/fuel factor.
- Ambiguous model families with petrol, diesel, hybrid, and electric variants
  do not receive a precise fuel factor unless the variant is resolved.
- Provider failures do not prevent a visible fallback estimate.

### Tests

- Use faked/cached provider records only; never require live vehicle services.
- Cover ambiguous model variants, explicit user overrides, successful
  enrichment, missing records, and provider failure fallback.
- Include multiple fixture makes/models that are not literal product examples
  in this ticket, proving the path is provider-driven rather than whitelist-driven.

### Do Not Do

- Do not replace transparent uncertainty with guessed model-specific factors.
- Do not require live external APIs in tests.
- Do not add make/model-specific extraction branches to make fixtures pass.

## Ticket 3: V2 Local-First Scored Factor Retrieval

### Goal

Improve V2 emission-factor search using local-first scored retrieval.

### Dependencies

Tickets 1, 2, 2A, and 2B.

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

The scorer must be generic over normalized event metadata and candidate
records. Adding a new compatible factor record or vehicle/provider result
must not require adding an `if` branch for that activity name, activity ID,
make, model, or journal phrase.

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

`score` is the candidate factor-fit signal used for retrieval and selection,
not a probability of emissions accuracy. Ticket 6 must derive factor
confidence from the selected compatible factor and apply it to overall
estimate confidence without changing CO2e calculations.

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
- Required-dimension and compatibility rules come from taxonomy/validation
  metadata, not a growing list of example-specific exclusions.

### Frontend Scope

Show factor match reasons in expanded/details view if available.

### Acceptance Criteria

- V2 retrieval returns scored candidates.
- Retrieval supports multiple candidate lookups in one request without one event suppressing later events.
- Candidates include match reasons.
- Wrong unit type candidates are rejected.
- Low-score candidates are not used for Climatiq calls.
- Energy and transport V2 slices still pass.
- New fixture candidates can be selected correctly without code changes.
- Match reasons identify structured evidence, not merely that a literal name matched.
- The selected score remains factor-fit metadata, not a multiplier applied to
  emissions amounts.

### Tests

Use fake local factor records.

Test:

- heater/electricity query prefers energy factor
- car query prefers transport distance factor
- wrong unit type rejected
- low score becomes fallback/unresolved
- match reasons populated
- an unseen fixture activity with compatible metadata ranks through the same scorer
- adding an irrelevant candidate does not change the selected compatible factor
- entity changes such as explicit electric versus diesel alter factor ranking
  through metadata, without model-specific retrieval code

### Do Not Do

- Do not depend on live Climatiq Search API in tests.
- Do not delete V1 Chroma retrieval.
- Do not hard-code winning activity IDs or per-example score bonuses.

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

Validation and fallback selection must dispatch from parameter dimensions,
unit compatibility, status rules, and centrally maintained fallback metadata.
They must not dispatch from complete journal strings or fixture-specific
activity IDs.

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
- Climatiq/fallback handling is per event, so one failed event does not prevent other valid events from being estimated.
- Invalid factor/parameter combinations are rejected before API call.
- Successful mocked Climatiq response yields `estimated`.
- Mocked API failure yields `fallback_estimated` where fallback exists.
- If no fallback exists, response is `failed` or `unresolved` with issues.
- Totals include fallback estimates.
- Source breakdown is correct.
- A newly introduced compatible candidate/fallback fixture follows the same
  validation path without a new code branch.
- Fallback source/factor confidence is available to cap overall estimate
  confidence in Ticket 6.

### Tests

Mock Climatiq client.

Test:

- successful Climatiq estimate
- validation failure tries next candidate
- validation failure with no candidate becomes fallback/unresolved
- Climatiq error becomes fallback
- fallback counts toward total
- source breakdown is correct
- validation behavior is invariant to wording once normalized event/parameters match
- failures in one event do not alter valid estimates for unrelated mixed events

### Do Not Do

- Do not use live Climatiq in tests.
- Do not remove fallback estimates from totals.
- Do not build fallback handling as one conditional per demonstration input.

## Ticket 5: V2 Frontend Transparency And UX Pass

### Goal

Make V2 results understandable in the frontend.

### Dependencies

Tickets 1, 1A, 2, 2A, 2B, 3, and 4.

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
- factor fit or factor confidence if available
- parameters used
- assumptions
- issues
- factor match reasons if available
- fallback vs Climatiq source
- preserved unknown entities and their visible fallback issues/assumptions

Show `not_estimated` support only if present from Ticket 6; otherwise make the UI tolerant of it.

Render from the response contract generically. Do not add UI components that
know individual model names, activity example strings, or fixed assumption
codes solely to make selected demonstrations look correct.

### Endpoint Strategy

Frontend should be able to target V2 without hardcoding production behavior.

Acceptable approaches:

- frontend env var for endpoint version
- simple local constant
- feature flag-style switch

Do not permanently remove V1 usage unless the user explicitly asks.

### Acceptance Criteria

- V2 response renders without crashing.
- Multiple event cards/details render in one journal result.
- Confidence appears as `Medium (0.72)` style.
- Assumptions and issues are visible.
- Source breakdown is visible.
- Frontend remains usable if an event has no assumptions/issues.
- New activity types and unknown named entities render using the same generic detail view.
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
- unknown named vehicle and a multi-event response

### Do Not Do

- Do not redesign the entire product UI.
- Do not remove V1 endpoint.
- Do not create per-entity presentation branches for inputs such as individual vehicle models.

## Ticket 6: V2 Regression, Not Estimated, Confidence, And Hardening

### Goal

Harden V2 with golden regressions, `not_estimated` behavior, unresolved
behavior, factor-aware confidence, and edge cases.

### Dependencies

Tickets 1, 1A, 2, 2A, 2B, 3, 4, and 5.

### Backend Scope

Add robust handling for:

```text
not_estimated
unresolved
failed
```

Add factor-aware confidence handling:

```text
factor match score / factor fit:
  keep as retrieval diagnostics and display metadata

factor confidence:
  derive from the selected compatible factor fit and source quality

overall confidence:
  min(parameter confidence, factor confidence, source confidence)
```

For the initial deterministic implementation:

```text
selected compatible factor score -> numeric factor-confidence score
confidence levels continue to use the existing thresholds:
  score >= 0.80 -> high
  0.50 <= score < 0.80 -> medium
  score < 0.50 -> low
successful validated Climatiq estimate -> source confidence 1.00 unless
  maintained source-quality metadata explicitly supplies a lower cap
fallback factor -> use maintained fallback source/factor confidence
```

A factor may be accepted normally for estimation at `0.75` while still
contributing medium factor confidence. Confidence is a transparency/trust
calculation only: never multiply or otherwise rescale `co2e` by factor fit or
confidence.

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

Render overall confidence and, when added to the response, `factor_confidence`
and factor fit generically. The established overall `confidence` field must
remain available; the new confidence detail fields are additive.

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
{"input":"I took a 5km bus ride.","expected_category":"transport","expected_activity_type":"bus_ride","expected_status":"fallback_estimated"}
{"input":"I took a 5 km ride in a BMW X5.","expected_category":"transport","expected_activity_type":"car_ride","expected_issue_code":"vehicle.named_model.unmapped"}
{"input":"I read a book for 2 hours.","expected_status":"not_estimated"}
```

Golden cases are regressions, not the coverage strategy. Add table-driven or
generated variation matrices around activity modes, units, named/unknown
entities, explicit overrides, missing values, contradictions, and
multi-event ordering. The suite should demonstrate that related unseen inputs
exercise the same structured pathway.

### Acceptance Criteria

- Golden tests pass deterministically.
- `not_estimated` events are returned but excluded from totals.
- `unresolved` events include visible issues.
- Mixed journals with multiple activities produce multiple details instead of only the first recognized event.
- Edge cases do not crash the API.
- Selected medium-confidence factors cap otherwise high parameter confidence.
- Strong factor matches do not raise overall confidence above uncertainty from
  assumed parameters or contradictory evidence.
- Fallback-estimated events expose source/factor uncertainty and their overall
  confidence is capped accordingly.
- Total confidence aggregates event confidence after factor/source caps.
- Factor-confidence changes do not alter calculated `co2e` for identical
  activity parameters and selected factors.
- Visible V1-to-V2 parity regressions for common supported behavior pass while
  the frontend targets V2.
- Generalization matrices pass without requiring example-specific branches.
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
- common V1 estimated inputs submitted through V2 do not unexpectedly return zero
- equivalent phrasing/spacing variants normalize to equivalent parameter sets
- explicit property changes produce justified output changes
- high parameter confidence plus medium factor fit yields medium overall confidence
- medium parameter confidence plus high factor fit remains medium overall confidence
- fallback factor confidence caps overall confidence
- total confidence reflects factor-capped event confidences
- identical calculation parameters and selected factor produce identical
  `co2e` before and after factor-confidence scoring
- API/frontend tolerate additive `parameter_confidence` and
  `factor_confidence` fields while preserving overall `confidence`

### Do Not Do

- Do not add telemetry.
- Do not add external vehicle APIs.
- Do not make tests depend on live services.
- Do not mistake a growing golden fixture list for robust implementation.
- Do not multiply CO2e values by factor match or confidence scores.

## Final Ticket Order

Implement in this order:

```text
1. V2 Energy Slice, Heater And Electricity
1A. Deployment Visibility Fix For V2 UI
2. V2 Transport Slice, Distance And Transparent Vehicle Defaults
2A. Common Transport Mode Parity
2B. Data-Backed Vehicle Specificity
3. V2 Local-First Scored Factor Retrieval
4. V2 Climatiq Validation And Fallback Integration
5. V2 Frontend Transparency And UX Pass
6. V2 Regression, Not Estimated, Confidence, And Hardening
7. Everyday Journal Coverage And Completeness
```

Ticket 7 is specified in:

```text
docs/carboncoach-v2-everyday-coverage-ticket.md
```

It addresses the mixed-journal gap exposed by the consumer dashboard:
activity segmentation, independent multi-activity processing, bounded
goods/services and waste coverage, and explicit partial-estimate coverage
metadata. Because the deterministic impact comparison has already been
implemented, Ticket 7 must suppress that comparison for partial results rather
than treating its implementation as future work.

## Overall Definition Of Done

V2 is complete when:

- `/api/estimate-v2` supports the energy and transport examples above.
- Arbitrary named vehicles are retained and never presented as if no vehicle
  details were supplied.
- Model-specific estimates use verified metadata or explicit user traits rather
  than unbounded hand-written model branches.
- Common V1 transport inputs used in the V2-default UI no longer silently
  regress to unresolved/zero results.
- Supported families generalize across variation matrices rather than only
  passing their named regression examples.
- V2 responses include confidence, assumptions, statuses, issues, totals, and source breakdown.
- V2 overall confidence is constrained by selected factor/source uncertainty,
  while raw factor fit remains visible as explanatory retrieval metadata.
- V2 handles multi-activity journal entries without dropping later supported events.
- Each slice adds robustness coverage beyond the happy-path examples.
- Factor retrieval is scored, local-first, and validates unit compatibility.
- Climatiq calls are made only with valid parameters.
- Fallback estimates count toward totals with transparent source breakdown.
- `not_estimated` and `unresolved` statuses are handled.
- Mixed everyday journals preserve detected goods/services, waste, and
  adjacent energy-device activities even when some remain unresolved.
- Bounded goods/services and waste pathways estimate only from compatible,
  maintained factor metadata and sufficient activity data.
- Responses distinguish partial activity coverage from confidence in included
  calculations.
- Existing impact comparisons are not shown for represented results that are
  partial because one or more activities remain unresolved or failed.
- Frontend can display V2 outputs clearly.
- Frontend changes are visible through the deployed production path.
- The production deployment serves the intended UI instead of the legacy inline FastAPI form.
- Golden regression tests pass.
- Unit/API tests do not require live external services.
- V1 `/api/estimate` still works until the user explicitly migrates away from it.
