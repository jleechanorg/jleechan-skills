# PR creation override behavior

## Outcome

The checked-in Bash `PreToolUse` hook enforces the existing split and stacked-PR
ceilings while honoring an explicit override supplied through the process
environment or as an assignment prefix to `gh pr create`.

## Non-goals

- Do not add, change, or widen a PR quantity ceiling.
- Do not change the hook's existing fail-open behavior or GitHub query.
- Do not install or update the user-level global hook; register only the
  project-scoped hook in checked-in settings.

## Acceptance

- A text mention of `ALLOW_PR_STACK_OVERRIDE=1` elsewhere in a command does not
  authorize a capped PR creation.
- An actual `ALLOW_PR_STACK_OVERRIDE=1` assignment immediately before the
  matching `gh pr create`, an `env` assignment prefix, or the process environment
  continues to allow the explicitly authorized operation.
- The checked-in `.claude/settings.json` registers the hook for Bash
  `PreToolUse`, and an integration test invokes that configured command.
- Existing below-cap requests pass; requests at the existing split and stacked
  caps block without an override.
- A bare `split/<feature>` branch does not consume the per-series split cap;
  unrelated `split/<other>/*` rows are counted separately.
- Comments and later commands cannot hide a stacked PR creation or change its
  parsed flags. Attached `-Rowner/repo` is still recognized.
- When `--base` is omitted, the current branch's configured
  `gh-merge-base` determines whether the request is stacked.

## User story

No player-facing behavior changes. An agent creating a PR at a hard cap can
proceed with an explicit operator override; command text that merely mentions
the override cannot silently bypass the cap.

## Proof plan

Run the focused executable hook checks against the published source to establish
the false-override and parser failures, then rerun them after the parser change.
Run the registered Bash `PreToolUse` command against the same local fixture.
Keep PR-list data in a test-only `gh` stub so checks cannot reach GitHub. Also
run focused installer/portability checks, source-link checks, and
`git diff --check` for the merge.

## Mock or exemption

Tests place a local `gh` stub first on `PATH`; it returns fixture rows for
`gh pr list` and fails for other commands. The production hook has no
test-only environment bypass, and the tests make no live network calls.

## Risk

The existing hook fails open when GitHub cannot be queried. This change does not
alter that behavior or the existing hard caps. It narrows only what counts as an
explicit override, preventing an incidental command-string mention from
disabling the existing check.
