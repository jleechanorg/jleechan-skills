# Cross-repo AO PR-drive cookbook

Verified 2026-07-08 driving **49 non-draft PRs across 7 repos** with direct `ao spawn --claim-pr` fanout: 2 MERGED, 6 CLEAN+APPROVED, 9 CLEAN, 25 UNSTABLE, 7 CONFLICTING after one ~45-min burst with 30 parallel AO workers.

This is the operational recipe for "drive every non-draft PR to /green + /er" when the scope spans multiple repos (which is the common case for any real fleet).

AO has a per-project spawn lock, so call `ao spawn -p <project> --claim-pr <N>` directly for each project.

## Recipe: cross-repo fanout

```bash
# Per-project: claim each PR (sequential, ~5-8 min per PR due to per-project lock)
PRS="754 753 752 751 750"
for pr in $PRS; do
  ~/bin/ao spawn -p jleechanclaw --claim-pr $pr \
    "drive PR #$pr to /green + /er — push to existing branch only, do not open new PR, do not merge"
done
```

For multiple projects, run the loop **in parallel** (one bash script per project — different projects have no cross-project lock).

## Required `env -i` wrapper for safe spawning

```bash
cd $HOME
export HOME="$HOME"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin"
unset GH_TOKEN GITHUB_TOKEN AO_BOT_GH_TOKEN    # CRITICAL: let gh use ~/.config/gh/hosts.yml
export AO_MAX_CONCURRENT_SESSIONS=80          # raise default cap=20 for burst
```

Failing to unset `GITHUB_TOKEN` causes every spawn to fail with "✗ GitHub CLI is not authenticated" — see `agento` skill pitfall #1.

## Adding a new project to agent-orchestrator.yaml

When the user has a repo with no AO project entry (e.g., `jleechanorg/.github`, `jleechanorg/browserclaw`):

```yaml
projects:
  github-org:
    name: github-org
    path: ~/projects/dot-github         # REQUIRED — Zod rejects without it
    repo: jleechanorg/.github          # Note: `.github` cannot be the project ID (Zod keys can't start with `.`)
    defaultBranch: main
    agentRules: "You are working in the jleechanorg/.github repo..."
```

Then prepare the on-disk path:
```bash
mkdir -p ~/projects/dot-github && cd ~/projects/dot-github
git init && git remote add origin https://github.com/jleechanorg/.github.git
git fetch origin main && git checkout main
```

Restart AO to load the new project (existing in-flight sessions are orphaned):
```bash
ao stop
cd <some-project> && ao start <new-project> --no-dashboard --no-open
```

## Verifying a fanout is alive

Don't rely on `tail -3` in scripts — it buffers indefinitely while `ao spawn` is in flight. Read session state directly via `ao session ls` or in batch via:

```python
import subprocess, re
out = subprocess.run(["ao","session","ls"], capture_output=True, text=True).stdout
covered = set()
for line in out.split('\n'):
    for m in re.finditer(r'pulls/(\d+)', line):
        covered.add(int(m.group(1)))
```

Workers that lack `--claim-pr` show up as `<session-id>` not `<session-id>  [...pulls/N]`. Detect and re-spawn.

## Conflict-rebase dispatcher

For PRs with `mergeable=CONFLICTING`, spawn a worker with explicit rebase instruction:

```bash
~/bin/ao spawn -p <project> --claim-pr <N> \
  "drive PR #<N> (CONFLICTING) to /green + /er — REBASE onto origin/main first \
   (git fetch && git rebase origin/main --force-with-lease), resolve any remaining \
   conflicts and push. Push to existing branch only; do not open new PR; do not merge"
```

If the project is `paused` due to model rate limit, the spawn returns immediately:
```
✗ Project is paused due to model rate limit until <ts>
```

These unblock automatically when the LLM provider's quota resets. Don't retry-spam.

## What success looks like (this run, 2026-07-08)

After ~45 min from spawn start:

| Outcome | Count | Repos |
|---|---|---|
| MERGED | 2 | WA |
| CLEAN + APPROVED (merge-ready) | 6 | claw (4), df (2) |
| CLEAN (no review yet) | 9 | WA (3), auf (3), df (1), browserclaw (1), .github (1) |
| UNSTABLE (CI still running) | 25 | mostly WA + claw |
| CONFLICTING | 7 | WA (2), claw (3, rate-limited), auf (1, rate-limited), browserclaw (1) |

The "drive to green" loop completes on a per-PR basis over the next 20-60 min as workers push fixes and CI flakiness settles. Set a babysit cron to monitor:

```python
hermes cron create "20m" --name "af-batch-status (20m)" --deliver "slack:<chan>:<thread_ts>"
```

## When NOT to do this

- **Single PR fix**: just spawn one AO worker, don't batch.
- **PRs needing human approval first**: the `/er` evidence gate requires PRs to be production-tier and have real evidence. The drive pattern produces mergeable PRs but doesn't auto-merge — `MERGE APPROVED` from the human is still required.
- **When the user wants to skip CI**: this drive pattern runs the full 7-green gate. If the user wants to bypass (e.g., for WIP drafts), use a different workflow.
