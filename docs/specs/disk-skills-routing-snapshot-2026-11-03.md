# Disk skill routing and snapshot-source correction

## Outcome

Keep quick capacity and reclaim estimates on `disk-audit`, route forensic root-cause questions through the full `diskm audit`, and make the two canonical disk skills describe the current `snapshots/disk_snapshot.json` source. Preserve existing cleanup approval and age-floor rules.

## Non-goals

No scripts, runtime code, tests, installed-skill changes, service changes, cleanup execution, or broad reconciliation of other divergent packages. Do not change the 14-day worktree caution or the forensic audit route.

## Acceptance

- `disk-magician` identifies the quick-check versus forensic route and labels its full audit as attribution-only.
- Quick-path freshness is determined from the owning tool output (`diskm ledger-freshness`), without a hardcoded interval in the skill.
- Root-cause work keeps the full three-lane audit; current and historical snapshot instructions use `snapshots/disk_snapshot.json`, with the frozen `backup/<host>/` layout identified as legacy.
- The root-cause example uses generic `df -h`; no mount path is tied to one host.
- The 14-day worktree caution, explicit `WORKTREE APPROVED` requirement, never-delete list, and command-specific approval gates remain. No approval token appears as a runnable command prefix.
- Cleanup examples use only verified read-only preview interfaces; `clean-all --dry-run` and the default report-only worktree-hygiene path remain discoverable.

## User stories

No user-facing application change. As an operator, I can get a quick capacity check without launching a forensic audit, and I can request a root-cause analysis that retains its full evidence path. As a cleanup reviewer, I can inspect candidates and skip reasons without examples that self-authorize deletion.

## Proof plan

- Review the owning Disk Magician policy and current disk-audit routing.
- Use the captured Linux CLI help and dispatch receipts at `/home/jleechan/Scratch/skills-parity-fullreport/diskm-help-receipts.txt` (SHA-256 `4d6fcecd7940a79fe2ff7c896780adf6c63fa8214e1075feef798c62b088df32`) for `ledger-freshness`, `clean`, `clean-all`, and `worktree-hygiene`.
- Run `git diff origin/main --check`; do not run tests or cleanup commands for this Markdown-only change.

## Mock or justified exemption

No UI, application flow, or runtime behavior changed. Mock evidence is not applicable; the CLI proof is help/source inspection only and does not claim cleanup behavior was exercised.

## Risk

CLI names and help can change. Keep the command-specific help as the source for available preview flags; freshness is tool-reported, not a fixed threshold. The snapshot location is host-owned and may move again. This patch does not install either skill or prove runtime activation.
