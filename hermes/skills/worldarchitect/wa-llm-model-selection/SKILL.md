---
name: wa-llm-model-selection
description: "Diagnose and fix your-project.com LLM model-selection bugs — wrong model in allowlist, missing from `MODELS_WITH_CODE_EXECUTION`, infinite-loop on code-execution calls, default-model changes that broke production. Triggers when the user reports 'dice stopped working after I picked X model', 'gemini-3-flash default broke something', 'why does Lite + 3.6 loop on code calls', 'swap Gemini model default', 'add new Gemini model to settings', or asks 'is model X supported for code execution / JSON / dice'. Distinct from `wa-cloud-run-deploy-failure-debug` (deploy infra), `wa-campaign-content-analysis` (LLM prose quality), and `campaign-bible-design` (new campaign creation). Verified 2026-07-30 on issue #8673 (gemini-3.5-flash-lite + 3.6-flash infinite-loop on code execution) and the historical PR #8571 → #8590 revert pair."
---

For current model selection or a new default, use Gemini 3.8 Flash (`gemini-3.8-flash`) or a later Flash model. Never select Gemini Pro. If the target provider or application cannot use a compliant model, report that limitation instead of choosing an older model. Older model IDs below are retained only as diagnostic history.


# WorldArchitect LLM Model Selection — diagnosis + fix recipe

## When to use this skill

- User reports a model-specific bug: "dice broke when I picked X", "Lite won't return JSON", "3.6 Flash loops forever"
- User wants to add or remove a Gemini model from the dropdown, allowlist, or default
- User asks which Gemini model supports code execution / JSON / structured output / dice
- User wants to compare Gemini vs Luna (or any non-Gemini OpenRouter model) on cost/latency/correctness
- A regression like PR #8571 (3.5-flash-lite default) happens again — silent dice degradation that doesn't surface until cost spike

## The single-source-of-truth files

Every model-selection question routes through these three files in `your-project.com`:

1. **`$PROJECT_ROOT/constants.py`** — `ALLOWED_GEMINI_MODELS`, `MODELS_WITH_CODE_EXECUTION`, `GEMINI_MODEL_MAPPING`, `MODEL_CONTEXT_WINDOW_TOKENS`, `MODEL_MAX_OUTPUT_TOKENS`
2. **`$PROJECT_ROOT/frontend_v1/js/settings.js`** — JS mirror of the catalog (single-source-of-truth refactor is PR #8592 OPEN)
3. **`$PROJECT_ROOT/templates/settings.html`** — Jinja dropdown options
4. **`$PROJECT_ROOT/llm_service.py:2207, 2250, 9393`** — usage sites that check `model_name in constants.MODELS_WITH_CODE_EXECUTION`
5. **`$PROJECT_ROOT/gemini_provider.py`** — `is_gemini_3_model()` and the temperature-strip path (PR #8571's other regression)

When ANY of these goes out of sync, you get a silent bug class (default works, model listed in dropdown, but dice path broken). Always grep ALL FIVE before claiming a fix is complete:

```bash
grep -rn "gemini-3-flash\|gemini-3.5-flash\|gemini-3.6-flash" \
  $PROJECT_ROOT/constants.py \
  $PROJECT_ROOT/frontend_v1/js/settings.js \
  $PROJECT_ROOT/templates/settings.html \
  $PROJECT_ROOT/gemini_provider.py \
  $PROJECT_ROOT/llm_service.py
```

## Bug class taxonomy (verified 2026-07-30)

| Bug class | Symptom | Where it hides | Fix shape |
|---|---|---|---|
| Default-model regression (PR #8571) | Default model picked for users without explicit pref hits a broken code-exec path | `DEFAULT_GEMINI_MODEL` + `MODELS_WITH_CODE_EXECUTION` | Revert default + ensure default IS in allowlist |
| Allowlist gap (PR #8512 / #8673) | Model is in dropdown + `ALLOWED_GEMINI_MODELS` but NOT in `MODELS_WITH_CODE_EXECUTION` — user picks it, silently gets native two-phase dice | `$PROJECT_ROOT/constants.py:132` | Add to allowlist (only after verifying code-exec works) OR remove from `ALLOWED_GEMINI_MODELS` |
| Comment drift (PR #8512) | Comment claims model "inherits 3.x code execution" but live API rejects | `$PROJECT_ROOT/constants.py` comments | Fix the comment + add a 12-test contract pinning the contract |
| Infinite loop on code-exec (Lite + 3.6 Flash) | Model emits 48 `codeExecution` parts, hits `TOO_MANY_TOOL_CALLS`, returns empty | Live API (`generativelanguage.googleapis.com`) | DO NOT add to allowlist even if comment says to; add guardrail at dice-orchestrator boundary |
| Temperature strip on 3.x (PR #8571 Bug B) | Direct Gemini call with `temperature=0.7` returns `INVALID_ARGUMENT` on 3.x models | `$PROJECT_ROOT/gemini_provider.py:is_gemini_3_model()` | Keep the strip — it's app-side, OpenRouter path bypasses it cleanly |
| Provider auth drift | Direct Gemini API key in `~/.gemini_api_key_secret` is dead (`API_KEY_INVALID`) | `gcloud secrets versions access latest --secret=gemini-api-key --project=worldarchitecture-ai` is the working path | Wire `gcloud secrets` into the worker brief; OpenRouter is the universal fallback for testing |

## Diagnostic recipe — the 3-step probe

For any model-selection bug, run these three probes in order. Each takes ~30 seconds.

```bash
# Step 1: allowlist check (no API call)
python3 -c "
import sys; sys.path.insert(0, '.')
from mvp_site import constants as c
for m in sorted(c.ALLOWED_GEMINI_MODELS):
    print(f'{m:35} in_allowlist={m in c.ALLOWED_GEMINI_MODELS} in_code_exec={m in c.MODELS_WITH_CODE_EXECUTION} default={m==c.DEFAULT_GEMINI_MODEL}')
"

# Step 2: live API probe with code_execution tool (GCP-secret-manager key)
SECRET=$(gcloud secrets versions access latest --secret="gemini-api-key" --project="worldarchitecture-ai" 2>/dev/null)
curl -sS -X POST "https://generativelanguage.googleapis.com/v1beta/models/<MODEL>:generateContent" \
  -H "Content-Type: application/json" -H "x-goog-api-key: $SECRET" \
  -d '{"contents":[{"parts":[{"text":"Return JSON: {\"dice_total\": 7, \"rolls\": [3, 4]}. Use the code execution tool to roll the dice."}]}],"tools":[{"codeExecution":{}}],"generationConfig":{"temperature":0.7,"responseMimeType":"application/json"}}' \
  | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d.get('candidates',[{}])[0]
parts = c.get('content',{}).get('parts',[])
code = sum(1 for p in parts if 'executableCode' in p or 'codeExecutionResult' in p)
print(f'finish={c.get(\"finishReason\")} code_parts={code} tokens={d.get(\"usageMetadata\",{}).get(\"totalTokenCount\")}')
"

# Step 3: OpenRouter fallback probe (works without GCP key)
OR_KEY=$(security find-generic-password -s openrouter-pilot-api-key -w 2>/dev/null)
curl -sS -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OR_KEY" -H "Content-Type: application/json" \
  -d '{"model":"google/<GEMINI_SLUG>","messages":[{"role":"user","content":"Return JSON: {\"dice_total\": 7, \"rolls\": [3, 4]}"}],"response_format":{"type":"json_object"},"temperature":0.7}'
```

**Expected output by bug class:**
- Default-model regression: Step 1 shows default NOT in allowlist; Step 2 still works on the default model but dice path is wrong; Step 3 returns clean JSON (different model used).
- Allowlist gap: Step 1 shows model in `ALLOWED_GEMINI_MODELS` but NOT in `MODELS_WITH_CODE_EXECUTION`; Step 2 may pass or `TOO_MANY_TOOL_CALLS`; Step 3 returns clean JSON.
- Infinite loop: Step 2 returns `finishReason=TOO_MANY_TOOL_CALLS, code_parts=48, tokens=20k+`. **This is the verdict — do NOT add to allowlist.**
- Temperature strip: Step 2 with `temperature=0.7` returns `INVALID_ARGUMENT` on direct path; Step 3 returns clean JSON via OpenRouter (which doesn't strip).

## Reference docs

- `references/gemini-flash-lite-code-exec-loop-8673.md` — full reproduction transcript + direct API evidence + Luna benchmark for the Lite + 3.6 Flash infinite-loop bug. Load this before opening any PR that touches `MODELS_WITH_CODE_EXECUTION` or `ALLOWED_GEMINI_MODELS`.

## Related skills + cross-references

- `wa-cloud-run-deploy-failure-debug` — if the symptom is "deploy broken", not "model wrong". Loads first to disambiguate.
- `wa-campaign-content-analysis` — if the symptom is "LLM prose is bad", not "LLM picks wrong model". Distinct from this skill.
- `wa-daily-cron-failure-diagnosis` — if a model change broke the daily Dice Audit cron.
- `repro` skill — for `/repro` invocations on a campaign that's hitting this bug class. The repro workflow will surface the bug as a `dice_total` mismatch in exported campaign state.
- `campaign-bible-design` — for designing new campaigns that should USE these models, not changing the model registry.
