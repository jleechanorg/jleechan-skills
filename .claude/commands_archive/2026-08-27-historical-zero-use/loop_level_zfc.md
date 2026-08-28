---
description: Run the task-specific level-up ZFC evolve loop for this repo
type: llm-orchestration
execution_mode: immediate
---

# /loop_level_zfc

## Command Summary

Purpose: run one cleanup-first ZFC supervision cycle that checks live worker and PR reality, steers work, and records an explicit ownership decision.
Scope: roadmap-aligned level-up/ZFC PRs, AO workers, tmux conversations, sparse codex/Claude history, and finish-bar tracking.
Non-goals: this command is not a generic repo monitor and does not treat stale AO inventory or green checks alone as proof of completion.

Use the repo-local skill:
- `.claude/skills/loop-level-zfc/SKILL.md`

Also consult (repo-local canonicals):
- `roadmap/zfc-level-up-model-computes-2026-04-19.md`
- `roadmap/evolve-loop-findings.md`

Operator-specific overrides (only if present):
- `~/roadmap/zfc-level-up-model-computes-2026-04-19.md`
- `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md`

Execute one full loop cycle now:
0. Assume the loop runs on a 30-minute cadence by default; if the scheduler differs, fix it or record the mismatch. Special case: while `#6420` or `#6404` is active and not yet demonstrably on-track, re-check those two worker/PR lanes every 5 minutes
1. Re-read the official roadmap docs first
2. Run memory search first, including sparse reads from `~/.codex/sessions` and `~/.claude/projects`
3. Observe workers/PRs and actual open PR inventory, including tmux conversation state and sparse codex/Claude worker history
3a. Audit `zfc_level` labels on all related open PRs and repair missing labels in the same cycle
4. Measure health and movement, including worker-by-worker classification and PR-by-PR next step / finish path
5. Diagnose friction with `/harness` when needed
6. Run `/nextsteps`
7. Steer/fix directly as needed
8. Record all interventions in both roadmap locations: `~/roadmap/nextsteps-2026-04-19-level-up-zfc.md` and repo `roadmap/evolve-loop-findings.md`; every cycle record must include:
   - worker-by-worker AO evaluation grounded in tmux + sparse codex/Claude history
   - PR-by-PR status
   - PR-by-PR next steps
   - PR-by-PR path to true `/green` (CI green + no merge conflicts) plus draft-phase quality gates (`/es`, `/er`, `/advice`) for production PRs, or CodeRabbit-approved plus proper evidence for non-production PRs
   - the bead created or updated for this cycle
9. Explicitly decide what to work on next from the roadmap and open PR state
10. Do not end the cycle with roadmap work unowned unless you record an intentional wait state with the exact signal being awaited
11. Before treating any lane as done, verify true `/green` (CI green + no merge conflicts) plus draft-phase quality gates with a deep review and apply the evidence rule: only non-production PRs can skip video evidence
11a. For `/green`, inspect current-head issue comments too; fresh `/smoke`, `/er`, evidence-required, or bot-failure comments can invalidate a nominally green check surface
12. Ensure every active worker has an explicit finish bar: true `/green` plus draft-phase quality gates for production lanes, CodeRabbit approval plus proper evidence for non-production lanes, or a delivered planning artifact/body update/note for planning lanes
13. Treat any `upstream-owned` blocker label as provisional only: within 1-2 cycles force a fresh `origin/main` repro; if `main` is green, immediately reclassify the blocker as branch-owned divergence on the active PR and push the merge-lane worker back into execute mode
14. Sequence production work as: merge conflicts or serious GitHub correctness comments first, then evidence, then skeptic/reviewer approval of that evidence/gate story, then adapted `/polish`-style green tightening
15. Do not run polish-first on a production PR that still has merge conflicts, serious correctness comments, or lacks a credible evidence bundle for the current head SHA
16. If a GitHub read fails, repair the auth path if possible (`env -u GITHUB_TOKEN` when env token is invalid and hosts auth is valid), then continue the same cycle; do not stop at read failure
17. If GitHub remains degraded after retry, complete the cycle with AO/tmux/local-git evidence and still make an ownership decision
18. For production PRs, generate required video evidence first, then get a skeptic-style approval of the current-head evidence/gate story before assigning polish
19. If PR comments indicate the whole PR is wrong in scope or design, do not polish; route back to scope/design correction instead
20. AO worker instructions must explicitly include this order of operations so workers do not stop at diagnosis or polish while conflicts/serious blockers remain
21. Distinguish execution mode explicitly: PR-shaped work uses AO by default; non-PR planning/review/audit work uses parallel subagents by default
22. If AO does not make enough progress on a non-PR task, stop retrying it in AO and move that work to parallel subagents
23. If AO does not make enough progress on a PR-shaped support task, narrow the task once; if it still drifts, either handle it locally or reduce it to a smaller PR-shaped unit
24. For the current roadmap by default: `#6420` should remain an AO merge lane, while `#6418` supersede planning and `#6404` activation analysis should be treated as subagent-first work unless they need real branch mutation
25. Always compare the official roadmap queue against currently open related PRs and either drive them, park them, or create the missing PR-shaped lane needed by the roadmap
26. If `#6420` or `#6404` still does not have a truly on-track AO worker after one full cycle of direct steering or respawn, the next cycle must stop waiting on AO quality and use parallel subagents to drive the PR directly to its finish bar
