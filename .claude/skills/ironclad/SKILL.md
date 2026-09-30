---
name: ironclad
description: Use when the user invokes /ironclad, asks for ironclad exit criteria, sets a sparse goal that needs hardening before autonomous work, or writes a bead contract that a weaker coding model (Haiku 4.5, Gemini 3.8 Flash, GPT Luna) must execute unaided.
---

# Ironclad exit criteria — harden, set, execute

**Provenance of the standard** (mined via /ms + /history, week of 2026-07-05..12):
- User, 2026-07-12 (session 40c1f666): *"whenever i do /goal i want the llm to brainstorm some ironclad exit criteria **better than what i asked for** and then run it"* → became the `~/.claude/hooks/goal-exit-criteria.sh` UserPromptSubmit hook (criteria count per Scope and process ceiling below; the literal condition is the floor).
- User, 2026-07-10 (worldai-2d /goal): *"make ironclad exit criteria and **iterate until the game truly working**"* → ironclad implies an iterate-until-verified loop, not a one-shot checklist.
- Exit-criteria charter (dark-factory `cutover-exit-criteria.md`, R1–R6 + X1–X10; adopted by the spec-design-docs skill): binary, executable, externally anchored; implementer-authored artifacts are corroborating, never sufficient; the verifier **reproduces** rather than inspects; satisfied-via-mock/dry-run = FAIL; default verdict is FAIL.
- Live validation (DK2D mission, 2026-07-12): iterate-until blocked premature closure, and independent verification caught a stale-bundle over-claim.

## Scope and process ceiling

Ironclad strengthens proof that the requested outcome works; it does not broaden the requested product scope. "Stronger than asked" means closing concrete loopholes in verification and failure containment, not adding features, redesigns, deliverables, or process artifacts. Every criterion must trace directly to the stated goal or a demonstrated failure mode.

**Criteria count rule (the only one; every other skill and hook defers here):** use three criteria by default; four or five only for distinct material risks; six or seven only when the user asks or the task is high stakes; never more than seven. Rationale: instruction-following degrades with inter-instruction conflict, not position (arXiv:2510.14842). Use one criteria-setting pass and one independent verification pass. When a check fails, fix that failure and rerun the affected checks; do not restart full planning or review. Follow `~/.claude/CLAUDE.md` § Push safety: never hold more than 30 minutes of uncommitted work.

Reuse the active tracker and goal state. Create a new bead, roadmap file, STATE entry, or memory pointer only when the task actually spans sessions, the active workflow requires it, or the user requests it. Tracking is never completion evidence.

## What "ironclad" means (all six required per criterion)

1. **Stronger proof, same scope** — the user's literal condition is the floor for evidence. Close concrete loopholes in satisfying the intended outcome without adding features, deliverables, surfaces, gates, or evidence classes. Record a materially broader idea as an optional follow-up; never promote it into an exit criterion.
2. **Binary** — pass/fail, no "mostly"/"improved"/"should".
3. **Executable** — a stated command or observable check anyone can run verbatim (quote it in the criterion).
4. **Externally anchored** — verified at the layer users experience (real system-of-record: merged PR state, live HTTP response, on-camera DOM, CI conclusion at head SHA) — never implementer logs/telemetry alone.
5. **Anti-gaming** — self-report insufficient; independent reproduction required (different agent/model than the author — adversarial verifier, cross-model review, or the human). The verifier **re-executes** the check against current HEAD; it never parses output the author pasted, because pasted output can be fabricated or stale-but-real. Write criteria as `independent re-execution of <cmd> at HEAD <sha> returns 0`, never `agent reports <cmd> passed` — a prose report of "verifier exited 0" satisfies nothing. Mock/dry-run/dev-mode satisfaction = FAIL. Serving-context matters (dev server ≠ vite preview ≠ backend-served SPA — the wc-1nli/wc-vs19 lesson: validate the SAME bundle/context the claim is about, and prove bundle identity by content hash).
6. **Iterate-until, capped** — the goal stays open until all criteria hold at the same HEAD/state, subject to the termination cap below. Iterate on failing behavior and its checks, not on plans, specs, or unrelated surfaces. A regression reopens the criterion but does not reset the cap.

## Derived, not asserted (binds every agent, including the orchestrator)

Measured 2026-09-06 across one mission (`~/roadmap/STATE-pr9739-honest-evidence-2026-09-06.md`): the orchestrator (Opus) produced 5 wrong claims of this class, Sonnet lanes 1–2, Gemini flash 2. The class is model-agnostic and the agent writing the contract is not exempt from it. These rules govern *how* a claim is made, not how many claims a task needs — criteria count still follows Proportionality below. Every count, SHA, path, ID, and state named in a criterion or a completion report is **derived at the moment of claiming**, never recalled from an earlier step, a prior report, or a lossy tool summary.

- **Verify against a committed SHA, never an intermediate tree.** Editor diagnostics and a dirty worktree reflect whatever is open, not what was committed. Confirm a defect exists at `git show <sha>:<path>` before reporting it.
- **Never cite the `gh pr checks` summary.** It prints only `Passed: N / Failed: 0` and structurally omits SKIPPED and NEUTRAL, so `N/N PASS` is a natural misreading. Use `gh pr view --json statusCheckRollup` grouped by `(.conclusion // .state)` and report every bucket. Skipped is not passed. Neutral is not passed.
- **Never count or eyeball git output for emptiness in this harness** — two distinct traps, verified with `od -c` on 2026-09-06. (a) A clean `git status --porcelain` renders as the literal string `ok` with no newline; do not read `ok` as a change. (b) `git log A..B` with zero commits emits a lone `\n`, so `| wc -l` returns 1, not 0. Compare refs (`git rev-parse A` vs `git rev-parse B`) or use `git diff --name-only` / `git diff --cached --name-only` / `git ls-files --others --exclude-standard`.
- **Fetch back and diff after publishing.** A source artifact keeps changing after you copy it; the published copy drifts. After any gist/PR-body/bundle publish, fetch the published copy and diff it against the source before claiming it is current.
- **Stale is a failure, not a rounding error.** A number restated from an earlier run is wrong in both directions — today's cases included `14` when 24 existed, not only inflations. If you did not run it in this session against this HEAD, you may not state its result.
- **Prefer the tool fix over the verifier.** When a claim was wrong because a tool's summary hid data, the durable fix is the instruction naming the tool trap, not another checker. The verifier is the backstop for when the instruction is ignored.
- **Backstop:** `python3 ~/.claude/skills/ironclad/scripts/verify_pr_claims.py --pr <N>` (run from inside any repo checkout; read-only against `gh` and `git fetch`) re-derives every test-count, CI-rollup, review-thread, SHA, and path claim in a PR body from live sources and exits 1 on any mismatch or unverifiable claim. It must be run by a party other than the body's author. It caught the orchestrator's own stale `7 tests` (actual 9) the day it was written.

## Plan review gate

Before implementing any nontrivial plan, obtain an independent plan review. `/advice` approval is mandatory by default. Bind the plan-review artifact to the plan content hash, scope, assumptions, exit criteria, verified executable checks, and the actual reviewer transcript and verdict. Run or probe each proposed check against the real target before writing it as an executable criterion; resolve its required inputs, flags, and expected failure semantics. Use read-only, help, or preflight probes when executing the criterion would mutate gated state; preserve existing action authorization. A material plan edit invalidates the affected approval; wording-only edits do not require another full review. For high-risk plans involving progression, XP, state persistence, security, deployment, or a disputed root cause, attempt canonical `/web-advice` as well; `/wa` is user shorthand for `/web-advice` only when that alias is installed, and its approval is mandatory only when the user explicitly requires it. If a mandatory reviewer is unavailable, the verdict is WITHHELD and dependent implementation halts; continue safe independent preparation. Browser unavailability is never approval. Optional high-risk `/web-advice` unavailability may proceed with approved `/advice` and a stated risk and limit.

One planning pass and one independent verification pass do not waive mandatory plan review. Plan approval does not satisfy runtime evidence, code-review, deployment, or merge gates. Expensive final evidence remains last, after implementation and blocker triage; it does not postpone plan review until after implementation. Drafting the plan and review packet is preparation; this gate does not recursively gate its own preparation.

For this gate, a nontrivial plan means a runtime, state, security, deployment, or contract change; multiple coordinated steps or files; or a material decision. An isolated low-risk wording or heading correction with no contract behavior change is a trivial direct edit. The model judges materiality; do not encode this decision as application heuristics.

## Procedure

1. Restate the literal goal in one line.
2. Define criteria per the count rule in Scope and process ceiling. State them as a numbered table: criterion | check command | external anchor | independent verifier.
3. For a nontrivial plan, complete the independent plan review gate above before implementation or autonomous execution. A low-risk trivial direct edit may proceed without this gate. Record the plan content hash, scope, assumptions, exit criteria, verified executable checks, reviewer transcript, and verdict; stop dependent implementation on a mandatory WITHHELD verdict.
4. **Set durably when needed**: update the existing goal bead or tracker first. For work that spans sessions, create a goal bead and set Claude Code's builtin `/goal`; keep the builtin condition short. Inside cmux, the model can set it with `cmux identify`, then `cmux send --surface <ref> '/goal <condition>'` and `cmux send-key --surface <ref> enter`. Add a repo-visible goal file only when the active workflow or user requires one.
5. Log to mission STATE only when a sidekick mission is active; add a memory pointer only when the goal spans sessions and no durable pointer already exists.
6. Execute. Route work through the active orchestration model (/sidekick, /swarm lanes) — do not implement directly if the mission delegates.
7. On each claimed completion: run the check commands, cite outputs, get the independent verification, and only then mark the criterion. Default verdict is FAIL.

## Executor-grade contracts (when a weaker model will execute)

A goal-level contract tells a strong agent *what must be true*. A bead contract
handed to a weaker model (Haiku 4.5, Gemini 3.8 Flash, GPT Luna, or any
delegated lane) must also tell it *exactly what to do*, because that model
cannot recover the planner's unstated decisions. Anthropic's own guidance is
the test: show the text to a brilliant colleague with no context; if they would
be confused, the model will be. `/plan-micro` requires this form for every
bead; this section is the single normative template and `/plan-micro` does not
restate it.

Required blocks, in this order, before the criteria table:

```
Environment: repo root; start SHA or branch; interpreter/wrapper (e.g. ./vpython);
             throwaway worktree required? (yes/no); credentials read from env
Goal:        one sentence; owned files as create:/modify:; dependency bead IDs;
             line budget
Reuse:       path:line + symbol for every helper to call or copy, plus one
             pattern exemplar file the executor mirrors
Steps:       1. <one self-grading command: exit 0 iff the condition holds and
                the last line is PASS <id> or FAIL <id>>
             2. <one edit: file, anchor text, exact content or source path@SHA>
RED:         <command → exact failure line>  or  RED: n/a — <reason> plus one
             pre-state check (docs, evidence, branch plumbing have no RED)
GREEN:       <command → PASS <id>>
Do not:      <each temptation as "do not X; instead Y">
Stop when:   <halt conditions; for a worker, stopping and reporting failure to parent is a successful lane outcome; parent diagnoses and retries>
Report:      <the exact command that records outputs (e.g. br comments add <id>)
             and which PASS/FAIL lines to paste verbatim>
```

Rules:

- **Self-contained.** Every value the executor needs is in the bead text, or is
  fetched by an explicit step (`read <path> § <heading>` or `path:line`). A bead
  never assumes the overall contract, a sibling bead's output, or the planning
  session. No placeholders such as `<cli>`, `<model>`, `<file>`, no `...`; the
  planner resolves them or writes the step that resolves them.
- **Self-grading commands.** The expected literal lives inside the command
  (`grep -q`, `cmp -s`, `diff -q`, `git diff --quiet`, `jq -e`, `[ "$(...)" = X ]`),
  never in prose beside it; the last line is `PASS <id>` or `FAIL <id>`. Neither
  executor nor verifier compares output by reading. "Run the tests" is not a
  step; "run the tests, expect `Failed: 0`" is not a step either.
- **Every step stands alone from the repo root.** No `cd`, no variable set in a
  previous step, no reliance on a prior step's shell state.
- **Every edit** names the file, the anchor (heading, function, or exact existing
  line text; a bare `path:line` number is not an anchor because lines move), and
  the content, verbatim or by exact source path plus commit SHA.
  Fixture and test data are given the same way; the executor never invents data.
- **Per-step mismatch default:** if actual output does not match (an expected
  RED failure is normal pre-state proof, not a mismatch), the worker stops and
  reports the failure back to the parent. At most one retry of the same command;
  the worker never substitutes a different command and never proceeds to the next
  step. The parent orchestrator handles the worker failure: it diagnoses, repairs,
  replans, and retries within authorized goal and time-box limits.
- **Precedence on conflict:** if Goal, Steps, criteria, or any two rules in the
  bead disagree, stop and report the conflict to the parent; never pick one side.
- **Every decision is made in the text.** Banned words: "as appropriate",
  "if needed", "similar to", "etc.", "handle edge cases", "clean up",
  "make sure it works". Pair each prohibition with the positive action.
- **Criteria table:** per the count rule in Scope and process ceiling, with
  check command, external anchor, independent verifier, default verdict FAIL.
  Judge-graded criteria (factuality, semantics) name a judge model of a
  different family from the generator and retain its transcript.
- **Self-check, recorded in the plan document:** hand the bead text alone to a
  fresh weak-tier agent and ask for the command list with a GUESS mark wherever
  it had to decide anything. Zero GUESS marks, or fix the text. The planner's
  own answer to "could Haiku execute this?" is not a substitute.

Canonical self-grading forms:

| Claim shape | Do not write | Write |
|---|---|---|
| no diff | `git diff --stat A B -- p` → expect empty | `git diff --quiet A B -- p && echo PASS I1 \|\| { echo FAIL I1; exit 1; }` |
| files identical | `cmp a b` → expect no output | `cmp -s a b && echo PASS E4 \|\| { echo FAIL E4; exit 1; }` |
| tests pass | `./run_tests.sh t.py` → expect `Failed: 0` | `./run_tests.sh t.py >"$(mktemp)" 2>&1 && echo PASS I3 \|\| { echo FAIL I3; exit 1; }` |
| exact count | `grep -c X f` → expect 3 | `[ "$(grep -c X f)" = 3 ] && echo PASS D1 \|\| { echo FAIL D1; exit 1; }` |
| JSON field | `gh pr view N --json isDraft` → read it | `gh pr view N --json isDraft -q .isDraft \| grep -qx true && echo PASS I4 \|\| { echo FAIL I4; exit 1; }` |
| CI rollup | `gh pr checks N` → read it | `gh pr view N --json statusCheckRollup -q '[.statusCheckRollup[] \| select((.conclusion // .state) != "SUCCESS")] \| length' \| grep -qx 0 && echo PASS \|\| { echo FAIL; exit 1; }` |

Never use `wc -l` or `wc -c` output as a literal (macOS pads with spaces; an
empty `git log` still yields one line). Strip ANSI before grepping tool output.

Filled example (one step of a docs bead):

```
Steps:       1. grep -q "test_core_memory_prompt_arm_real_e2e" testing_mcp/CLAUDE.md
                && echo PASS D1 || { echo FAIL D1; exit 1; }
             2. In testing_mcp/CLAUDE.md, directly after the table row beginning
                "| `testing_mcp/core/test_level_up_organic.py` |", insert the row:
                | `testing_mcp/core/test_core_memory_prompt_arm_real_e2e.py` | Direct Gemini SDK only: ... |
RED:         step 1 before the edit → FAIL D1
GREEN:       step 1 after the edit → PASS D1
Report:      br --no-auto-flush comments add rev-1bjrp.2.4 "<paste the PASS/FAIL lines of steps 1 and 3>"
```

## Termination and proportionality

An ironclad contract must terminate. Apply all of these limits:

- **Autonomy time-box:** after eight hours of autonomous work, stop the loop, publish the exact failing criteria and evidence, and surface the scope or authority blocker to the user. Paraphrased self-permission does not extend the time-box.
- **Delivery checkpoint:** the 30-minute uncommitted-work limit in `~/.claude/CLAUDE.md` § Push safety still applies throughout the task.
- **Evidence sequencing:** run expensive evidence such as real-model calls, browser/video capture, or bundle production once and last, after implementation and blocker triage. Use cheap targeted checks during iteration.
- **Materiality:** a changed HEAD invalidates prior evidence only when the changed files or behavior intersect that evidence. SHA inequality alone is not a reason to rerun every gate.
- **Finding triage:** correctness, security, data-integrity, or requested-behavior defects block completion. Batch their fixes into one new state before rerunning affected evidence. Style, wording, and unrelated improvements become optional follow-ups, not new blockers.
- **Proportionality:** criteria count and evidence depth scale with the requested change's risk. A narrow low-risk change does not receive the maximal gate stack.

## Anti-patterns (ban list — each caught at least once in real missions)

- Criteria satisfied by artifact EXISTENCE ("video file present") instead of artifact CONTENT (all-frames read, >85% single-state = FAIL; region-aware clustering so side-panel text doesn't masquerade as game-world motion).
- "Tests pass" without naming which layer (unit-only proof is insufficient for production behavior).
- Tool-layer proof for end-state claims (`git push` ok ≠ PR mergeable; job "running" ≠ runner online; server "started" ≠ SPA served).
- Criteria the implementer can grade themselves with no reproduction path.
- Validating a DIFFERENT artifact than the claim covers (fresh build vs the stale bundle actually recorded; gate bundle ≠ served bundle).
- Vague quantifiers: "works well", "high quality", "properly handles".
- Expanding proof hardening into new features, architectural redesign, or unrelated deliverables.
- Repeating full planning or review rounds after a narrow blocker is known.
- Producing beads, roadmaps, memory, handoffs, or reports instead of implementing and verifying the requested outcome.

ZFC note: the harness command is mechanical dispatch; the judgment (which loopholes exist, which criteria close them) is the model's, per the goal-exit-criteria.sh design.

## Verify the structural precondition BEFORE the first grind

Moved here from `~/.claude/CLAUDE.md` on 2026-07-25.

**Rule:** for any ironclad goal with a *sustained-time* criterion ("free ≥ 100 GB sustained 60 min", "p99 latency < 200 ms for 1 h", "error rate < 0.1% for 24 h"), verify the structural precondition holds at goal-met time, not just at tool time. **Do not iterate safe-action reclaim when the rate of renewal exceeds the rate of reclaim.**

Before launching any long-running cleanup / reclaim / sustain loop, ask:

1. Is there an *active producer* (AO auto-spawner, cron job, watch process, log writer) that can refill the resource faster than the planned reclaim rate?
2. If yes, can I structurally stop the producer, or do I have to keep fighting it?
3. If the answer is "keep fighting it", the goal is **unachievable in safe-action time**. Ask the user to pause the producer, accept a partial result, or extend your authority (sudo / kill scope) — and ask within about 5 minutes, not after a long grind.

Measure the *rate*, not the *level*: if the fill rate exceeds the reclaim rate, the goal is unreachable without addressing the producer, no matter how many reclaim passes you run.

**Incident (2026-07-23):** an agent spent 25+ minutes grinding cache reclaims on `jeffreys-macbook-pro` while AO created `/private/tmp/your-project.com` scratch at ~3 GB/min. "Free ≥ 100 GB sustained 60 min" was structurally unreachable until AGY was paused, but the agent kept reclaiming because the user had said "do all the work i asked". A user instruction to be thorough is not a reason to pursue a structurally impossible goal — surface the blocker instead. Memory: `feedback_2026-07-23_ao_respawner_blocks_disk_reclaim.md`.
