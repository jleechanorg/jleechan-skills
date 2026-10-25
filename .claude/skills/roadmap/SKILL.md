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
   - `Stage` = the explicit pr-lifecycle stage. Discover the workflow through
     `../pr-workflow-manager/SKILL.md`; `/pr-workflow` and `/prw` are command aliases
     only where they are installed and verified to resolve. Stage rules stay owned by
     `~/.claude/skills/pr-lifecycle/SKILL.md` § Stage, title and labels — e.g.
     `2 evidence generation`, plus any `hold:*` label. In a repository that opts into
     the six-stage workflow, read the stage label, title suffix and `## PR Stage`
     block; if they disagree, report the earliest unmet stage and write
     `MISMATCH (label X / title Y)` instead of picking one. A PR with no stage
     marker is `unstaged`; never infer a stage from draft status or CI colour. For
     PRs this session owns, run the workflow entry point first — `/pr-workflow` or
     `/prw` where those aliases are installed and verified — so each one's markers
     are synchronized
     before the board reads them.
   - `State` = OPEN/draft/ready + MERGEABLE|BLOCKED|UNKNOWN at the measured head.
   - `Head` = first 8 chars of the head SHA.
   - `Δ (lines)` = `+additions/−deletions` for the whole PR.
   - `Next` = the next action or exact blocker that exits the current stage.
   - `Brief` = ONE sentence stating what the PR changes and whether it is prod or
     test-only. No changelog.
3. **Not yet a PR** — items with an owner but no branch/PR yet.
4. **Human actions outstanding** — merges needing approval, undrafts, deploys,
   review attention (>150 prod-line PRs with no approval).
5. **Owners (cmux surfaces)** — lane → workspace › surface title → PRs covered.
6. **Later** — which PRs will need a `/pr-summary` (architecture diagram, Why It Is
   Needed, How It Works, prod vs non-prod deltas) and the condition for writing it.

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
- Rebase on `origin/main` before pushing; the roadmap repo is busy. If a rebase is
  blocked by unrelated dirty files, stash only those paths, rebase, push, then restore
  them and drop only your own stash entries.
- Report the pushed commit URL and the file URL
  (`https://github.com/jleechanorg/roadmap/blob/main/pr-inflight-YYYY-MM-DD.md`).

## Canonical source

`~/.claude/skills/roadmap/` is the live copy; `jleechan-skills/.claude/skills/roadmap/`
is the published source. Edit both, keep them byte-identical, and verify with
`shasum -a 256` after any change.
