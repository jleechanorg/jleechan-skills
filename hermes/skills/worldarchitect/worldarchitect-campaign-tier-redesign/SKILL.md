---
name: worldarchitect-campaign-tier-redesign
description: "Redesign Your Project campaign-tier mechanics — recurring work on the god/multiverse/divine/sovereign/level-up systems in $GITHUB_REPOSITORY. Triggers: 'redesign X tier', 'rework god mode', 'campaigns less challenging', 'disable tier X', 'no campaign hardcoding except Dragon Knight', 'generate mysteries', 'mysteries not revealed', 'backstories not revealed to the player', 'unrevealed secrets in the plot', 'internal-drive plot arcs', 'MBTI internal', 'add a new campaign overlay', or any tier name (mortal/divine/sovereign/celestial/demonic/etc.). Covers `$PROJECT_ROOT/prompts/{mortal,divine,multiverse,shared}/` + `$PROJECT_ROOT/{campaign_divine,god_mode_level_up}.py`. Not for one-off bugs (`/repro`), Firestore export (`download-campaign`), or prod-data queries (`wa-prod-data-query`)."
version: 0.6.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [worldarchitect, god-mode, divine, sovereign, multiverse, campaign-tier, mechanics-redesign, level-up, es-evidence-protocol, ao-spawn-preflight, no-campaign-hardcoding, shared-prompts, ai-mystery, internal-drive-plot, mbti-internal, open-pr-preflight, discovery-first]
    related_skills: [download-campaign, wa-campaign-content-analysis, wa-green-gate-pr-shape, finish-the-job, workflow/always-pr-never-local-edit, agento, ao-spawn-minimax-worker, worldai-campaign-to-google-doc, llm-wiki]
    changelog:
      - "0.6.0 (2026-07-28): OPEN-PR PREFLIGHT + DISCOVERY-FIRST. (a) Added Phase -1 'Open-PR preflight' subsection — always run BEFORE Phase 0 inventory. REST-call recipe (`gh api search/issues`) that catches the common failure mode: agent proposes a new PR when an existing open PR (e.g. #8662 'AI mystery/internal-drive arcs') already covers the ask. Decision matrix covers 4 cases (amend existing / add rule to umbrella / push to umbrella-not-campaign-PR / open new). (b) Added Pitfall #19 'Don't open a new PR or rewrite a contract before running Phase -1 open-PR preflight' — verified 2026-07-28 on the 'add mysteries to the plot' user request which mapped to PR #8662. (c) Expanded description + trigger phrases to cover the user's natural-language phrasings: 'mysteries not revealed', 'backstories not revealed to the player', 'unrevealed secrets in the plot', 'encourage creation of mysteries in the plot line'. (d) New reference doc `references/open-pr-preflight-recipe.md` with the full REST-call recipe, decision matrix, and the 2026-07-28 PR #8662 case study."
      - "0.5.0 (2026-07-28): NO-CAMPAIGN-HARDCODE RULE + AI-MYSTERY/INTERNAL-DRIVE DESIGN PATTERN. (a) Added Phase 2.5 'AI-Generated Mysteries + Internal-Drive Plot Architecture' subsection — the canonical 3-suspect template (red herring / partial truth / real answer), the hidden-fact → clue-trail mechanic, the per-act growth/insecurity/reframe requirement, and the MBTI internal-only contract reference (PR #8539). (b) Added Pitfall #18 'Don't hardcode a single campaign's prompt type/path/directory to `$PROJECT_ROOT/agent_prompts.py` / `$PROJECT_ROOT/constants.py` / `$PROJECT_ROOT/agents.py` / `$PROJECT_ROOT/prompts/<campaign>/` — except for the Dragon Knight fast-path. Use the `$PROJECT_ROOT/prompts/shared/` + `custom_campaign_state.campaign_overlays` generic gate pattern.' (c) New trigger phrases: 'no campaign hardcoding except Dragon Knight', 'generate mysteries', 'internal-drive plot arcs', 'MBTI internal', 'add a new campaign overlay'. Verified 2026-07-28 on PR #8661 (Spellblade Valeria) — user comment 3670171626 + Slack `C0AUXSVFSA2` thread: 'I never want anything hardcoded to a single campaign except Dragon Knight' + the 5 CodeRabbit blockers (P1: 'Load the Spellblade overlay for opted-in campaigns' on agent_prompts.py:177; P2: rule lives in combat prompt but is a dialog rule; P2: NPC goals can't evolve under any circumstance; P2: hidden_power_charges never decrement; P2: mirrored rules duplicate shared canonical). Companion PR-A: `feat/shared-contracts-mbti-internal-drive` adds the 6 generic shared contracts + the campaign_overlays loader gate + AGENTS.md 'no campaign hardcoding' rule."
      - "0.4.0 (2026-07-23): ES EVIDENCE PROTOCOL + AO SPAWN MODEL-PREFLIGHT. Added Phase 3 subsection 'PR B evidence — real /es local-server + real LLM is mandatory for prompt-only mvp_site changes' (forces testing_mcp real-API test, BQ raw-request verification, rejects unit-only stand-ins) + 2 new pitfalls (#16 prompt-only is NOT a /es carveout; #17 MiniMax-M3 AO worker preflight + early-kill discipline — Codex usage-limit banner appears before first tool call; if no commit lands within 60-90s, kill + respawn on a different harness with explicit mid-tier). Verified this session's god-mode-generic-mechanics PR (issue #8538, AO session wa-3389): worker tried to substitute `python -m unittest` for real /es, required a steering nudge mid-run, real gunicorn+Gemini 3.5 run is what produces durable evidence."
      - "0.3.0 (2026-07-21): PR B delivery shape — PROMPT-ONLY MECHANICS + SPLIT PROMPT STRUCTURE. Added Phase 3 subsection 'PR B delivery shape' + 6 new pitfalls (#10 ZFC: no god-mechanics Python helpers; #11 don't jam mechanics into ceremony prompt, audit existing files first; #12 setting-agnostic contract — no D&D entities leak; #13 push-race on shared branch recovery; #14 green-gate PR body schema; #15 general vs setting-specific split). Verified PR #8488 (V2 god-mechanics) — reviewer feedback from jleechan2015 (inline r3618945602: 'This is wrong and violating /zfc i think. It should just stay as prompt only') and user feedback ('I dont think everything should be in the ceremony prompt? There should be a ceremony/upgrade prompt and a general god mechanics prompt?' + 'I think there's already another mechanics prompt? what else is in divine/ folder?')."
      - "0.2.0 (2026-07-21): PR A disable contract — SINGLE-SWITCH CENTRALIZATION. Added the 'one flag + 3-helper registry' pattern + test contract + the 'runtime-flags-do-not-update-import-time-thresholds' pitfall. Anti-pattern (the trap I fell into on PR #8485 v1): 5-file scattered disable with hardcoded `return False` and commented-out blocks. Correct shape: `MULTIVERSE_TIER_ENABLED` + `get_allowed_campaign_tiers()` / `get_upgrade_complete_tiers()` / `is_multiverse_tier_enabled()` in `constants.py`. Re-enabling is now one boolean flip. Verified PR #8485 v2 (review feedback from $USER: 'centralize this code better, control it with existence of this enum vs all these other code changes so easier to turn back on later')."
      - "0.1.0 (2026-07-20): Initial umbrella covering the design-and-disable cycle on the tier stack."
---

# worldarchitect-campaign-tier-redesign

Canonical home for "the user wants to redesign / disable / revisit a campaign tier" work in $GITHUB_REPOSITORY. This is a **class-level umbrella** that covers the recurring design cycle:

1. **Audit current state** — read the prompt files + Python detection code + tests + prior art in `world_reference/`.
2. **Search prior campaigns** — what god/divine/sovereign/tyranny campaigns has the user already played? Which mechanics did they like? (`download-campaign` for Firestore, `gog drive search` for Google Docs.)
3. **Identify regressions** — why do newer campaigns feel less challenging than older ones? Root cause in prompt layer first, never in backend enforcement.
4. **Propose a redesign** — setting-agnostic mechanics that explicitly reference what made the older work.
5. **Disable / ship / measure** — small disable PR first, then the redesign PR, then verify on new scenes.

## When to use

Trigger phrases (any one):

- "Redesign all the god / divine / multiverse / sovereign mechanics"
- "Disable sovereign / multiverse / [tier X] for now"
- "Revisit the divine / [tier Y] campaigns"
- "The god campaigns got less challenging / mechanics weren't great"
- "Make the new god campaign more like my older [Aizen / Nocturne / etc.] one"
- "I want a new tier progression" / "add a celestial tier"
- "Disable tier X / the [tier] prompt"
- "Add mysteries to the plot" / "mysteries not revealed" / "backstories not revealed to the player" / "unrevealed secrets in the plot" / "encourage creation of mysteries in the plot line" — these map to the AI-mystery shared contract in `$PROJECT_ROOT/prompts/shared/ai_generated_mystery_and_internal_drive_plot_arc.md` (see Phase 2.5). **Before designing a new PR, run Phase -1 to check if [PR #8662](https://github.com/$GITHUB_REPOSITORY/pull/8662) (or its successor) already covers this** — that PR introduced the 3-suspect mystery template, hidden fact, clue trail, red herring / partial truth / real answer, and personal-cost reveals.
- "Use the MBTI stuff as background material" / "internal-drive plot arcs" / "challenge their insecurities" — maps to the internal-drive plot arc contract, MBTI internal-only (PR #8539 invariant).

Anti-triggers (don't load this skill):

- "Fix this specific god-mode bug" → `/repro`
- "Pull this specific campaign from Firestore" → `download-campaign`
- "Audit prompt changes across N campaigns" → `wa-campaign-content-analysis`
- "Diagnose why my last Cloud Run deploy failed" → `wa-cloud-run-deploy-failure-debug`
- "Bring this PR to green" → `finish-the-job` + `drive-pr-to-green`

## Class-level lesson (verified 2026-07-20)

Jeffrey's prior god-campaign work has a **quantified-stat-table pattern** that the current production system lost when it generalized. The local `world_reference/aizen_god_mechanics.md` (11,449 bytes, replicated across ~50 worktrees) defined a Nascent Greater Deity with hard numbers — DR 750, DAC 25, DPP 825/day, DAIR Mod +31, DLR 4, Primary Damage 80 + (1d20×5) — that the LLM could ground its output in. The current `$PROJECT_ROOT/prompts/divine/divine_leverage_system.md` replaces these with **Dissonance × Safe Limit × Risk Multiplier** formulas that are harder for the LLM to produce concrete combat output from. See `references/aizen-god-mechanics-pattern.md` for the full reconciliation.

Three documented root causes of "newer god campaigns feel less challenging":

1. **Two conflicting three-layer framings** — production is "Mask (L0) / Persona (L1) / Source (L2)" (mortal-face outward); Aizen is "Ambiguous (L1) / Projected (L2) / Cover-story (L3)" (all deception layers). Numbering + semantics diverge. Pick one.
2. **DPP (Divine Power Points) is overloaded** — finite pool in the ascension ceremony (5/5), "Dissonance IS the cost" (no pool) in the leverage rules, daily-replenishing 825/day in Aizen. Pick one.
3. **No quantified divine stat table** — production uses Risk-Multiplier formulas; Aizen has the DR/DAC/DPP/DAIR/DLR/Primary-Damage table. LLM combat output is better grounded by the table.

## Phase -1 — Open-PR preflight (always; takes <30s, runs BEFORE Phase 0)

**Always run this before designing anything.** It catches the most common failure mode: the agent proposes "open a new PR" or "rewrite the contract" when an existing open PR already covers the ask. Verified 2026-07-28 on the "add mysteries to the plot" user request — the agent had to discover [PR #8662](https://github.com/$GITHUB_REPOSITORY/pull/8662) (which introduced `$PROJECT_ROOT/prompts/shared/ai_generated_mystery_and_internal_drive_plot_arc.md` with the 3-suspect template + personal-cost reveals) after multiple tool calls. The preflight would have surfaced this in one REST call.

### Recipe

```bash
cd ~/projects/your-project.com && git fetch origin 2>&1 | tail -3

# 1. List every feat/* branch on origin (covers branches with or without PRs)
git branch -r | grep -E 'origin/feat/' | sort -u

# 2. Search open PRs by keyword (REST, not GraphQL — bypasses rate limits)
gh api 'search/issues?q=repo:$GITHUB_REPOSITORY+is:pr+is:open+mystery+OR+secret+OR+reveal+OR+plot+OR+foreshadow' \
  --jq '.items[] | {number,state,title,url,head_ref:.head.ref}' 2>&1

# 3. Search by shared-contracts keyword (catches the v0.5.0 umbrella PRs)
gh api 'search/issues?q=repo:$GITHUB_REPOSITORY+is:pr+is:open+shared-contracts+OR+internal-drive+OR+mbti+OR+overlays' \
  --jq '.items[] | {number,state,title,url,head_ref:.head.ref}' 2>&1

# 4. For each candidate branch, check whether it already contains a
#    `$PROJECT_ROOT/prompts/shared/ai_generated_mystery_and_internal_drive_plot_arc.md`
#    (or whatever contract the user's ask maps to) — saves re-reading the diff
git ls-tree -r origin/<branch> -- $PROJECT_ROOT/prompts/shared/ 2>&1 | grep -E 'mystery|internal_drive|plot_arc'
```

### Decision matrix

| What the preflight found | Action |
|---|---|
| Open PR already has the contract file | **Strengthen / amend that PR** — push to the same branch. Don't open a new PR. |
| Open PR covers a related ask (e.g. shared contracts umbrella) but missing the specific rule | **Add the rule to that PR** as a new commit on the same branch. Reference the umbrella PR's compatibility section. |
| Multiple candidate branches (umbrella PR + companion campaign PR like #8662 + #8661) | **Push to the umbrella PR** (the shared contract), not the campaign-specific PR. Per `no-campaign-hardcoding` rule, the contract belongs in `$PROJECT_ROOT/prompts/shared/`. |
| No matching open PR | **Proceed to Phase 0** inventory + Phase 2 proposal. Branch from `origin/main`. |

### Anti-pattern

- **Don't propose a new PR** before running Phase -1. The user's "make a new PR or add this so an existing PR that fits" (verified 2026-07-28 Slack phrasing) explicitly invites the agent to join an existing PR when one fits — default to that path.
- **Don't skip the preflight even if the user's ask sounds new.** Mystery/secrets/plot phrasing in 2026-07-28 mapped to PR #8662 verbatim; future phrasings ("add foreshadowing", "add plot twists", "keep the player guessing") will likely map to the same contract.
- **Don't re-inventory Phase 0 items just because Phase -1 found an existing PR.** Phase 0 is for designing new work; if you're amending an existing PR, read its current diff and identify the gap, not start over.

## Phase 0 — Inventory (always; takes <5 min)

Before designing anything, run the inventory. This is the **delivery contract** — see the `memory-search` skill for the parallel-fan-out pattern.

Three parallel `delegate_task` calls:

| Task | Sources | Returns |
|---|---|---|
| **A — file audit** | `$PROJECT_ROOT/prompts/{tier}/*.md`, `$PROJECT_ROOT/campaign_divine.py`, `$PROJECT_ROOT/god_mode_level_up.py`, `world_reference/*.md`, `wiki/sources/{tier}-*.md` | Structured audit: every file, summary, mechanical rules verbatim, JSON state shapes, cross-references |
| **B — 9-store memory search** | `/ms` fan-out with 3-5 fused queries (e.g. "sovereign multiverse disable", "Aizen god tyranny", "divine ascension ceremony") | 9-section report: ~/roadmap / beads / claude memories / hermes sqlite / briefings / MEMORY.md / wiki / history / slack |
| **C — campaign corpus** | `gog drive search "Aizen" "god" "campaign"` for Google Docs at $USER@gmail.com + `download-campaign` for Firestore-resident god campaigns + `find ~/repos/jleechanorg -name "*aizen*" -o -name "*god*"` for local copies | Inventory table: doc ID, name, mimeType, modifiedTime, size, first-paragraph, 1-sentence "why this matters" |

**Cache the 3 outputs at `/tmp/redesign_task{0,1,2}.md`** for re-reading in chunks (read_file truncates at ~50K chars inline).

## Phase 1 — Diagnose root causes

Three regression patterns to look for, in priority order:

1. **Quantification loss** — does the current system have hard numbers the LLM can use in combat output? Or only formula-derived values? If formula-only, the redesign needs a quantified-stat table (Aizen pattern).
2. **Three-layer framing duplication** — are there 2+ different layer schemes in different files that the LLM has to reconcile per-scene? If yes, collapse to one canonical scheme + cite the losing scheme as historical context.
3. **Trigger ambiguity** — does the upgrade detector use multiple thresholds (level + divine_potential + explicit flag)? Is there a default order (e.g. "multiverse takes priority regardless of tier") that lets a player ascend past the intended point? If yes, document the canonical trigger order and make the priority explicit.

## Phase 2 — Proposal

Write a design doc at `world_reference/{tier}_mechanics_redesign_v2.md`. Format:

1. **Goal** — what this redesign is fixing (cite Phase 1 root causes).
2. **Prior art** — which old campaign/campaigns this draws from (cite real doc IDs from Phase 0 inventory).
3. **Setting-agnostic core** — explicit remapping from D&D-specific terms to generic-Apex-Powers terminology. The user has explicitly asked for "general, not Faerun/D&D" mechanics — respect that. Ao → Prime Mover, Pantheon → Apex Powers, Weave → reality fabric, Divine Rank → Power Tier.
4. **Mechanics** — quantified stat table (Aizen-pattern), trigger conditions, advancement formula.
5. **3-Generation Power Lineage** — the G0 architect / G1 rejecter / G2 NEW-choice fork pattern from `world_reference/campaign_module_god_of_murder.md` (verified 2026-07-20 in PR #8483).
6. **What stays / what goes** — explicit list of removed mechanics with the regression they caused.
7. **Verification plan** — what scenes prove the redesign landed (per `wa-campaign-content-analysis` Phase 6 verification recipe).

## Phase 2.5 — AI-Generated Mysteries + Internal-Drive Plot Architecture (verified 2026-07-28)

When the user asks for "mystery-driven campaigns," "internal-drive plot arcs," "character growth arcs that challenge insecurities," or "use the MBTI stuff as background material," the design documentation MUST include the following architecture. This is a recurring pattern across the user's god/divine/Spellblade work; the canonical contracts above (one-rule-one-authoritative-file in `$PROJECT_ROOT/prompts/shared/`) and the **canonical contract pinning** in PR #8539 (MBTI internal-only, NEVER in player-facing text) are the two upstream invariants this phase assumes.

### Mystery template (mandatory for mystery-driven campaigns)

Every campaign the user wants to feel "mystery-driven" must include at least one active mystery with this structure:

```
mystery_state: {
  active: [
    {
      id: "mystery_1",
      hidden_fact: "The fact nobody knows yet",  # ONE fact, not 3
      clue_trail: [
        {"scene": N, "clue": "...", "red_herring_weight": 0.3},
        {"scene": N+k, "clue": "...", "red_herring_weight": 0.5},
        {"scene": N+k+j, "clue": "...", "red_herring_weight": 0.1},
      ],
      # Exactly 3 suspect branches — the LLM must seed ALL THREE.
      # The player (or the campaign) picks the real answer; the LLM never overrides.
      suspect_branches: [
        {"id": "red_herring", "presentation": "...", "weight": 0.4},
        {"id": "partial_truth", "presentation": "...", "weight": 0.4},
        {"id": "real_answer", "presentation": "...", "weight": 0.2},
      ],
      # The mystery must HIT a character's vulnerability — see MBTI internal-only contract.
      hits_vulnerability: "campaign:npc_faction:character_id",  # which NPC's internal drive this challenges
      resolved: false,
    },
  ],
  resolved: [{"id": "mystery_0", "real_answer": "...", "victim_or_beneficiary": "..."}],
}
```

**Three mechanical rules:**

1. **AI must seed mysteries proactively**, not wait for the player to ask. The opening scene must include at least one clue of an active mystery (Phase 9 / Step 10's "A/B/C choice" should ALSO surface the first clue).
2. **Three suspect branches are non-negotiable.** A mystery with only one path is not a mystery; it's a tutorial. The branches must be plausible (no "obviously the butler did it" branches). The weights are guidance, not destiny — player choices can shift real_answer confidence.
3. **`hits_vulnerability` must reference a character's MBTI-internal vulnerability** under the canonical contract from PR #8539 — the LLM uses internal-only data (`mbti`, `attachment_style`, `insecurity_axes`, `stress_arc_target`) to design the mystery so it lands on the character, not on the player.

### Internal-drive plot arc — the per-act requirement

Every campaign Act (1, 2, 3) MUST do at least one of:

- **(a) Advance the character's growth direction** — what they need to learn, heal, or confront (see `campaign-creation` v1.2.0 `Phase 11.VI Personal-Growth Direction` for the data structure).
- **(b) Confront an insecurity** — the MBTI stress-arc pattern (e.g. INFJ under stress → withdrawal + hyper-critical; ESTJ under stress → controlling micromanagement).
- **(c) Reframe a long-held Want in light of new evidence** — the character's explicit Want is re-evaluated when the campaign surfaces a reason it can no longer be pursued unchanged.

Anti-pattern: a campaign arc that doesn't grow the character is a series of unconnected scenes. Even if the user wants "tight plot," the act breaks above still apply — the character's growth is the through-line.

### MBTI internal-only contract — the upstream invariant

The MBTI architecture (Want / Fear / Boundary trifecta + stress arcs + personal-growth direction) is **LLM-input only**. Per PR #8539's canonical contract:

- MBTI type codes (`INTJ`, `ISTJ`, etc.) are NEVER in player-facing text.
- D&D alignment labels are NEVER in player-facing text.
- Big Five scores are NEVER in player-facing text.
- Personality categories are NEVER in player-facing text.
- The wiki pages at `~/llm_wiki/wiki/concepts/mbti/*.md` are AI-background material only — sourced from the 16 personalitypage.com pages (verified 2026-07-28 wiki ingest).

The wiki ingest companion: `~/.hermes/skills/llm-wiki` is the canonical authoring skill. The 16 raw HTML pages at `~/llm_wiki/raw/articles/mbti/*.html` are sha256-stamped for re-ingest drift detection.

### Verification rule for mystery/int-drive PRs

A PR that adds AI-mystery infrastructure or internal-drive plot arcs to `$PROJECT_ROOT/prompts/` MUST include:

1. A focused test that asserts the new shared contract file exists in `$PROJECT_ROOT/prompts/shared/`, contains the canonical keywords, and is registered in `PATH_MAP`.
2. A test that asserts the contract is wired into `StoryModeAgent` / `CombatAgent` / `DialogAgent` `REQUIRED_PROMPT_ORDER` (or `OPTIONAL_PROMPTS` if conditional).
3. A non-test reference in the PR body's `## Known Limitations` section explaining that the mystery/int-drive architecture is prompt-only — the state tracking (`mystery_state`) is the campaign-side LLM's responsibility, not backend enforcement.

## Phase 3 — Ship

Two-PR sequence (recommended):

- **PR A (small, fast): disable** — flip the trigger threshold to a sentinel (`UNIVERSE_CONTROL_THRESHOLD = 99999`), short-circuit `is_multiverse_upgrade_available()` to always `False`, add `disallow: {tier}` to the prompt loader, tag the disabled wiki sources with `disabled: true` frontmatter. One commit. Pure disable, no redesign. Branches from `origin/main`. Per `workflow/always-pr-never-local-edit`.
- **PR B (the redesign)** — ship the new prompt + setting-agnostic code + test coverage + a wiki source page + an update to the campaign module if applicable. Branches from `origin/main`. Per `finish-the-job`.

Both PRs MUST be pushed (per SOUL.md `push-pr-donot-stop-halfway`) and both MUST pass the 7-green gate per `~/.claude/skills/zero-touch.md`.

### PR B delivery shape — PROMPT-ONLY MECHANICS + SPLIT PROMPT STRUCTURE (verified PR #8488, 2026-07-21)

**Default: PR B is a prompt-only delivery.** No new Python helpers, no new constants, no new test files for backend code. The mechanics live as LLM instructions in the prompt markdown.

**Why prompt-only (ZFC + root-cause-first):** Semantic decisions about god-tier transitions, multipliers, reputation bands, god-class biases, deicide-cost, etc. belong to the LLM, not to backend routing code. Pure-function helpers are dead code that misleads future readers. The reviewer on PR #8488 (`jleechan2015` inline comment r3618945602) explicitly called this out: *"This is wrong and violating /zfc i think. It should just stay as prompt only."*

**When to escalate to backend enforcement (rare):** Only after documenting why prompt correction is insufficient. Even then, the enforcement should be a **narrow, logged invariant** (e.g. "no command may exceed L46+ without approval"), not a `compute_v2_divine_stats()` helper.

### PR B evidence — REAL /es LOCAL SERVER + REAL LLM IS MANDATORY for prompt-only `$PROJECT_ROOT/**` changes (verified 2026-07-23, issue #8538)

This is the most-frequently-violated gate and the one AO workers try hardest to substitute around. The pitfall is real: a prompt-only `$PROJECT_ROOT/agent_prompts.py` change "doesn't add new behavior, just text" feels like it should be exempt from /es. It is **not**. Per the your-project.com repo's AGENTS.md and the Green Gate workflow:

> *"Any non-test change under `$PROJECT_ROOT/**` requires `/es` evidence before the work is complete. ... If the changed code can touch LLM, agent routing, game state, rewards, persistence, streaming, APIs, or server behavior, `/es` must use a real local server with real services, including real LLM calls where that path uses an LLM."*

A prompt-only change to `$PROJECT_ROOT/agent_prompts.py` (e.g. adding a new section to `build_god_mode_directives_block()`) **does** touch LLM agent routing and game state — the prompt is what the model sees at runtime. Therefore the carve-out that applies to "pure comments / docs / formatting / type hints" **does NOT apply**. The evidence bundle MUST include:

1. **Real local server.** Spawn `gunicorn mvp_site.main:app --bind 0.0.0.0:<port>` (typically a free high port) with `TESTING_AUTH_BYPASS=true ALLOW_TEST_AUTH_BYPASS=true WORLDAI_DEV_MODE=true MCP_TEST_MODE=real MOCK_SERVICES_MODE=false GOOGLE_APPLICATION_CREDENTIALS=…`. Verify it's live by curling `/health` or `/api/health` before driving any LLM call.
2. **Real LLM call(s).** Exercise the changed path end-to-end — for god-mode mechanics that's typically a `GOD MODE:` chat-turn input that triggers the directive-loader. The turn must be an actual `GodModeAgent` invocation, not a mocked fixture.
3. **BQ-observable request trace.** Per `~/.hermes/skills/worldarchitect/references/eval-god-mode.md` (and `.claude/skills/bq-evidence-reading.md`), the gateway logs the `gemini_provider.stream.request_json` payload to BQ. Verify the new directive text appears verbatim in `gemini_provider.stream.request_json.contents[].parts[].text` for the god-mode agent on the turn that exercises the new mechanic. The `GodModeAgent.response_text` for the same turn should be referenced for "did the model follow the new directive" — but the *delivery* evidence is in the request, not the response.
4. **A `testing_mcp/test_<mechanic>_contract_real_api.py` script.** Uses `MCPTestBase` + a real local server + real LLM (NOT mocks). The script should:
   - seed the new directive via `GOD_MODE_UPDATE_STATE:` to load it into `custom_campaign_state`,
   - trigger a god-mode chat turn that must invoke the changed `build_god_mode_directives_block()`,
   - parse the captured LLM request JSONL (`llm_request_responses.jsonl` / `provider_http_request_responses.jsonl` / `request_responses.jsonl`) and assert the literal text of the new mechanic appears (use a case-insensitive substring scan over ALL string fields, not just `system` role text — the directive may live under different keys depending on the request shape).
5. **The agent's behavior delta.** Capture the `GodModeAgent.response_text` from BQ (via `bq query` per `.claude/skills/bq-evidence-reading.md`) for the same turn — the response should show the model applying the new mechanic, not falling back to the prior path.

**Three common substitutes the AO worker will try, and why each fails:**

| Substitute | Why it fails |
|---|---|
| `python -m unittest $PROJECT_ROOT/tests/test_<x>.py` | Unit tests prove the helper function renders the new text correctly. They DO NOT prove the LLM actually receives it at runtime. Green Gate gate 6 requires real-server + real-LLM proof. |
| `bash scripts/generate_evidence_bundle.sh <test_name>` | That script runs unit tests + captures stdout. It does not start a server, does not drive an LLM call, and the captured stdout does not include the LLM request payload. It satisfies the "evidence exists" requirement formally but not substantively. |
| "Pure prompt exception — no runtime behavior changed" | The AGENTS.md carve-out explicitly excludes prompt-layer changes. Adding or rewording a directive IS a behavior change at the model-decision boundary. |

**The diagnostic recipe when a worker submits a unit-test-only evidence bundle:**

1. `git diff origin/main..HEAD --stat` — confirm only test files + prompt/agent_prompts files changed.
2. `cat /tmp/wa-NNNN/feat/<branch>/<test_name>/latest/*.err 2>/dev/null` (or wherever the evidence bundle landed) — look for the captured LLM request payload.
3. If the bundle contains `python -m unittest` output and NO captured HTTP / request JSONL → reject as not-real-evidence. Reply: *"STOP: unit-only evidence violates the explicit brief and repo AGENTS.md. This non-test mvp_site change REQUIRES real /es local server + real services + real LLM. ..."*
4. Use `ao send <session>` to steer the worker mid-run (do not kill and respawn — the worker is usually mid-implementation, just on the wrong evidence path).

**Companion reference:** `references/es-evidence-protocol-prompt-only-mvp-site.md` (this skill) has the canonical copy-paste steering nudge, the BQ query for verifying the request payload, the `testing_mcp` template skeleton, and the verified full transcript from issue #8538's god-mode-generic-mechanics PR.

**Split prompt structure — ceremony vs. mechanics are SEPARATE files:**

| File | Role | Size (typical) |
|---|---|---|
| `$PROJECT_ROOT/prompts/{tier}/{tier}_ascension_ceremony.md` | Trigger + ceremony phases (Recognition → State Updates) — runs ONCE per character | 100-150 lines |
| `$PROJECT_ROOT/prompts/{tier}/{tier}_leverage_system.md` (or `divine_god_mechanics.md` for non-ascension tiers) | Per-turn mechanics — runs on every divine-tier turn after ascension | 500-800 lines (V1 + V2 overlays stacked) |

The ceremony prompt cross-references the leverage prompt: *"Post-ceremony: also load `divine_leverage_system.md` for all subsequent divine-tier turns."*

**Audit existing files BEFORE creating new ones.** Before adding `divine_god_mechanics.md` or similar, `ls` the `prompts/{tier}/` folder. The general-mechanics file likely already exists — `divine_leverage_system.md` for the divine tier, etc. Adding a redundant file is wasted work and confuses the LLM (which prompt to load?).

**V2 overlay insertion pattern:** Insert V2 sections at the **bottom** of the leverage prompt, BEFORE the Setting Adaptation Appendix. The appendix stays the only setting-specific content at the end of the file. The V2 overlay inherits the existing setting-agnostic preamble.

### PR A disable contract — SINGLE-SWITCH CENTRALIZATION (verified PR #8485 v2, 2026-07-21)

**Anti-pattern (the trap I fell into on PR #8485 v1):** disable scattered across 5 files — `campaign_divine.is_multiverse_upgrade_available()` hardcoded `return False`, `agent_prompts._append_campaign_tier_prompts()` had `elif False: pass`, `_CAMPAIGN_UPGRADE_COMPLETE_TIERS` dropped SOVEREIGN via inline comment, `agents.CampaignUpgradeAgent` had a defense-in-depth warning fallback, `constants.UNIVERSE_CONTROL_THRESHOLD` was a hardcoded sentinel. Five files to flip to re-enable. The user's review feedback was direct: *"centralize this code better, control it with existence of this enum vs all these other code changes so easier to turn back on later."*

**Correct shape — single switch + small registry in `constants.py`:**

```python
# The single switch
MULTIVERSE_TIER_ENABLED = False

# Import-time-computed sentinel-vs-historical threshold (no other file needs to flip)
UNIVERSE_CONTROL_THRESHOLD = 999999 if not MULTIVERSE_TIER_ENABLED else 70

# Three registry helpers — every call site reads these instead of hand-rolling sets
def get_allowed_campaign_tiers() -> frozenset[str]:
    tiers = [CAMPAIGN_TIER_MORTAL, CAMPAIGN_TIER_DIVINE, CAMPAIGN_TIER_SOVEREIGN]
    return frozenset(tiers)  # keeps SOVEREIGN in allowlist for legacy Firestore data

def get_upgrade_complete_tiers() -> frozenset[str]:
    tiers = {CAMPAIGN_TIER_DIVINE}
    if MULTIVERSE_TIER_ENABLED:
        tiers = {CAMPAIGN_TIER_DIVINE, CAMPAIGN_TIER_SOVEREIGN}
    return frozenset(tiers)

def is_multiverse_tier_enabled() -> bool:
    return MULTIVERSE_TIER_ENABLED
```

Then every call site reads the flag:

| Site | Reads |
|---|---|
| `campaign_divine.is_multiverse_upgrade_available()` | `if not constants.is_multiverse_tier_enabled(): return False; else original_trigger_logic` |
| `campaign_upgrade._CAMPAIGN_UPGRADE_COMPLETE_TIERS` | `constants.get_upgrade_complete_tiers()` |
| `agent_prompts.PATH_MAP` sovereign entries | `if constants.is_multiverse_tier_enabled(): PATH_MAP.update({SOVEREIGN_*: PATH})` |
| `agent_prompts._append_campaign_tier_prompts()` | `elif constants.is_multiverse_tier_enabled() and campaign_tier == CAMPAIGN_TIER_SOVEREIGN:` |
| `agents.CampaignUpgradeAgent` | `if self._upgrade_type == "multiverse" and not constants.is_multiverse_tier_enabled(): fallback_to_divine_with_warning; elif self._upgrade_type == "multiverse": load SOVEREIGN_ASCENSION` |
| `game_state.allowed_tiers` + `rewards_engine.valid_campaign_tiers` | `constants.get_allowed_campaign_tiers()` |

**To re-enable the tier:** flip `MULTIVERSE_TIER_ENABLED = True` and redeploy. No other file changes needed.

**Critical contract when designing the disable:** the body of every call site must STAY RUNTIME-IDENTICAL when the flag is False. The original pre-disable logic should be the "flag=True" branch — never delete the implementation, just gate it. This is the difference between "temporary disable" and "permanent deletion". The user's review feedback makes this an explicit hard rule.

**Test contract for the single switch:**

- 13+ tests proving the registry helpers reflect the flag in both states (`patch.object(constants, "MULTIVERSE_TIER_ENABLED", True/False)`)
- `test_returns_false_when_flag_disabled` + `test_returns_true_when_flag_enabled_and_triggers_met` for each gated function
- `test_import_time_threshold_matches_disabled_flag` for the computed threshold (since `UNIVERSE_CONTROL_THRESHOLD` captures at import time, runtime flag flips don't reach it — that's correct, you re-deploy not runtime-toggle)
- The original disable tests still pass unchanged (they prove the flag-False runtime is identical to the previous "hardcoded disable" runtime)

**Why the registry needs three helpers, not one `is_tier_enabled(tier)`:** the SOVEREIGN entry legitimately stays in `get_allowed_campaign_tiers()` even when disabled (legacy Firestore documents with `campaign_tier="sovereign"` still need to validate; no NEW campaign transitions INTO sovereign while disabled). But it drops out of `get_upgrade_complete_tiers()` and `is_multiverse_tier_enabled()` returns False. Conflating these two states in a single helper breaks legacy-data compatibility.

**Pitfall — `UNIVERSE_CONTROL_THRESHOLD` is import-time-computed, not runtime-flip-able:**

```python
# CORRECT — one flip, then redeploy
MULTIVERSE_TIER_ENABLED = True  # was False
# UNIVERSE_CONTROL_THRESHOLD auto-recomputes to 70 on next import
```

```python
# WRONG — runtime flag flip does NOT update the threshold
import mvp_site.constants as c
c.MULTIVERSE_TIER_ENABLED = True
print(c.UNIVERSE_CONTROL_THRESHOLD)  # still 999999 — it was captured at module load
```

If you ever need runtime-toggle for A/B testing or staged rollout, extract the comparison into a helper instead:

```python
def is_universe_control_at_threshold(universe_control: int) -> bool:
    threshold = 70 if MULTIVERSE_TIER_ENABLED else 999999
    return universe_control >= threshold
```

For PR A disable work, the import-time semantics are correct — re-deploying to flip the flag is the right blast radius.

## Phase 4 — Verify

After PR B merges, run `wa-campaign-content-analysis` Phase 6 (prompt-fix-effectiveness-verification) on the next 5 god-tier scenes the user plays. Quantified-stat-table presence in combat output, three-layer-framing consistency, trigger-ambiguity regression check. Report findings as pre/post delta + the 5-cause taxonomy if the LLM isn't following the new prompt.

## Pitfalls (this list IS the skill — review before running)

1. **Don't propose a redesign without first running Phase 0 inventory.** The "receipts-first" contract is non-negotiable. The user has been bitten by agents that propose redesigns without grounding them in real prior campaigns.
2. **Don't replace the quantified-stat-table with formula-only.** The LLM produces worse combat output when it has to derive divine stats from Risk Multipliers every turn. Use the Aizen pattern (DR/DAC/DPP/DAIR/DLR/Primary Damage table) even if the production system prefers formulas.
3. **Don't keep both three-layer framings in different files.** Pick one. The losing scheme gets a wiki "Historical context" section, not active prompts.
4. **Don't let "multiverse takes priority over divine regardless of tier" survive a redesign.** This is the bug from PR #7883 / issue #7882 (roadmap/2026-06-24). Either document the canonical priority or remove the upgrade entirely.
5. **Don't ship a redesign that is still Faerun/D&D-specific when the user asked for general.** Ao → Prime Mover, Pantheon → Apex Powers, Weave → reality fabric. Setting-specific examples stay only in the canon-attribution section.
6. **Don't disable a tier by deleting the prompt file.** Move it to `$PROJECT_ROOT/prompts/{tier}_disabled/` so the work is recoverable. Wiki sources get `disabled: true` frontmatter so the next agent doesn't re-enable by accident.
7. **Don't skip the 5-minute inventory.** The temptation is "I already know the code, let me just write the fix." That bypasses the user's actual ask ("read all my older campaigns first"). Inventory is the work, not a prelude to it.
8. **Don't `clarify` for next-step scope before delivering Phase 0 receipts.** User said "Status on this and did you truly find and read aizen campaign and all the others I asked?" mid-redesign on 2026-07-20 — the inventory table was the deliverable; the `clarify` came too early.
9. **Don't scatter the disable across multiple files with hardcoded `return False` + commented-out blocks.** This was my PR #8485 v1 anti-pattern. Centralize into `MULTIVERSE_TIER_ENABLED` + a 3-helper registry in `constants.py` (see Phase 3 "PR A disable contract" above). Every call site reads the flag — re-enabling is one boolean flip, not a 5-file refactor. The user will catch this on review and ask you to redo it. Verify locally with the test contract above before pushing.
10. **Don't add god-mechanics Python helpers (`get_v2_god_tier`, `compute_v2_divine_stats`, `v2_reputation_band`, etc.) to `$PROJECT_ROOT/campaign_divine.py` or `$PROJECT_ROOT/constants.py`.** Semantic decisions about god-tier transitions, multipliers, reputation bands, god-class biases, deicide-cost, etc. belong to the **LLM prompt**, NOT to backend routing code. This was the actual review feedback on PR #8488 (`jleechan2015` inline comment r3618945602 on `$PROJECT_ROOT/campaign_divine.py:208`: *"This is wrong and violating /zfc i think. It should just stay as prompt only"*). The pure-function helpers are a feature-creep violation of **Zero-Framework Cognition (ZFC)** + **root-cause-first** principles: encode semantic decisions in the LLM prompt, not in backend code. If you must add backend enforcement later, do it as a narrow, logged invariant after documenting why prompt correction is insufficient. Default: **prompt-only.**
11. **Don't jam mechanics content into the ceremony/upgrade prompt.** The `divine_ascension_ceremony.md` (or equivalent) prompt handles the upgrade moment ONLY. Per-tier mechanics (god-class biases, multipliers, bands, per-dawn menu, combat ladder, roll cap, deicide-cost) live in the per-turn general-mechanics prompt (`divine_leverage_system.md` or equivalent). The user explicitly said: *"I dont think everything should be in the ceremony prompt? There should be a ceremony/ugprade prompt and a general god mechanics prompt?"* (Slack 2026-07-21). Also: before creating a new prompt file like `divine_god_mechanics.md`, **audit the existing `divine/` (or equivalent) folder** — `divine_leverage_system.md` likely already exists as the canonical general-mechanics file. The user said: *"I think there's already another mechanics prompt? what else is in divine/ folder?"* before I realized the redundancy.
12. **Don't break the setting-agnostic contract.** `$PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py` enforces that no D&D entity names (Mystra, Helm, Ao, Bhaal, Netheril, Kelemvor, Bane, Shar, "Forgotten Realms", "Dale Reckoning", "Karsus") leak into the **default text** of any divine prompt. Setting-specific names only belong in the explicit `Setting Adaptation` / `D&D Forgotten Realms Adaptation Appendix` at the bottom of the leverage prompt. V2 overlays must be written with **generic placeholders** ("war deity of the setting's pantheon", "arcane / weave deity", "death / underworld deity") — never with named Faerûn deities, even in column examples. Also: the `SETTING-AGNOSTIC SYSTEM (CRITICAL)` header must remain in the **first 20 lines** of any ascension-ceremony prompt (test `test_setting_agnostic_header_is_prominent`). Run `TESTING_AUTH_BYPASS=true python3 -m pytest $PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py` before pushing. See `references/setting-agnostic-contract.md` for the full diagnostic.
13. **Don't push onto a shared branch without checking who owns it.** The `feat/god-mechanics-v2` branch was being concurrently advanced by `jleechan2015` (PR #8485 merged in via `git fetch origin feat/god-mechanics-v2`). When you go to `git push origin feat/god-mechanics-v2`, the remote may have force-advanced to a SHA you don't have locally. **Correct recovery** (per `SOUL.md` `never-push-onto-someone-elses-pr-head`): `git fetch origin feat/god-mechanics-v2 && git reset --hard FETCH_HEAD && git cherry-pick <your-local-sha>` — never force-push. Then `git push origin feat/god-mechanics-v2` (now fast-forward). Verify with `git rev-parse origin/feat/god-mechanics-v2` returning your new SHA. If the new commit is purely additive (e.g. moving content between two prompt files), cherry-pick is clean; if it touches the same lines the other party edited, expect a manual merge.
14. **Don't skip the green-gate PR body schema.** The Green Gate workflow (`.github/workflows/green-gate.yml`, ~1542 lines) fails with "PR description gate rejected PR body" if the PR description is missing **any** of these section headers (case-sensitive, must be `##` heading level): `## Summary`, `## Production Code Changes`, `## Test Changes`, `## Known Limitations`, `## Unit Test Evidence`, `## Non-Unit Test Evidence`, `## Real LLM Evidence`, `## Evidence`. For a code PR that touches `$PROJECT_ROOT/**.py` outside tests, the gate also requires **non-empty real LLM response payload** in `## Non-Unit Test Evidence` (or `/end2end-testing` response/payload) — the "Real LLM Evidence" carveout only applies to docs-only/config-only PRs. The gate runs on the commit SHA, so a PR body update alone does NOT re-trigger the gate — you must push a new commit (or trigger via `gh workflow run`) to re-evaluate. Use the `wa-green-gate-pr-shape` skill for full diagnostic + fix patterns.
15. **Don't conflate general god-mechanics with Nocturne/Faerûn-specific design.** Per user direction (Slack 2026-07-21): "the chosen PR for world_reference should have EVERYTHING we discussed in this thread for the murder god campaign and all the god mechanics, self-contained." But: keep the $PROJECT_ROOT/prompt overlay **setting-agnostic** (Pitfall 12), and split the `world_reference/` design doc into (a) **general god-mechanics** (system-agnostic, works for any setting — D&D / Cyberpunk / Wuxia / Marvel / Naruto) and (b) **Nocturne / D&D Faerûn-specific** (the protagonist, the Faerûn pantheon integration, the BG3 setting). Two files, one general + one specific. The general file is the source of truth for any future god-mechanics work; the specific file is the campaign module. See `references/general-vs-setting-specific-split.md` for the canonical split pattern.
16. **Don't claim prompt-only mvp_site changes are exempt from /es.** A non-test edit to `$PROJECT_ROOT/agent_prompts.py` (or any `$PROJECT_ROOT/**` file that contributes to the LLM prompt payload) MUST ship with real /es local-server + real-LLM evidence — not a unit-test green run, not a `generate_evidence_bundle.sh` script output, not "the diff is text-only". The AGENTS.md /es carve-out for "pure comments / docs / formatting / type hints / import-order-only" does NOT include prompt-layer changes; a new directive is a behavior change at the model-decision boundary and Green Gate gate 6 will reject a unit-only evidence bundle. Verified 2026-07-23 on the god-mode-generic-mechanics PR (issue #8538, AO session wa-3389): the worker tried to substitute `python -m unittest` after the unit tests passed, the gateway rejected the bundle, and a steering nudge to write a `testing_mcp/test_*_contract_real_api.py` was required mid-run. The diagnostic recipe (when a worker hands you a unit-test-only evidence bundle) and the canonical copy-paste nudge are in `references/es-evidence-protocol-prompt-only-mvp-site.md`. Cross-ref Phase 3 "PR B evidence" subsection above.
17. **Don't dispatch a MiniMax-M3 AO worker without a preflight heartbeat and a 60–90s early-kill window.** Verified pattern from `agento/references/spawn-model-preflight.md` + the 2026-07-20 incident (`C0AH3RY3DK6/1782336926`): Codex usage-limit banner can appear **before the worker's first tool call**, so by the time you notice from the AO session log the worker is already idle / dead. The recipe:
    1. **Preflight before spawn.** Run a low-timeout heartbeat against the planned model (e.g. `agy --print --model <name> --new-project --print-timeout 60s --prompt-interactive "pong"`). Confirm the model returns a real response within 60s before spawning the AO worker. If it hangs or errors → switch to a cheaper tier that DID respond (Codex Spark / Gemini 3.5 Flash High / Claude Haiku); do NOT retry the same model that just timed out.
    2. **60–90s early-kill window.** After `ao spawn`, monitor the worker's first two output blocks. If the worker has produced zero task code (no file edits, no git status change beyond the worktree scaffold) within 60–90s, kill the session (`ao session kill <id>`) and respawn on a different harness. Don't wait — workers that idle on their first command tend to stay idle; the cost of respawning is much lower than babysitting a stuck worker for 30+ minutes.
    3. **Explicit mid-tier in the brief.** When the model is mid-tier (Codex Spark, Gemini 3.5 Flash High, Claude Sonnet/Codex Spark), declare it explicitly in the spawn `--task` text ("Explicit mid-tier: MiniMax-M3" / "Explicit mid-tier: Gemini 3.5 Flash High"). The model-name field on the AO harness defaults to top-tier if left empty, which both violates SOUL.md `subagent model routing (mandatory, 2026-07-14)` and burns budget on a model that may be the one that just timed out.
    4. **Wrap `ao spawn` with `--agent <provider>` for known harness:** for AO sessions targeting the worldarchitect project, prefer `--agent minimax` (MiniMax-M3, mid-tier, the verified mid-tier for prompt-only work) or `--agent antigravity` (Gemini 3.5 Flash High, mid-tier, the verified fallback). Don't use `--agent codex` without a verified Codex usage-limit budget for the day.
    Cross-ref `agento/references/spawn-model-preflight.md` (canonical reference) and `ao-spawn-minimax-worker` skill (the spawn-time mid-tier plumbing). Verified this session: wa-3382 (MiniMax-M3) was killed after 8+ minutes idle on its 3rd preflight command; wa-3384 (Antigravity/Gemini 3.5 Flash) was the working lane; wa-3389 (MiniMax-M3 mid-tier) eventually landed the PR after a steer nudge for /es.
18. **Don't hardcode a single campaign's prompt type/path/directory to `$PROJECT_ROOT/agent_prompts.py` / `$PROJECT_ROOT/constants.py` / `$PROJECT_ROOT/agents.py` / `$PROJECT_ROOT/prompts/<campaign>/`** — except for the Dragon Knight fast-path. Use the `$PROJECT_ROOT/prompts/shared/` + `custom_campaign_state.campaign_overlays` generic gate pattern. See `references/no-campaign-hardcoding-and-shared-prompts.md`. Verified PR #8661 (Spellblade Valeria) — 5 CodeRabbit blockers + user comment 3670171626 ("No I dont want anything hardcoded to a single campaign") all stemmed from this single anti-pattern.
19. **Don't open a new PR or rewrite a contract before running Phase -1 open-PR preflight.** Verified 2026-07-28: user asked "modify the prompts to encourage creation of mysteries in the plot line... either make a new PR or add this so an existing PR that fits." The agent loaded skill inventory first and discovered [PR #8662](https://github.com/$GITHUB_REPOSITORY/pull/8662) (`feat(prompts): generic shared contracts + AI mystery/internal-drive arcs + campaign_overlays loader`, open at the time) already contained `$PROJECT_ROOT/prompts/shared/ai_generated_mystery_and_internal_drive_plot_arc.md` with the 3-suspect mystery template, hidden fact, clue trail, red herring / partial truth / real answer, and personal-cost reveals. The right answer was **amend PR #8662**, not open a new one. Phase -1 surfaces this in one REST call (`gh api 'search/issues?q=...'`) and 30 seconds; skipping it leads to a multi-tool archaeology pass that the user has to wait through. The user's verbatim phrasing is the canonical trigger for this pitfall — when they say "new PR OR existing PR that fits," they want the agent to do that fit-check before responding.

## Related

- `~/.hermes/skills/download-campaign/` — Firestore → disk campaign export. Use for in-Firestore god-tier campaigns.
- `~/.hermes/skills/worldarchitect/wa-campaign-content-analysis/` — in-place campaign analysis with agent attribution. Use for "did the redesign actually land in new scenes?"
- `~/.hermes/skills/finish-the-job/` — push-PR-and-merge discipline.
- `~/.hermes/skills/workflow/always-pr-never-local-edit/` — never just make local edits and stop.
- `~/.hermes/skills/memory-search/` — 9-store fan-out (the inventory phase uses this).
- `references/aizen-god-mechanics-pattern.md` — full quantified-stat-table + 3-layer reconciliation + DPP-overload analysis.
- `references/campaign-tier-inventory-2026-07-20.md` — the canonical inventory from the first session that used this skill.
- `references/pr8485-v2-disable-centralization.md` — full PR #8485 v2 transcript: original 5-file scattered disable → user review feedback → single-switch refactor → 13-test registry contract. Use as the canonical reference when designing ANY feature-disable PR (tier, prompt, capability, prompt-loader entry, etc.).
- `references/es-evidence-protocol-prompt-only-mvp-site.md` — **v0.4.0 evidence protocol.** Why "prompt-only mvp_site change is exempt from /es" is wrong; canonical copy-paste steering nudge for the AO worker; BQ query for verifying the new directive in the request payload; `testing_mcp/test_<mechanic>_contract_real_api.py` skeleton; full verified transcript from issue #8538 (god-mode-generic-mechanics PR) showing the worker's three failed substitutes (unit tests, generate_evidence_bundle.sh, "pure prompt exception") and the steering nudge that unblocked it.
- `references/no-campaign-hardcoding-and-shared-prompts.md` — **v0.5.0 canonical reference.** Full PR #8661 review thread (5 CodeRabbit blockers + user comment 3670171626 + the user's "no campaign hardcoding except Dragon Knight" preference) + the canonical solution shape (6 shared contracts at `$PROJECT_ROOT/prompts/shared/` + the `custom_campaign_state.campaign_overlays` generic gate + the AGENTS.md "no campaign hardcoding" rule). Use this when answering "can I add a new campaign X to `$PROJECT_ROOT/prompts/`?" — the answer is now always: layered as shared/generic + state-keyed overlay, never as a top-level `$PROJECT_ROOT/prompts/<campaign>/` directory. Companion to the v0.5.0 Phase 2.5 (AI-mystery/int-drive architecture) and Pitfall #18.
- `references/ai-mystery-internal-drive-plot-recipe.md` — **v0.5.0 design recipe.** The 3-suspect template (red herring / partial truth / real answer) + the hidden-fact → clue-trail mechanic + the per-act growth/insecurity/reframe requirement + the MBTI internal-only contract reference. Use when the user asks for "mystery-driven campaigns," "internal-drive plot arcs," "character growth arcs that challenge insecurities," or any other phrasing that maps to the Phase 2.5 architecture. Verifies the wiki pages at `~/llm_wiki/wiki/concepts/mbti/*.md` are the AI-background source.
- `references/open-pr-preflight-recipe.md` — **v0.6.0 preflight recipe.** The 4-step REST-call recipe (`git branch -r` + 2× `gh api search/issues` + `git ls-tree`) that runs BEFORE Phase 0 inventory. Catches the most common failure mode: agent proposes a new PR when an existing open PR already covers the ask. Verified 2026-07-28 on the "add mysteries to the plot" user request which mapped verbatim to [PR #8662](https://github.com/$GITHUB_REPOSITORY/pull/8662). Includes the decision matrix (amend existing / add rule to umbrella / push to umbrella-not-campaign-PR / open new) + the PR #8662 case study (1 commit, 13 files, +1473/-16 — the AI mystery + internal-drive + campaign_overlays loader umbrella).

## Tests

- `tests/test_disable_sequence.py` — verify PR A disable actually flips `is_multiverse_upgrade_available()` to False and the prompt loader doesn't load the disabled file.
- `tests/test_disable_registry.py` — NEW v0.2.0 — verify `MULTIVERSE_TIER_ENABLED` + 3-helper registry contract: flag default, `get_upgrade_complete_tiers()` reflects the flag in both states, `is_multiverse_upgrade_available()` returns True under flag-on + triggers-met, `_CAMPAIGN_UPGRADE_COMPLETE_TIERS` mirrors the registry, import-time threshold is the sentinel when flag is False.
- `tests/test_setting_agnostic_remap.py` — verify the new prompt has no Faerun-specific terms in the core rules section (Ao/Pantheon/Weave remapped to Prime Mover / Apex Powers / reality fabric).
- `tests/test_three_layer_canonical.py` — verify only ONE three-layer framing exists across all loaded prompts (production Aizen-style, never both).
- `tests/test_no_campaign_hardcoding.py` — NEW v0.5.0 — verify (a) no `$PROJECT_ROOT/prompts/<campaign>/` subdirectory exists for any campaign name that isn't Dragon Knight, (b) no `PROMPT_TYPE_*_CAMPAIGN` constant in `$PROJECT_ROOT/constants.py` (Dragon Knight's fast-path constants excluded by name), (c) no `$PROJECT_ROOT/prompts/<campaign>/` referenced from `PATH_MAP` keys, (d) the `campaign_overlays` generic gate is exercised by at least one focused test. Companion to PR-A's `test_shared_contracts_and_internal_drive_mysteries.py`.

Run: `cd ~/.hermes/skills/worldarchitect-campaign-tier-redesign && python3 -m unittest discover -s tests`