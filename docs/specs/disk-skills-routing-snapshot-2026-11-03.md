# Disk skill routing and snapshot-source correction

## Outcome

Keep quick capacity and reclaim estimates on `disk-audit`, route forensic root-cause questions through the full `diskm audit`, and make the two canonical disk skills describe the current `snapshots/disk_snapshot.json` source. Preserve existing cleanup approval and age-floor rules.

## Non-goals

No scripts, runtime code, tests, installed-skill changes, service changes, cleanup execution, or broad reconciliation of other divergent packages. Do not change the 14-day worktree caution or the forensic audit route.

## Acceptance

- `disk-magician` states that missing or tool-reported-stale quick-path inputs escalate to the full audit; it uses the `diskm ledger-freshness` result rather than a fixed age.
- Forensic root-cause work keeps the full three-lane `diskm audit` method.
- `diskm state status` prints the active state repo root in human-readable output; use its `state repo:` value for the current snapshot and Git history, without assuming JSON or creating a resolver. The canonical reader/writer use `snapshots/disk_snapshot.json`; the resolver, not the skill, owns legacy fallback.
- The root-cause example uses generic `df -h`; no mount path or state-repo default is hardcoded.
- The 14-day worktree caution, explicit `WORKTREE APPROVED` requirement, never-delete list, and approval gates for every non-preview mode remain. Approval variables are not shown as runnable prefixes.
- Cleanup examples use verified previews; `clean-all --dry-run` and default report-only `worktree-hygiene` remain discoverable.

## User stories

No user-facing application change. As an operator, I can get a quick capacity check without launching a forensic audit, and I can request a root-cause analysis that retains its full evidence path. As a cleanup reviewer, I can inspect candidates and skip reasons without examples that self-authorize deletion.

## Proof plan

- Review the owning Disk Magician policy and current disk-audit routing.
- Use the corrected CLI help/source receipt (SHA-256 `142c9a7f6d10c174e1e19770bacbe26538324ec077a423f070df75588886747f`) for `ledger-freshness`, `clean`, `clean-all`, and `worktree-hygiene`; it records that `clean --help` fell through to the default dry-run preview and no cleanup was executed. Link the receipt in the PR body.
- Use the source-bound state-root receipt (SHA-256 `a8ae07292f7c7dc894a484944a37d641f04cb63572e55b5e1e4fe55fb2fcedc2`) for source revision, resolver/config precedence, writer/reader paths, configured Mac root, XDG-default Linux root, current status, and snapshot hashes. The source revision is `ded05f64df9364503fde0bf0e043b446b4bbffff`; installed resolver/reader/writer hashes match it on both hosts.
- Run `git diff origin/main --check`; do not run tests or cleanup commands for this Markdown-only change.

## Mock or justified exemption

No UI, application flow, or runtime behavior changed. Mock evidence is not applicable; the CLI proof is help/source inspection only and does not claim cleanup behavior was exercised.

## Risk

CLI names and help can change. Keep the command-specific help as the source for available preview flags; freshness is tool-reported, not a fixed threshold. The snapshot location is host-owned and may move again. This patch does not install either skill or prove runtime activation.
