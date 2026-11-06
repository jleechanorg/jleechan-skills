# PR #706 specification: on-demand lifecycle details

## Outcome

Reduce the default PR lifecycle skill context while preserving its current rules and making detailed guidance available when needed.

## Non-goals

- Change review routing, evidence requirements, reviewer quorum, merge authority, or PR command behavior.
- Change application or player-facing behavior.
- Add a second helper for computing documentation-only PR paths.
- Claim that moving text reduces the total amount of lifecycle documentation.

## Acceptance

- The lifecycle root points to on-demand files for the six-stage workflow, proportional exceptions, and PR-body review records.
- Updated sibling references resolve to the file and heading that own each moved section.
- The PRW profile includes the moved Markdown parts and retains the existing executable pr-base-changed-paths.sh helper.
- Documentation-only guidance reuses that existing helper; it does not ship docs-only-paths.sh.
- The current main-line Markdown instruction-only route and its publication exceptions remain intact.
- The diff contains no production application or service logic.

## User story

No application UI change: this changes agent guidance and its installer package, not the WorldArchitect player journey.

## Proof plan

- Run `python3 -m unittest tests.test_coding_lifecycle_contract -q` for lifecycle section references and anchors.
- Run `python3 -m unittest tests.test_installer.InstallerRealProfileTest.test_prw_profile_carries_the_pr_workflow_set -q` for package membership and executable-bit checks on the existing helper and moved parts.
- Use the repository `contract-tests` workflow for the full contract suite.
- Inspect the complete base-to-head diff, run `git diff --check`, and verify conflict resolutions have a committed resolution record.

## Mock or exemption

Mock application tests are not applicable because this change adds no application or service behavior. The focused tests inspect the real source tree and installer packaging logic.

## Risk

A stale link or omitted installed part could make lifecycle guidance unavailable. The focused reference and installer tests cover those boundaries. The path-enumeration behavior remains owned by the existing helper and is not a new behavior claim in this PR.
