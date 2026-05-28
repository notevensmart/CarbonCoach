# CarbonCoach Consumer Result Dashboard UI Ticket Plan

This document defines the UI work that should follow CarbonCoach V2 Ticket 6.
It turns the transparent V2 estimate response into a consumer-facing daily
reflection experience without weakening the visibility of uncertainty.

Agents implementing these tickets must also follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`

## Product Goal

The result page should feel like:

```text
An intelligent sustainability reflection assistant
```

It should not feel like:

```text
A raw estimation/debug console
```

A user should be able to understand, within a few seconds:

- their total estimated emissions
- which category contributed most
- which activities could not yet be included
- the most important assumptions affecting trust
- one concise, evidence-backed reflection

Technical evidence must remain available, but collapsed by default.

## Sequencing Decision

Do not build all dashboard ideas in one implementation ticket.

Implement in this order:

```text
UI-1. Consumer Dashboard Core
UI-2. Deterministic Impact Comparison (already implemented)
Backend Ticket 7. Everyday Journal Coverage And Completeness and UI-2 hardening
UI-3. Structured Clarification Workflow
```

`UI-1` is the recommended immediate next ticket after V2 Ticket 6.
`UI-2` has already been implemented. Backend Ticket 7 must now make mixed
everyday journals, especially goods/services and waste activities, visible and
honestly estimable where supported, and must suppress the existing impact
comparison when a represented result is partial due to unresolved or failed
activities.

## Shared Rules

### Dependencies

These tickets assume V2 Ticket 6 has established:

- `estimated`, `fallback_estimated`, `not_estimated`, `unresolved`, and
  `failed` statuses
- overall `confidence`
- additive `parameter_confidence` and `factor_confidence` fields where present
- factor fit retained as explanatory metadata
- factor-aware total confidence
- multi-event V2 responses

Do not weaken or replace those behaviors for presentation convenience.

### Response Contract Strategy

The consumer dashboard renders from the existing generic V2 response contract.

The frontend may derive presentation summaries such as category totals, main
driver, and deterministic insight text from `details`. It must not require
activity-specific backend fields or recognize literal journal examples.

No UI ticket may remove:

```text
POST /api/estimate
POST /api/estimate-v2
```

### Category Presentation

Keep backend taxonomy unchanged. Use frontend presentation labels:

```text
transport       -> Transport
energy          -> Energy
goods_services  -> Goods
waste           -> Waste
```

Display order:

```text
Transport, Energy, Goods, Waste
```

Use this stable order for legends and equal-value tie display; do not imply
one category is larger when values are tied.

### What Counts Toward Emissions

Only details with statuses below contribute to totals, category breakdowns,
main driver calculation, largest activity calculation, and comparison cards:

```text
estimated
fallback_estimated
```

Do not include:

```text
not_estimated
unresolved
failed
```

The UI may show those activities, but must not visually imply that they were
included in estimated emissions.

### Honest Framing

Use the phrase:

```text
estimated footprint
```

Do not label a partial estimate as the user's complete footprint.

If any `unresolved` or `failed` detail exists, the summary must visibly say
that one or more activities could not yet be included.

The category visualization must be labelled:

```text
Breakdown of estimated emissions
```

### Confidence And Explainability

The main dashboard should show:

- overall confidence label
- per-activity overall confidence label
- friendly significant assumption text when assumptions exist
- an approximation/fallback indication for `fallback_estimated` details

The main dashboard should not show:

- activity IDs
- raw factor match-reason lists
- issue codes
- assumption codes
- retrieval terminology
- raw factor scores

The developer details accordion may show:

- raw event text
- parameters used
- assumption and issue codes/messages
- factor name and activity ID
- factor fit
- `parameter_confidence`
- `factor_confidence`
- overall `confidence`
- factor match reasons

Do not call factor fit "accuracy" or suggest that confidence modifies CO2e.

### Assumption Visibility

Do not hide material assumptions inside the developer accordion.

For any estimated card with assumptions, show consumer-facing assumption
messages without their internal codes under a heading such as:

```text
What we assumed
```

The frontend must render assumption messages generically. It must not create
special UI branches for particular vehicle models, activity examples, or
assumption codes.

### Friendly Unresolved Copy

Do not expose internal issue text as the main unresolved message when that
text discusses factor pathways or implementation state.

Until a structured clarification contract exists, use safe generic consumer
copy:

```text
unresolved:
  We could not estimate this activity yet.

failed:
  This activity could not be estimated right now.

not_estimated:
  This activity was recognised but is not included in estimated emissions.
```

Keep underlying issue details in the developer accordion.

### Determinism And External Services

Consumer insights and dashboard summaries in these tickets must be derived
deterministically from V2 response data.

Do not introduce a live LLM request to write result-page prose.

Frontend and API tests must not require live:

```text
Climatiq
OpenRouter
Hugging Face
Google Cloud Storage
```

### Deployment Visibility

Frontend work is complete only when it is visible through the production-like
served React path established in Ticket 1A:

```text
FastAPI serves the built React app at /
```

For every UI implementation ticket:

- run frontend tests where added
- run `npm run build`
- run backend tests if response handling or served-app integration is touched
- verify the built React app through the FastAPI-served route in a browser

## UI-1: Consumer Dashboard Core

### Goal

Replace the developer-heavy default result display with a clean consumer
dashboard while preserving technical evidence in a collapsed details area.

### Dependencies

V2 Ticket 6.

### Scope

Implement:

- hero summary card
- category breakdown visualization
- readable estimated activity cards
- needs-attention section
- secondary `not_estimated` display
- deterministic insight summary
- developer details accordion

Do not implement:

- impact equivalence comparisons
- interactive clarification controls
- LLM-generated result prose
- historical/trend features

### UI Hierarchy

Render result content in this order:

```text
1. Hero Summary Card
2. Deterministic Insight Summary
3. Category Breakdown
4. Estimated Activity Cards
5. Needs Attention
6. Not Included Activities, only when present
7. Developer Details Accordion
```

#### 1. Hero Summary Card

Display:

- title: `Today's Estimated Footprint`
- total `kg CO2e`
- main driver
- overall confidence label
- inclusion warning when unresolved/failed activities exist

Examples:

```text
Today's Estimated Footprint
3.15 kg CO2e

Main driver: Transport
Confidence: Medium
1 activity could not yet be included.
```

For total `0` with no contributing events:

```text
No emissions estimate is available yet.
```

Main-driver logic:

```text
sum co2e by category from estimated and fallback_estimated details only
if exactly one positive category has the highest amount:
  show that category
if two or more positive categories tie for the highest amount:
  show "Multiple categories"
if no category has positive emissions:
  omit main driver
```

Do not show numeric confidence scores in the hero by default. Display:

```text
High
Medium
Low
```

Numeric scores remain available in developer details.

#### 2. Deterministic Insight Summary

Generate one or two concise sentences from result data only.

Allowed logic:

```text
unique largest contributing category:
  "{Category} was the largest part of today's estimated footprint."

largest-category tie:
  "Today's estimated footprint was spread across multiple categories."

unresolved or failed details present:
  "{N} activity/activities could not yet be included in the estimate."

overall confidence is medium or low:
  "Treat this as an approximate guide because some details were uncertain or assumed."
```

Selection order:

```text
1. largest-category sentence, if a contributing category exists
2. unresolved/failed sentence, if applicable
3. confidence-awareness sentence, only if fewer than 2 sentences have been shown
```

Constraints:

- maximum 2 sentences in UI-1
- non-judgmental tone
- no behavioral advice
- no counterfactual claim such as "taking the bus reduced emissions"
- no statement unsupported by current estimate details

#### 3. Category Breakdown

Display an accessible donut chart or equivalent compact visual labelled:

```text
Breakdown of estimated emissions
```

Implementation guidance:

- prefer a lightweight accessible SVG/CSS implementation for this single chart
- do not introduce a charting dependency unless it provides clear accessibility
  or maintainability value
- provide visible text legend values and percentages; color alone is not enough

Data rules:

```text
use estimated + fallback_estimated detail co2e only
hide categories whose calculated amount is 0
percentage = category co2e / contributing total
round presentation percentages deterministically
```

If the contributing total is `0`, do not show an empty chart. Show:

```text
No estimated emissions to break down yet.
```

If unresolved or failed details exist, show a note below the chart:

```text
Activities needing attention are not included in this breakdown.
```

#### 4. Estimated Activity Cards

Show one card for each:

```text
estimated
fallback_estimated
```

Each card displays:

- category icon derived from category, not named entities
- human-readable activity label derived from `activity_type`
- concise parameter summary
- emissions estimate
- overall confidence label
- visible assumptions if present
- friendly approximation label when source is fallback

Generic icon map:

```text
transport       -> transport icon
energy          -> energy icon
goods_services  -> goods icon
waste           -> waste icon
```

Do not add model-specific or activity-example-specific images or branches.

Label formatting examples:

```text
car_ride          -> Car Ride
space_heater_use  -> Space Heater Use
coffee_purchase   -> Coffee Purchase
```

Parameter presentation must be generic over known response keys. Examples:

```text
distance + distance_unit       -> 18 km
energy + energy_unit           -> 4.5 kWh
vehicle_description            -> BMW X5
fuel_type                      -> petrol
duration + duration_unit       -> 3 hours
```

Fallback card copy:

```text
Approximate estimate
```

Do not display:

```text
fallback_estimated
climatiq
activity_id
factor fit
factor confidence score
```

in the primary card surface.

Assumption display:

```text
What we assumed
- {assumption.message}
```

Use messages directly and omit internal codes from the main card.

#### 5. Needs Attention

Display this section only when any detail has status:

```text
unresolved
failed
```

Section title:

```text
Needs Attention
```

Each item displays:

- human-readable activity label
- raw user fragment when available
- friendly status wording from the shared rules
- confidence label only if helpful and present

Do not present unresolved details as zero-emissions activities.

Do not create clarification controls in UI-1.

#### 6. Not Included Activities

Display only when one or more details have status:

```text
not_estimated
```

Use a visually secondary section:

```text
Not Included in Estimated Emissions
```

This is appropriate for activities such as walking where the current
operational-emissions boundary deliberately returns no estimate.

These activities must never contribute to hero totals or category charts.

#### 7. Developer Details Accordion

Collapsed by default.

Section label:

```text
How this estimate was calculated
```

For each detail, expose existing technical fields generically:

- raw activity text
- status and source
- calculation parameters
- assumptions and issue codes/messages
- factor name and activity ID, if present
- factor fit, if present
- `parameter_confidence`, `factor_confidence`, and overall `confidence`
- match reasons, if present

Use the terminology:

```text
Factor fit
Factor confidence
Estimate confidence
```

Never use:

```text
Factor accuracy
Estimate certainty
```

### Backend Scope

None expected.

Small additive response normalization is permitted only if a necessary field
from Ticket 6 is inconsistently serialized. Do not change estimation,
retrieval, fallback, or confidence calculations as part of UI-1.

### Frontend Implementation Guidance

Suggested component structure:

```text
frontend/src/components/results/
  ConsumerDashboard.jsx
  HeroSummaryCard.jsx
  InsightSummary.jsx
  CategoryBreakdown.jsx
  ActivityCard.jsx
  NeedsAttention.jsx
  NotIncludedActivities.jsx
  DeveloperDetailsAccordion.jsx
  resultPresentation.js
```

The exact structure may follow existing project style, but separate:

- deterministic presentation derivation
- visual components
- developer details rendering

Keep computation out of large JSX blocks where practical.

### Acceptance Criteria

- The default V2 result surface is consumer-facing rather than a visible debug panel.
- A user can identify total estimated emissions and main contributing category immediately.
- Overall confidence is visible without requiring expansion.
- Category breakdown includes only emissions-contributing event statuses.
- Zero-value categories are hidden.
- The chart is not shown for a zero contributing total.
- Material assumptions are visible in consumer-friendly wording on relevant cards.
- Fallback estimates are visibly marked as approximate.
- Unresolved/failed events appear in `Needs Attention` and are not shown as zero contributors.
- `not_estimated` activities appear in a secondary section and do not affect totals.
- The deterministic insight contains only supported claims.
- Technical fields remain accessible in a collapsed accordion.
- Factor fit is clearly distinct from estimate confidence inside developer details.
- Mixed multi-event responses render correctly.
- New activity types render through generic label/category logic.
- V1 remains reachable and V2 endpoint usage remains configurable as already established.

### Test Matrix

Add frontend tests for:

- one estimated heater result with assumptions
- one explicit high-confidence electricity result without assumptions
- mixed transport and energy result with correct main driver and breakdown
- equal largest-category tie
- unknown named vehicle fallback with visible consumer assumption
- fallback estimate marked approximate
- unresolved result shown in `Needs Attention` but excluded from hero/chart totals
- `not_estimated` walking result shown separately and excluded from totals
- all-unresolved response with no chart and no main driver
- empty details response
- additive Ticket 6 confidence fields rendered only inside developer details
- developer details accordion initially collapsed and expandable

Use response fixtures or component props only; do not call live services.

### Verification

Run:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

from `app` if integration or response-handling code changes.

Run:

```powershell
npm test -- --watchAll=false
npm run build
```

from `app/frontend`.

Verify through the production-like FastAPI-served React path:

- mixed estimated result
- fallback named vehicle result
- unresolved result
- `not_estimated` result
- expanded developer details

### Do Not Do

- Do not add an LLM-generated insight request.
- Do not add a comparison card in UI-1.
- Do not add clarification inputs in UI-1.
- Do not hide consumer-significant assumptions in developer details.
- Do not surface technical issue codes on the primary dashboard.
- Do not compute category totals from unresolved, failed, or `not_estimated` details.
- Do not add branches for individual model names or demonstration phrases.

## UI-2: Deterministic Impact Comparison

### Goal

Add one understandable emissions equivalence only after its methodology is
defined centrally and tested.

### Current Status And Hardening Dependency

UI-2 has already been implemented. Its eligibility rules must be hardened by
Backend Ticket 7, as specified in:

```text
docs/carboncoach-v2-everyday-coverage-ticket.md
```

### Scope

Add an optional comparison card such as:

```text
About the same emissions as driving an average petrol car for 16 km.
```

This must be a deterministic comparison, not generated prose.

### Methodology Requirement

Store comparison definitions in maintained backend metadata or a documented
domain module, not as constants hidden in React JSX.

Each comparison record must define:

```text
comparison key
display label
kg CO2e per display unit
unit
region or applicability boundary
source/provenance note
confidence/display eligibility rule
```

Initial scope should use at most one comparison family:

```text
average petrol passenger car distance
```

### Display Rules

Show at most one comparison.

Only show it when:

- total emissions are greater than zero
- total confidence is not low
- the maintained comparison is available and compatible
- the result is not partial because a represented activity is `unresolved` or
  `failed`

Use approximate language:

```text
About the same emissions as...
Roughly equivalent to...
```

Do not imply:

- emissions avoided
- a recommendation
- lifecycle equivalence beyond the maintained boundary
- exact accuracy

### Acceptance Criteria

- Comparison content is generated deterministically from maintained metadata.
- Its source and calculation are visible in developer details.
- It is hidden for low-confidence or zero-total results.
- It is hidden when coverage marks a represented result as partial due to
  unresolved or failed activities.
- It does not alter estimate totals or confidence.
- No comparison constants are embedded in presentation-only components.

### Tests

- positive total plus eligible confidence shows one comparison
- low confidence hides comparison
- zero total hides comparison
- positive-total partial mixed result hides comparison
- comparison wording is approximate
- comparison conversion is deterministic
- calculation metadata is visible in developer details

### Do Not Do

- Do not show more than one or two competing equivalences.
- Do not add unsupported environmental comparisons.
- Do not say public transport reduced emissions unless an actual
  counterfactual calculation is later implemented.

## UI-3: Structured Clarification Workflow

### Goal

Let users repair unresolved estimates with lightweight follow-up input while
preserving traceability of what they originally wrote and what they later
clarified.

### Dependencies

UI-1 and a separately approved API contract.

### Why This Is Separate

Clarification controls are not merely presentation. They require:

- stable identification of the unresolved event being clarified
- structured input fields and units
- deterministic merge/recalculation behavior
- provenance for added details
- multi-event handling when several details need clarification

Do not simulate this by silently rewriting journal text in the browser.

### Required API Design Before Implementation

Define an additive contract such as:

```json
{
  "journal": "I took the bus to work.",
  "clarifications": [
    {
      "event_id": "event-1",
      "field": "distance",
      "value": 10,
      "unit": "km"
    }
  ]
}
```

The corresponding response must preserve:

- original raw journal fragment
- clarification provenance
- recalculated parameters
- changed assumptions/issues/status/confidence

The exact request shape may evolve, but it must be documented and tested
before adding quick-choice controls.

### Initial Supported Clarification

Start narrowly with missing transport distance:

```text
How far was this trip?
[5 km] [10 km] [15 km] [Custom]
```

Do not expand to arbitrary corrections, fuel overrides, or appliance
properties in the same first clarification slice.

### Acceptance Criteria

- A supported unresolved distance event can be clarified and re-estimated.
- Original input remains visible.
- The supplied clarification is represented as user evidence, not a hidden assumption.
- Other events in the same journal retain their calculations.
- Unsupported clarification needs continue to show friendly guidance.

### Tests

- missing bus distance followed by supplied distance becomes estimable
- clarified value is treated as explicit user input
- multiple events do not bleed clarification values into one another
- original raw journal remains preserved
- malformed clarification input is rejected safely

### Do Not Do

- Do not append hidden prose to the original journal and pretend it was supplied originally.
- Do not prompt for information unless the backend knows how to consume it.
- Do not implement generic conversational follow-ups without a bounded schema.

## Future Work Outside These Tickets

Not included:

- accounts or authentication
- stored history
- weekly/monthly trends
- personalized recommendations
- long-term analytics
- counterfactual avoided-emissions claims
- LLM-written coaching summaries

## Overall Definition Of Done

The consumer dashboard work is complete when:

- the primary result screen emphasizes estimated footprint, main driver, and
  overall confidence
- categories are visualized honestly from included estimate details only
- important assumptions are understandable without opening developer details
- unresolved and `not_estimated` events remain visible without distorting totals
- deterministic insights avoid unsupported claims
- impact comparisons, if added, use documented maintained methodology
- clarification controls, if added, use an explicit provenance-preserving API contract
- developer details preserve explainability while remaining collapsed by default
- frontend verification passes through the production-like served React path
- no live external services are required by tests
- V1 endpoint availability and V2 response transparency are preserved
