---
name: levelup
description: Trigger and monitor the level-up organic test (testing_mcp/core/test_level_up_organic.py) against the PR's deployed preview server.
scope: your-project.com level-up CI
---

# /levelup Skill

Run `testing_mcp/core/test_level_up_organic.py` — the real-server + real-LLM organic
level-up playthrough — either **locally** (default, via `local.sh`) or against a PR's
**deployed GCP preview server** (via `.github/workflows/levelup-tests.yml`). Mirrors the
`/smoke` pattern but specifically exercises the organic level-up flow end-to-end.

## When to Use

- After `/smoke` passes, to verify level-up flows on the PR
- When iterating on level-up prompt/code changes
- To get `## Real LLM Evidence` for PRs touching `$PROJECT_ROOT/prompts/level_up_instruction.md`

## Local Mode (default — `local.sh`)

For fast iteration on your own machine, run the organic playthrough against a freshly
auto-started local gunicorn server with real Firebase + the AGY CLI provider by default
(no mocks). Missing AGY setup fails closed with an `$PROJECT_ROOT/install.sh` instruction. The
helper `.claude/skills/levelup/local.sh` sets the required env
(`TESTING_AUTH_BYPASS=true`, `ALLOW_TEST_AUTH_BYPASS=true`, `PYTHONPATH`), scrubs leaked mock-enabling flags with a loud notice and continues, defaults to the full scenario sweep, and
passes any extra args straight through to the test:

```bash
# From repo root — all scenarios against an auto-started local server:
.claude/skills/levelup/local.sh

# A single scenario:
.claude/skills/levelup/local.sh --level-up-scenario single-organic

# Pick the character class / enable full evidence guards:
.claude/skills/levelup/local.sh --class-name wizard --full

# Target an existing server OR a GCP preview URL instead of auto-starting:
.claude/skills/levelup/local.sh --server https://mvp-site-app-s....run.app
```

Scenario choices: `single-organic`, `multi-organic`, `projected-button`, `god-reward`,
`atomicity`, `classifier`, `all` (default via `local.sh`). Evidence bundle lands at
`/tmp/<repo>/<branch>/test_level_up_organic/latest/` with streaming captures, LLM traces,
and per-scenario results. Use this for `/es` / `/er` evidence before the CI preview run.

## Preview Mode (CI — `workflow_dispatch` / `/levelup` comment)

## Trigger Method

The workflow has an `author_association` guard on `issue_comment` — post a
`/levelup` PR comment only if you are OWNER/MEMBER/COLLABORATOR. Otherwise use
`workflow_dispatch` (reliable, no association check):

```bash
gh workflow run levelup-tests.yml \
  --repo $GITHUB_REPOSITORY \
  --ref main \
  -f pr_number=<PR_NUMBER>
```

**Do NOT use `--ref feat/<branch>`** — the workflow must be reachable on the default branch.

## Monitoring

```bash
# Get the latest levelup run
gh run list --workflow=levelup-tests.yml --repo $GITHUB_REPOSITORY \
  --limit 3 --json databaseId,status,conclusion,createdAt \
  --jq '.[] | "\(.databaseId) \(.status) \(.conclusion) \(.createdAt)"'

# Watch a specific run
gh run watch <RUN_ID> --repo $GITHUB_REPOSITORY
```

## What It Runs

1. **Phase 1** (`resolve-pr-context`): resolves the PR head SHA and ref from GitHub API
2. **Phase 2** (`run-levelup-tests`): checks out the PR head, resolves the GCP preview URL,
   then runs `testing_mcp/core/test_level_up_organic.py` with `SKIP_CODEX_REVIEW=true`

The test itself runs all organic level-up scenarios (multi-level, god mode, finish intent, etc.)
against the preview service's configured live LLM provider + Firebase.

## Success Criteria

The workflow posts a PR comment starting with:
```
## ✅ Level-up Organic Tests Passed
```

or fails with:
```
## ❌ Level-up Organic Tests Failed
```

Check for the comment:
```bash
gh pr view <PR_NUMBER> --repo $GITHUB_REPOSITORY \
  --json comments --jq '.comments[-5:]|.[].body' | grep -E "(Level-up Organic|PASSED|FAILED)"
```

## Iterating on Failures

1. Read the failure comment body for the failing scenario name
2. Check the workflow logs:
   ```bash
   gh run view <RUN_ID> --repo $GITHUB_REPOSITORY --log | grep -A 20 "FAILED\|ERROR"
   ```
3. Fix prompt or code on the branch, push, then dispatch again:
   ```bash
   gh workflow run levelup-tests.yml --repo $GITHUB_REPOSITORY --ref main -f pr_number=<PR>
   ```

## Relationship to Smoke Tests

`/smoke` (11 general scenarios) and `/levelup` (level-up organic scenarios) are independent.
A PR must pass both before `/green` (CI green + no merge conflicts) plus draft-phase quality gates (`/es`, `/er`, `/advice`) are claimed for level-up changes.
