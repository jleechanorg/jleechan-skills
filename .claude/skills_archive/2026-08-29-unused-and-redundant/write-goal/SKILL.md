---
name: write-goal
version: 1.1.0
description: "Write an outcome-driven goal spec that drives agents toward verifiable outcomes — solid evidence, green-CI PRs, high code quality. Pulls context from the last 30 days of coding-CLI convos (/history) and cross-session memory (/ms) so the goal is grounded in real past failures, not invented acceptance criteria. Output is a .converge/goal.md ready to feed /h (goal_harness) or /a (finish-the-job). Grounded in a 30-day audit of 6,433 Hermes + 18,773 Codex sessions (2026-06-28)."
when_to_use: "Use when the user types /write-goal <topic>, asks to 'write a goal spec for X', 'draft a goal for X', 'design a goal with evidence', or wants a goal doc that will actually drive agents to a green-PR outcome instead of stalling halfway."
tags: [goal, spec, evidence, green-pr, code-quality, outcome-driven, history, memory]
triggers:
  - /write-goal
  - write a goal
  - write a goal spec
  - draft a goal
  - design a goal
  - goal with evidence
  - goal spec for
  - write me a goal
category: workflow
related_skills:
  - finish-the-job
  - drive-pr-to-green
  - always-pr-never-local-edit
  - evidence-standards
  - pr-green-definition
  - session-history-search
  - memory-search
  - ponytail
  - root-cause-first
  - harness
changelog:
  - 1.1.0 (2026-06-28): Actually ran /history + /ms against 6,433 Hermes sessions + 18,773 Codex threads + Claude Code JSONL. Added "Ground truth" section with real pattern counts (Skeptic QA 3,305 threads, Green CI 1,014 threads, /harness only 1 session in 30d). Added Phase 2.5 (/repro for bug-shaped goals). Added audit-grounded goal shapes (verify-completion, meta-goal, design/evaluate). Added 8 design decisions grounded in verbatim user goals from last month. Added mem0 memory findings.
  - 1.0.0 (2026-06-28): Initial skill — mines last 30d of coding-CLI convos + memory, writes a structured outcome-driven goal spec wired for evidence/green-CI/quality. Output compatible with /goal_harness and /finish-the-job.
---

# write-goal

**Write a goal spec that drives agents to verifiable outcomes — solid evidence, green CI PRs, high code quality — grounded in your actual coding history, not invented acceptance criteria.**

## Why this skill exists

Three failure modes that keep recurring in the user's last month of coding-CLI sessions (May 22 → June 28, 2026):

1. **Vague goal → vague outcome.** Goal written as "fix the cold-start bug" produces an investigation summary, not a merged PR. No verifiable end-state is named up front, so the agent ships a write-up and stops.
2. **No evidence contract.** Goal says "make it work" but never says which evidence layer counts. Agent posts a green claim without verifying current-head CI green and no merge conflicts — `gh pr checks` alone can report stale passes or miss merge conflicts.
3. **No project-specific quality bar.** Goal omits the repo's own adversarial gates (ZFC, ZFC-leveling, root-cause-first, /es, /er). The agent thinks lint + unit tests are "done" and the user has to redo the work in a follow-up PR.

**The fix:** mine the last 30 days of coding-CLI convos + memory for the real failure shape and the real success shape on this codebase, then write a goal spec that encodes the specific evidence artifacts, CI gates, and quality checks the agent must produce. The goal becomes a contract the agent can drive itself against — `/h`, `/a`, `/finish` all consume it.

## When to load this skill

- User types `/write-goal <topic>`, or natural-language equivalent ("write a goal spec for X", "draft a goal that …")
- User asks for a goal to be designed with explicit evidence + green-CI + quality requirements
- User wants to take an ambiguous ask ("ship the new campaign wizard step") and turn it into a contract the next agent (or `/h` loop) can execute against

## Pipeline (execute all phases in order; no optional skips)

### Phase 1 — Intake (≤1 turn)

Collect the goal topic and any constraints. If the user gave the topic as `$ARGUMENTS`, use that verbatim. Otherwise ask ONE consolidate question:

> What's the one outcome you want — the verifiable end-state (merged PR URL, verified local behavior, deployed service), not an activity?

**Capture as inputs (write to a scratchpad, not the goal file yet):**
- `topic` — the noun at the center (a feature, a bug class, an infra change)
- `scope` — repo(s) / file(s) / surface(s) in scope
- `outcome_shape` — one of: `green-pr-merged`, `pr-open-green`, `local-state-verified`, `dry-run-on-machine` (these are the four provable end-states from `finish-the-job` — never invent a fifth)
- `hard_constraints` — anything the user named (no API keys in code, ≤N tokens, must keep feature flag X off, etc.)

**If the user typed `/write-goal <topic>` with no constraints at all → make the call yourself per the user's standing rule (finish-the-job § Anti-patterns: "correct but misinterpret is fine"), do not block on Phase 1 questions.**

### Phase 2 — Mine the last 30 days of coding-CLI history (mandatory)

Pull the user's actual coding history so the goal is grounded. Run two parallel searches:

**A. History search (cross-CLI)** — invoke `/history <topic> --recent 30 --limit 20`. Sources it covers (per `~/.claude/skills/history-search/SKILL.md`):
- Claude Code: `~/.claude/projects/*/*.jsonl`
- Codex: `~/.codex/state_5.sqlite` threads
- Hermes: `~/.hermes/state.db` messages (FTS5)

**What to extract from the history results:**
- **Prior attempts on this topic** — what was tried, what failed, what shape the failure took (test red, CI timeout, reviewer CHANGES_REQUESTED, agent stopped halfway, etc.)
- **The real success shape on this codebase** — was "done" last time a merged PR + CI log, a screenshot + `/er` verdict, or a local run output? Capture the exact artifact type.
- **Pitfalls this repo has hit before** — merge conflicts on the same files, flaky tests, quick "looks green" false positives, deny-list patterns from `adoptive-external-agent-convention` if the user has needed it.
- **The specific checks this repo runs** — note any CI workflow names, /es /er /code_standards invocation patterns that appear in past sessions.

**B. Memory search** — invoke `/ms <topic> --recent 30 --source beads --limit 5` (and a second `/ms <topic> --source hermes --limit 5` if beads is sparse). Pull:
- User preferences (e.g. `(h)` no parallel PRs, `(i)` centralize repeated frontend strings as constants, `(j)` thread-roadmap cadence)
- Environment facts (Node 22, gog CLI, Hermes deploy pipeline, launchd plist rules, gh dual-bucket fallback)
- Tool quirks (`gh pr checks` can report stale passes—use `statusCheckRollup` + `mergeable` check for 2-gate `/green`, `.beads/issues.jsonl` is huge—use `br`, etc.)
- Past failures with the same shape — these become the "Pitfalls" section in the goal.

**If both history and memory return nothing** → say so explicitly in the goal doc's "Prior Context" section: "No prior CLI sessions or memory entries matched `<topic>` in the last 30 days. Goal spec written from the user's input only; first run — pitfalls to be discovered during execution."

### Phase 2.5 — Bug-shaped goals: run /repro first (if applicable)

From the 30-day audit: 319 of 6,433 Hermes sessions were test/repro sessions. When the goal is bug-shaped ("X isn't working", "Y is broken", "Z is failing"), add a "/repro step before Phase 3:

- Load the `repro` skill (or `repro-twin-clone-evidence` skill for your-project.com)
- Reproduce the bug FIRST — get the actual error/failure output — Before writing the goal doc
- Put the repro output into the "Prior context" section of the goal

**Skip this for:** design goals, green-PR goals on existing branches, feature implementation goals, infra goals. Only bug-shaped goals need repro first.

### Phase 3 — Select the outcome contract (one decision)

Pick the ONE end-state the agent must provably reach, drawing on Phase 2's history:

**Additional goal shapes from the audit** (map to the existing 4 states):
- *"Did X merge?"* / *"Is X finished?"* → `local-state-verified` (verify with `gh pr view` / `git log`, not a new PR)
- *"Design/evaluate a plan for X"* → `dry-run-on-machine` (the design doc IS the artifact; the user will execute if they approve)
- *"Fix the harness/skill behavior"* → `green-pr-merged` if a code fix is needed, `local-state-verified` if only a config/skill file changed
- *"Why aren't these PRs green?"* → `pr-open-green` (drive the existing PR to green, not a new PR)

| Outcome shape | When to pick | Required proof artifact |
|---|---|---|
| **green-pr-merged** | Default for code changes that touch production paths | `gh pr view <N> --json state` = `MERGED` (verified at current-head SHA with CI green + no merge conflicts; `/er` verdicts are advisory) + Layer-2 evidence (env-preferences rule: unit-only is INSUFFICIENT for production changes) |
| **pr-open-green** | When the user must do the merge (e.g. protected branch, auth gate) | `gh pr view <N> --json statusCheckRollup,mergeable` shows `mergeable == MERGEABLE` + success-only, null-safe current-head `statusCheckRollup[]` (0 non-success checks excluding exact advisory `Green Gate` and `Cursor Bugbot`; reviewDecision, mergeStateStatus advisory only) + one-line blocker the user must clear |
| **local-state-verified** | For non-PR changes (config, ops, infra) | `git diff --stat` + `git log --oneline -3` + actual command output captured in the final reply (described = fail; shown = pass) |
| **dry-run-on-machine** | For risky migrations / destructive changes the user will execute | Exact pasteable commands run against a fresh worktree, output captured, user can paste and get the same result |

**Never invent a fifth outcome shape.** finish-the-job's contract has four; this skill stays inside that.

### Phase 4 — Write the goal spec (the deliverable)

Write the goal to `.converge/goal.md` in the session's cwd (the path `/goal_harness` reads). Use the template at `templates/goal-spec.md` — copy it and fill in every field. **All fields are mandatory; `<TBD>` is a fail.** The template contents:

```markdown
# Goal: <topic>

## Outcome (verifiable, single end-state)
<ONE of: green-pr-merged | pr-open-green | local-state-verified | dry-run-on-machine>

### Proof artifact
<exact artifact the agent must produce at completion — e.g. "PR #N on $GITHUB_REPOSITORY merged with current-head CI green + no merge conflicts, /er PASS verdict (advisory), screenshot of /campaigns/new after merge">

## Scope
- Repo(s): <owner/repo>
- Files / surfaces: <paths or feature areas>
- Out of scope: <what the agent must NOT touch — protects against scope creep>

## Hard constraints (non-negotiable)
- <each constraint the user named or that's encoded in memory — e.g. "no parallel PRs; push onto existing PR's head branch if one exists", "centralize new strings in frontend_constants.ts", "no ANTHROPIC_API_KEY in ai_universe backend", "use nvm Node 22, never Homebrew node">

## Evidence required
- Layer: **Layer 2 integration minimum** (env-preferences rule — unit-only is INSUFFICIENT for production changes; <100 delta lines of non-test code is the only unit-only exception)
- Artifacts:
  - <e.g. "real callstack log showing the fix path is hit, mock only at external API boundaries">
  - <e.g. "browser screenshot of the user-facing surface after deploy">
  - <e.g. "/er verdict URL from evidence review">
- Forbidden:
  - Bullet list of command names only (proof-before-claim rule)
  - "Key output observed: dependency install completed" (fabrication pattern)
  - Green claim without verifying current-head CI green and no merge conflicts (env-preferences rule)
  - `<60s` completion claim on a multi-step I/O task (proof-before-claim)

## Green-CI definition (specific to this repo)
- Canonical /green 2-gate definition (current-head SHA):
  - Gate 1: CI green — every CI check at HEAD passes (`statusCheckRollup` 0 non-success checks, excluding advisory `Green Gate` and `Cursor Bugbot` only)
  - Gate 2: No merge conflicts — `mergeable == MERGEABLE`
- Green Gate workflow logs are advisory only and are not aggregate `/green` proof.
- CodeRabbit/Bugbot and review feedback remain optional advisory checks and do not block `/green`.
- Failure on CI or merge conflicts = iterate the fix, push to PR head branch (pr-ci-fix-autopush rule: push without being asked), re-check. Do NOT report "fixed" until the new head SHA shows both gates PASS.

## Quality bar (adversarial gates this repo uses)
Run all of these at completion (from /goal_harness):
- **/es** — Evidence Standards (both ~/.claude/skills/evidence-standards/SKILL.md AND .claude/skills/evidence-standards.md if the repo has one)
- **/er** — Evidence Review (adversarial, independent reviewer)
- **/code_standards** — 3 parallel lanes:
  - ZFC (zero-framework cognition) — no keyword routing, no regex intent detection, no hand-tuned scoring
  - ZFC-leveling — no level-up fields leaking into non-leveled surfaces
  - root-cause-first — prompt/schema fixes tried before backend protection; document why if backend enforcement is added
- **Independent Agent Review** — full-diff code review by an isolated subagent
- 4/4 PASS = DONE. Any FAIL = fix & loop. Same score 2 iterations = STALLED → escalate to human.

## Dispatch routing
- Inline if: single tool call OR tight sequence with no fork, <10 lines changed
- AO worker (`ao spawn` via dispatch-task) if: multi-step code work, PR creation, worktree isolation needed, CI iteration loop
- `/h` (goal_harness) if: user wants the full 4-gate adversarial loop to wave the goal in
- `/a` (finish-the-job) if: user wants hands-off single-task drive to the end-state
- Do NOT self-execute anything that crosses the write/PR threshold inline (SOUL.md scope-pivot-to-ao commit)

## Definition of Done
At the end, the agent's final reply MUST contain (finish-the-job Phase 4):
1. End-state declaration: "✅ Done: <green PR #N merged> | <PR #N open + green, awaiting your review> | <local state X verified> | <dry-run output captured>"
2. Proof artifact: PR URL as markdown hyperlink `[#<N>](https://github.com/<owner>/<repo>/pull/<N>)` — never bare `#N` (pr-hyperlink rule)
3. Mid-stream judgment calls: every decision the agent made instead of asking, with one-line rationale
4. NO follow-up question — "want me to X?" is a violation

## Pitfalls (mined from history — Phase 2)
- <pitfall 1 — e.g. "PR mergeability flipped to CONFLICTING after main branch updated — re-verify mergeable status at current HEAD">
- <pitfall 2 — e.g. "merge conflicts on world_logic.py recur because it's a 421KB file — always pull --rebase before push">
- <pitfall 3 — e.g. "Quick `looks green` false positive — must verify current-head statusCheckRollup, not `gh pr checks` conclusion">
- <pitfall 4 — e.g. "Unit tests pass but Layer 2 integration fails — env-preferences says unit-only is INSUFFICIENT for production changes">

## Prior context (Phase 2 output summary)
- History searches: <count> sessions matched "<topic>" in last 30 days
- Memory searches: <count> matching entries (beads + hermes)
- Key findings:
  - <finding 1 — e.g. "PR #7832 hit the same file in May 23 session; same fix shape applies">
  - <finding 2>
- If no prior context: state explicitly "No prior CLI sessions or memory matched; first run on this topic."

## Hand-off
- Goal file written to: `.converge/goal.md` (this file)
- To execute: `/h` (run /goal_harness against this goal) — or `/a` for hands-off single-task drive — or `ao spawn` via dispatch-task for raw worker dispatch
- This goal spec is consumable by finish-the-job, goal_harness, and dark-factory — all three read `.converge/goal.md`
```

### Phase 5 — Quality scaffold the spec (mandatory self-check)

Before declaring the goal written, run these gates on your own draft:

1. **Outcome verifiability** — is the "Outcome" line ONE of the four named end-states, with a concrete artifact? If it says "improve" / "address" / "investigate" / "explore" — rewrite it. Those are activities, not outcomes.
2. **Evidence specificity** — does "Evidence required" name the actual artifact (file:line, PR URL, screenshot path, log excerpt), not a category ("tests", "logs")?
3. **Green-CI grounded** — does "Green-CI definition" list this repo's actual workflow names from Phase 2? If Phase 2 found none, write "first run — gates to be enumerated from `gh run list --workflow` on first execution" instead of inventing gate names.
4. **Pitfalls sourced** — does every "Pitfalls" entry cite a real Phase 2 finding (date, session id, or memory key)? Invented pitfalls are fabrication — strike them.
5. **Definition of Done includes the no-follow-up rule** — verbatim: "NO follow-up question" appears in the DoD section.
6. **Dispatch routing references the real commits** — does it cite `scope-pivot-to-ao` / `pr-green-dispatch` so a worker reading the goal knows when to escalate inline→AO?

**If any gate fails → rewrite the goal section in question. Do not post a half-spec.**

### Phase 6 — Hand off (final reply)

Post a single reply containing:

1. **Goal spec path** — `~/.converge/goal.md` (or repo-local `.converge/goal.md`) as an absolute path with `file://` scheme (env-preferences rule)
2. **One-line outcome summary** — what the agent drives toward
3. **Provenance** — how many history + memory entries fed the spec, dated
4. **Hand-off command** — one of:
   - `/h` — to run the full adversarial 4-gate loop (`/goal_harness`)
   - `/a <topic>` — hands-off single-task drive (`finish-the-job`)
   - `ao spawn --task "$(cat .converge/goal.md)"` — raw worker dispatch
   - `gh issue create --title "<topic>" --body-file .converge/goal.md` — issue-track the goal for babysitting
5. **What was decided mid-stream** — any judgment call you made (which outcome shape, which gates to include, which pitfalls to surface)
6. **NO follow-up question** — finish-the-job's final-reply contract applies here too

## Pitfalls (do NOT do these)

- ❌ **Inventing acceptance criteria** — gates, workflow names, pitfall shape that don't appear in Phase 2 history are fabrication. If Phase 2 returned nothing for a field, write "first run — to be discovered during execution" rather than guessing.
- ❌ **Activity-shaped outcomes** — "improve cold start", "investigate the BQ gap", "address reviewer feedback" are activities. Rewrite as "PR #N merged with cold-start p50 < Xs measured by <probe> / CI green + no merge conflicts / /er PASS (advisory)".
- ❌ **Unit-only evidence for production changes** — env-preferences: unit-only is INSUFFICIENT for production changes (Layer 2 integration minimum). Only the <100 delta lines of non-test code exception applies.
- ❌ **`gh pr checks` as green proof** — env-preferences: `gh pr checks` can report stale passes; must verify current-head `statusCheckRollup` (CI green) and `mergeable == MERGEABLE` (no conflicts).
- ❌ **Goal with no dispatch routing** — without an inline-vs-AO rule, a future agent will self-execute a 30-commit PR inline and drop it when the gateway session caps. Cite `scope-pivot-to-ao`.
- ❌ **Goal with no "no follow-up question" in DoD** — finish-the-job's contract requires the agent drive to conclusion. A goal that allows "want me to X?" mid-stream reproduces the silent-stop pattern.
- ❌ **Skipping Phase 2 mining** — without history+memory grounding the goal is generic; the third failure mode (vague goal → vague outcome) recurs. **Specific failure mode (2026-06-28):** substituting `session_search` (a different tool that searches message summaries) for actual `/history` queries against the SQLite databases. `session_search` does NOT query `state.db` or `state_5.sqlite` — it has different scope and returns different results. Phase 2 MUST use `session-history-search` to query the actual session stores with the SQL patterns documented in that skill.
- ❌ **Writing project-specific workflow names into the skill itself** — the SKILL.md stays general; the workflow names live in the generated `.converge/goal.md`. The skill is reusable across repos.
- ❌ **Bare `#N` PR references** — pr-hyperlink rule: every PR number in the goal doc itself and in the final reply must be a markdown hyperlink.

## Verification (the skill works when…)

- ✅ Generated `.converge/goal.md` has all template fields filled (no `<TBD>`)
- ✅ Outcome line is one of the four named end-states with a concrete proof artifact
- ✅ At least one Pitfalls entry cites a real Phase 2 finding (session id, date, or memory key)
- ✅ Green-CI definition either lists real workflow names from history OR explicitly says "first run"
- ✅ DoD section contains "NO follow-up question" verbatim
- ✅ Final reply paths use the `file://` absolute-path scheme for the goal doc
- ✅ A future session invoking `/h` or `/a` against the goal produces a green-PR-merged (or other end-state) outcome without needing a mid-stream clarifying question

## Related skills — load order when this fires

1. `session-history-search` (Phase 2A — `/history` invocation)
2. `memory-search` (Phase 2B — `/ms` invocation)
3. `finish-the-job` (the end-state contract the goal spec plugs into)
4. `drive-pr-to-green` (Phase 3 green-pr-merged outcome shape)
5. `evidence-standards` (Phase 4 evidence-requirements section — load to know what counts as evidence)
6. `pr-green-definition` (Phase 4 green-CI section — canonical 2-gate PR green definition: CI green + no merge conflicts)
7. `ponytail` (Phase 4 quality bar — referenced by /code_standards)
8. `root-cause-first` (Phase 4 quality bar — referenced by /code_standards)
9. `harness` (Phase 6 hand-off — if user picks `/h`)

## Ground truth — 30-day history audit (2026-06-28)

Ran `/history` + `/ms` against all three session stores on 2026-06-28 before designing this skill. **These are the real findings that shaped the skill design.**

### Data volume mined

| Source | Sessions (30d) | Coding-related |
|---|---|---|
| Hermes (`state.db`) | 6,433 | 1,036 (title-match coding terms) |
| Codex (`state_5.sqlite`) | ~3,500+ (150-240/day) | 18,773 total threads |
| Claude Code (`~/.claude/projects/`) | 20+ (JSONL files) | All coding |

### Pattern frequency (actual counts)

**Hermes sessions by title keyword:**
- Slack/infra/testing: 717 sessions (ack plugins, delivery verification, E2E monitors)
- PR/green/merge: 402 sessions
- Test/repro: 319 sessions
- Fix/bug: 122 sessions
- Skill/skillify: 36 sessions
- Level-up/ZFC: 24 sessions
- Deploy/CI: 17 sessions
- Evidence/review: 14 sessions
- Harness/goal: **1 session** (underused — this skill exists to fix that)

**Codex threads by first-user-message pattern:**
- Skeptic QA Agent (adversarial review): **3,305 threads** — dominant pattern
- Green CI verification: **1,014 threads**
- ZFC audit: 147 threads
- Evidence review (`/er`): 89 threads
- Fix-gate iterations: 11 threads
- Read-only live review: 6 threads
- Cold plan review: 7 threads

### Real user goals from the last month (verbatim from session first-messages)

These are the actual goal-shaped messages Jeffrey sent (filtered from cron/test/ping noise):

1. *"Make or find the PR where we make all local servers default to agy cli"* — outcome: PR found/created, verified merged
2. *"did this PR truly merge and is agy_provider.py on origin main?"* — verification goal, needs proof not activity
3. *"fullrun lets confirm agy cli is the default cli"* — autonomous drive request
4. *"Why arent these PRs /green?"* — frustration with CI blocking, needs 2-gate green fix
5. *"Run /repro — other people in the battle aren't taking their turns"* — bug repro + fix
6. *"Lets design/evaluate a plan to convert game state json into a game state ledger"* — design/evaluate goal, not a PR
7. *"Review this evidence using /er and /advice — how do we increase parallelism?"* — evidence review + meta question
8. *"Look at the test and CI failures and merge conflicts across all PRs last 48 hours"* — triage/babysit goal
9. *"cleanup merge conflicts and /green the PR"* — drive-to-green goal
10. *"Dont do the task do the meta task. Lets read this thread and see why hermes misunderstood /green and run /harness"* — meta-goal: fix the harness behavior, not just the bug
11. *"Is this finished? Lets do 1-4"* — verification + drive forward

### Memory findings (mem0 search)

- `"Can drive agents toward outcomes with solid evidence, and values high code quality and green CI PRs"` (score 0.82)
- `"Can identify anti-patterns in agent behavior"` (score 0.71)
- `"Likes designing and evaluating plans"` (score 0.65)
- `"Can make drive decisions autonomously"` (score 0.66)
- `"Prefers to present options and let the user respond"` — BUT finish-the-job overrides this for execution

### Design decisions grounded in the audit

1. **Goal shapes must include "verify completion"** — goal #2 ("did this PR merge?") and #11 ("Is this finished?") are verification goals, not code goals. The existing 4-state contract handles this via `local-state-verified` but the skill should explicitly call it out.

2. **Meta-goals are real** — goal #10 ("Dont do the task do the meta task") is a harness-fix, not a code-fix. The skill must handle meta-goal shapes (fix the harness/skill/agent behavior, not the code).

3. **Evidence review is the dominant adversarial pattern** (3,305 Codex threads). The skill must wire evidence deeply — not just "run tests" but route to the actual Skeptic QA Agent + /er pipeline the user already uses.

4. **Green verification is a top-3 activity** (1,014 Codex threads). The skill must encode the canonical 2-gate green procedure (current-head CI green via `statusCheckRollup` + no merge conflicts via `mergeable`, with review feedback treated as advisory).

5. **/harness is severely underused** (1 session in 30 days). This skill should make it easy to produce goal specs that feed `/h`, increasing harness adoption.

6. **Repro/testing patterns are common** (319 sessions). The skill should know when a goal needs `/repro` as a Phase-1 step (bug-shaped goals, not feature-shaped).

7. **Design/evaluate goals are valid** — goal #6 ("design/evaluate a plan") doesn't produce a PR. The skill must support `dry-run-on-machine` as a valid outcome for architecture/design goals.

8. **The user's actual phrasing is casual and outcome-oriented** — not formal ("fix the thing", "did this merge?", "why aren't these green"). The skill must accept informal phrasing and translate to the structured contract.

## Worked example — 2026-06-28 (this session)

User invoked `/write-goal` after a month of recurring CI/deploy issues that never shipped.

- **Phase 1 intake:** topic = "fix the auto-deploy precompute OOM", outcome_shape = `green-pr-merged`, scope = `$GITHUB_REPOSITORY` (embed pipeline), hard_constraints = "no parallel PRs; if PR #7880 is open, push onto its head branch".
- **Phase 2 mining:** `/history "precompute OOM"` returned 3 Slack sessions + 1 CLI session; `/ms "embed batch size"` surfaced the recipe doc at `~/.hermes/skills/worldarchitect/references/auto-deploy-dev-precompute-oom-investigation.md` and `~/.hermes/skills/devops/production-vs-main-drift/references/precompute-oom-deploy-workflow-2026-06-23.md`. Findings: prior sessions diagnosed + wrote a fix recipe but never pushed to main; deploy has been failing 80+ days.
- **Phase 3:** outcome_shape = `green-pr-merged` (the recipe is a destructive change to `_embed_texts`; user wants it on main, not a worktree dry-run).
- **Phase 4:** goal doc names the exact EMBED_BATCH_SIZE change, the deploy.sh exit-137 detection, the current-head CI requirements, and the prior-failure pitfalls (recipe written twice, never pushed).
- **Phase 5:** quality scaffold passes — outcome is verifiable, evidence is Layer 2 (real callstack on embed path), gates named from history, pitfalls cite session ids.
- **Phase 6:** reply posts `file://.../.converge/goal.md` + hands off `/h precompute OOM fix` or `ao spawn --task "$(cat .converge/goal.md)"`.

The goal became the input for the `/harness` (or `/a`) loop that finally drove the fix to a merged PR — closing the 80-day failure the user identified in SOUL.md `COMMIT: diagnosis-with-fix-not-shipped`.
