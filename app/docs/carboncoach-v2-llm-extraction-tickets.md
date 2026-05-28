# CarbonCoach V2 Tickets 8 And 9: LLM Extraction Intelligence

This document defines the next two backend intelligence tickets after Ticket 7.
Ticket 7 established stronger deterministic everyday coverage. Tickets 8 and
9 add a controlled LLM extraction layer so CarbonCoach understands natural
daily journals more broadly without making emissions accounting opaque.

Agents implementing these tickets must also follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`
- `docs/carboncoach-v2-everyday-coverage-ticket.md`
- `docs/carboncoach-consumer-ui-ticket-plan.md`

## Product Intent

The biggest remaining intelligence gap is language understanding:

```text
ordinary journal phrasing -> structured carbon events
```

The LLM should improve:

- event segmentation in messy multi-activity journals
- everyday wording variation
- goods/services and waste recognition
- device-energy mentions
- raw text span preservation
- unsupported-but-carbon-relevant activity visibility

The LLM must not decide:

- final CO2e values
- final emission factors
- final confidence
- whether to hide unsupported activities
- undocumented assumptions

Core principle:

```text
LLM proposes candidate structured events.
Deterministic code validates, normalizes, scores, estimates, and explains.
```

## Shared Rules For Tickets 8 And 9

### No Live LLM In Tests

Automated tests must not require live:

```text
OpenRouter
OpenAI
Anthropic
Climatiq
Hugging Face
Google Cloud Storage
```

Use fake LLM clients, fixture responses, and deterministic validation tests.
Optional live smoke scripts may exist only when skipped by default and clearly
marked as manual.

### Compatibility With Existing V2

Keep:

```text
POST /api/estimate-v2
POST /api/estimate
```

V1 must keep working. V2 must fall back to deterministic extraction if the LLM
client is unavailable, disabled, times out, returns invalid JSON, or proposes
invalid events.

### Do Not Revive Legacy Matching As The Strategy

Do not use `services/llm_matcher.py` as the core design. It asks an LLM to
select a final activity name from a large list and does not provide sufficient
schema validation, unit compatibility, factor-fit reasoning, or deterministic
fallback behavior.

Do not route V2 through the V1 `embedder.retrieve_best_activities()` flow.
V2 factor retrieval should remain structured and validated through the
existing V2 retrieval/validation path.

### Feature Flagging

Introduce a clear configuration boundary.

Suggested environment variable:

```text
CARBONCOACH_V2_EXTRACTOR_MODE=heuristic|llm|hybrid
```

Default behavior should be conservative:

- local tests use injected fake extractors or fake LLM clients
- production may use `hybrid` only when the required API key/provider config is present
- missing LLM config must not break `/api/estimate-v2`

### Traceability

When an LLM-assisted event is used, preserve enough developer detail to debug
the extraction path without cluttering the consumer dashboard.

Recommended additive fields or metadata:

```text
extractor_source: heuristic | llm | hybrid
extraction_confidence: Confidence
llm_event_id or candidate index, if useful
validation/repair issues, only in developer details
```

Do not expose raw prompts, API keys, full provider payloads, or chain-of-thought.

## Ticket 8: LLM Structured Event Extraction Adapter

### Goal

Add a safe, optional LLM event-extraction adapter that converts a journal into
candidate `CarbonEvent` objects using a strict schema, then validates those
candidates before any event enters the V2 pipeline.

This ticket creates the safe intelligence boundary. It does not need to make
LLM extraction the default path yet.

### Dependencies

Ticket 7.

### Backend Scope

Create or extend files primarily under:

```text
app/domain/
app/pipeline_v2/
```

Suggested new files:

```text
app/pipeline_v2/extraction_schema.py
app/pipeline_v2/llm_event_extractor.py
app/pipeline_v2/extractor_protocol.py
```

Existing files may be touched for small integration points:

```text
app/pipeline_v2/event_extractor.py
app/pipeline_v2/pipeline.py
app/domain/models.py
app/domain/activity_taxonomy.py
```

### Extractor Interface

Define a small protocol so extraction implementations are swappable:

```python
class EventExtractor(Protocol):
    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        ...
```

Existing deterministic extraction should conform to the same interface.

### LLM Client Boundary

Do not hardcode LangChain/OpenRouter calls inside the extraction logic.

Use an injectable client boundary such as:

```python
class LLMExtractionClient(Protocol):
    def extract_events_json(self, prompt: str) -> str:
        ...
```

Tests inject fake clients that return fixed JSON or errors.

### LLM Output Schema

The LLM must return JSON only. No markdown, explanations, or prose.

Use a flat schema similar to:

```json
{
  "events": [
    {
      "raw_text": "grabbed a takeaway coffee",
      "category": "goods_services",
      "activity_type": "coffee_purchase",
      "quantities": [
        {
          "value": 1,
          "unit": "item",
          "dimension": "number",
          "surface": "a coffee",
          "evidence": "inferred_from_singular_phrase"
        }
      ],
      "entities": {
        "item": "coffee",
        "purchase_context": "takeaway"
      }
    }
  ]
}
```

Keep the schema deliberately shallow. Deep nested schemas tend to be brittle.

### Validation Rules

LLM output is untrusted.

Validation must:

- parse JSON with a strict parser, not `ast.literal_eval`
- reject non-object top-level output
- reject unknown top-level keys unless intentionally allowed
- require `events` to be a list
- validate every event with Pydantic or equivalent strict models
- reject unknown categories
- reject invented activity types
- reject category/activity mismatches
- reject or downgrade `raw_text` that is not found in the raw or cleaned journal
- preserve only allowed entity fields or put unknown meaningful values into a
  controlled generic entity map
- ignore or reject LLM-provided final CO2e, factor IDs, confidence labels,
  assumptions, and issue codes
- cap event confidence from LLM extraction before deterministic validation

### Quantity Handling

The deterministic `QuantityNormalizer` remains the source of truth.

The LLM may propose quantity hints, but deterministic code must:

- rescan the raw event text
- verify explicit quantity surfaces where possible
- treat unverified inferred quantities as assumptions or low-confidence hints
- never allow the LLM to invent missing distance, weight, money, power, or
  duration as if the user supplied it

Examples:

```text
"two coffees"
-> count 2 may be accepted if surface evidence exists

"a takeaway coffee"
-> count 1 may be inferred only through a maintained singular-count rule with
   an assumption

"a bag of rubbish"
-> must not become 1 kg or any mass without a reviewed default

"most of the evening"
-> must not become 4 hours unless a separately documented vague-duration rule exists
```

### Prompt Requirements

The prompt must instruct the model to:

- output JSON only
- use only the controlled categories and activity types
- preserve short raw text spans from the journal
- include carbon-relevant unsupported activities rather than dropping them
- avoid estimating quantities that are not stated
- use `goods_services` for food, coffee, meals, and purchases
- use `waste` only when there is disposal/recycling/composting context
- distinguish owning/mentioning an object from disposing of it
- return candidate events, not final estimates

### Failure Behavior

If the LLM call fails, times out, returns invalid JSON, or returns no valid
events:

```text
fall back to deterministic heuristic extraction
add no user-facing error unless the whole pipeline fails
optionally record a developer-only extraction issue
```

The user should still receive a normal V2 response.

### Frontend Scope

No consumer UI redesign.

If extraction provenance is added to the response, show it only in developer
details. Do not add an AI badge or make consumer-facing claims that a result
is better merely because an LLM was used.

### Acceptance Criteria

- A swappable event extractor interface exists.
- Deterministic extraction still works through that interface.
- An LLM extractor adapter can parse valid fixture JSON into candidate events.
- Invalid JSON, invalid categories, invalid activity types, category/activity
  mismatches, and unsafe quantities are rejected or safely downgraded.
- LLM output cannot inject CO2e, factor IDs, final confidence, assumptions, or
  issue codes into the trusted pipeline.
- Missing LLM configuration does not break `/api/estimate-v2`.
- Tests prove the adapter can surface candidate events for everyday language
  that deterministic regexes historically struggled with.
- V1 `/api/estimate` remains intact.

### Required Tests

Use fake LLM clients only.

Add tests for:

- valid multi-event JSON becomes validated `CarbonEvent` candidates
- malformed JSON falls back safely
- provider exception falls back safely
- provider timeout or empty output falls back safely
- invented category such as `food` is rejected
- invented activity type is rejected
- category/activity mismatch is rejected
- raw span not present in journal is rejected or downgraded
- LLM-proposed final `co2e`, `activity_id`, `confidence`, assumption code, or
  issue code is ignored
- explicit quantity from raw text is preserved
- unsupported inferred quantity is not accepted as explicit evidence
- singular coffee count inference requires a maintained deterministic rule
- bag/bin/bottle waste mass is not invented
- LLM extraction works with fake outputs for coffee, meal, waste, heater, PC
  use, and mixed journals
- `/api/estimate-v2` still succeeds when the LLM adapter returns invalid output

### Verification

Run:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

If frontend files change:

```powershell
npm test -- --watchAll=false
npm run build
```

from `app/frontend`.

### Do Not Do

- Do not make live LLM calls in tests.
- Do not require an API key for local tests or app startup.
- Do not let the LLM choose final emission factors.
- Do not let the LLM calculate CO2e.
- Do not let the LLM assign final confidence.
- Do not trust LLM-provided assumptions or issue codes.
- Do not route V2 through `services/llm_matcher.py`.
- Do not route V2 through V1 `retrieve_best_activities()`.
- Do not replace deterministic validation, normalization, or factor retrieval.

## Ticket 9: Hybrid Extraction Intelligence Evaluation And Rollout

### Goal

Turn the safe LLM adapter from Ticket 8 into a measured intelligence upgrade
by combining it with deterministic extraction, deduping/merging candidate
events, and proving uplift on messy everyday journals.

Ticket 9 is where the product should start feeling substantially smarter.

### Dependencies

Tickets 7 and 8.

### Backend Scope

Add or extend:

```text
app/pipeline_v2/hybrid_event_extractor.py
app/pipeline_v2/extraction_evaluator.py
tests/fixtures/v2_extraction_eval.jsonl
```

Use the same `EventExtractor` interface from Ticket 8.

### Hybrid Strategy

The hybrid extractor should combine:

```text
deterministic heuristic events
LLM candidate events
strict validation
dedupe/merge logic
deterministic quantity normalization
```

Recommended flow:

```text
1. run deterministic extractor
2. run LLM extractor when configured
3. validate LLM candidates
4. normalize quantities/entities deterministically
5. dedupe overlapping events
6. preserve heuristic events when conflict is unresolved
7. add LLM-only validated events when they improve coverage
8. return ordered event list to the existing V2 pipeline
```

Quantity precedence is fixed:

```text
explicit deterministic quantity evidence
> validated LLM quantity hint backed by raw surface text
> maintained deterministic inference rule
> unresolved
```

LLM quantities must never override deterministic quantities from the same span.
If the LLM proposes a distance, weight, spend, duration, power, or mass that
the deterministic normalizer cannot verify from the event text, discard that
quantity and let the normal pipeline return an assumption or unresolved issue.

### Merge And Dedupe Rules

Deduping must be deterministic.

Potential duplicate signals:

- same category
- same activity type
- overlapping raw text spans
- same required quantity surface
- same dominant entity such as item/material/device/mode

An event should be treated as a duplicate only when the overlap points to the
same calculation boundary. Adjacent activities in the same sentence, such as
`grabbed a coffee and recycled the cup`, must remain separate events.

Rules:

- exact deterministic event wins over a lower-confidence LLM duplicate
- LLM may enrich an event with additional non-conflicting entities only if
  validation permits it
- conflicting explicit quantities are not merged silently
- same-span category or activity conflicts are not merged silently; preserve
  the deterministic event unless a maintained rule proves the LLM event is
  the safer controlled interpretation
- same-span quantity conflicts keep the deterministic quantity and add no LLM
  quantity unless the raw surface evidence is identical
- if both extractors find adjacent but distinct activities, keep both
- detail order follows journal order after merging
- if ordering cannot be determined, preserve deterministic order and append
  valid LLM-only events in candidate order

Example conflicts:

```text
Uber Eats
heuristic: goods_services / restaurant_meal
LLM: transport / rideshare
-> keep the food/delivery context; do not turn delivery wording into a ride

bag of rubbish
heuristic: waste / landfill_waste with missing weight
LLM: waste / landfill_waste with 1 kg
-> keep the waste event but discard the invented mass
```

### Confidence And Provenance

Set extraction confidence conservatively.

Guidance:

```text
heuristic-only high-quality event:
  existing event confidence rules

validated LLM-only event:
  cap around 0.75 before parameter/factor/source confidence

heuristic + LLM agreement:
  may use the stronger existing event confidence, but do not raise final
  estimate confidence above parameter/factor/source constraints

LLM event with weak span or inferred entity:
  cap lower and/or add developer issue
```

Overall estimate confidence remains:

```text
min(parameter confidence, factor confidence, source confidence)
```

Extraction confidence may cap parameter/event confidence where appropriate,
but it must not multiply or rescale CO2e.

When provenance is serialized, keep it developer-only and additive. Useful
fields are:

```text
extractor_source: heuristic | llm | hybrid
merged_from: heuristic+llm, if a duplicate was collapsed
llm_candidate_index: optional stable index for debugging fixture behavior
```

Do not expose AI badges, raw prompts, provider payloads, or chain-of-thought.

### Coverage And Comparison Behavior

The hybrid extractor should improve represented coverage, but it must keep
Ticket 7 behavior:

- every detected unresolved or failed event remains visible
- coverage counts derive from final details
- partial represented results suppress the impact comparison
- a more complete extraction may make the estimate look less polished if it
  reveals unresolved activities; that is correct

### Evaluation Harness

Create a deterministic extraction evaluation fixture such as:

```text
tests/fixtures/v2_extraction_eval.jsonl
```

Each row should include:

```json
{
  "input": "I grabbed coffee, drove 8 km home, and recycled 500 g of bottles.",
  "expected_events": [
    {"category": "goods_services", "activity_type": "coffee_purchase"},
    {"category": "transport", "activity_type": "car_ride"},
    {"category": "waste", "activity_type": "recycling"}
  ],
  "negative_activity_types": ["restaurant_meal"]
}
```

Rows may include fake LLM candidates when needed to make the comparison fully
deterministic:

```json
{
  "input": "I grabbed coffee and drove 8 km home.",
  "llm_events": [
    {"raw_text": "grabbed coffee", "category": "goods_services", "activity_type": "coffee_purchase"}
  ],
  "expected_events": [
    {"category": "goods_services", "activity_type": "coffee_purchase"},
    {"category": "transport", "activity_type": "car_ride"}
  ],
  "negative_activity_types": []
}
```

The harness should compare:

```text
heuristic-only extraction
hybrid extraction with fake LLM candidates
```

Do not require live model calls.

### Required Uplift Standard

Ticket 9 must demonstrate measurable improvement over heuristic-only
extraction on the fixture suite.

Use deterministic metrics such as:

- expected event recall
- false positive count on negative examples
- event ordering correctness
- duplicate event count
- supported-category validity
- pipeline survival rate
- represented activity count for known mixed journals

Minimum acceptance target for the fixture suite:

```text
hybrid expected-event recall > heuristic-only expected-event recall
hybrid must not drop any correctly extracted heuristic event
hybrid false positives on explicit negative cases must be zero
hybrid duplicate event count must be zero for expected non-duplicate inputs
all hybrid events must use controlled categories and activity types
```

The exact numeric recall threshold may be set by the implementation agent
based on fixture size, but it must be strict enough to prevent meaningless
uplift. A recommended starting target is:

```text
hybrid recall >= 0.90 on the curated everyday-journal evaluation fixture
```

### Evaluation Fixture Families

Include at least:

#### Everyday Mixed Journals

```text
car + coffee + meal + heater + PC + rubbish
coffee + recycling + electricity
meal + delivery context + rubbish + PC use
transport + coffee + compost
two purchases plus two disposal events
same activities in different orders
```

#### Goods/Services Variation

```text
grabbed a coffee
picked up a flat white
ordered takeaway
had a burrito and soft drink
bought groceries
spent money on coffee
coffee table negative example
meal plan negative example
```

#### Waste Variation

```text
recycled bottles
put cardboard in recycling
composted food scraps
general rubbish bin
took out a bag of rubbish
plastic bottles in backpack negative example
waste of time negative example
```

#### Energy/Device Variation

```text
ran the heater while gaming
used my PC for a few hours
charged my laptop
watched TV for 2 hours
worked on laptop with no energy-use implication, if policy says negative
washing machine, dryer, dishwasher, or laundry wording maps only to a
controlled existing activity such as generic_energy_use unless a taxonomy
entry is explicitly added
```

### Live LLM Manual Smoke Test

Optional only.

If included, create a manual script or test marker that is skipped unless an
explicit environment variable is present, for example:

```text
RUN_LIVE_LLM_EXTRACTION_SMOKE=1
```

The manual smoke test must:

- use temperature `0`
- use a short timeout
- avoid asserting exact provider phrasing
- assert only schema validity and safe fallback behavior
- never run in normal CI or local test commands

### Pipeline/API Acceptance

The full `/api/estimate-v2` path must work with the hybrid extractor.

Required API/pipeline cases:

- representative Ticket 7 mixed journal produces more complete represented
  activity details than heuristic-only baseline
- valid LLM-only coffee event reaches goods/services builder or unresolved
  path safely
- valid LLM-only waste event reaches waste builder or unresolved path safely
- valid LLM-only PC/device event reaches energy unresolved path safely
- appliance/laundry wording that lacks a controlled taxonomy activity reaches
  `generic_energy_use` or unresolved, not invented activity types
- invalid LLM output still returns heuristic V2 result
- LLM timeout still returns heuristic V2 result
- hybrid extraction does not change CO2e for an already-correct deterministic
  transport or energy event unless new valid additional events are included
- coverage and comparison suppression behave correctly with hybrid-only
  unresolved events

### Frontend Scope

No major frontend redesign.

If extractor provenance is serialized, keep it in developer details. The
consumer dashboard should simply become more complete because more activity
details are represented.

The consumer UI may show stronger Needs Attention content because the hybrid
extractor detects more unresolved activities. That is expected.

### Acceptance Criteria

- Hybrid extraction can be enabled through configuration or dependency
  injection without breaking heuristic-only mode.
- Hybrid extraction improves expected-event recall over heuristic-only on a
  deterministic evaluation fixture.
- Hybrid extraction does not drop any correct heuristic event.
- Hybrid extraction does not add false positives for explicit negative cases.
- Dedupe prevents duplicate activity cards/details for the same event.
- Same-span conflicts preserve the deterministic event and reject unsafe LLM
  quantities or category changes.
- Developer-only extractor provenance is available when serialized, without
  changing consumer-facing copy.
- Raw event ordering remains stable.
- LLM failures, invalid output, and timeouts fall back safely.
- Controlled taxonomy is enforced for all LLM-assisted events.
- Deterministic quantity normalization remains authoritative.
- Full pipeline/API tests pass with fake LLM candidates.
- V1 `/api/estimate` remains intact.
- UI-2 comparison remains suppressed for partial represented results.

### Required Tests

Add tests for:

- hybrid combines heuristic and LLM events
- hybrid adds validated LLM-only coffee, meal, waste, and PC events
- heuristic events survive when the LLM misses them
- heuristic events survive when the LLM conflicts with them
- duplicate LLM and heuristic events collapse to one detail
- adjacent distinct events are not collapsed
- conflicting quantities are not silently merged
- same-span category/activity conflicts preserve the safer deterministic event
- invalid LLM category/activity is rejected
- unsupported appliance names do not create invented activity types
- raw span ordering controls detail ordering
- evaluation harness reports recall improvement over heuristic-only
- negative examples produce zero false positives
- representative mixed journal has improved represented coverage
- hybrid extraction with provider failure falls back to heuristic-only
- API response remains valid when hybrid mode is enabled with a fake client
- coverage counts and comparison gating remain correct

### Verification

Run:

```powershell
..\venv\Scripts\python.exe -m pytest tests
```

If frontend files change:

```powershell
npm test -- --watchAll=false
npm run build
```

from `app/frontend`.

If a manual live LLM smoke test is added, do not run it as part of normal
verification unless explicitly requested.

### Do Not Do

- Do not make live LLM calls in normal tests.
- Do not require a live LLM for `/api/estimate-v2` startup or normal operation.
- Do not replace deterministic extraction entirely.
- Do not let the LLM override explicit user quantities.
- Do not let the LLM invent missing mass, distance, power, duration, or spend.
- Do not hide newly detected unresolved events to keep the dashboard cleaner.
- Do not make comparison cards appear for partial represented results.
- Do not treat recall improvement alone as sufficient if false positives grow.
- Do not use `llm_matcher.py` or V1 embedding retrieval as the V2 intelligence layer.

## Overall Definition Of Done For LLM Intelligence

The LLM extraction intelligence work is complete when:

- V2 has a safe LLM extraction adapter with strict schema validation.
- V2 can run without any live LLM configuration.
- Automated tests use fake LLM clients only.
- Hybrid extraction demonstrably improves everyday-journal event coverage.
- Hybrid extraction preserves deterministic wins and avoids false positives.
- LLM-assisted events remain explainable, validated, and compatible with the
  existing confidence/assumption/status model.
- No LLM output can directly control final CO2e, factors, final confidence, or
  hidden product behavior.
- The consumer dashboard benefits from richer represented activity details
  while developer details retain traceability.
