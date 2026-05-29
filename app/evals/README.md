# CarbonCoach Evals

This folder contains lightweight evaluation scripts for measuring CarbonCoach behavior in a way that is safe to cite.

The evals are split into two parts:

1. **Offline intelligence and trust evaluation**
   - Runs the structured CarbonCoach pipeline with a deterministic provider stub.
   - Avoids live Climatiq, GCS, OpenRouter, and network variability.
   - Reports a hand-authored curated regression suite and a frozen LLM-generated challenge suite separately.
   - Measures extraction, status handling, quantity normalization, assumption visibility, confidence discipline, partial coverage, and total integrity.

2. **Deployed latency evaluation**
   - Sends representative requests to a deployed `/api/estimate-v2` endpoint.
   - Measures success rate, median latency, p95 latency, and max latency.
   - Keeps performance claims separate from intelligence/trust claims.

## Run

From `app/`:

```powershell
..\venv\Scripts\python.exe evals\carboncoach_eval.py --offline
```

With deployed latency:

```powershell
..\venv\Scripts\python.exe evals\carboncoach_eval.py `
  --offline `
  --deployed-url "https://YOUR_BACKEND_URL/api/estimate-v2" `
  --iterations 20
```

## Metrics

- `activity_extraction_recall`: expected activity events found in the output.
- `status_correctness`: expected included / attention / not-included status group.
- `quantity_parameter_accuracy`: expected normalized parameters, such as distance, energy, duration, weight, money, or count.
- `assumption_visibility`: expected assumptions are present on the relevant activity.
- `confidence_discipline`: assumption-heavy activities do not show confidence above the expected level.
- `partial_coverage_correctness`: mixed partial journals are marked partial, complete journals are not.
- `total_integrity`: only estimated and fallback-estimated activities contribute to the reported total.

## Interpreting Results

These are product-behavior evals, not scientific carbon-accounting benchmarks.

The LLM-generated challenge set is intentionally separate from the curated regression set. It is useful for spotting broader phrasing gaps, while the curated set is better for stable regression claims.

Good resume wording:

```text
Built a two-layer evaluation harness for CarbonCoach combining curated regression cases with a frozen LLM-generated challenge set to measure activity extraction, quantity normalization, assumption visibility, confidence discipline, partial-result handling, and deployed API latency.
```

Use exact percentages only with the benchmark size and date.
