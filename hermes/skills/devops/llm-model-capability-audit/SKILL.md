---
name: llm-model-capability-audit
description: Audit which LLM models actually support the capabilities claimed in their config (code execution, structured JSON, tool calling) BEFORE promoting them to defaults, allowlists, or dropdowns. Covers Gemini code_execution, OpenAI reasoning_token footprint, OpenRouter routing fallbacks, and tail-latency cliffs. Triggers on any "make X the default model", "add model Y to dropdown", "is this model safe to enable for dice/narrative/dice?", or "we just shipped a regression on model Z" question.
---

# LLM model capability audit

> **What this skill is:** the pre-promotion gate that catches "model claims X in marketing docs but actually returns `TOO_MANY_TOOL_CALLS` / empty content / 30k reasoning tokens on a trivial prompt" regressions BEFORE they ship as a default. Distinct from `llm-model-upgrade-survey` (which is for surveying new options); this is for verifying that a model actually does what the catalog says before flipping the default.

**Read first:** canonical examples in `references/worldarchitect-gemini-flash-lite-2026-07-30.md` — the live evidence behind this skill.

---

For new Gemini selections or promotions, only consider Gemini 3.8 Flash or later; never promote Gemini Pro or an earlier Gemini model. Older model IDs below describe historical findings.

## When to use this skill

Use it whenever ANY of the following lands in your session:

- "make X the new default model"
- "add Y to the model dropdown / settings / ALLOWED_MODELS"
- "why is the dice tool slow / using the wrong path?"
- "we just shipped a regression — users picked model X and got different behavior"
- A PR title like "feat: switch default to X" / "feat: add Y to allowlist"
- A code change touching `MODELS_WITH_CODE_EXECUTION`, `ALLOWED_MODELS`, `DEFAULT_*_MODEL`, or equivalent per-provider allowlists
- A user report of "the LLM is taking forever" / "model returned empty" / "cost jumped 5× after we changed defaults"

**Do NOT use it** for: pure creative prose evaluation, narrative-quality review, brand-tone critique — those are not capability audits.

---

## The audit workflow

### Phase 1 — Catalog snapshot (no LLM calls, 5 minutes)

For every model the change touches, capture:
- Catalog entries (`ALLOWED_MODELS`, `MODELS_WITH_CODE_EXECUTION`, model mapping tables, frontend dropdown options)
- The **claimed** capability comment for each (e.g. "inherits 3.x code execution + JSON single-pass")
- Whether the model is in any allowlist that gates critical features (dice, structured output, code execution)

Cross-reference: is every model in the dropdown also in the relevant allowlists? If not, **that's the latent bug** — users picking it silently degrade.

Output: a verdict table with 4 columns (model, in dropdown, in allowlist, capability claim).

### Phase 2 — Direct API probe (real LLM calls, 10 minutes per model)

For each model the change touches, hit the **real provider API** (not just docs) with the EXACT request shape the app sends:

- Same tools array (e.g. `{"code_execution": {}}` for Gemini)
- Same response format
- Same temperature + system prompt structure
- Same approximate prompt length the app sends (often much larger than test prompts)

Capture: `finish_reason`, `code_parts` / tool-call count, `total_tokens`, `usage.completion_tokens_details.reasoning_tokens`, and the actual text output. **Critical: reasoning_tokens count on trivial prompts**. A model that emits 200 reasoning tokens on a one-line JSON request is 5-10× more expensive than its base rate suggests.

**Auth-source priority** (in order, per `dual-probe-secrets` SOUL.md rule):
1. `os.environ.get("PROVIDER_API_KEY")` from bashrc-sourced shell
2. macOS Keychain via `security find-generic-password -s <service> -w`
3. GCP Secret Manager via `gcloud secrets versions access latest --secret=<name> --project=<project>`
4. Local secret file (`~/.gemini_api_key_secret`, etc.)

Never trust a single source — dual-probe both local file AND GCP secret-manager when both exist.

### Phase 3 — Latency benchmark (12 turns minimum, 10 minutes)

For latency-sensitive decisions (default model selection, dice provider choice), run 12 turns per model with a representative prompt:
- Capture mean, p50, p95 latency
- Capture cost per 12 turns
- Capture total tokens + reasoning tokens
- Capture finish_reason distribution (any non-`stop` is a smell)

**Tail-latency cliff check:** if p95 > 3× mean, the model has unstable latency under load. Worth flagging.

For structured-output workloads (dice, JSON schema validation), also run a `response_format={"type": "json_object"}` test — some models accept the parameter but emit markdown-wrapped JSON instead.

### Phase 4 — Promotion gate (3 questions)

Before approving any "make X the default" PR, answer:
1. **Is X in every allowlist that gates critical features?** (dice, code execution, structured JSON)
2. **Does the direct-API probe show clean finish + correct output + reasonable token footprint?**
3. **Is the p95 latency within 2× the existing default?**

If any answer is "no" — the change is NOT safe to ship. Either patch the allowlist first, fix the model choice, or document the limitation in the catalog comment.

---

## Common pitfalls (verified in production)

### Pitfall 1 — Allowlist drift after model add

When a PR adds a new model to `ALLOWED_MODELS` but forgets to add it to `MODELS_WITH_CODE_EXECUTION`, users picking that model silently get a slower fallback path (e.g. native two-phase dice instead of code-execution dice). Symptom is silent: the LLM still returns valid JSON, just via a slower + more expensive code path.

**Defense:** Phase 1 catalog snapshot must cross-check every allowlist the model affects.

### Pitfall 2 — Comment claims capabilities that don't exist

A code comment like "inherits 3.x code execution + JSON single-pass" is documentation debt. If the model doesn't actually inherit the capability (e.g. `gemini-3.5-flash-lite` loops on code-execution calls), the comment becomes a lie that future agents trust. Always verify the comment against the direct-API probe.

**Verified example:** PR #8512 (your-project.com) added `gemini-3.5-flash-lite` and `gemini-3.6-flash` with the claim that both inherit code execution. Direct API test: both return `TOO_MANY_TOOL_CALLS` with 48 code_parts and 20-27k tokens of empty output.

### Pitfall 3 — Reasoning-token footgun

"Fast" tier models often emit reasoning tokens on trivial prompts. `gemini-3.5-flash` emits 220 reasoning tokens on a 1-line JSON request. `gemini-3.6-flash` emits 237. That makes them 20-30× more expensive per turn than their headline price suggests. Always capture `usage.completion_tokens_details.reasoning_tokens` separately.

### Pitfall 4 — Default flip without allowlist patch

PR #8571 (your-project.com) made `gemini-3.5-flash-lite` the default. The model wasn't in `MODELS_WITH_CODE_EXECUTION`, so every user silently got native two-phase dice. The PR was reverted 8 hours later by PR #8590, which only fixed the **default**, not the allowlist. The latent bug persists for users who explicitly pick Lite or 3.6.

**Defense:** Phase 4 promotion gate must explicitly ask "does this model work for every allowlist that the current default works in?"

### Pitfall 5 — Tail-latency cliff

`gemini-3.6-flash` has mean=3.20s, p50=2.06s, p95=**11.84s** on a 12-turn dice benchmark. The model is "fine" on average and terrible on the 5th percentile. Always run p95, not just mean.

### Pitfall 6 — Bashrc-vs-Keychain vs GCP secret-manager divergence

The "where's the key" question has 4 valid answers and they often disagree:
- bashrc export (often unset or commented out for security)
- macOS Keychain via `security find-generic-password`
- GCP Secret Manager via `gcloud secrets versions access`
- Local secret file (`~/.gemini_api_key_secret` style)

`dual-probe-secrets` SOUL.md rule: probe at least 2 of these before declaring "key is broken". The local secret file in this repo was stale (`AIzaSyDQ6a...` returns `API_KEY_INVALID`) but the GCP secret-manager version (`AIzaSyAvyb...`) was live.

### Pitfall 7 — Codex is a UI, not an API

GPT-6 Luna is only exposed in the Codex picker — but the underlying API is OpenRouter. `POST https://openrouter.ai/api/v1/chat/completions` with `model="openai/gpt-6-luna"` works directly. Same for any "Codex-only" model: it's almost always OpenRouter under the hood.

### Pitfall 8 — `claudem` worker with stale `.agent_prompt_*.txt`

When dispatching a `claudem -p` worker via `git worktree add`, the worktree may inherit a stale `.agent_prompt_<prior-branch>.txt` from a prior session. The worker reads the stale prompt and either loops silently or exits with no evidence. Always check `ls .agent_prompt_*.txt` after `worktree add` and delete if it's not for the current branch. (Pattern verified across sessions `20260722_155550_273bd3e1`, `20260730_*`).

---

## The audit produces 4 deliverables

1. **Verdict table** — model × capability matrix with `pass`/`fail`/`partial` per row
2. **Direct-API evidence** — raw JSON responses saved to `evidence/<model>_<capability>.json`
3. **Latency benchmark** — `evidence/latency_<workload>.json` with per-turn + aggregate stats
4. **Promotion recommendation** — explicit `safe-to-ship: yes/no/with-fixes` + the specific fixes if `no`

If any deliverable is missing, the audit is not complete. Don't ship the model change.

---

## Reference

- `references/worldarchitect-gemini-flash-lite-2026-07-30.md` — verified reproduction of the Lite/3.6 Flash infinite-loop + the PR #8571 → #8590 history + the latency/cost table.
