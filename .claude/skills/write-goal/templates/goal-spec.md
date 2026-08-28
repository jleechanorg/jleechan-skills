# Goal: <TOPIC>

## Outcome (verifiable, single end-state)
<ONE of: green-pr-merged | pr-open-green | local-state-verified | dry-run-on-machine>

### Proof artifact
<exact artifact the agent must produce at completion — e.g. "PR #N on $GITHUB_REPOSITORY, Green Gate workflow log showing 7/7 gates PASS, /er PASS verdict, screenshot of /campaigns/new after merge">

## Scope
- Repo(s): <owner/repo>
- Files / surfaces: <paths or feature areas>
- Out of scope: <what the agent must NOT touch — protects against scope creep>

## Hard constraints (non-negotiable)
- <constraint 1 — e.g. "no parallel PRs; push onto existing PR's head branch if one exists">
- <constraint 2 — e.g. "centralize new strings in frontend_constants.ts">
- <constraint 3 — e.g. "no ANTHROPIC_API_KEY in ai_universe backend">
- <constraint 4 — e.g. "use nvm Node 22, never Homebrew node">

## Evidence required
- Layer: **Layer 2 integration minimum** (env-preferences rule — unit-only is INSUFFICIENT for production changes; <100 delta lines of non-test code is the only unit-only exception)
- Artifacts:
  - <e.g. "real callstack log showing the fix path is hit, mock only at external API boundaries">
  - <e.g. "browser screenshot of the user-facing surface after deploy">
  - <e.g. "/er verdict URL from skeptic gate">
- Forbidden:
  - Bullet list of command names only (proof-before-claim rule)
  - "Key output observed: dependency install completed" (fabrication pattern)
  - Green Gate exit-0 claim without independent current-head CI and mergeability proof
  - `<60s` completion claim on a multi-step I/O task (proof-before-claim)

## Green-CI definition (specific to this repo)
- Required workflows (gate names from `gh run list --workflow`):
  - <workflow 1> — PASS
  - <workflow 2> — PASS
  - ...
- Green Gate exit-0 is NOT sufficient — verify current-head CI conclusions and mergeability using the canonical `/green` skill
- Draft readiness follows the canonical `draft-first-pr` skill before the PR is marked ready
- Failure on a gate = iterate the fix, push to PR head branch (pr-ci-fix-autopush rule: push without being asked), re-check. Do NOT report "fixed" until the new head SHA shows the gate green.

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
4. **NO follow-up question** — "want me to X?" is a violation

## Pitfalls (mined from history — Phase 2)
- <pitfall 1 — cite real session/date/memory key>
- <pitfall 2>
- <pitfall 3>
- <pitfall 4 — e.g. "Unit tests pass but Layer 2 integration fails — env-preferences says unit-only is INSUFFICIENT for production changes">

## Prior context (Phase 2 output summary)
- History searches: <count> sessions matched "<topic>" in last 30 days
- Memory searches: <count> matching entries (beads + hermes)
- Key findings:
  - <finding 1>
  - <finding 2>
- If no prior context: state explicitly "No prior CLI sessions or memory matched; first run on this topic."

## Hand-off
- Goal file written to: `.converge/goal.md` (this file)
- To execute: `/h` (run /goal_harness against this goal) — or `/a` for hands-off single-task drive — or `ao spawn` via dispatch-task for raw worker dispatch
- This goal spec is consumable by finish-the-job, goal_harness, and dark-factory — all three read `.converge/goal.md`
