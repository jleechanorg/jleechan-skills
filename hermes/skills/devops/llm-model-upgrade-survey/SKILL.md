---
name: llm-model-upgrade-survey
description: "Survey available LLM models across the project-app's configured providers (Gemini, Claude, OpenAI, Grok, Perplexity, Cerebras, etc.) and produce a cost-vs-quality upgrade matrix for a specific model upgrade request. Then dispatch an AO worker to land the upgrade PR — never edit the project repo inline. Trigger when the user says 'upgrade <model> in <project-app>', 'bump gemini/anthropic/openai to <new>', 'investigate model upgrades for our providers', 'check cost vs quality on benchmarks', 'is <new model> worth switching to', 'upgrade from <old> to <new>', or pairs a project name with a 'model upgrade' / 'investigate model upgrade' verb."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llm, provider, model-upgrade, benchmark, cost-analysis, ai-universe, project-app, ao-dispatch]
    related_skills: [always-pr-never-local-edit, drive-pr-to-green, finish-the-job, swap-hermes-provider, eval-vendor-tooling, real-claude-teammate-tmux]
---

# LLM model upgrade survey + dispatch (class-level)

For current Gemini model selection or an upgrade target, use Gemini 3.8 Flash or later only; never select Gemini Pro or an earlier Gemini model. Older identifiers elsewhere are historical survey context.

When a user asks to upgrade a model in a project-app (e.g. `jleechanorg/ai_universe`, `$GITHUB_REPOSITORY`), survey the available models across every provider the project uses, build a cost-vs-quality matrix, and dispatch an AO worker to land the upgrade PR. This skill is the **research + decision** phase; the **execution** phase is `always-pr-never-local-edit` + `drive-pr-to-green` + the AO dispatch path.

The class-level survey has three principles:

1. **Project-app scope, not Hermes scope.** This is for `jleechanorg/<project>` repos, NOT for `~/.hermes/config.yaml`. Mutating the Hermes gateway is `swap-hermes-provider`. Surveying a third-party repo with no project context is `eval-vendor-tooling`.
2. **Read the actual config first, don't trust the README.** The default model in `ConfigManager.ts` may already be the new model — the "upgrade" may be a no-op or a pricing-table update only.
3. **The output is a cost-vs-quality matrix + a small menu of next actions.** The user gets to choose. The agent does not auto-pick.

## Phase 0 — Map the project's provider wiring

Before answering "what should we upgrade to," answer "what is the project actually using today." The project's three files always tell the story:

| File (canonical layout) | What it holds |
|---|---|
| `<repo>/shared-libs/packages/config-utils/src/ConfigManager.ts` | Default model strings per provider, env-var names, context-window limits, endpoint URLs |
| `<repo>/shared-libs/packages/mcp-server-utils/src/CostCalculator.ts` | Per-1M-token pricing lookup keyed by model name |
| `<repo>/shared-libs/packages/mcp-server-utils/src/ModelDisplayNames.ts` | Map of internal model id → user-facing display name |

Read all three before doing any vendor research. The defaults may already be at the latest model — the user may be asking based on a stale Slack thread or a docs page they read 6 months ago.

```bash
# Canonical 3-file scan
PROJECT_DIR="${PROJECT_DIR:-~/project_ai_universe/ai_universe/shared-libs/packages/config-utils/src}"
grep -nE 'model:|maxInputTokens|endpoint|apiKeys' "$PROJECT_DIR/ConfigManager.ts" | head -40

COST_DIR="${COST_DIR:-~/project_ai_universe/ai_universe/shared-libs/packages/mcp-server-utils/src}"
grep -nE 'PRICING|modelMappings|normalizeModelName' "$COST_DIR/CostCalculator.ts" | head -30
grep -nE 'MODEL_DISPLAY_NAMES' "$COST_DIR/ModelDisplayNames.ts" | head -30
```

The `PROVIDER_CONTEXT_TOKEN_LIMITS` constant in `ConfigManager.ts` (e.g. `cerebras: 262_144, claude: 200_000, gemini: 1_048_576, grok: 1_000_000, perplexity: 200_000, openai: 128_000`) is the canonical "what contexts does each provider support" table — cross-reference it against the new model's published context window to confirm the upgrade doesn't break long-context code paths.

**Three findings worth surfacing even if the user already knew:**
- "You already moved to `gemini-3-flash-preview` last quarter — the legacy `gemini-2.5-flash` pricing key in `CostCalculator.ts` is dead code."
- "ConfigManager still pins `claude-sonnet-4-20250514` even though Claude Sonnet 5 launched — that's the actual upgrade target."
- "OpenAI default is `gpt-5-nano` ($0.05/$0.40) but the canonical mapping in `CostCalculator.ts` has `gpt-5` and `gpt-5-mini` listed separately — make sure the new modelId is in BOTH the modelMappings object AND the PRICING table."

## Phase 1 — Survey the new model (verify the user's claim, don't trust it)

The user said "upgrade from X to Y." Before doing the upgrade, prove Y exists AND has published pricing AND has published benchmarks. The research-integrity rule says: search snippets are leads, not evidence. Use `web_search`/`web_extract` + `curl` for vendor pages; verify the model id is in the official model card AND in OpenRouter's API surface.

**Verification sequence (canonical recipe):**

1. **Vendor's model page** (deepmind.google, ai.google.dev, anthropic.com, openai.com, x.ai, cerebras.ai):
   ```bash
   curl -fsS -A "Mozilla/5.0" "https://deepmind.google/models/gemini/flash/" | \
     grep -oE '<th[^>]*>[^<]*</th>|<td[^>]*>[^<]*</td>' | head -200
   ```
   The `<table>` HTML for benchmark comparisons gives you the head-to-head with the previous-gen sibling, the previous-gen Pro, and the closest competitors. Headlines like "released 2026-07-21" anchor the date.

2. **OpenRouter pricing as the cross-vendor canonical source** (most reliable pricing aggregator):
   ```bash
   curl -fsS -A "Mozilla/5.0" "https://openrouter.ai/<vendor>/<model-id>" | \
     grep -oE '(\$|0\.|7\.5e-6|1\.5e-6|9\.00e-7)[^"]{0,30}|Input (Modalities|Price):[^<]{0,80}'
   ```
   OpenRouter renders JSON-LD with `price` as a decimal per token — `7.5e-6` = $7.50/1M tokens. This is the same price Google charges; OpenRouter adds a 5% margin on top, so the divisor is exactly the vendor list price.

3. **Vendor's developer docs page** (ai.google.dev/gemini-api/docs/models/<model-id>) for modality + tool-use + context-window data:
   ```bash
   curl -fsS -A "Mozilla/5.0" "https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash"
   ```
   Confirm: text + image + video + audio in, text out, 1M context, 64k max output, function-calling / search-as-a-tool / computer-use.

4. **Cross-check the launch date** with a third-party news source (9to5google.com, thedecoder.co, TechCrunch) — this catches the "vendor accidentally published the page before GA" trap.

**Pitfall P1 — search snippets vs primary source.** A `web_search` returning "Gemini 3.6 Flash" mentions is a lead, not evidence. The `web_extract` tool returns "DuckDuckGo is a search-only backend" against most pages — fall back to `curl` against the raw HTML. The `web_search` result count is a popularity signal, not a verification.

**Pitfall P2 — OpenRouter 5% markup.** If the OpenRouter JSON-LD says `5.0e-6` per output token, the vendor list price is `5.0e-6 * 0.9524 = $4.76/1M`. Round to the nearest published tier ($5 / $7.50). Don't double-count the markup.

**Pitfall P3 — "Gemini 3 Flash has cache pricing too."** OpenRouter exposes `cache_read` and `cache_write` separately. If the user runs high-prompt-volume secondary-opinion workloads, cache pricing can dominate the cost — surface this in the matrix.

**Pitfall P4 — deprecation lanes.** Some "preview" and "exp" models have GA tiers with different pricing (`gemini-2.0-flash-exp` → `gemini-2.0-flash` doubling output cost). Always check the GA tier separately from the preview.

## Phase 2 — Build the cost-vs-quality matrix

The user's mental model is: "is the new model worth it?" The matrix answers that in one table.

**Sources to cite (in order of authority):**
1. Vendor's own model-comparison page (deepmind.google/models/gemini/flash/, anthropic.com/news/<model>, openai.com/index/<model>). These have the vendor-curated head-to-head table.
2. Third-party benchmarks (lm-evaluation-harness, LMArena, BenchLM.ai, llm-stats). Use when the vendor doesn't publish a comparison.
3. OpenRouter's pricing page — authoritative for list pricing across all major vendors.

**The matrix shape (verified deliverable shape for vision-formatted Slack/chat posts):**

```markdown
| Benchmark | New Model | Prev Gen | Top Comp | Cheaper Comp | Notes |
|---|---|---|---|---|---|
| Price in / out ($/1M) | $X / $Y | … | … | … | source |
| MMLU / MLE-Bench | …% | …% | …% | …% | |
| HumanEval / SWE-Bench | …% | …% | …% | …% | |
| Long-context (MRCR v2 128k) | …% | …% | …% | …% | |
| Long-context (1M pointwise) | …% | …% | …% | …% | the only model that scores here |
| Agentic (OSWorld-Verified) | …% | …% | …% | …% | |
| Context window | 1M | 1M | 200k | 128k | |
| Max output | 64k | 8k | 8k | 16k | |
```

Also include a **sibling-line comparison** (e.g. 3.6F vs 3.5F vs 3.1F) — the user's actual decision is often "stay on the older tier" vs "upgrade one tier" vs "upgrade two tiers," and a 3-row comparison shows the gradient.

**The recommendation tile (last section of the deliverable):**

| Slot | Current | Recommended swap | Reasoning |
|---|---|---|---|

This is the table the user reads. The previous benchmark matrix is the evidence. The recommendation is the action.

## Phase 3 — Deliver the response shape

The user wants a structured response, not a flowing narrative. Use this exact shape — verified against Jeffrey's preferences across at least 3 sessions:

1. **What's currently wired** (1 short table, 3-6 rows, file:line citations to the actual config files).
2. **Vendors confirmed exists** (one paragraph, with citation links to vendor + 3rd-party).
3. **Verified vendor numbers** (pricing table, 4-6 rows, source: openrouter.ai + deepmind.google).
4. **Cost-vs-quality matrix** (8-10 rows, columns: NewModel, PrevGen, TopComp, CheaperComp).
5. **Headline reads** (4-6 bullet points, each ≤ 2 lines, framed in plain English).
6. **Recommendation matrix** (per-slot table: current → recommended → reasoning).
7. **Next-step menu** (4 numbered options, no asking "what do you want to do?" — clearly named action paths the user picks from).

**Forbidden in the deliverable:**
- "I recommend X" without the matrix backing it.
- "Want me to do X?" — always "Option 1 — X. Option 2 — Y."
- "Pick one: A) B) C)" multi-menu picks (per SOUL.md `no-pick-one-menus` COMMIT).
- "I cannot verify pricing" without a fallback to OpenRouter as the canonical cross-vendor source.
- Nested quotes of the original request — paraphrase once, then move on.

## Phase 4 — Dispatch path (after the user picks a menu option)

The deliverable is research, not code. The user approving "Option 1 — apply now" triggers the dispatch. Per `always-pr-never-local-edit` + `finish-the-job`, the right move is:

1. **Spawn the AO worker** with the full task description + the cost-vs-quality matrix + the exact file paths to edit. The worker handles the worktree + PR + push.
2. **The worker touches** (canonical 4-5 file touch list for an AI-Universe style upgrade):
   - `shared-libs/packages/config-utils/src/ConfigManager.ts` — update `gemini.model` string
   - `shared-libs/packages/mcp-server-utils/src/CostCalculator.ts` — add new pricing entry + `modelMappings` entry
   - `shared-libs/packages/mcp-server-utils/src/ModelDisplayNames.ts` — add display name
   - `ai_universe_frontend/src/mocks/mockMcpServer.ts` + `src/mockData/canonicalSamples.ts` + `src/test/mocks/mcpFixtures.ts` — update fixtures
   - Run `npm test` in `shared-libs/packages/mcp-server-utils` to verify the cost-calculator unit tests pass
3. **The worker does NOT** bump the shared library's `dist/*.js` (those are regenerated by `npm run build` in CI).
4. **The PR body** lists the file:line touched, the new pricing numbers, and WHY the upgrade is worthwhile (the matrix summary).

**Worker prompt template (canonical, from the 2026-07-30 ai-universe-gemini-3.6-flash session):**

```
Task: upgrade <vendor>/<model> from <old> to <new> in jleechanorg/<repo>.
Touch these files exactly:
- <repo>/shared-libs/packages/config-utils/src/ConfigManager.ts — change `<provider>.model` to '<new-model-id>'
- <repo>/shared-libs/packages/mcp-server-utils/src/CostCalculator.ts — add pricing entry for <new-model-id>:
    '<new-model-id>': { input: <input_price>, output: <output_price> },
  AND add a normalizer in `modelMappings`:
    '<new-model-id>': '<pricing-key>',
- <repo>/shared-libs/packages/mcp-server-utils/src/ModelDisplayNames.ts — add display name:
    '<new-model-id>': '<Display Name>',
- <repo>/ai_universe_frontend/src/mocks/mockMcpServer.ts + src/mockData/canonicalSamples.ts + src/test/mocks/mcpFixtures.ts — update any 'gemini-2.0-flash-exp' / 'gemini-2.5-flash' / 'gemini-3-flash-preview' fixture to 'gemini-3.6-flash' (or whichever new model).

Verify:
- `cd <repo>/shared-libs/packages/mcp-server-utils && npm test` passes
- After bumping, models normalize to the new pricing key (no fallback warnings)
- `git diff --stat origin/main...HEAD` shows only the touched files, no incidental dirt

Cost-vs-quality rationale (paste the matrix from this session):

| Benchmark | New Model | Notes |
|---|---|---|
| Price in | $X / 1M | |
| Price out | $Y / 1M | |
| Long-context | 91.8% on 128k MRCR | only Flash-line model with 1M coverage |
| Agentic | 83% OSWorld | $X/$Y vs Sonnet 5 81% at $3/$15 |

PR body sections (required by your-project.com Gate 0 if this is a `$PROJECT_ROOT/**` file — N/A for ai-universe's shared-libs but include for completeness):
- ## Tenets
- ## Design Decision (the 4 rules: avoid-<old-model>-gotchas, use-vendor-published-pricing, no-preview-model-in-prod, etc.)
- ## Linked artifacts (bead rev-xxxx if applicable)
```

**The worker prompt MUST include the cost-vs-quality matrix** — otherwise the worker has no signal to pick the right pricing tier over the wrong one. The matrix is the deliverable's evidence, the upgrade is the action.

## Pitfalls

### P1. The user may be asking about a model the project already uses

Always re-read the three canonical files BEFORE answering. The "upgrade" may be a no-op (model already on the new tier) or a pricing-only update (ConfigManager already points to the new model, but CostCalculator still has the old pricing key). Surface this in the first paragraph of the deliverable — the user trusts you more if you say "actually, you already did this last quarter" than if you treat their request as fresh.

### P2. OpenRouter markup confuses pricing math

OpenRouter's listed price is vendor-list + ~5% markup. Divide by 1.05 (or look at the OpenRouter JSON-LD `price` field — it's the OpenRouter price, not the vendor price). When in doubt, cite the vendor's own pricing page for the headline number and OpenRouter for the cross-vendor comparison.

### P3. Preview/experimental models have different pricing than GA

`gemini-2.0-flash-exp` (preview) → `gemini-2.0-flash` (GA) → `gemini-2.5-flash` (GA) all have different price points. The default in `ConfigManager.ts` may be the preview string; the user is asking about the GA tier. Always confirm which tier the upgrade targets.

### P4. Don't trust unit numbers — read the full benchmark table

A single MMLU score (e.g. "88.5%") doesn't tell you the model is the best. The full table on the vendor's model page includes the model's weakness on long-context or reasoning. The deliverable should cite the model's STRENGTH (why upgrade) and the closest competitor's STRENGTH (why not). Surface both.

### P5. Cache pricing dominates at high-prompt-volume

For second-opinion workloads (the same prompt sent to N models), the cache_read rate ($0.15/1M on Gemini 3.6 Flash) is the dominant cost when the prompt is reused. The cost-vs-quality matrix should break out cache pricing when the user runs high-volume secondary queries.

### P6. The "best" model is often the wrong upgrade

When the matrix shows "the new model is 5% better at 2× the cost," the right answer is "stay on the current model." The deliverable should explicitly say so when the trade-off is unfavorable. The user wants a recommendation, not a sales pitch.

### P7. The dispatch decision is "apply now" vs "AO worker" vs "research only"

Per `always-pr-never-local-edit` + `finish-the-job`, the default is "AO worker on a fresh worktree from `origin/main`" — never inline edits. The deliverable's menu should default to this option. Inline edits are only OK if the change is single-file and <10 lines and the user has explicitly said "do it now, don't bother with a PR."

## Verification

Before posting the deliverable:

1. **All three canonical files have been read** — ConfigManager.ts, CostCalculator.ts, ModelDisplayNames.ts. The "current model" claim is anchored to a file:line.
2. **The new model is verified to exist** — at least one curl against the vendor's model page or OpenRouter returned the model name + pricing.
3. **The cost-vs-quality matrix has ≥ 4 columns** (new model, prev gen, top competitor, cheaper competitor) and ≥ 6 benchmark rows.
4. **The recommendation matrix has a per-slot decision** — at least one slot is "keep" (don't blindly upgrade everything).
5. **The next-step menu has 3-4 concrete options** — no "what would you like me to do?" framing.
6. **The LLM-provenance caveat is included** at the bottom of any Slack post per SOUL.md `llm-provenance-caveat` COMMIT.

## Related references

- `references/gemini-3.6-flash-verified-pricing-benchmarks-2026-07-30.md` — the verified Gemini 3.6 Flash vendor numbers + same-vendor benchmark comparison from `deepmind.google/models/gemini/flash/`. Read this when starting a Gemini 3-line upgrade.
- `references/ai-universe-config-file-map-2026-07-30.md` — the canonical 3-file layout for `jleechanorg/ai_universe` (ConfigManager, CostCalculator, ModelDisplayNames).

## Related skills

- `always-pr-never-local-edit` — the PR lifecycle that the dispatch step calls.
- `finish-the-job` — the end-state contract for the dispatched AO worker.
- `drive-pr-to-green` — when the upgrade PR needs to navigate your-project.com's Design Doc Grep Gate (Gate 0) or equivalent.
- `swap-hermes-provider` — the sibling skill for `~/.hermes/config.yaml` provider swaps. NOT this skill.
- `eval-vendor-tooling` — the sibling skill for evaluating a third-party vendor ML repo. NOT this skill.
