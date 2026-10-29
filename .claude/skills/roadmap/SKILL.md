---
name: roadmap
description: Use when /roadmap is requested to survey, update, and coordinate roadmap work.
---

# Roadmap

## Contract

Run `/roadmap` by producing (or updating) ONE in-flight PR board document in the
roadmap repo, committing it, pushing it, and showing the URL. Anything else — surveys,
memory reads, nextsteps rotas — is supporting material, not the deliverable.

Phase 0 survey (optional context gathering) lives in
`references/legacy-command.md`; use it when the board needs history, but the output
format below is mandatory.

## Output document

Path convention: `~/roadmap/pr-inflight-YYYY-MM-DD.md` (update the same day's file
instead of creating a second one). Repo: `jleechanorg/roadmap`.

Required structure, in this order:

1. **TLDR at the very top.** 3–6 sentences a reader can act on without scrolling:
   how many PRs are in flight and how many sit in each stage, how many are blocked only on a human action, which
   carry the user-visible P−1 fixes, which are stale or have no owner, and the total
   line delta. Name the biggest deltas explicitly.
2. **PR ledger table**, one row per PR:
   `| PR | Repo | Stage | State | Head | Δ (lines) | Next | Brief |`
   - `PR` links to the full GitHub URL (number visible in the link text).
   - `Stage` = the explicit pr-lifecycle stage. Follow the manager's [Find the skills before inventing
     a workflow step](../pr-workflow-manager/SKILL.md#find-the-skills-before-inventing-a-workflow) to
     verify its official remote and record its commit before acting. Use `/pr-workflow` or `/prw` only
     when installed and verified; otherwise follow that entry point directly. Stage rules stay owned by
     `~/.claude/skills/pr-lifecycle/SKILL.md` § Stage, title and labels — e.g.
     `2 evidence generation`, plus any `hold:*` label. In a repository that opts into
     the six-stage workflow, read the stage label, title suffix and `## PR Stage`
     block; if they disagree, report the earliest unmet stage and write
     `MISMATCH (label X / title Y / block Z)` instead of picking one. A PR with no stage
     marker is `unstaged`; never infer a stage from draft status or CI colour. For
     PRs this session owns, before running the resolved `/prw` workflow entry point,
     read and retain the pre-sync values of the stage label, title and
     `## PR Stage` block, including any missing marker. If they disagree, record the
     earliest unmet stage and exact pre-sync mismatch
     (`MISMATCH (label X / title Y / block Z)`) for the final report.
     Then follow the resolved workflow entry point so the board reads synchronized markers, and preserve
     and report every recorded pre-sync mismatch even when that workflow resolves it. This is mandatory
     for every `/roadmap` invocation, including status-only and concise-report modes, and
     it must happen before the stage table is produced. When another owner controls a
     PR, run the resolved workflow in its status/read-only mode, preserve that owner's
     markers, and do not advance the stage without live workflow proof. If markers
     disagree, report the earliest unmet stage and the exact mismatch
     (`MISMATCH (label X / title Y / block Z)`); do not select a stage from draft
     status, CI colour, or prose.
   - `State` = OPEN/draft/ready + MERGEABLE|BLOCKED|UNKNOWN at the measured head.
   - `Head` = first 8 chars of the head SHA.
   - `Δ (lines)` = `+additions/−deletions` for the whole PR.
   - `Next` = the next action or exact blocker that exits the current stage.
   - `Brief` = ONE sentence stating what the PR changes and whether it is prod or
     test-only. No changelog.
3. **Not yet a PR** — items with an owner but no branch/PR yet.
4. **Human actions outstanding** — only actions that meet the shared human-only
   boundary. For each, state `Why the LLM cannot execute this next step now:`
   with the exact authority, physical dependency or essential unresolved decision.
   Undrafting, evidence review, checks and authorized deployments are not human
   actions merely because they remain undone. Execute available authorized work
   in the caller's scope before ending; preserve a planning/status-only scope.
5. **Owners (cmux surfaces)** — lane → workspace › surface title → PRs covered.
6. **Later** — which PRs will need a `/pr-summary` (architecture diagram, Why It Is
   Needed, How It Works, prod vs non-prod deltas) and the condition for writing it.

Every `/roadmap` report, including a concise chat or status reply, must include a
stage table. A compact reply may shorten the surrounding prose, but it must retain
one row per in-scope PR with the `Stage`, `State`, `Head`, `Next`, and exact marker
status; a prose-only status is incomplete.

## Open the published board in cmux

After publishing the board, when `/roadmap` is invoked from a verified cmux
context—or the caller explicitly requests the current cmux workspace—resolve the
current workspace at action time. Reuse the board's existing browser tab there,
update it to the current published URL if needed, and reload it; otherwise create
a browser tab in that same workspace. Do not create or select a workspace/window,
change focus, or open a duplicate board tab. Outside cmux, do not launch cmux or a
browser; return the published links. Verify the tab URL, rendered board, and
workspace before reporting success. Follow the browser-control and cmux-steer
skills for isolation, authentication, and no-focus-steal behavior.

## Evidence rules

- Every row comes from a live `gh pr view` at write time. Never carry a state, head, or
  delta forward from prose, a prior board, or another agent's report.
- Say the measurement time in one line at the bottom, and state that deltas are total
  additions/deletions (not prod-only) unless you computed the split.
- If a PR is stale, say how stale (last-updated date). If an item has no owner, write
  `no owner` rather than listing a retained name.

## Git rules

- Commit only the board file (`git commit -- <path>`); never sweep unrelated dirty
  files into the commit. Preserve other lanes' uncommitted work exactly as found.
- Use an isolated branch/worktree and the roadmap repository's PR workflow.
  Preserve unrelated dirty files and the shared index; do not stash another
  lane's work to force a rebase or push directly to main.
- Report the actual pushed commit, PR and commit-pinned board URLs. Do not claim
  the board is on main before the verified merge; merge authority remains separate.

## Canonical source

`~/.claude/skills/roadmap/` is the live copy; `jleechan-skills/.claude/skills/roadmap/`
is the published source. Diff both copies and repository status first, reconcile
only authorized changes, then verify exact hashes after synchronization. Do not
absorb another lane's unpublished edit merely to make copies match.
