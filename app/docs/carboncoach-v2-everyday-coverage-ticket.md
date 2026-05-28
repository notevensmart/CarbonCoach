# CarbonCoach V2 Ticket 7: Everyday Journal Coverage And Completeness

This document defines the backend coverage ticket that should follow V2
Ticket 6 and harden the already implemented consumer dashboard and impact
comparison behavior.

Agents implementing this ticket must also follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`
- `docs/carboncoach-consumer-ui-ticket-plan.md`

## Why This Ticket Exists

A consumer dashboard can present a technically correct subtotal in a way that
still feels like an estimate of the whole day.

Example journal:

```text
Today I drove around 12 km to work and grabbed a takeaway coffee on the way.
During lunch I ordered a beef burrito and a soft drink through a delivery app.
After getting home I ran the heater for most of the evening while gaming on my
PC for a few hours. Later I took out a bag of rubbish that had some food
packaging and plastic bottles in it.
```

An output containing only the car ride in the total and the heater as
unresolved is not sufficient. At minimum, the response must represent the
carbon-relevant goods, energy-device, and waste activities that were described,
even if some cannot yet be estimated.

This ticket addresses four related problems:

```text
1. activity segmentation and extraction are incomplete for ordinary journals
2. multiple activities can disappear while one supported activity survives
3. goods/services and waste are not sufficiently covered for a daily dashboard
4. the API does not explicitly describe how much represented activity is omitted
   from the total
```

## Current UI State And Sequencing

Implement this ticket:

```text
after V2 Ticket 6
after the already implemented UI-1 dashboard and UI-2 impact comparison
before relying on comparison output for mixed everyday journals
```

UI-1 and UI-2 are already present. This ticket must not remove UI-2 or
reimplement its methodology. Instead, it must ensure an equivalence
comparison is not displayed for a partial mixed-journal estimate where
represented carbon-relevant activities are unresolved or failed. An impact
comparison generated from an incomplete subtotal would make that subtotal
look more complete than it is.

## Goal

Make V2 reliable for mixed everyday journal entries by:

- improving activity segmentation and extraction across everyday narrative text
- improving multi-activity handling from extraction through totals, coverage,
  and existing comparison eligibility
- preserving supported and unsupported events independently through the response
- adding bounded, maintainable goods/services and waste estimation pathways
- returning explicit coverage-summary metadata for partial estimates
- stress-testing the system heavily on goods/services and waste language

The goal is not to estimate everything mentioned by a user. The goal is to
represent carbon-relevant activities honestly and estimate only those with a
defensible calculation path.

## Dependencies

- V2 Ticket 6: statuses, confidence hardening, multi-event regression baseline
- UI-1 may be complete or in progress; any frontend edits in this ticket must
  preserve its consumer/developer-detail separation

## Existing Behavior To Preserve

Do not regress existing behavior for:

- energy estimates and visible unresolved energy activities
- transport estimates and common transport-mode parity
- `not_estimated` events such as walking or reading where applicable
- factor fit, factor confidence, and overall confidence rules
- the centrally maintained deterministic impact-comparison methodology already
  implemented by UI-2
- `/api/estimate-v2`
- V1 `/api/estimate`

Existing recognition of goods or waste as `unresolved` is a useful baseline,
not sufficient completion of this ticket. This ticket must add robust coverage
and bounded estimation, not replace visible unresolved behavior with silent
drops or unjustified estimates.

## Product Boundary

Use the existing category taxonomy:

```text
transport
energy
goods_services
waste
```

Food and drinks remain under:

```text
goods_services
```

Do not introduce a new top-level `food` category.

## Core Behavioral Rule

For each carbon-relevant activity represented in a journal, the V2 response
must contain one event detail with one controlled status:

```text
estimated
fallback_estimated
unresolved
not_estimated
failed
```

An activity may remain unresolved because the app lacks weight, quantity,
disposal method, power, a compatible maintained factor, or a supported
methodology. It must not vanish merely because it cannot contribute to the
current total.

## Scope

### 1. Activity Segmentation And Extraction

Improve extraction so ordinary narrative structure does not suppress later or
embedded events.

Handle:

- multiple sentences
- clauses separated by `and`, `then`, `while`, `after`, `during`, and `later`
- two relevant activities in one clause
- event text surrounded by non-carbon context
- repeated activities in different parts of the journal
- activities that are detected but cannot yet be estimated

Required extraction properties:

- preserve the raw text span or the smallest useful user fragment for each event
- preserve source order in `details`
- avoid merging different calculation pathways into one event
- avoid duplicate details for the same span and activity pathway
- allow a supported event to estimate even when adjacent events are unresolved
- use controlled taxonomy and reusable phrase/synonym metadata rather than
  branches for a complete demonstration sentence

Event boundary examples:

```text
"grabbed a coffee and threw the empty cup in general rubbish"
-> goods_services / coffee_purchase
-> waste / landfill_waste

"ordered a beef burrito and a soft drink through a delivery app"
-> one or more goods_services events according to maintained product-factor
   coverage; preserve the drink and delivery context if not included

"ran the heater while gaming on my PC"
-> energy / space_heater_use
-> energy / generic_energy_use or a maintained computing-device activity type
```

Do not force every mentioned object into its own estimate if it cannot be
mapped to an independent maintained calculation boundary. If an add-on or
delivery component is outside the selected factor boundary, preserve it in
entities or issues so the response does not imply that it was counted.

### 2. Multi-Activity Pipeline Handling

Extraction alone is not sufficient. Once multiple events have been identified,
the pipeline must handle each one independently and preserve that independence
through estimation, aggregation, coverage reporting, and display eligibility.

Required behavior:

- each event is normalized, enriched, built, retrieved, validated, and
  estimated or status-classified independently
- a failure, unresolved parameter, rejected factor, or provider failure for
  one event does not suppress other event details or estimates
- repeated same-category activities remain separate details unless a
  documented aggregation step is added later
- quantities and entities do not bleed from one event into an adjacent event
- totals and category breakdowns include only contributing statuses
- `coverage` counts are derived from the final detail set, not from an early
  extraction count that may diverge after processing
- existing comparison eligibility is evaluated after event processing and
  coverage calculation

Examples:

```text
"bought two coffees, drove 8 km home, and recycled 500 g of bottles"
-> three independently processed details in narrative order

"ordered a burrito through a delivery app, ran the heater, and took out rubbish"
-> meal/delivery boundary, heater status, and waste status remain independently
   visible even if only one activity can currently be estimated
```

For the existing impact comparison:

```text
if coverage.estimate_is_partial is true:
  comparison = null
```

This is deliberately stricter than the current total/confidence-only
eligibility check. Confidence describes included calculations; it does not
make an equivalence for an incomplete daily subtotal appropriate.

### 3. Goods/Services Coverage

Add or complete a bounded goods/services estimation pathway driven by
maintained factor metadata.

Initial controlled activity types:

```text
coffee_purchase
restaurant_meal
food_purchase
```

Existing controlled types such as `clothing_purchase`,
`electronics_purchase`, and `generic_purchase` must remain visible when
detected, but they do not need new estimates in this ticket unless supported
by the same metadata-driven mechanism.

#### Required Calculation Boundary

Estimate a goods/services event only when:

- its product or meal class maps to a reviewed maintained factor record
- the record defines the required calculation unit, such as `item`, `serving`,
  `kg`, or `money`
- the event contains that quantity or the quantity can be derived from a
  conservative singular/count rule with a visible assumption
- factor retrieval and validation accept a compatible factor or a maintained
  fallback factor exists

If these requirements are not met, return `unresolved` with a specific issue.

Required missing-data examples:

```text
"grabbed a takeaway coffee"
-> may derive count = 1 only if the maintained coffee pathway uses item/serving
   units; show a visible count assumption

"bought two coffees"
-> use explicit count = 2 where an item/serving factor is maintained

"spent $6 on coffee"
-> estimate only if a compatible money-based factor is maintained;
   do not convert price to beverage count silently

"ordered groceries"
-> unresolved unless the journal supplies mapped product quantities or an
   explicitly documented spend-based factor exists

"ordered a beef burrito and a soft drink"
-> do not claim both components were counted if only a meal factor is used;
   estimate represented mapped components and return a visible issue or
   unresolved detail for components outside the maintained boundary
```

#### Goods Factor Metadata

Goods/services factor definitions must be maintained as reviewed data, not
hidden in extraction branches or JSX.

Each record must include at least:

```text
factor key or activity identifier
supported activity_type
supported product or meal class
calculation unit type
required parameter dimension
factor value or provider mapping
region/boundary note where relevant
source/provenance note
factor/source confidence
```

Do not invent product-level precision from generic words. If a broad fallback
is used, state its boundary and reduce confidence appropriately.

#### Delivery Context

A phrase such as:

```text
"through a delivery app"
```

does not provide transport distance or vehicle data for delivery emissions.
Preserve this context and show that delivery transport is not included unless
a documented delivery-estimation methodology is added.

Do not silently treat a restaurant meal factor as including delivery travel.

### 4. Waste Coverage

Add or complete a bounded waste estimation pathway driven by material,
disposal method, and weight.

Initial controlled activity types:

```text
landfill_waste
recycling
composting
```

#### Required Calculation Boundary

Estimate a waste event only when:

- disposal method is explicit or safely normalized from a controlled phrase
- material is mapped if required by the chosen factor
- weight is explicit or a documented, reviewed default exists for the exact
  bounded item class
- a compatible maintained factor or validated provider factor exists

Prefer `unresolved` to guessing the weight of a bag, bin, bottle, takeaway
container, or mixed rubbish load.

Required behavior:

```text
"I recycled 500 g of plastic bottles."
-> recycling with plastic and 0.5 kg; estimate if compatible factor is maintained

"I put 2 kg of food scraps in the compost bin."
-> composting with food waste and 2 kg; estimate if compatible factor is maintained

"I put 1 kg of general rubbish in the landfill bin."
-> landfill_waste with 1 kg; estimate if compatible factor is maintained

"I took out a bag of rubbish containing food packaging and plastic bottles."
-> visible waste event; unresolved because mass is missing and recyclable-looking
   contents do not prove the disposal route

"I had plastic bottles in my bag."
-> do not classify as disposed waste without disposal context
```

#### Material And Disposal Rules

- Do not assume `recycling` merely because plastic, glass, cans, or cardboard
  are mentioned.
- Do not assume a known mass for `bag`, `bin`, `bottle`, `cup`, or
  `packaging` unless a separately reviewed default is introduced.
- Preserve mixed material descriptions when one material-specific factor
  cannot represent the whole disposed load.
- If a user explicitly states a method and mass but uses an unmapped material,
  return unresolved or use only a clearly documented mixed/general waste
  factor.
- Store waste material and disposal synonym mappings centrally.

### 5. Other Carbon-Relevant Events In Mixed Journals

This ticket is strongest on goods/services and waste, but mixed journals must
not lose adjacent energy activities.

At minimum, inputs such as:

```text
"while gaming on my PC for a few hours"
```

must become a visible energy event if the phrase is carbon-relevant and
detectable. It may remain `unresolved` until the system has a reviewed
device-power pathway and usable duration.

Do not introduce speculative PC power estimates merely to increase coverage.

### 6. Additive Coverage Summary

Add an optional top-level V2 response field:

```json
{
  "coverage": {
    "represented_activity_count": 6,
    "included_in_total_count": 2,
    "unresolved_count": 3,
    "not_estimated_count": 1,
    "failed_count": 0,
    "estimate_is_partial": true
  }
}
```

Definitions:

```text
represented_activity_count:
  number of details returned by the extractor/pipeline

included_in_total_count:
  number of estimated and fallback_estimated details

estimate_is_partial:
  true when any represented event is unresolved or failed
```

This summary is not a claim that extraction found every possible activity in
the journal. Do not label it `complete` or assign a completeness probability.

The existing overall confidence field continues to describe confidence in
calculated estimates. It must not be reduced solely because separate activities
were unresolved; partial coverage is communicated through `coverage` and the
returned event statuses.

### 7. Existing Impact Comparison Guard

UI-2 has already implemented a deterministic impact comparison. Preserve its
maintained metadata and approximate language, but extend its display
eligibility with partial-coverage behavior:

```text
comparison may be returned only when:
  total emissions are greater than zero
  total confidence is not low
  maintained comparison metadata is compatible
  coverage.estimate_is_partial is false
```

When a mixed result contains any `unresolved` or `failed` represented event:

```text
comparison = null
```

Do not remove a comparison only because a deliberate `not_estimated` activity
exists, such as walking under a zero-operational-emissions boundary, unless
that status also reflects a known omitted carbon-relevant component in a later
documented methodology.

This rule does not change totals, factors, or confidence. It prevents a
consumer-facing equivalence from overstating a partial estimate.

## Backend Implementation Guidance

Keep work primarily in:

```text
app/domain/
app/pipeline_v2/
```

Expected areas:

```text
domain/models.py
domain/activity_taxonomy.py
domain/assumptions.py or reviewed factor metadata module
pipeline_v2/event_extractor.py
pipeline_v2/quantity_normalizer.py
pipeline_v2/parameter_builders.py
pipeline_v2/factor_retriever.py
pipeline_v2/validator.py
pipeline_v2/pipeline.py or response builder
```

Implementation must be data-driven:

- put product classes, material classes, synonyms, required dimensions, and
  factor keys in maintained metadata
- make builders dispatch from activity type and normalized dimensions
- make retrieval/validation choose factors from compatibility metadata
- do not encode complete journal sentences as special-case decisions
- do not introduce one regular-expression calculation branch per test example

Regex or deterministic phrase recognition may be used for bounded extraction,
provided the controlled vocabulary is centralized and variation tests prove
the pipeline is not only matching the listed demonstrations.

## Frontend Scope

Keep frontend changes small and generic.

If UI-1 is already implemented, ensure it can render:

- Goods and Waste category contributions from estimated/fallback details
- goods/services and waste activity cards without activity-specific layout code
- newly visible unresolved goods, waste, and device details in Needs Attention
- partial coverage warning derived from details or the additive `coverage` field
- technical factor/issue details only in the developer accordion
- no impact comparison for a result whose `coverage.estimate_is_partial` is true

Preserve the already implemented UI-2 comparison card and developer
methodology details for eligible complete-enough represented results.

Do not implement:

- UI-3 clarification controls
- LLM-written insight prose

## Representative End-To-End Journal

The following journal is a mandatory pipeline/API regression:

```text
Today I drove around 12 km to work and grabbed a takeaway coffee on the way.
During lunch I ordered a beef burrito and a soft drink through a delivery app.
After getting home I ran the heater for most of the evening while gaming on my
PC for a few hours. Later I took out a bag of rubbish that had some food
packaging and plastic bottles in it.
```

Minimum required representation:

| Described activity | Category | Required response behavior |
| --- | --- | --- |
| car journey | `transport` | existing estimable pathway remains represented |
| takeaway coffee | `goods_services` | visible; estimate only with maintained compatible pathway |
| beef burrito / soft drink order | `goods_services` | visible mapped components or honest unresolved boundary |
| delivery context | `goods_services` context or issue | state when delivery travel is not included |
| heater use | `energy` | visible; unresolved if duration cannot safely be quantified |
| gaming PC use | `energy` | visible, at least unresolved unless a maintained pathway exists |
| bag of rubbish/materials | `waste` | visible; unresolved when mass/disposal path is insufficient |

Assertions:

- the response contains details for each represented carbon-relevant pathway
- output ordering follows the input narrative
- any excluded activity is visible through status and/or issue
- the total includes only estimated/fallback-estimated details
- `coverage.estimate_is_partial` is true while relevant represented events are unresolved
- the existing impact comparison is absent because this represented result is partial
- no delivery or waste quantity is fabricated from the narrative

## Robustness And Stress-Test Standard

Goods/services and waste tests are the center of this ticket, not optional
extras. Use parameterized family matrices and mixed-journal fixtures in
addition to golden examples.

Tests must prove:

- detection across common synonyms and sentence structure
- compatible estimates only when required quantities/methodology exist
- unresolved visibility for missing or unsupported calculation dimensions
- negative phrases are not treated as carbon activities
- event ordering and independence in mixed journals
- irrelevant prose does not change parameters or chosen factor for the same event
- external failures do not remove other event details
- all factor/provider behavior is fake or fixture-backed in tests

### Goods/Services Stress Matrix

Include at least the following cases, plus additional variations discovered
during implementation:

| Journal fragment | Required result |
| --- | --- |
| `I grabbed a takeaway coffee.` | `coffee_purchase`; estimate only through maintained item/serving pathway with visible inferred count |
| `I bought two coffees on the way to work.` | `coffee_purchase` with explicit count `2` |
| `I had 2 flat whites.` | mapped coffee event or visible unresolved if beverage synonyms are outside maintained vocabulary; never silent drop |
| `I spent $6 on coffee.` | money-based estimate only with compatible factor; otherwise unresolved |
| `I ordered a beef burrito for lunch.` | mapped meal/product event; estimate only with maintained applicable class |
| `I ordered a beef burrito and a soft drink.` | preserve both components or visibly disclose an excluded component |
| `I ordered takeaway through a delivery app.` | food/meal event visible; delivery transport not silently included |
| `I bought groceries for dinner.` | visible `food_purchase`; unresolved without suitable product/spend methodology |
| `I bought 1 kg of beef.` | normalized product/weight path if factor exists; otherwise unresolved with preserved quantity |
| `I bought an oat milk coffee and a shirt.` | two goods events, independent statuses |
| `I bought coffee, then drove 8 km home.` | goods and transport both retained in order |
| `I sat at the coffee table for an hour.` | must not produce `coffee_purchase` |
| `I reviewed a meal plan.` | must not produce `restaurant_meal` or `food_purchase` |
| `I worked on Java while drinking water.` | must not produce a coffee estimate |

Goods matrix assertions:

- singular/count inference has an assumption and lower parameter confidence
  than explicit count
- explicit quantities override defaults
- unsupported product variants remain visible without receiving a generic
  precise estimate
- delivery wording cannot silently add or erase an emissions component

### Waste Stress Matrix

Include at least the following cases, plus additional variations discovered
during implementation:

| Journal fragment | Required result |
| --- | --- |
| `I recycled 500 g of plastic bottles.` | `recycling`, plastic, `0.5 kg`; estimable only with compatible factor |
| `I recycled half a kilogram of cardboard.` | normalize supported natural quantity wording or visible unresolved, not drop |
| `I composted 2 kg of food scraps.` | `composting`, food waste, `2 kg` |
| `I put 1 kg of general rubbish in the landfill bin.` | `landfill_waste`, `1 kg` |
| `I threw away 750 g of mixed packaging.` | landfill/general path only if disposal language and factor boundary support it |
| `I put glass and plastic in the recycling bin.` | visible recycling event; unresolved if mass is absent |
| `I took out a bag of rubbish containing packaging and plastic bottles.` | visible waste event; unresolved for missing mass and/or disposal certainty |
| `I had plastic bottles in my backpack.` | no disposal event |
| `I bought a reusable bottle.` | goods event if supported, never a recycling event merely due to `bottle` |
| `That meeting was a waste of time.` | no waste event |
| `I recycled bottles after buying coffee.` | waste and goods both retained |
| `I drove home and put 500 g food waste into compost.` | transport and waste both retained |

Waste matrix assertions:

- recyclable materials do not imply recycling without method/context
- container words do not imply a mass
- mixed-material input does not receive a material-specific estimate that
  claims to cover the whole load without disclosure
- explicit method and weight take priority over defaults
- absent mass produces a visible missing-data issue

### Multi-Activity Stress Matrix

Test at least:

```text
transport + coffee + waste
transport + meal + heater + waste
coffee + recycling + electricity
meal + delivery context + rubbish + PC use
two separate purchases plus two separate disposal events
same activities in a different sentence order
relevant events mixed with irrelevant narrative sentences
```

For every mixed journal assert:

- expected event types or visible unresolved generic pathways are present
- detail order is stable and follows the journal
- an unresolved event does not prevent another event being estimated
- totals equal only contributing statuses
- coverage counts match returned details and included statuses
- comparison is absent whenever a returned unresolved or failed event makes
  `coverage.estimate_is_partial` true

### Estimation And Failure Tests

Use fake local factors and mocked clients to test:

- goods compatible factor selected and validated by its unit dimension
- waste compatible factor selected and validated by weight/material/method
- goods factor rejected for waste event and waste factor rejected for goods event
- low-fit factor becomes fallback or unresolved according to maintained metadata
- factor/source confidence caps overall confidence without changing CO2e
- Climatiq failure for one goods or waste event does not remove transport or energy results
- absent fallback yields visible unresolved/failed event rather than disappearance

### API And UI Tests

Add API tests for:

- the representative end-to-end journal above
- additive `coverage` serialization and counts
- total/source breakdown exclusions for unresolved events
- existing impact comparison is suppressed for a positive-total,
  non-low-confidence result that is partial due to unresolved/failed details
- existing impact comparison remains eligible for an otherwise eligible
  result with no unresolved or failed represented details
- backwards-tolerant clients when `coverage` is absent if rollout requires it
- V1 `/api/estimate` still responds

If frontend behavior changes, add frontend tests for:

- estimated Goods/Waste category contribution in the breakdown
- unresolved waste appears in Needs Attention
- partial coverage warning for a mixed result
- existing comparison card is hidden for partial mixed results and remains
  available for an eligible result without unresolved/failed details

## Acceptance Criteria

- Mixed ordinary journal entries return all detectable carbon-relevant event
  pathways rather than only transport or the first supported event.
- Goods/services and waste activity vocabulary and required dimensions are
  maintained centrally.
- At least one bounded goods/services pathway can contribute to estimated
  emissions from compatible, reviewable factor metadata.
- At least one bounded waste pathway can contribute to estimated emissions
  when required method/material/weight evidence is present.
- Missing goods quantities, missing waste weights, ambiguous waste disposal,
  delivery context, and unsupported products remain visible and do not gain
  fabricated precision.
- Adjacent device-energy activity such as PC gaming is represented visibly
  when detected, even if unresolved.
- The additive coverage summary correctly describes returned and included
  activities without claiming complete extraction.
- Multi-activity processing preserves detail order and isolation across
  parameters, statuses, failures, totals, and coverage computation.
- Overall confidence remains distinct from partial coverage and remains
  constrained by parameter, factor, and source confidence for contributing
  estimates.
- The already implemented impact comparison is suppressed for partial results
  and preserved for eligible results without unresolved/failed represented
  activities.
- Category totals and source breakdown include only `estimated` and
  `fallback_estimated` activity details.
- Goods/waste family stress matrices, mixed-event tests, negative tests, and
  invariance tests pass.
- Existing energy, transport, Ticket 6 confidence, and V1 endpoint tests pass.
- No test requires live Climatiq, OpenRouter, Hugging Face, or Google Cloud
  Storage.
- Any frontend edits are generic and the production-like served React path is
  verified.

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

If frontend files change, verify in the FastAPI-served built React app:

- the representative mixed journal
- a goods estimate with a visible assumption
- a waste estimate with explicit weight and method
- a waste unresolved result with missing mass
- suppression of the existing comparison for a positive partial mixed result
- developer details for included and excluded components

## Do Not Do

- Do not introduce `food` as a fifth display/backend category.
- Do not hide detected unsupported activities merely to make totals cleaner.
- Do not estimate delivery travel from the words `delivery app`.
- Do not infer recycling from mention of recyclable materials alone.
- Do not invent mass for a bag, bin, bottle, cup, or packaging item.
- Do not embed goods/waste factor constants in React display code.
- Do not add a calculation branch for each demonstration sentence.
- Do not remove or duplicate the already implemented UI-2 comparison
  methodology; harden its eligibility for partial results.
- Do not make confidence a proxy for how much of the journal was represented.
- Do not multiply CO2e by confidence, factor fit, or partial-coverage status.
- Do not break or replace V1 `/api/estimate`.
