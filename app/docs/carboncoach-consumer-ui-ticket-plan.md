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
UI-4. Demo-Grade Intelligent Reflection Experience
```

`UI-1` is the recommended immediate next ticket after V2 Ticket 6.
`UI-2` has already been implemented. Backend Ticket 7 must now make mixed
everyday journals, especially goods/services and waste activities, visible and
honestly estimable where supported, and must suppress the existing impact
comparison when a represented result is partial due to unresolved or failed
activities.

`UI-4` is the final consumer-facing polish ticket after the backend
intelligence tickets and UI-3. It should make the single-session app feel
useful, intelligent, and visually premium without adding accounts,
persistence, history, or unsupported coaching claims.

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

## UI-4: Demo-Grade Intelligent Reflection Experience

### Goal

Turn the existing consumer dashboard into a polished single-session AI product
experience that feels insightful, capable, and demo-ready.

The UI should communicate:

```text
CarbonCoach understood my day, estimated what it safely could, and knows what
would improve the estimate next.
```

It should not feel like:

```text
A prettier debug output.
```

### Dependencies

- UI-1 Consumer Dashboard Core
- UI-2 Deterministic Impact Comparison and partial-result hardening
- UI-3 Structured Clarification Workflow, if implemented
- Backend Tickets 7-11, especially richer coverage, factor intent, and
  enriched factor metadata

If UI-3 is not implemented yet, UI-4 may still render non-interactive
clarification priorities, but it must not fake clarification behavior.

### Design Skill Requirement

Use the installed UI/UX skill before implementation:

```text
C:\Users\parth\OneDrive\Documents\ML projects\CarbonCoach\CarbonCoach\.codex\skills\ui-ux-pro-max\SKILL.md
```

Follow its workflow:

1. Generate a design system with `--design-system`.
2. Pull supplemental UX/chart/React guidance as needed.
3. Apply the pre-delivery checklist.

The design direction should use the skill's recommended CarbonCoach fit:

```text
Organic biophilic data dashboard
calm sustainability assistant
rounded, premium, readable, accessible
```

Use an earth/data palette with strong contrast. Avoid greenwashing visuals,
emoji icons, low-contrast text, layout-shifting hover states, and cluttered
debug terminology on the primary surface.

### Current Codebase Integration Points

Build on the current React/Tailwind frontend structure:

```text
frontend/src/pages/Home.jsx
frontend/src/components/EmissionResult.jsx
frontend/src/components/results/ConsumerDashboard.jsx
frontend/src/components/results/HeroSummaryCard.jsx
frontend/src/components/results/InsightSummary.jsx
frontend/src/components/results/ImpactComparisonCard.jsx
frontend/src/components/results/CategoryBreakdown.jsx
frontend/src/components/results/ActivityCard.jsx
frontend/src/components/results/NeedsAttention.jsx
frontend/src/components/results/NotIncludedActivities.jsx
frontend/src/components/results/DeveloperDetailsAccordion.jsx
frontend/src/components/results/resultPresentation.js
frontend/src/index.css
```

Build against the current V2 backend response models:

```text
domain/models.py
pipeline_v2/pipeline.py
pipeline_v2/retrieval_diagnostics.py
domain/impact_comparisons.py
domain/factor_metadata_overlay.py
```

The UI should consume these existing response fields when present:

```text
version
total.co2e
total.unit
total.confidence
total.source_breakdown
details[]
details[].raw_text
details[].category
details[].activity_type
details[].status
details[].parameters
details[].co2e
details[].unit
details[].source
details[].confidence
details[].parameter_confidence
details[].factor_confidence
details[].source_confidence
details[].assumptions
details[].issues
details[].factor
details[].factor_diagnostics
coverage
comparison
```

Current backend `coverage` shape:

```text
represented_activity_count
included_in_total_count
unresolved_count
not_estimated_count
failed_count
estimate_is_partial
```

Current `factor_diagnostics` may include:

```text
intent_key
intent
search_query
selector_filters
candidate_count
selected_activity_id
selected_reason
top_rejections
fallback_used
fallback_reason
fallback_assumption_code
attempts
```

Add small new components only where they simplify the existing structure.
Suggested additions:

```text
frontend/src/components/results/ResultTabs.jsx
frontend/src/components/results/ActivityCoverageSummary.jsx
frontend/src/components/results/EstimateQualityCard.jsx
frontend/src/components/results/CategoryCommandCenter.jsx
frontend/src/components/results/ClarificationPriorityCard.jsx
frontend/src/components/results/DemoExampleChips.jsx
```

Do not rewrite the app in a different framework, add a component library, or
introduce a charting dependency unless the existing accessible SVG/CSS approach
cannot meet the requirement.

### Result View Structure

Use lightweight tabs inside the result area, not global app navigation.

Required tabs:

```text
Overview
Activities
Details
```

The input panel remains above the result. Tabs only change how the latest
single-session result is presented.

Do not add a day timeline in this ticket.

#### Overview Tab

The Overview tab is the demo-first view.

It should include:

- hero estimated footprint
- estimate quality card
- activity coverage summary
- category command center
- deterministic reflection summary
- eligible impact comparison
- next best clarification, when safe

This tab should answer in under five seconds:

```text
How much was estimated?
What drove it?
How complete is it?
What would improve it most?
```

#### Activities Tab

The Activities tab shows the system's decomposition of the journal without a
timeline.

It should include:

- estimated activity cards
- needs-attention cards
- not-included activities
- per-activity assumptions
- optional filters or grouped sections by status/category if useful

The user should be able to see all represented activities without technical
metadata dominating the screen.

#### Details Tab

The Details tab replaces the old single accordion as the engineering view.

It should preserve or improve the existing developer details content:

- raw activity text
- status and source
- calculation parameters
- assumptions and issues, including codes
- confidence breakdown
- factor fit and factor confidence
- selected factor, activity ID, and match reasons when available
- factor intent and rejected candidates when Ticket 10/11 diagnostics exist
- comparison methodology when `comparison` is present
- coverage counts and partial-estimate reason

Technical sections should be grouped and collapsible. Do not expose API keys,
raw prompts, chain-of-thought, or huge provider payloads.

Recommended grouping:

```text
Response Summary
Coverage
Per-Activity Details
Factor Linking
Impact Comparison
Raw JSON Preview, optional and collapsed
```

`Factor Linking` should be generated from `detail.factor`,
`detail.factor_confidence`, and `detail.factor_diagnostics`. It must use
developer terminology only inside Details, not in Overview.

### Activity Coverage Summary

Add a prominent summary derived from `details` and existing/additive coverage
metadata:

```text
We found 9 activities
3 estimated
4 need details
2 not included yet
```

Counting rules:

- `estimated` and `fallback_estimated` count as estimated
- `unresolved` and `failed` count as needing details or attention
- `not_estimated` counts as not included
- if backend coverage metadata exposes additional detected-but-not-represented
  counts, show it separately as `not represented yet`
- never count unresolved, failed, or not-estimated activities in emissions
  totals

If the backend cannot yet expose missed/detected-but-not-represented
activities, do not invent them. Use only represented `details`.

Prefer backend `coverage` counts over recomputing when they are present. If
`coverage` is absent, derive a graceful fallback from `details`.

Recommended mapping from current backend fields:

```text
found activities:
  coverage.represented_activity_count or details.length

estimated:
  coverage.included_in_total_count or count(status in estimated/fallback_estimated)

need details:
  coverage.unresolved_count + coverage.failed_count or count(status in unresolved/failed)

not included:
  coverage.not_estimated_count or count(status == not_estimated)

partial estimate:
  coverage.estimate_is_partial or any unresolved/failed detail
```

### Estimate Quality Card

Add a human-readable quality explanation derived deterministically from the
response.

Example:

```text
Estimate quality: Medium

Why:
- 3 activities used assumptions
- 2 activities need more detail
- The largest estimated categories were Transport and Energy
```

Rules:

- use the existing total confidence label as the headline quality
- mention assumption count when assumptions exist
- mention unresolved/failed count when present
- mention approximate estimates when fallback-estimated details exist
- mention partial coverage when coverage marks the result partial
- do not call confidence "accuracy"
- do not suggest confidence changes the CO2e amount

### Category Command Center

Improve the category section from a single breakdown bar into four polished
category cards plus the existing chart or equivalent visualization.

Display categories in the stable order:

```text
Transport
Energy
Goods
Waste
```

Each category card should show:

- category label
- estimated kg CO2e for included statuses
- percentage of estimated total when total is positive
- count of estimated activities
- count of activities needing attention in that category
- clear empty state when category has no represented activity

Use text and iconography in addition to color.

### Deterministic Reflection Summary

Upgrade the existing deterministic insight into a more useful reflection
without using a live LLM.

Allowed facts:

- largest estimated category
- top estimated activity by CO2e
- partial estimate warning
- assumption and fallback counts
- next clarification priority
- confidence/quality explanation

Example:

```text
Transport and home energy drove most of today's estimated footprint.
The estimate is incomplete because several waste and goods activities need
more detail.
```

Do not add behavioral advice, moral judgment, avoided-emissions claims, or
unsupported alternatives.

### Next Best Clarification

Show one prioritized clarification prompt when the backend response supports
it, or derive a non-interactive priority from unresolved details.

Examples:

```text
Most useful detail to add
How much plastic packaging did you throw away?
```

```text
Most useful detail to add
How far was the bus ride?
[5 km] [10 km] [15 km] [Custom]
```

Rules:

- if UI-3 clarification API exists for the field, quick controls may submit a
  structured clarification
- if UI-3 does not exist for the field, show the prompt as guidance only
- prioritize unresolved details that are likely to affect emissions:
  missing distance, missing weight, missing energy/duration, then broad goods
  details
- never append hidden text to the journal to simulate clarification
- never ask for a field the backend cannot consume

### Demo Example Chips

Add example chips near the journal input to improve demos.

Suggested chips:

```text
Commute Day
Food + Waste
Household Energy
Messy Mixed Journal
Low-Detail Journal
```

Behavior:

- clicking a chip populates the textarea with a realistic journal
- it does not fake or pre-seed results
- the normal `/api/estimate-v2` request still runs
- examples should exercise multiple categories and honest unresolved states

Keep examples in frontend metadata or a small fixture module, not embedded
throughout JSX.

### Visual Polish Requirements

Apply a cohesive premium look:

- comfortable max-width container instead of full-bleed result sprawl
- responsive layout at 375px, 768px, 1024px, and 1440px
- organic rounded cards, soft shadows, and strong whitespace
- consistent category colors and icons
- no emoji icons; use inline SVG, Heroicons, Lucide-style SVGs, or simple
  accessible custom SVGs
- visible keyboard focus states
- pointer cursor on clickable controls
- hover states that do not shift layout
- reduced-motion-safe transitions
- accessible contrast for all text
- no horizontal scroll on mobile

Keep CarbonCoach visually calm and credible. Avoid noisy animations, glossy
greenwashing, or an enterprise analytics wall of tiny numbers.

### Backend Scope

No backend calculation changes are expected.

UI-4 may consume additive backend fields if already present, such as:

```text
coverage
comparison
factor_diagnostics
clarification_suggestions
```

The UI must degrade gracefully when these fields are absent.

Small backend additions are allowed only if they are presentation metadata and
do not change calculation semantics. Acceptable examples:

```text
clarification_suggestions
coverage display reason
stable event_id for UI-3 clarification, if already approved
```

If a backend addition is made:

- add API/model tests
- keep it additive
- keep `/api/estimate` working
- keep `/api/estimate-v2` response backward-compatible
- do not alter total CO2e, selected factors, confidence calculations, or
  statuses for existing inputs

Do not change V2 estimate calculations, factor selection, confidence
calculation, or response semantics as part of UI-4.

### Acceptance Criteria

- Result area uses `Overview`, `Activities`, and `Details` tabs.
- No day timeline is implemented.
- Overview reads as a polished intelligent reflection experience.
- Activity coverage summary is visible and derived from response data.
- Estimate quality card explains confidence in human terms.
- Category command center shows the four supported categories clearly.
- Deterministic reflection is more useful but still evidence-bound.
- Next best clarification is shown only when safe and never faked.
- Demo example chips populate the journal and still use the real API.
- Activities tab preserves all estimated, unresolved/failed, and
  not-estimated details.
- Details tab preserves developer explainability and improves organization.
- Primary UI avoids raw activity IDs, issue codes, retrieval terminology, and
  factor scores.
- Developer details retain technical fields needed for demos/interviews.
- Existing V1 result rendering still works.
- Existing `/api/estimate-v2` response contract remains compatible.
- UI remains useful when optional Ticket 10/11 diagnostics are absent.
- UI uses backend `coverage` when present instead of relying only on frontend
  inference.
- Details tab renders current backend `factor_diagnostics` fields in a readable
  developer format.
- Impact comparison methodology is visible in Details when `comparison` is
  present.
- If any backend presentation metadata is added, it is additive and tested.
- UI passes accessibility basics: labels, focus states, keyboard navigation,
  color contrast, non-color indicators, and `aria-live` error handling.
- Frontend is responsive and visually polished at mobile, tablet, laptop, and
  wide desktop widths.

### Test Matrix

Add or update frontend tests using fixtures and accessible queries.

Cover:

- tabs render and switch between Overview, Activities, and Details
- coverage summary counts estimated, needs-attention, and not-included details
- estimate quality explains assumptions, fallback estimates, and partial results
- category command center displays all four categories in stable order
- zero-total result has a useful empty state
- unresolved-only result does not show included emissions totals as complete
- next best clarification appears for supported missing distance or weight
- next best clarification is guidance-only when no clarification API is wired
- demo example chip populates the textarea without creating fake results
- Activities tab shows estimated cards, needs-attention items, and not-included
  items
- Details tab exposes developer details and remains navigable by keyboard
- primary Overview does not expose activity IDs or raw issue codes
- optional diagnostics absence does not crash rendering
- current backend `factor_diagnostics` shape renders selected activity,
  candidate count, fallback reason, and top rejections in Details
- backend `coverage` counts drive Overview coverage summary when present
- comparison metadata renders in Details without showing the comparison when
  partial coverage suppresses the primary card
- V1 response still renders through `EmissionResult`

Use `getByRole`, `getByLabelText`, and other Testing Library accessible queries
where possible. Do not rely on `getByTestId` for everything.

### Verification

Run from `app/frontend`:

```powershell
npm test -- --watchAll=false
npm run build
```

Run backend tests from `app` if backend integration, models, API serialization,
or served-app behavior is touched:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

Verify the production-like FastAPI-served React path in a browser:

- mixed high-coverage journal
- partial mixed journal with unresolved goods/waste
- all-unresolved or low-detail journal
- V1-compatible response if accessible through configuration
- keyboard tab navigation through input, example chips, result tabs, and
  details controls
- mobile-width layout

### Do Not Do

- Do not add login, accounts, persistence, saved history, or trends.
- Do not implement a day timeline.
- Do not add live LLM result prose.
- Do not make unsupported coaching or avoided-emissions claims.
- Do not hide unresolved or failed activities to make the result look cleaner.
- Do not make comparison cards appear for partial represented results.
- Do not make the UI depend on Ticket 10/11 diagnostics being present.
- Do not add a heavy charting or UI dependency without a clear accessibility
  and maintainability reason.
- Do not remove V1 rendering or `/api/estimate`.
- Do not change V2 confidence, total, or factor semantics in presentation code.

## Future Work Outside These Tickets

Not included:

- accounts or authentication
- stored history
- weekly/monthly trends
- personalized recommendations
- long-term analytics
- counterfactual avoided-emissions claims
- LLM-written coaching summaries
- full day timeline or calendar visualization

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
- final demo-grade UI has lightweight result tabs, activity coverage,
  estimate quality, category command center, and example chips
- developer details preserve explainability while remaining collapsed by default
- frontend verification passes through the production-like served React path
- no live external services are required by tests
- V1 endpoint availability and V2 response transparency are preserved
