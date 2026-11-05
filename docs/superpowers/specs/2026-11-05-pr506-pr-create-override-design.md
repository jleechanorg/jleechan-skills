# PR creation override behavior

## Outcome

The existing PR quantity hook enforces its documented split and stacked-PR
ceilings while honoring an explicit override supplied through the process
environment or as an assignment prefix to `gh pr create`.

## Non-goals

- Do not add, change, or widen a PR quantity ceiling.
- Do not change the hook's existing fail-open behavior or GitHub query.
- Do not install or activate the hook on a host.

## Acceptance

- A text mention of `ALLOW_PR_STACK_OVERRIDE=1` elsewhere in a command does not
  authorize a capped PR creation.
- An actual `ALLOW_PR_STACK_OVERRIDE=1` assignment immediately before the
  matching `gh pr create`, an `env` assignment prefix, or the process environment
  continues to allow the explicitly authorized operation.
- Existing below-cap requests pass; requests at the existing split and stacked
  caps block without an override.

## User story

No player-facing behavior changes. An agent creating a PR at a hard cap can
proceed with an explicit operator override; command text that merely mentions
the override cannot silently bypass the cap.

## Proof plan

Run the focused executable hook checks against the published source to establish
the false-override failure, then rerun them after the parser change. Keep PR-list
data mocked and use a local `gh` stub so checks cannot reach GitHub. Also run the
repository's focused Markdown/link checks and `git diff --check` for the merge.

## Mock or exemption

Use the hook's existing `PROTECT_PR_CREATE_MOCK_JSON` fixture to supply open PR
rows. A `gh` stub in a temporary test directory fails if the hook bypasses the
fixture; no live network or PR mutation is needed.

## Risk

The existing hook fails open when GitHub cannot be queried. This change does not
alter that behavior or the existing hard caps. It narrows only what counts as an
explicit override, preventing an incidental command-string mention from
disabling the existing check.
