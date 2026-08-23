---
name: loop-level-zfc
description: Use when supervising the level-up ZFC migration loop in this repo, especially when the cleanup-first roadmap is drifting, AO workers need steering, or PR sequencing must stay aligned with the canonical roadmap.
---

# Loop Level ZFC

## Overview

This is the task-specific evolve loop for the level-up ZFC migration in this repo.
It is not a generic observer. It must drive the cleanup-first roadmap, steer AO workers, record interventions, and keep the PR stack aligned with the canonical design.
Run this loop on a 30-minute cadence by default unless the roadmap or operator explicitly requires a shorter interval.
When `#6420` or `#6404` is active and not yet demonstrably on-track, treat them as fast-watch lanes and re-check their worker tmux panes and PR state every 5 minutes until they are either truly on-track or explicitly escalated out of AO.

Use this with the canonical design and nextsteps docs:
- `roadmap/zfc-level-up-model-computes-2026-04-19.md`
- `roadmap/evolve-loop-findings.md`

Operator-specific overrides (only if present):
- `~/roadmap/zfc-level-up-model-computes-2026-04-19.md`
- `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`

## Non-Negotiable Goals

1. Keep the work aligned to the actual roadmap.
2. Start every cycle by re-reading the official roadmap docs and a memory source; do not rely on stale conversational recall.
3. Cleanup/deletion is the highest priority.
4. Do not let side-lanes count as core ZFC progress.
5. Use at most 5 parallel workers total across core lanes and valid support lanes.
6. Record every manual intervention and why it was needed.
7. Never end a cycle with roadmap work unowned. A cycle must explicitly decide what happens next.
8. No roadmap lane counts as complete until it is truly `/green` (CI green + no merge conflicts) under `~/.claude/skills/pr-green-definition.md`, plus draft-phase quality gates (`/es`, `/er`, `/advice`) for production PRs.
9. Production-code PRs require full evidence discipline; only non-production PRs may skip video evidence.
10. Prefer parallel subagents/workers whenever the work is genuinely independent and materially useful.
11. Every worker must be driving its assigned lane or PR to an explicit finish bar, not merely classifying the state.
12. For production PRs, conflicts and serious GitHub review blockers come before everything else.
13. After conflicts/serious blockers are cleared, evidence comes before polish. Do not spend cycles polishing comments or green-loop churn on a PR that still lacks a solid evidence bundle.
14. For production PRs, generate video evidence first, then get a skeptic-style verdict on the evidence/gate story before spending time on polish.
15. Every cycle must inspect open PR reality, not just remembered queue state; if the roadmap needs a new PR-shaped lane, create or assign it in the same cycle.
16. Do not treat a worker as active just because its tmux pane exists; a pane stuck in repeated `Continue working...` prompts is a waiting-state failure until explicitly corrected.
17. Do not treat stale review summaries as truth; always verify fresh current-head review state, unresolved threads, and evidence comments before declaring a lane done or review-only.
18. Every related open ZFC PR must carry the GitHub label `zfc_level`; audit and repair missing labels in the same cycle.
19. Do not call a PR `/green` or merge-ready from check runs alone; verify current-head issue comments for fresh `/smoke`, `/er`, evidence-required, or bot-reported failures that can invalidate the green story.
20. Trust hierarchy for cycle decisions is: current-head PR state first, tmux conversation second, AO status last.
21. Do not let a worker spend more than one cycle in pure bot-rereview or stale-review argument loops without fresh branch movement.
22. A waiting pane must be repurposed, explicitly parked, or closed in the same or next cycle; do not carry it as fake active capacity.

## Queue Source Of Truth

Do not treat this skill as the queue authority.
Rebuild the active queue every cycle from:
1. `~/roadmap/zfc-level-up-model-computes-2026-04-19.md`
2. `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`
3. current open related PR state

If the roadmap docs and live PR reality disagree, record the mismatch and make an explicit ownership decision in the same cycle.

## Parallelization Model

Do not confuse:
- **active merge lane**: the roadmap item currently allowed to advance toward landing
- **support lanes**: parallel work that helps the active merge lane without violating sequencing
- **execution mode**: whether a lane should run as an AO worker or as a parallel subagent task

Execution-mode rule:
- **PR-shaped work defaults to AO**:
  - code changes
  - test fixes
  - CI/review follow-up
  - conflict resolution
  - evidence generation that must land on a branch/PR
- **non-PR cognition work defaults to parallel subagents**:
  - roadmap synthesis
  - skeptic/audit review
  - supersede/park planning
  - keep/drop analysis
  - postmortem / harness diagnosis
  - artifact drafting that does not yet need branch state

Do not force AO workers onto pure cognition/planning tasks when a subagent can produce the artifact faster and with less workflow drift.
Promote a non-PR subagent result into an AO worker only when it becomes a real branch/PR task.

For this project, parallel support work is allowed when it is independent and materially helps the active merge lane. Valid examples:
- upstream blocker root-cause/fix work
- true `/green` / evidence audit work
- supersede/split planning for a parked lane
- architecture prework that does not violate M0-first sequencing

Finish bars by lane type:
- production merge lane: true `/green` plus draft-phase quality gates, or explicit justified-wait when only non-branch-owned blockers remain
- production support PR: green enough to unblock the active merge lane, then explicit stop/park
- non-production PR: CodeRabbit approval plus the repo-appropriate evidence bar
- planning/support artifact lane: promised artifact or PR/body/note delivered, then stop

Execution order within a production lane:
1. clear merge conflicts and any serious GitHub review blockers that make the current PR mechanically or conceptually wrong
2. get or refresh solid evidence for the current head
3. if UI/interactive or otherwise evidence-bearing, generate or refresh video evidence tied to the current head SHA
4. get skeptic approval or equivalent reviewer-subagent approval on the evidence/gate story for the current head
5. close remaining branch-owned code/test blockers
6. run final green/polish loop only after 1-5 are satisfied

Do not invert that order.

Default cap:
- at most **1 active merge lane**
- at most **4 additional support workers**
- never exceed **5 total live workers**

Default split:
- at most **1 active production AO merge lane**
- use **parallel subagents first** for non-PR/support cognition work
- only spend additional AO slots on support work when the support task is itself PR-shaped or must mutate branch/PR state

Preference rule:
- if two or more useful tasks can proceed independently, do not serialize them by default
- spawn parallel support workers instead, as long as they do not mutate roadmap order or overload the lane with noise
- when the support task is non-PR analysis/planning/review, prefer parallel subagents over AO workers

AO fallback rule:
- if AO workers are not making enough progress, the loop must stop treating AO as mandatory
- evidence of insufficient AO progress includes:
  - 2+ cycles with no remote movement on a PR-shaped lane
  - repeated prompt drift into unrelated work
  - repeated environment/setup friction (missing venv, broken auth, worktree creation errors)
  - session materialization failures or missing tmux/session identity
- once AO is judged insufficient for a non-PR task, reassign that task to a parallel subagent in the same or next cycle
- once AO is judged insufficient for a PR-shaped support task, either:
  1. respawn one more time with a narrower instruction, or
  2. execute it locally / with a worker only if it truly needs branch mutation

Upstream-blocker rule:
- `upstream-owned` is a provisional classification, not a terminal state
- within 1-2 cycles, the loop must force one of these outcomes:
  1. reproduce the blocker on a fresh `origin/main` worktree and assign an upstream fix lane, or
  2. fail to reproduce it on fresh `origin/main` and immediately reclassify it as branch-owned divergence on the active PR
- do not allow a production merge lane to sit in repeated justified-wait on an alleged upstream blocker without a fresh `main` repro
- after a failed fresh-`main` repro, the loop must send a direct fix-order to the active merge-lane worker in the same cycle

## Loop Body

### Phase 1: Memory First

Before making decisions, always:

1. Re-read the official roadmap docs:
   - `~/roadmap/zfc-level-up-model-computes-2026-04-19.md`
   - `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`
2. Run a memory search source before any steering:
   - current `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`
   - current repo-local findings log
   - a sparse history search from `~/.codex/sessions` and `~/.claude/projects`

Run memory search before making decisions:

- `/ms "level up zfc open tasks"`
- `/ms "level up zfc stuck tasks"`
- `/ms "level up zfc roadmap drift"`
- `/ms "level up zfc AO friction"`

If memory conflicts with the canonical roadmap files, prefer the roadmap files and note the conflict in findings.
Do not skip sparse history just because roadmap docs exist; each cycle must sample enough history to detect worker/session drift.

### Phase 2: Observe

Inspect:
- official roadmap queue vs current open related PRs
- whether every related open PR carries the `zfc_level` label
- active AO sessions for `your-project.com`
- last 20-30 lines from each worker tmux pane
- if a pane is ambiguous, capture 60-80 lines rather than trusting a short tail
- current worker conversation state from sparse `~/.codex/sessions` / `~/.claude/projects` history where available
- open related PRs and current head SHAs
- whether any worker is on stale, merged, or side-lane work
- GitHub/AO auth mode for this shell
- all active ZFC PRs for recurring G6/G7 drift, not just the current merge lane

Kill zombie sessions working on merged/closed/stale lanes.
Treat AO branch/PR mapping as advisory only; if AO status disagrees with tmux or current-head PR state, record the mismatch and follow tmux/PR truth.

Auth probe:
- explicitly check whether `gh` works through `hosts.yml`, env token, or neither
- do not blindly `unset GITHUB_TOKEN` if the loop still needs env-backed auth for `gh` or `ao`
- record the auth mode in the cycle when it affects worker spawning or PR actions
- if `gh auth status` shows `GITHUB_TOKEN` invalid but `hosts.yml` is valid, clear only the env override for the loop subprocess and continue; this is not a stop condition
- if GitHub CLI still fails after clearing an invalid env override, fall back to GitHub connector data or AO/tmux/local git evidence in the same cycle

### Phase 3: Measure

For each related PR:
- does it have a live worker?
- has the branch moved remotely since the last cycle?
- is it blocked on code, review, CI, or harness?
- is it core roadmap work or side-lane noise?
- what is the latest current-head review event, not just `reviewDecision`?
- are unresolved threads counted on the current head?
- does current-head evidence actually exist as a posted gist/comment/video, not just as local temp files?
- do current-head issue comments show fresh `/smoke`, `/er`, or bot-reported failures that still need action?
- what is the exact next step for this PR?
- what is the shortest path from the current state to either true `/green` plus draft-phase quality gates, or for non-production lanes, CodeRabbit-approved with the proper evidence bar?

For each active worker:
- is the worker truly executing or just sitting in repeated `Continue working...` prompts?
- what did the latest tmux conversation actually do?
- what do sparse codex / Claude session samples say the worker believes it is doing?
- does the worker's understanding match the real PR state?
- classify the worker as `on-track`, `partly-on-track`, `waiting`, `drifting`, or `done`
- if the worker is in a rereview loop, did the branch move this cycle?
- if the worker is `waiting` or `done`, should the slot be repurposed immediately?

For all active ZFC PRs, also measure:
- G6 evidence status
- G7 skeptic status
- unresolved thread state
- whether the same gate gap is repeating across multiple PRs

Evidence-first status:
- if a production PR lacks a credible evidence bundle, mark it as evidence-blocked before calling it review-blocked or polish-ready
- unresolved comments without evidence are secondary until the evidence bar is satisfied
- if video evidence is required but missing or stale for the current head SHA, mark the PR as evidence-blocked
- if skeptic has not approved the evidence/gate story for the current head, mark the PR as evidence-review-blocked rather than polish-ready

Correctness-first status:
- if `mergeStateStatus` is `DIRTY`, `mergeable` is false/CONFLICTING, or a serious review comment indicates the PR is wrong in scope/design/correctness, mark it as correctness-blocked
- correctness-blocked outranks evidence-blocked, evidence-review-blocked, and polish-ready

Health signal:
- healthy if core PRs have live workers and at least one core lane is making real remote progress
- unhealthy if workers are only classifying/analyzing, or if no core lane moved for 2+ cycles
- unhealthy if a worker pane repeats generic `Continue working on the task` prompts for a full cycle without fresh commands or branch movement
- unhealthy if AO inventory still reports sessions as active after tmux shows they are effectively parked or irrelevant

Also compute an ownership signal:
- owned if each active core roadmap item is either:
  - being executed by a live worker, or
  - intentionally waiting on fresh CI/review state with a recorded re-check plan
- unowned if the roadmap is incomplete and there is no explicit next executor or wait state

Also compute a support-lane signal:
- healthy if the active merge lane has the support workers it needs for its current bottlenecks
- unhealthy if a lane is waiting on upstream, review, or evidence questions that could be advanced in parallel but no support worker owns them

Also compute a label-hygiene signal:
- healthy if all related open PRs carry `zfc_level`
- unhealthy if any related open PR lacks `zfc_level`

Also compute an execution-fit signal:
- **AO fit** when the task is PR-shaped and branch mutation/evidence posting is required
- **subagent fit** when the task is mainly analysis, review, planning, or artifact drafting
- mark the cycle unhealthy if a subagent-fit task is still being burned through AO worker boilerplate

### Phase 4: Diagnose

Run `/harness` on each new recurring friction point.

Classify each blocker as:
- harness gap
- code bug
- external
- roadmap drift

If the same class of failure happens twice, fix the harness and record it.
If a cycle only fixes code without improving the harness that caused the repeat failure, treat the cycle as incomplete.

Special case: AO / GitHub auth degradation
- if `gh auth status` fails because `~/.config/gh/hosts.yml` is stale/invalid, treat that as harness degradation
- if env-backed auth still works, preserve it for spawn/comment actions instead of clearing it reflexively
- if neither hosts auth nor env auth works, do not keep retrying identical AO spawns; switch to fallback execution and record the auth blocker
- if env auth is invalid but `hosts.yml` auth is valid, the loop must switch to `env -u GITHUB_TOKEN gh ...` immediately and continue the cycle
- a GitHub fetch failure is never sufficient reason to stop the cycle if AO/tmux/local evidence still exists

Special case: recurring G6/G7 drift across multiple ZFC PRs
- if two or more active ZFC PRs are missing evidence bundles or skeptic verdicts, classify that as a harness/system gap first
- do not treat each PR as an isolated failure until you have ruled out shared automation or process drift
- assign one worker to the cross-PR gate problem if it is recurring

Special case: comment churn without evidence
- if a production PR is missing evidence, do not let the loop burn cycles on comment-polish-only work
- comments can still be triaged for severity, but the primary owner must first build enough evidence to prove the PR works
- unless comments show the whole PR is conceptually wrong, comment churn does not outrank evidence generation and skeptic review
- once evidence is posted, verify the evidence exists on the PR itself (comment/gist/video link) before downgrading the lane to review-only

Special case: fresh current-head issue-comment failures
- if `/smoke`, `/er`, or bot-generated issue comments report failure on the current head SHA, the PR is not merge-ready even if all standard checks are green
- treat that as active gate debt until the failure is investigated, rebutted with proof, or superseded by a newer successful run on the same head

Special case: repeated `continue?` prompts / waiting panes
- if a worker has already delivered its bounded finish bar and the pane falls into repeated `Continue working on the task` prompts, hard-park it in the same cycle
- if a worker has not delivered its finish bar and the pane falls into repeated `Continue working on the task` prompts, send one direct autonomy steer in the same cycle
- if the same worker is still in repeated `Continue working on the task` prompts next cycle, reassign or respawn it; do not keep counting it as active

Special case: fresh current-head review churn
- when a PR receives a new `CHANGES_REQUESTED` or fresh actionable review comment on the current head SHA, that lane is not review-only
- assign or keep a worker on the new current-head review items until they are fixed, explicitly rebutted, or intentionally deferred with proof
- do not rely on an older green summary if fresh current-head review state disagrees

Special case: merge conflicts and serious GitHub comments
- merge conflicts are not polish work; they are correctness blockers and must be assigned immediately
- serious GitHub comments that question correctness, scope, or merge vehicle also block evidence/polish work until triaged
- low/nit comments do not outrank evidence once correctness blockers are cleared

Special case: `#6420` / `#6404` AO fallback
- `#6420` and `#6404` are not allowed to sit in repeated nominal-ownership states without real execution
- if either PR still lacks a truly on-track AO worker after one full loop cycle of direct steering or respawn, the next cycle must stop waiting on AO quality
- for `#6420`, spawn parallel subagents to directly drive the branch to true `/green`
- for `#6404`, spawn parallel subagents to directly drive the branch to the non-production finish bar: current-head CI green, CodeRabbit approved, proper evidence
- record the failed AO attempt, the specific reason AO was judged insufficient, and the subagent takeover decision in both roadmap logs and the cycle bead

Special case: long-lived upstream claims
- if a blocker has been labeled upstream-owned for 2+ cycles, treat that label as stale until re-proven
- require a fresh repro on `origin/main`; do not reuse an old note as sufficient evidence
- if the fresh repro shows green on `main`, record the reclassification and move the active lane out of wait immediately

### Phase 5: Plan

Run `/nextsteps` and keep all updates aligned with:
- cleanup-first M0
- supersede current `#6418`
- architecture work only after M0

Do not invent a new queue unless the roadmap docs are updated.
Also read `.claude/skills/level-up-zfc/SKILL.md` as the phase-checklist source, especially for:
- M0 checklist
- M0 anti-patterns
- M1/M2 sequencing constraints
Before treating any PR as ready to advance the roadmap, verify it against the real `/green` policy (CI green + no merge conflicts), not `gh pr checks` alone.

Review workflow adaptation:
- adapt `/copilot` logic first for serious comment triage to determine whether the PR is fundamentally wrong, then later for cleanup once correctness is restored
- adapt `/polish` logic only as a terminal tightening loop after evidence exists; do not use its default "iterate toward green" structure as a substitute for evidence-first discipline
- `/polish` and the repo's canonical `/green` standard (CI green + no merge conflicts only — CodeRabbit/Bugbot/comments/evidence are now draft-phase quality gates, not `/green` conditions) must still apply the ZFC-specific evidence-first rigor above (Design Doc Compliance, level-up file boundaries, etc.) during the draft phase, not just adopt `/polish`'s generic "iterate toward green" loop structure as-is
- adapt skeptic-agent logic before polish: skeptic should first assess whether the current-head evidence bundle and gate story are sufficient and truthful
- if skeptic or major PR comments indicate the whole PR direction is wrong, stop polish work and route the lane back to design/scope correction

### Phase 6: Act

Allowed actions:
- steer AO workers
- kill or respawn stuck workers
- spawn parallel subagents for non-PR work items
- update PR descriptions to reflect roadmap truth
- open a new PR only when needed by the roadmap, and keep core open lanes <= 5
- if dispatch fails twice, fix directly
- if AO spawn is blocked by auth but the task is still roadmap-valid, use the next-best execution path rather than leaving the slot empty

Specific rules:
- if a production PR has a merge conflict or serious GitHub correctness blocker, assign that before evidence or polish work
- if a production PR lacks evidence, assign evidence work before polish work
- if a production PR needs video evidence under repo policy, assign video evidence work before polish work
- after evidence is refreshed, assign skeptic or reviewer-subagent review of the current-head evidence/gate story before assigning polish
- if a primary GitHub query fails, retry once with the corrected auth path and then continue with fallback evidence sources in the same cycle
- if a worker is stuck for 2+ cycles with no remote movement, interrupt it
- if a worker has completed a planning artifact, require it to stage/push/comment and stop
- if a side-lane is distracting from M0, park it
- if M0 cleanup requires a new narrow PR, create it; do not overload `#6404`
- if work is claimed as M0 cleanup, verify it against the M0 checklist from `.claude/skills/level-up-zfc/SKILL.md`
- if a supposed M0 change increases production LOC or adds formatter behavior on top of live legacy paths, flag roadmap drift immediately
- if a core worker is stopped, immediately decide whether to:
  - respawn a worker on the same core lane,
  - move a worker to the next roadmap lane, or
  - intentionally wait on fresh CI/review state
- if the decision is "wait", record:
  - which PR is waiting,
  - what exact signal is being waited on,
  - when the loop should re-check,
  - why no other roadmap lane should start first
- do not leave the queue with zero live workers unless the cycle explicitly concludes that waiting is the highest-value next action
- if no core lane is actively executing and no justified wait state exists, spawn the next roadmap-appropriate worker before ending the cycle
- if an active merge lane is blocked on independent subproblems, spawn support workers rather than forcing one worker to serialize all work
- if the independent support problem is non-PR cognition work, spawn a parallel subagent rather than an AO worker
- only keep a non-PR task in AO when the output must be committed/pushed/commented from a dedicated worktree

Roadmap execution split for the current queue:
- `#6420` active merge lane: **AO worker**
- `#6418` supersede/park analysis: **parallel subagent first**, promote to AO only if a real branch/PR artifact update is required
- `#6404` post-M0 keep/drop and activation analysis: **parallel subagent first**, promote to AO only if the artifact must be landed in branch state
- support workers must not mutate roadmap order; they exist to unblock or verify the active lane
- when choosing between one overloaded worker and multiple bounded independent workers, prefer the bounded parallel split
- if AO spawn fails because of auth:
  - first determine whether env-backed `GITHUB_TOKEN` still works
  - if env-backed auth works, retry with that auth path intact
  - if env-backed auth does not work, repurpose an existing dormant worker or start a manual Codex tmux worker
  - do not silently reduce worker count when valid parallel work still exists
- every worker instruction must include its finish bar explicitly:
  - production lane: true `/green` plus draft-phase quality gates if branch-owned work remains, otherwise explicit justified-wait
  - support PR: keep going until the PR is actually unblocked or proven external-only
  - non-production PR: CodeRabbit approval and required evidence state
  - planning lane: promised artifact, PR body update, or PR note delivered
- if the same G6/G7 gap is affecting multiple ZFC PRs, repurpose or spawn one worker to own that shared gate problem rather than letting every PR stall on the same missing automation/evidence condition
- if a worker reports an upstream-owned blocker, the loop must either:
  - assign a support worker to reproduce/fix it on fresh `main`, or
  - if such a support lane already ran and `main` is green, treat the blocker as branch-owned and push the active lane worker back into execute mode
- do not let an active production lane remain in justified-wait on an upstream label that has not been freshly revalidated
- for production PRs, a review worker may run `/copilot`-style triage immediately to determine whether serious comments block correctness
- only after conflicts and serious blockers are cleared may the lane move to evidence work
- only after evidence exists, skeptic/reviewer approval is in place, and branch-owned blockers are closed may a worker run a `/polish`-style iterative green loop
- do not run polish as the first response to a red PR
- if PR comments indicate the whole PR is wrong in scope, design, or merge vehicle, do not polish; redirect to scope correction instead
- for `#6420` and `#6404`, if AO ownership is still stale, dead-shell, non-materialized, or obviously not addressing the current blocker after one cycle, skip further AO waiting and move the execution to parallel subagents in that same cycle

### Phase 6.5: Decide Next Work

Before ending the cycle, explicitly answer:
1. What is the highest-priority roadmap item right now?
2. Is it blocked on code, CI, review, or harness?
3. Who owns the next action?
4. If nobody owns it yet, spawn or assign that owner now.

Default decision order:
1. Keep `#6420` as the active lane until M0 is honestly green or explicitly blocked on fresh external state.
2. Do not resume current `#6418` except to preserve supersede/park status.
3. Only move to `#6404` if M0 is in a justified wait state or complete.
4. If either `#6420` or `#6404` is still off-track from AO execution when revisited next cycle, bypass AO for that PR and assign direct parallel subagents to carry it to the finish bar.

When the active lane is in `wait`, ask:
1. Is the wait caused by an upstream issue that can be root-caused/fixed in parallel?
2. Is there unresolved `/green`/evidence audit work that can be done in parallel?
3. Is there a parked-lane prep task that can be advanced without violating sequencing?

If yes, spawn support workers up to the total cap instead of leaving only one worker alive.

Comment/polish worker selection:
1. Conflict/serious-comment worker if the PR is correctness-blocked
2. Evidence worker if G6 is missing or stale
3. Video-evidence worker if video is required and missing/stale
4. Skeptic/reviewer-subagent for the current-head evidence/gate story
5. Code/test closure worker if a branch-owned blocker exists
6. Final polish/green-loop worker using adapted `/polish` logic only after 1-5 are satisfied

Auth-aware parallelization rule:
1. Prefer normal AO spawn when GitHub/AO auth is healthy.
2. If AO spawn is blocked only by invalid `hosts.yml`, try the env-backed auth path before giving up.
3. If fresh AO spawn remains blocked, fill the slot with a repurposed dormant worker or manual Codex tmux worker and record that this is a fallback lane.
4. If `GITHUB_TOKEN` is invalid but `gh` hosts auth is valid, use `env -u GITHUB_TOKEN` for the GitHub CLI calls inside the loop rather than treating the cycle as blocked.

### Phase 6.6: Green and Evidence Gate

Before declaring a lane complete or moving the roadmap forward:
- verify against `~/.claude/skills/pr-green-definition.md`
- do a deep review of:
  - mergeability
  - evidence bundle integrity
  - unresolved review/comment state
  - skeptic/G7 state

Evidence-first guardrail:
- "needs polish" is never the top diagnosis for a production PR that still lacks proof it works
- if there is no evidence bundle or the evidence is stale relative to the current head SHA, the next worker should be assigned to rebuild/refresh evidence, not to polish comments
- if the current-head evidence has not received a skeptic-style approval, the next worker should close that evidence-review gap before polish
- if major PR comments show the whole PR is wrong, skip polish entirely and reopen scope/design correction
- if the PR is merge-conflicting or has serious correctness comments, skip evidence/polish reassignment and fix those blockers first
- if a GitHub API read path is degraded, the loop must still complete an ownership decision using tmux output, AO state, local worktree state, or other available evidence rather than ending as an incomplete cycle
  - latest non-commented CodeRabbit state
  - Bugbot state
  - unresolved review comments/threads
  - skeptic verdict
  - evidence state

Evidence rule:
- if the PR touches production code, require full evidence discipline and do not treat screenshots or log snippets as enough
- only non-production PRs may skip video evidence
- if evidence is missing, the lane is not done even if CI is green

Worker completion rule:
- a worker is not done merely because it identified the blocker class
- if its assigned PR still has branch-owned work toward the lane's finish bar, it must keep going
- only when the lane reaches its finish bar, or reaches explicit justified-wait, may the worker stop or be repurposed
- if the only remaining activity is repeated bot rereview nudges without branch movement, demote the lane from active execution to review-state waiting or repurpose the slot

Cross-PR audit rule:
- every cycle, do a compact `/green` sweep across all active ZFC PRs
- if the same missing gate appears repeatedly (for example G6 evidence or G7 skeptic), record it once as a shared harness problem and route one worker to address that system gap

### Phase 6.7: M0 Integrity Gate

For any active M0 lane, explicitly verify:
- the work does not violate the M0 anti-patterns from `.claude/skills/level-up-zfc/SKILL.md`
- production cleanup claims are backed by the actual M0 checklist, not narrative
- test-first / deletion-second ordering is being respected where applicable
- net production LOC is not drifting positive while calling the work “cleanup”

### Phase 7: Record

Always update:
- `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`

When the cycle changes roadmap truth, also update:
- `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`
- `~/roadmap/learnings-2026-04.md`
- relevant beads

Each intervention record must include:
- what worker/PR was touched
- why intervention was needed
- what action was taken
- whether it was a harness gap

Each cycle record must also include:
- a worker-by-worker evaluation grounded in tmux conversation plus sparse codex/Claude history
- a PR-by-PR status block for all active or roadmap-related open PRs
- a PR-by-PR next-step block
- a PR-by-PR finish path to either true `/green` plus draft-phase quality gates, or for non-production lanes, CodeRabbit-approved plus proper evidence
- the chosen next work item
- whether the next state is `execute` or `wait`
- the owning worker/session if any
- if `wait`, the exact condition that will cause the next cycle to resume execution

## Completion Condition

Stop only if one of these is true:
- user explicitly says stop/pause
- the full level-up ZFC roadmap is truly complete
- context pressure requires handoff

Do not stop merely because a single PR went green.
Do not stop merely because the current worker finished a subtask; re-evaluate the roadmap and assign the next action.

## Anti-Drift Rules

- Do not optimize for PR-local green if it conflicts with roadmap sequencing.
- Do not let current `#6418` absorb more work.
- Do not count `#6386` or `#6413` as core roadmap progress.
- Do not claim M0 complete unless cleanup/deletion is actually leading.
- If production code addition exceeds deletion on a cleanup milestone, flag drift immediately.
