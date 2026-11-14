---
name: prompt-compaction-safe
description: Compact an LLM prompt (markdown file in `**/prompts/**` or equivalent) by 10-50% without breaking the test-anchored contract that pins its content. Trigger when the user asks to "compact", "shrink", "trim", "shorten", "tighten", or "compress" a prompt file, AND the prompt is guarded by a contract test file (a `test_*setting_agnostic*.py` / `test_*contract*.py` / `test_<prompt_name>*.py` that pins regex anchors, verbatim strings, table rows, section headers, or forbidden-entity lists). Use when the LLM prompt is the runtime contract for an agent (StoryModeAgent, GodModeAgent, etc.) and "smaller" must NOT mean "weaker". For LLM behavior fixes ("AI keeps doing X") use `wa-prompt-editorial-fix` instead. For code compaction / dead-code removal use `simplify-code` instead.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [prompt, compaction, contract-test, regex-anchor, prose-only, worldarchitect, llm-runtime]
    related_skills: [wa-prompt-editorial-fix, worldarchitect-campaign-tier-redesign, simplify-code, test-driven-development, always-pr-never-local-edit, pr-clean-branch-from-main]
    changelog:
      - "1.0.0 (2026-07-24): Initial umbrella. Captures the regex-anchor cataloging pattern, the prose-only discipline, the per-edit test-loop (catch the `250 DPP` → `DPP 250` word-order regression mid-run), and the verified PR #8564 outcome (1305 → 1086 lines, 53/53 contract tests pass, 382/382 agent tests pass)."
---

# Prompt compaction — safe (test-anchored contract preserved)

Shrink an LLM prompt without breaking the test-anchored contract. Two
disciplines that look similar but operate in opposite directions: this skill
**removes words** while keeping every contract anchor verbatim; `wa-prompt-editorial-fix`
**adds words** to correct LLM behavior.

## When to use

Trigger phrases (any one):

- "Compact the [prompt name] prompt — it's getting too long"
- "Shrink / trim / shorten / tighten / compress `$PROJECT_ROOT/prompts/<file>.md`"
- "Can we make this prompt smaller without losing behavior?"
- "The LLM prompt is bloating the context window; trim it"
- "This is 1300 lines, can it be 800?"

Mandatory pre-condition: the prompt must be guarded by a **contract test file** —
a test module that pins part of the prompt's content (regex anchors, verbatim
strings, section headers, table rows, forbidden-entity lists). For your-project.com
divine/sovereign/multiverse tier prompts, that's
`$PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py`. For other repos, look
for `test_<prompt>*contract*.py`, `test_*setting_agnostic*.py`, or any test file
that does `assertIn` / `assertRegex` / `assertNotIn` against strings from the
prompt.

If no contract test exists, the compaction can be more aggressive — but then
this skill's discipline is overkill. Fall through to plain LLM-powered
prose rewriting.

## Anti-triggers (don't use this skill)

- "The AI keeps doing X — fix the prompt" → `wa-prompt-editorial-fix`
- "Remove dead code from `src/foo.py`" → `simplify-code`
- "Rewrite this prompt to be clearer / less ambiguous" → general LLM rewrite, no test-anchor discipline needed
- "We need a smaller prompt for token budget" but the prompt is already
  heavily tested by behavior (real LLM eval harness) without static contract
  tests — then "smaller" should be paired with a behavior eval, not prose rewrites

## The core contract

The test-anchored contract defines what **cannot change**. Everything else
is prose that can be removed or rewritten. The discipline:

1. Every regex anchor in the test file is **untouchable**.
2. Every verbatim string the test asserts `assertIn` is **untouchable**.
3. Every section header the test regex-matches against is **untouchable**
   (header text + nesting level).
4. Every forbidden entity the test asserts `assertNotIn` must **stay out**
   of the default text.
5. Prose between anchors can be removed, condensed, or rewritten freely.
6. Tables that the test pins row-by-row can only have **prose** in non-pinned
   cells removed; the pinned rows stay verbatim.

Word order matters for regex anchors. `"250 DPP"` is regex `(\d+) DPP`; `"DPP 250"`
breaks the anchor. The fix is word-order, not "tighter phrasing".

## Phase 0 — Find the contract test file

If the user said "compact `$PROJECT_ROOT/prompts/divine/divine_leverage_system.md`",
the matching test file is `$PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py`.
Search patterns in priority order:

```bash
# 1. Same repo, similar filename
grep -rln "<prompt_filename>" $PROJECT_ROOT/tests/ --include="*.py" | head -5

# 2. Same repo, *_contract*.py / *_setting_agnostic*.py
grep -rln "<prompt_basename>" $PROJECT_ROOT/tests/ --include="*contract*.py" --include="*setting_agnostic*.py" | head -5

# 3. Same repo, tests importing the prompt path
grep -rln "prompts/<tier>/" $PROJECT_ROOT/tests/ --include="*.py" | head -5

# 4. If none, there may be no contract test — flag to the user, ask before compacting
```

If step 4 returns empty: **stop and ask the user**. Without a contract test, you
have no anchor list, and "smaller" can silently drop a critical mechanical rule
the LLM needs. Either:

- The user accepts the risk and wants pure prose rewriting → proceed without
  contract discipline, but flag clearly.
- The user wants the contract written first → switch to a "first add a contract
  test, then compact" plan.

## Phase 1 — Catalog the anchors

Read the contract test file in full (the test is usually <2000 lines; if longer,
read in 500-line chunks). Build an anchor inventory:

| Category | Count | Examples (from PR #8564) |
|---|---|---|
| Header regexes (`## V3.X` or `## Section Title`) | ~20 | `## V3.13`, `## V3.20` — must appear at correct nesting |
| Verbatim strings (`assertIn`) | ~30 | `"stat_divine(L, F, Repr) = stat_mortal × tier_multiplier(L) + bonus_f(F, L) + bonus_repr(Repr, L)"`, `"(L − 19) × 10 + 100"`, `"DPP does NOT carry across dawns"`, `"APPENDIX_MARKER"` |
| Verbatim table rows | ~10 | `\| DHP \| 138 \| 745 \|`, `\| **Celestial Coup** \| 400 \|`, `\| **Tyrant** \| Smite a heretic \|` |
| Numbered tokens with regex | ~6 | `(\d+) DPP` — the regex eats the digit, then the literal " DPP" |
| Forbidden-entity regex (`assertNotIn` / `assertNotRegex`) | ~25 | `Mystra`, `Helm`, `Oghma`, `Savras`, `Torm`, `Karsus`, `Ao`, `\bDR\b`, `Dale Reckoning`, `Netheril`, `Forgotten Realms`, etc. |
| Section-spanning regexes | ~10 | `r"## V3\.13 [^\n]*\n(.*?)(?=\n## V3\.14|\Z)"` — these anchor a subsection's BODY, so internal reordering inside §V3.13.1 vs §V3.13.2 still has to match the section pattern |

Categorize each anchor by edit-freedom:

- **Hard anchor** — verbatim string or regex literal. Cannot move, rename, reorder, or word-flip.
- **Soft anchor** — section header, table cell, or row. Can move WITHIN its section if the test regex covers the whole section, but the section itself must stay.
- **Forbidden entity** — must NOT appear in the default text (text before the APPENDIX marker, if applicable). Can appear in any appendix after the marker.

Save the inventory to `/tmp/<prompt>_anchor_inventory.md` for reference during the compaction. Re-read it before every prose edit.

## Phase 2 — Identify prose headroom

Walk the prompt section by section. For each section, classify:

- **Section content = anchors only.** No prose headroom. Skip. Example: a lookup table (every row is anchored).
- **Section content = anchors + dense prose.** High headroom. Example: §V3.20 worked examples (kept both examples, required labels, but compressed the narrative).
- **Section content = anchors + redundant prose.** Highest headroom. Example: a paragraph that restates the same rule from two paragraphs earlier.
- **Section content = mostly prose, no anchors.** Free to rewrite or condense.

Compile a "prose-only edit list" before touching the file. Order sections
by headroom size (highest first) so the early passes gain the most line
reduction with the least risk.

## Phase 3 — Compaction rules (the discipline)

### Rule 1 — Prose only

Touch prose, not anchors. Allowed edits:

- ✅ Remove redundant prose paragraphs that restate earlier content.
- ✅ Inline multi-line bullet lists into a single tight paragraph (preserve every list item's content).
- ✅ Collapse "Constraint / Risk / Status / Power" 4-bullet patterns into a single inlined sentence per layer.
- ✅ Drop orphan sentences that drifted from their parent section (e.g. a `**Phase 1: Ascension (21-30)**` sentence orphaned inside the Transcendent Spellcasting section).
- ✅ Compress worked examples by keeping required labels verbatim and removing only the narrative prose between them.

Forbidden edits:

- ❌ Renaming or rewording section headers that the test regex anchors (`## V3.X`, `## Appendix A: D&D Forgotten Realms Adaptation Appendix`).
- ❌ Changing word order on numbered tokens (the `250 DPP` → `DPP 250` regression).
- ❌ Combining two anchored sections into one (the test regex `## V3.13 …(?=## V3.14|\Z)` requires the boundary).
- ❌ Removing a forbidden entity's appendix citation — the appendix marker is itself anchored.
- ❌ Cutting lines that match a forbidden-entity regex (`\bDR\b`, etc.).

### Rule 2 — Cross-file deference

If the prompt you are compacting defers mechanics to another prompt (e.g.
ceremony defers to leverage), the deferred mechanics stay in the OTHER file —
not duplicated in both. Removing the duplication from the deferring file is
safe. Removing the mechanics from the canonical file is NOT safe.

Verify the cross-reference string is preserved: e.g. the ceremony must keep
`"(L − 19) × 10 + 100"` (a required token) but can drop the surrounding prose
paragraph explaining the formula — the reader is expected to load the leverage
prompt for the formula.

### Rule 3 — Tables: prose cells free, anchored rows verbatim

For tables with anchored rows (like the god-class table with `War / Trickster /
Domain / Magic / Death / Skilled` rows), you can:

- ✅ Shorten the "Pantheon fit" cell prose.
- ✅ Shorten the "Example (replace per setting)" cell to one token instead of three slash-separated names.

You cannot:

- ❌ Drop a column that the test scans for.
- ❌ Rename a class that the test anchors (`War`, `Trickster`, etc. — these are
  test-anchored in `test_stat_formula_consistency`).

### Rule 4 — Examples stay labeled

If the test requires each worked example to contain `"F (LLM-only)"` and
`"narrative hint"` (test `test_v320_stat_sheet_labels_hidden_fields`), those
labels are anchors. Compress the example's narrative prose freely; the labels
must remain in the same line positions relative to the section markers.

## Phase 4 — The test loop (mandatory)

After **every** prose edit, re-run the contract test. Not after the whole pass —
after every meaningful edit. This catches regressions immediately.

```bash
# The contract test must run from the right working directory and use the right venv
cd <repo>
python3 -m pytest $PROJECT_ROOT/tests/test_<prompt>_setting_agnostic.py -v 2>&1 | tail -15
```

A regression in this skill is **catastrophic** for trust — the whole point of
the contract test is that compaction can't break behavior. If a regression
appears, revert the last edit (the test will go green again) and write the
edit differently.

### Why per-edit, not per-pass

A single pass can introduce multiple regressions that mask each other. The
`250 DPP` → `DPP 250` regression in PR #8564's first compaction pass only
broke ONE test (`test_v3_legendary_actions_fit_the_max_dawn_budget`) but the
test message said "Expected numeric DPP costs in §V3.13" — without the
per-edit discipline, the next compaction would have piled on top of the
regression and made the diagnosis harder. Catch it the moment it appears.

### Run the broader test surface too

The contract test is one file. The prompt may also be tested by:

- `$PROJECT_ROOT/tests/test_agents.py` (agent-loader tests that check the prompt
  filename appears in the rendered instruction block)
- Any `test_<tier>*.py` that exercises the agent path that loads the prompt
- Any test that pins a string like `assertIn("divine_leverage_system.md", tier_block)`

Run all of these after every pass:

```bash
cd <repo>
python3 -m pytest $PROJECT_ROOT/tests/test_<prompt>*contract*.py \
                $PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py \
                $PROJECT_ROOT/tests/test_agents.py -v 2>&1 | tail -25
```

## Phase 5 — Branch, commit, push, PR

Standard PR hygiene, no shortcuts. From `.cursor/rules/pr-branch-from-main.mdc`
and SOUL.md `push-pr-donot-stop-halfway`:

1. **Branch from `origin/main`.** `git worktree add -b feat/compact-<prompt-name> /tmp/<wt> origin/main`. Verify clean: `git log --oneline origin/main..HEAD` shows only your commits.
2. **Path-scoped commit.** `git add $PROJECT_ROOT/prompts/<tier>/<file>.md` (do NOT `git add -A`).
3. **Commit message with full audit trail.** List what changed, what was preserved verbatim, the test result deltas (before/after pass count), and any regression caught-and-fixed mid-pass.
4. **Push and open PR.** `git push -u origin feat/compact-<prompt-name>` then `gh pr create --base main --head ...`. PR body MUST be honest about: (a) what test-anchored strings were preserved verbatim, (b) which test passes were verified before push, (c) any mid-pass regression that was caught and fixed.
5. **Markdown hyperlink the PR number** in any reply per `.cursor/rules/pr-hyperlink.mdc`.

## Phase 6 — Skillify (only if novel pattern emerged)

Per the `always-skillify-after-non-trivial-work` SOUL.md commitment, after
compaction work that surfaced a new pitfall or technique (e.g. a new regex
class, a new cross-file deferral pattern, a new "this anchor type breaks
under prose rewrites" finding), update THIS skill (or create a reference file
under `references/`) with the verified case. Keep the SKILL.md body tight;
put the verified-case recipe in `references/<pr>-compact-<prompt>.md` and
link from the skill body.

## Pitfalls

### 1. Don't rename section headers (the regex anchor trap)

Test regex `r"## V3\.13 [^\n]*\n(.*?)(?=\n## V3\.14|\Z)"` matches the literal
text `## V3.13` followed by the section's body up to `## V3.14` or end of
file. Renaming `## V3.13` to `## §V3.13 — AT-3 Legendary Actions menu` changes
both the start anchor AND the body boundary. Always preserve the header text
the test pins.

### 2. Don't flip word order on numbered tokens

Regex `(\d+) DPP` matches a digit followed by literal ` DPP`. If you rewrite
`"250 DPP (one-time, AT-3 Legendary Action)"` as `"DPP 250 (one-time, AT-3
Legendary Action)"` to match tighter prose elsewhere, the regex fails. The
catch: the regex captures digits in front, not behind. When you flip word
order to make the prose tighter, the test breaks. Either keep the original
word order or accept the prose ugliness.

### 3. Don't combine two anchored sections into one

Test regex `r"## V3\.13 [^\n]*\n(.*?)(?=\n## V3\.14|\Z)"` requires
`## V3.14` to appear AFTER `## V3.13`. If you delete `## V3.13.1` and
`## V3.13.2` headers and inline their content under `## V3.13`, the section
body extends past `## V3.14` and the regex captures the wrong span. Always
preserve the section hierarchy the test expects.

### 4. Don't drop the forbidden-entity appendix

If the test anchors `# Appendix A: D&D Forgotten Realms Adaptation Appendix`
as the marker that splits "default text" from "appendix content" (the test
calls `default_text = full_text.split(marker, 1)[0]`), then deleting the
appendix is a contract violation. The appendix is the ONLY place forbidden
entities (Mystra, Helm, Ao, Karsus, etc.) are allowed to appear; removing
the appendix makes the test impossible to satisfy.

### 5. Don't claim compaction exempts you from "test before push"

SOUL.md `proof-before-claim` applies. Compacted prose is still a code change.
Run the test, paste the actual pytest output (not "tests pass" — the green
counts), and only then push.

### 6. Don't compact across prompts without cross-checking both test files

If prompt A defers to prompt B (ceremony defers to leverage), compacting A
might remove strings that A's test anchors (`(L − 19) × 10 + 100` in the
ceremony test) while B's test already pins them elsewhere. Run BOTH test
files after every compaction pass.

### 7. Don't compress the "static" prose but miss the duplicate prose

The biggest headroom is usually **duplicate prose** — paragraphs that restate
earlier content (the Setting Adaptation preamble was restated 3× in
PR #8564's pre-state). Find these first. They give the biggest reduction with
the lowest regression risk (you can't break an anchor by deleting prose that
restates an anchor).

### 8. Don't propose "I'll just use an LLM to rewrite the prompt"

That's the failure mode this skill is designed to prevent. An LLM rewrite has
no anchor awareness; it will rewrite verbatim formulas, rename headers, and
add forbidden entities. The discipline here is: the agent reads the test,
catalogs anchors, and does prose-only edits with per-edit test verification.
LLM-assisted rewriting can help draft tighter prose, but every draft must be
verified against the anchor inventory before commit.

## Verified case

PR [#8564](https://github.com/$GITHUB_REPOSITORY/pull/8564)
(`$GITHUB_REPOSITORY`, 2026-07-24):

- **Target:** `$PROJECT_ROOT/prompts/divine/divine_leverage_system.md` (1023 lines,
  64,228 bytes) + `$PROJECT_ROOT/prompts/divine/divine_ascension_ceremony.md`
  (282 lines, 11,764 bytes).
- **Contract test:** `$PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py`
  (1098 lines, 53 tests).
- **Reduction:** 1305 → 1086 lines (-16.8%), 75,992 → 72,325 bytes (-4.8%).
  Per-file: leverage 1023 → 894 (-12.6%), ceremony 282 → 192 (-31.9%).
- **Mid-pass regression caught:** first pass rewrote `"250 DPP (one-time,
  AT-3 Legendary Action)"` as `"DPP 250 (one-time, AT-3 Legendary Action)"`
  in §V3.13.1. `test_v3_legendary_actions_fit_the_max_dawn_budget` failed
  with `[] is not true : Expected numeric DPP costs in §V3.13.` Reverted the
  word-order, test passed. **Saved by per-edit test loop.**
- **Final result:** 53/53 contract tests pass; 7/7 divine-related
  `test_agents.py` tests pass; combined 382 passed + 3 skipped + 0 failed.
- **No forbidden-entity leak.** All forbidden regexes still pass on the
  post-compaction default text.

Recipe (concrete sequence applied):

1. Read the prompt's contract test in full to build the anchor inventory.
2. Walk the prompt section by section, classify each as anchor-only / dense-prose / redundant-prose / free-prose.
3. Apply prose-only edits in order of highest headroom first.
4. After each meaningful edit, run `pytest $PROJECT_ROOT/tests/test_divine_prompts_setting_agnostic.py` and check the count.
5. When test count drops: revert last edit, write it differently, re-run.
6. Once contract test is green, run `pytest $PROJECT_ROOT/tests/test_agents.py` to check the agent-loader tests.
7. Commit, push, open PR with honest PR body documenting the mid-pass
   regression caught + the final test counts.

## Reference

- `references/pr-8564-divine-prompt-compaction.md` — full step-by-step
  transcript with the exact anchor inventory + per-pass test counts +
  the `250 DPP` regression catch.