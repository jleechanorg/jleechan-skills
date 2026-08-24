---
description: Deterministically trigger a Bugbot CI run for its optional advisory feedback.
type: action
scope: project
---

# Wake Bugbot (/wakebugbot)

## Purpose
Bugbot is an **optional advisory reviewer** — it never gates or blocks `/green`
or merge (see `.claude/skills/pr-green-definition.md`). This command is a
convenience for getting Bugbot's feedback when it hasn't triggered on its own
(reporting `Bugbot=none status=none`), by injecting an empty trigger commit.
Use it when you want Bugbot's input, not because anything is stalled on it.

## Execution Requirements
1. The current branch MUST be a PR branch.
2. The PR MUST be out of draft state.
3. The branch MUST have no unpushed commits before running the trigger.

## Action Steps

Execute these steps deterministically:
1. Verify the current branch is tied to a PR and not draft:
```bash
gh pr view --json number,isDraft,headRefName --jq '
  if .isDraft then error("PR is draft; wakebugbot requires ready-for-review PR") else .number end
'
test "$(git rev-parse --abbrev-ref HEAD)" = "$(gh pr view --json headRefName --jq .headRefName)"
```
2. Verify deterministic clean state (no staged changes and no unpushed commits), then push an empty commit with the exact trigger message:
```bash
if ! git diff --cached --quiet; then
  echo "Error: You have staged changes. Please commit or unstage them before running /wakebugbot."
  exit 1
fi
if [ "$(git rev-list --count @{upstream}..HEAD 2>/dev/null || echo 0)" -ne 0 ]; then
  echo "Error: You have unpushed commits. Push or isolate them before running /wakebugbot."
  exit 1
fi
git commit --allow-empty -m "trigger bugbot"
git push origin HEAD
```
3. Verify that the workflow has restarted: `gh run list --limit 3`
4. Report success to the user.
