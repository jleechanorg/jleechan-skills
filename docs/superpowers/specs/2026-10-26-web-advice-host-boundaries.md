# Web-advice and shared policy boundaries

## Outcome
Align the shared web-advice, browser-use, Dot recovery, lifecycle, and shared-policy instructions with their current canonical ownership contracts while preserving supported review and merge behavior.

## Non-goals
No runtime code, scripts, tests, CI, live profile or credential changes, provider calls, deployments, merges, or product UI changes. Do not change the existing web-advice transport helper in this documentation scope. PR-body updates and final review/readiness gates remain with the PR coordinator.

## Acceptance
- Browser guidance uses the canonical task-owned context, isolation, and authentication contracts; it does not route through a personal/default browser or transfer cookies without the required authorization.
- Web-advice retains its real-browser packet, response-coverage, and quorum requirements; transport guidance does not substitute API, CLI, or inference for a required browser review.
- Shared and lifecycle merge wording follows the shared size-tiered owner and preserves stricter repository-specific approval and delegated-worker restrictions.
- Dot logout recovery uses same-profile restore only while Chrome is stopped and verifies with read/probe. Visible login requires explicit current-thread authorization and an independently verified task-owned profile separate from personal/default Chrome; otherwise report the scoped authentication blocker. No cookie transfer or alternate-browser fallback is introduced.
- Implementation changes remain limited to the seven approved instruction files: `.claude/skills/web-advice/SKILL.md`, `.claude/skills/web-advice/references/browser-transports.md`, `.claude/skills/claude-code-computer-use/SKILL.md`, `.claude/skills/antigravity-computer-use/SKILL.md`, `md_files/AGENTS.shared.md`, `.claude/skills/pr-lifecycle/SKILL.md`, and `.claude/skills/dot/SKILL.md`. This specification is the sole additional committed artifact.

## User story
An agent or reviewer following these instructions can choose an authorized browser context, recover a Dot session without exposing a personal profile, and apply the correct web-advice and merge gates. No player-facing behavior or UI changes, so no product mock applies.

## Proof plan
Review the full changed Markdown against the canonical browser-control, web-advice, and lifecycle owners; verify linked paths and the four acceptance scenarios above. Run the existing focused approval/lifecycle contract suite and `git diff --check`; inspect the exact PR diff, line classification, clean worktree, remote head, and merge-tree result. Source policy checks do not claim runtime enforcement or prove a real browser/provider session.

## Mock exemption
This PR changes agent instructions only. It has no player-visible or product UI output; no mock or visual evidence is applicable. Existing contract tests are document-level checks, not runtime evidence.

## Risk
Conflicting or underspecified policy could misroute authenticated review, expose browser state, or weaken approval gates. Keep canonical owners explicit and preserve stricter local restrictions. The documentation does not change the separate unused-by-skill transport helper, so it must not be reported as runtime enforcement of this policy.
