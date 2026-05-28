# CarbonCoach V2 Ticket 10: Semantic Factor Intent Resolution

This document defines the final planned backend architecture ticket for
semantic factor linking in CarbonCoach V2.

Tickets 7-9 improve event coverage and LLM-assisted understanding. Ticket 10
improves the missing bridge between a validated carbon event and the rich
emission-factor database.

Agents implementing this ticket must also follow:

- `docs/carboncoach-v2-agent-readme.md`
- `docs/carboncoach-v2-design-spec.md`
- `docs/carboncoach-v2-ticket-plan.md`
- `docs/carboncoach-v2-everyday-coverage-ticket.md`
- `docs/carboncoach-v2-llm-extraction-tickets.md`
- `docs/carboncoach-consumer-ui-ticket-plan.md`

## Why This Ticket Exists

The backend can now detect more activities, but some detected activities still
fail to connect to a useful database activity ID.

Example:

```text
Threw away 2kg of plastic.
```

The system should understand:

```text
category: waste
activity_type: landfill_waste
disposal_method: landfill / thrown away / discarded
material_class: plastic
weight: 2 kg
required unit type: Weight
factor intent: plastic waste landfill/disposal/end-of-life treatment by mass
```

If the database has a compatible plastic landfill/disposal factor, the engine
should find it. If not, the engine should either use a documented general
landfill fallback with a visible assumption or explain why no safe factor
pathway exists.

The current weakness is not only extraction. It is that factor retrieval is
often constrained by narrow local pathways before the database receives a
rich semantic search intent.

## Goal

Add a semantic factor-intent layer so validated events can use the database
more intelligently while preserving safety.

The engine should move from:

```text
event -> local fallback/pathway gate -> factor retrieval
```

to:

```text
event + parameters
-> calculation intent resolution
-> database candidate discovery
-> compatibility validation
-> specific factor estimate, documented fallback, or explainable unresolved
```

## Dependencies

- Ticket 7: everyday goods/waste coverage and coverage metadata
- Ticket 8: safe LLM structured extraction adapter
- Ticket 9: hybrid extraction evaluation and rollout

Ticket 10 should be the last planned backend architecture improvement ticket
before stabilization, polish, deployment work, and any focused data quality
overlay work.

## Non-Goals

Do not:

- add another extraction system
- make the LLM choose final factors
- route V2 through V1 `retrieve_best_activities()`
- revive `services/llm_matcher.py`
- multiply CO2e by confidence or factor fit
- weaken deterministic validation
- require live Climatiq, OpenRouter, Hugging Face, or GCS in tests

## Core Principle

Use the LLM and extractors to understand user language. Use deterministic
factor intent resolution to translate that understanding into database search.

```text
LLM/heuristic extraction: what did the user describe?
Intent resolver: what factor shape should we search for?
Retriever: what candidate factors exist?
Validator: which candidate is compatible?
Estimator: calculate, fallback, or return unresolved.
```

## Backend Scope

Create or extend primarily under:

```text
app/domain/
app/pipeline_v2/
```

Suggested new files:

```text
app/domain/factor_intents.py
app/domain/material_ontology.py
app/pipeline_v2/calculation_intent_resolver.py
app/pipeline_v2/retrieval_diagnostics.py
```

Expected existing files to touch:

```text
app/domain/models.py
app/domain/activity_taxonomy.py
app/domain/fallback_factors.py
app/pipeline_v2/factor_retriever.py
app/pipeline_v2/validator.py
app/pipeline_v2/emission_estimator.py
app/pipeline_v2/parameter_builders.py
app/pipeline_v2/pipeline.py
```

Keep edits scoped. Do not refactor the whole pipeline if a narrow intent
adapter can connect the existing pieces.

## Factor Intent Model

Add a structured factor intent model. Exact names may vary, but the model
should represent:

```text
intent_key
category
activity_type
unit_type
required_parameters
semantic_dimensions
hard_constraints
preferred_terms
excluded_terms
search_query
selector_filters
fallback_strategy
assumption_if_generic_fallback_used
```

Example:

```json
{
  "intent_key": "waste.landfill.plastic.weight",
  "category": "waste",
  "activity_type": "landfill_waste",
  "unit_type": "Weight",
  "required_parameters": {
    "weight": 2,
    "weight_unit": "kg"
  },
  "semantic_dimensions": {
    "disposal_method": "landfill",
    "material_class": "plastic"
  },
  "hard_constraints": {
    "unit_type": "Weight",
    "category_family": "waste"
  },
  "preferred_terms": [
    "plastic waste",
    "landfill",
    "disposal",
    "end of life",
    "kg"
  ],
  "search_query": "plastic waste landfill disposal end of life treatment by weight kg",
  "selector_filters": {
    "unit_type": "Weight",
    "sector": "Waste"
  },
  "fallback_strategy": [
    "same_method_same_material",
    "same_method_general_waste",
    "maintained_local_fallback"
  ]
}
```

## CalculationIntentResolver

Add a resolver that turns validated events plus built parameters into one or
more factor intents.

The resolver must:

- run after event extraction, entity normalization, and parameter building
- require deterministic required parameters before generating estimable intents
- produce no estimable intent when required quantities are missing
- produce multiple prioritized intents when a specific and generic route are
  both reasonable
- avoid requiring a maintained fallback factor before database retrieval
- preserve explicit user evidence as intent dimensions
- use maintained ontology/synonym data rather than test-sentence branches

Example for:

```text
Threw away 2kg of plastic.
```

Expected prioritized intents:

```text
1. waste landfill plastic by weight
2. waste landfill general/mixed waste by weight, only if no specific compatible
   plastic landfill factor exists and a visible assumption is added
```

## Waste Ontology Refactor

Decouple material and disposal method.

Do not structure waste knowledge as:

```text
recycling knows plastic
landfill does not know plastic
```

Use independent dimensions:

```text
material_class:
  plastic
  cardboard
  paper
  glass
  metal
  food_waste
  mixed_packaging
  general_waste
  unknown

disposal_method:
  landfill
  recycling
  composting
  incineration
  unknown
```

Controlled synonyms must live in reviewed metadata.

Examples:

```text
threw away 2kg plastic
-> material_class: plastic
-> disposal_method: landfill

recycled 2kg plastic
-> material_class: plastic
-> disposal_method: recycling

put 2kg plastic in general waste
-> material_class: plastic
-> disposal_method: landfill

plastic bottles in my backpack
-> no disposal method; no waste estimate
```

Mentioning recyclable-looking material still does not imply recycling.

## Database Candidate Discovery

Factor retrieval must accept resolved factor intents, not only raw event
metadata.

Required behavior:

- search the database for specific compatible candidates when an intent has
  required parameters and semantic dimensions
- use unit type and required parameter dimensions as hard filters
- use category/sector ontology as a controlled compatibility signal
- use material and disposal method as strong ranking evidence
- allow retrieval even when no local fallback factor is configured
- record candidate count and rejection reasons for developer diagnostics

Search query construction should include:

```text
activity type
material class
disposal method
category family
unit type
database-friendly synonyms
```

For waste examples, include terms such as:

```text
waste
landfill
disposal
end of life
treatment
recycling
compost
plastic
cardboard
food waste
by weight
kg
```

## Validator Updates

Keep hard validation strict for:

- activity ID exists
- unit type compatibility
- required parameters exist
- parameter units match expected units
- obvious wrong category families

Make category/sector validation ontology-aware.

Real factor records may use labels such as:

```text
Waste
Waste treatment
End-of-life treatment
Disposal
Municipal solid waste
Recycling
Landfill
Compost
```

The validator should recognize these as waste-family labels when appropriate.

Do not accept:

- energy factors for waste
- distance factors for waste
- goods purchase factors for waste disposal
- weight factors with missing weight
- recycling factors for a landfill event unless the user actually described recycling

## Fallback Strategy

Fallback is allowed only after specific database search has been attempted or
when using a maintained local fallback is explicitly configured as the best
available path.

Fallback ladder for waste:

```text
1. database factor for same disposal method and same material
2. database factor for same disposal method and compatible broader material
3. maintained local fallback for same method and material, if available
4. maintained local fallback for same method and general/mixed waste, with
   visible assumption
5. unresolved with diagnostics if no safe path exists
```

For:

```text
Threw away 2kg of plastic.
```

Best behavior:

```text
estimated with a compatible plastic landfill/disposal database activity_id
```

Acceptable behavior:

```text
fallback_estimated using general landfill waste, with a visible assumption:
"Used a general landfill waste factor because no compatible plastic-specific
landfill factor was found."
```

Not acceptable:

```text
unresolved without showing that a specific database search was attempted
```

## Goods/Services Intent Resolution

Although the motivating example is waste, the same pattern must work for
goods/services.

Examples:

```text
bought 1 kg of beef
-> goods_services / food_purchase
-> material/product: beef
-> unit_type: Weight
-> search intent: beef food purchase by mass

bought two coffees
-> goods_services / coffee_purchase
-> product: coffee
-> unit_type: Number
-> search intent: coffee serving item count

spent $6 on coffee
-> unit_type: Money only if a compatible money-based factor exists
-> do not convert spend into count silently

ordered a beef burrito
-> restaurant_meal / meal component
-> unit_type: Number if maintained serving factor exists
```

Goods retrieval should not require a local fallback factor before searching a
compatible database factor.

## Retrieval Diagnostics

Add developer-only diagnostics for factor linking.

The exact response shape may vary, but diagnostics must expose enough to
answer:

- What intent was generated?
- What database query/filter was used?
- How many candidates were considered?
- Which candidate was selected?
- Why were top candidates rejected?
- Was fallback used?
- What assumption was added if a generic fallback was used?

Example additive shape:

```json
{
  "factor_diagnostics": {
    "intent_key": "waste.landfill.plastic.weight",
    "search_query": "plastic waste landfill disposal end of life treatment by weight kg",
    "candidate_count": 4,
    "selected_activity_id": "waste-treatment_plastic-landfill_weight",
    "selected_reason": "unit, waste family, landfill method, and plastic material matched",
    "top_rejections": [
      {
        "activity_id": "waste-treatment_plastic-recycling_weight",
        "reason": "recycling method conflicts with landfill disposal"
      }
    ],
    "fallback_used": false
  }
}
```

Keep this out of the primary consumer dashboard surface. It may appear in the
developer details accordion.

Do not expose API keys, prompts, chain-of-thought, or huge raw provider
payloads.

## Frontend Scope

No consumer redesign.

If diagnostics are serialized, render them generically in developer details:

```text
Factor intent
Search query
Selected factor
Rejected candidates
Fallback reason
```

Primary cards should still show only consumer-friendly emissions, confidence,
assumptions, and issues.

## Mandatory Regression Cases

### Waste Factor-Linking Cases

Add tests for:

```text
Threw away 2kg of plastic.
Discarded 2 kg of plastic packaging.
Put 2kg of plastic in the general waste bin.
Threw away 750 g of mixed packaging.
Recycled 500 g of plastic bottles.
Composted 2 kg of food scraps.
```

Expected:

- correct activity type
- correct disposal method
- correct material class
- correct weight in kg
- database factor selected when a compatible fake database record exists
- fallback only after specific candidate search fails or when configured
- visible assumption when generic fallback is used
- diagnostics show the intent and selected/rejected candidates

Negative cases:

```text
I bought 2kg of plastic pellets.
I had plastic bottles in my backpack.
That meeting was a waste of time.
I sorted my files into folders.
```

Expected:

- no waste disposal estimate
- no landfill/recycling factor search for non-disposal text

### Specific Versus Generic Waste Candidate Selection

Use fake local database records.

Case 1:

```text
input: Threw away 2kg of plastic.
records:
  plastic landfill Weight factor
  general landfill Weight factor
  plastic recycling Weight factor
expected:
  selected plastic landfill factor
```

Case 2:

```text
input: Threw away 2kg of plastic.
records:
  general landfill Weight factor
  plastic recycling Weight factor
expected:
  selected general landfill only with visible generic fallback assumption
  plastic recycling rejected because method conflicts
```

Case 3:

```text
input: Threw away 2kg of plastic.
records:
  plastic recycling Weight factor
  unrelated goods Weight factor
expected:
  unresolved or maintained fallback, never recycling-as-landfill
```

### Goods Factor-Linking Cases

Add tests for:

```text
Bought 1 kg of beef.
Bought two coffees.
Spent $6 on coffee.
Ordered a beef burrito.
Bought groceries.
```

Expected:

- compatible database record selected when present
- money-based retrieval only when unit type is Money and compatible factor exists
- no price-to-count conversion
- unresolved or documented fallback when product class is too broad
- diagnostics show intent and candidate decisions

### Cross-Domain Rejection Cases

Use fake database records to prove:

- waste events cannot use goods factors
- goods events cannot use waste factors
- transport events cannot use waste factors
- energy events cannot use weight factors
- wrong unit type candidates are rejected before Climatiq

### Hybrid Extraction Integration

If Ticket 9 hybrid extraction is enabled:

- validated LLM-only waste event reaches intent resolver
- validated LLM-only goods event reaches intent resolver
- invalid LLM material/method does not bypass deterministic ontology
- hybrid extraction plus factor intent produces the same candidate decision as
  heuristic extraction for the same normalized event

## Acceptance Criteria

- `CalculationIntentResolver` or equivalent exists and is used before factor
  retrieval for V2 estimable events.
- Factor retrieval can search by semantic intent even when no local fallback
  factor key is configured.
- Waste material and disposal method are modeled as independent dimensions.
- `Threw away 2kg of plastic` no longer fails silently before meaningful
  database candidate discovery.
- Specific compatible database factors are preferred over generic fallbacks.
- Generic fallback is used only with visible assumption and only after a safer
  specific path is unavailable.
- Retrieval diagnostics explain intent generation, selected candidates,
  rejected candidates, and fallback use.
- Unit compatibility remains a hard gate.
- Wrong-method candidates, such as recycling factors for landfill disposal,
  are rejected.
- Goods/services use the same intent pattern for product, unit, and factor
  discovery.
- Existing energy, transport, goods, waste, Ticket 7 coverage, Ticket 8 LLM
  adapter, and Ticket 9 hybrid extraction tests pass.
- V1 `/api/estimate` remains intact.
- No tests require live external services.

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

If frontend files change, verify the FastAPI-served built React app for:

- `Threw away 2kg of plastic`
- a specific database-factor waste result
- a generic fallback waste result with assumption
- a rejected wrong-method candidate shown only in developer details
- a goods factor-linking result

## Do Not Do

- Do not make the LLM choose final activity IDs.
- Do not route V2 factor linking through V1 embedding retrieval.
- Do not use `services/llm_matcher.py`.
- Do not accept wrong-unit candidates.
- Do not use recycling factors for thrown-away landfill waste.
- Do not fabricate missing quantities.
- Do not hide unresolved results to make the dashboard cleaner.
- Do not show technical retrieval diagnostics on the primary consumer surface.
- Do not remove existing transparent fallback behavior.
- Do not make live provider calls in tests.

## Final Backend Completion Definition

After Ticket 10, the backend architecture should be considered complete for
the V2 intelligence milestone when:

- ordinary journal language is represented as validated events
- hybrid extraction improves event coverage
- validated events generate semantic factor intents
- the rich factor database is searched through structured intent, not only
  narrow fallback keys
- compatible database factors are selected when available
- generic fallbacks are transparent and conservative
- failed factor linking is diagnosable
- confidence, coverage, and comparison gating remain honest
- V1 continues to work
