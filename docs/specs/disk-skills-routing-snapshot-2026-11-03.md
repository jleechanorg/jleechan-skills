# Disk skill routing and snapshot-source correction

## Outcome

Keep quick capacity and reclaim estimates on `disk-audit`, route forensic root-cause questions through the full `diskm audit`, resolve the active state repo through `diskm state status`, and cover both current and legacy snapshot layouts. Preserve existing cleanup approval and age-floor rules.

## Non-goals

No scripts, runtime code, tests, installed-skill changes, service changes, cleanup execution, or broad reconciliation of other divergent packages. Do not change the 14-day worktree caution or the forensic audit route.

## Acceptance

- `disk-magician` identifies the quick-check versus forensic route and labels its full audit as attribution-only.
- Quick-path freshness follows the owning tool's `OK`/`STALE`/`UNKNOWN` output from `diskm ledger-freshness`; missing input also escalates to the full audit.
- Root-cause work keeps the full three-lane audit. `diskm state status` supplies the active state repo root; the installed resolver prefers `snapshots/disk_snapshot.json` and falls back to legacy `backup/<host>/disk_snapshot.json` only when needed. Historical search covers both paths and compares timestamps when both exist in a commit.
- The root-cause example uses generic `df -h`; no mount path is tied to one host.
- The 14-day worktree caution, explicit `WORKTREE APPROVED` requirement, never-delete list, and command-specific gates for cleanup mutations and WIP publication remain. Approval variables are not shown as runnable command prefixes.
- Cleanup examples use only verified read-only preview interfaces; `clean-all --dry-run` and the default report-only worktree-hygiene path remain discoverable.

## User stories

No user-facing application change. As an operator, I can get a quick capacity check without launching a forensic audit, and I can request a root-cause analysis that retains its full evidence path. As a cleanup reviewer, I can inspect candidates and skip reasons without examples that self-authorize deletion.

## Proof plan

- Review the owning Disk Magician policy and current disk-audit routing.
- Verify state-root resolution, snapshot paths, preview commands, and documented action gates against the owning Disk Magician source and CLI help; bind any published receipt to the reviewed candidate.
- Run `git diff --check` plus structural and relative-link checks; do not run tests or cleanup commands for this Markdown-only change.

## Mock or justified exemption

No UI, application flow, or runtime behavior changed. Mock evidence is not applicable; the CLI proof is help/source inspection only and does not claim cleanup behavior was exercised.

## Risk

CLI names and help can change. Keep the command-specific help as the source for available preview flags; freshness is tool-reported, not a fixed threshold. The state repo root is configuration-dependent, and the snapshot resolver owns new-layout versus legacy fallback. This patch does not install either skill or prove runtime activation.
