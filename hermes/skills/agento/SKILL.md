---
name: agento
version: 1.5.0
description: Delegate coding change tasks to Agent-Orchestrator (AO). Triggered by the keyword "agento" anywhere in a message, or by default for any coding task. Never use mctrl unless explicitly requested. Default worker is `MiniMax-M2.7` via `agent-minimax` plugin — do NOT assume "Sonnet" or "Claude" without verifying against `agent-orchestrator/AGENTS.md`. Aliases `/a`, `/fullrun`, `/finish`, `/f` are all no-confirmation triggers — see §⚠️ EXECUTION RULE below for the canonical forbidden-pattern list.
---

# agento

Use this skill by default for coding change requests.

## Spawn-time model preflight (MANDATORY — see `references/spawn-model-preflight.md`)

An `ao spawn` worker boots, the harness prints the chosen model, and only after the prompt is sent does the worker hit a provider-side rate/usage limit. Verified 2026-07-20 in `C0AH3RY3DK6/1782336926.897789` — both a Codex worker and a parallel `codex exec` died with `You've hit your usage limit`. Run the preflight BEFORE every spawn: probe tier, send a low-timeout heartbeat, downgrade to a cheaper available tier if rate-limited, kill + respawn on a different harness if the worker stays `idle > 90s`.

## Spec-soundness gate before PR-N+1 (MANDATORY)

When a fix-PR lands the **reducer / contract layer** and a follow-on PR will consume a richer spec from the design doc, run an `/advice` source-accuracy review (or delegate it as Reviewer A) BEFORE the follow-on PR is dispatched. If the implementation contract diverges from the design, fix the implementation in the fix-PR — do not let the follow-on PR inherit ambiguity. Verified 2026-07-20 on the auto-level-up train: PR 8476 shipped `apply_character_adjustment()` gated on `auto_applied AND review_open` (selection-key amendment only), while merged design PR 7927 §2.1 Change 3 mandated an always-on reducer with `fields_locked=["level","experience.current"]`. That ambiguity is what turns a 3-PR plan into a 5-PR recovery.

## When to use

Route coding change requests through Agent-Orchestrator unless the user explicitly asks for mctrl.
Examples:
- "agento spawn worldai-claw-agento fix the login bug"
- "agento status"
- "agento send wa-abc1234 please push your changes"
- "agento fix PR 5879"
- "agento make this PR good"
- "agento keep fixing comments and CI until merge-ready"

## Worktree Requirement

**agento MUST always use a new git worktree** for agent sessions, unless already running inside an AO-managed worktree or session.

- The AO workspace plugin (`worktree`) is configured in `agent-orchestrator.yaml` with `workspace: worktree` for all projects
- Each spawn creates an isolated worktree in `~/.worktrees/<projectId>/<sessionId>/`
- This ensures agents never run directly in the base repo working tree
- Verify: if inside a worktree, `git rev-parse --git-common-dir` should point to the parent repo's .git

## CI & PR Comment Auto-Resolution

**agento automatically resolves CI failures and PR review comments** by default. This is configured in `agent-orchestrator.yaml` reactions:

```yaml
reactions:
  ci-failed:
    auto: true
    action: send-to-agent
    retries: 3
  changes-requested:
    auto: true
    action: send-to-agent
    escalateAfter: 10m
  bugbot-comments:
    auto: true
    action: send-to-agent
    escalateAfter: 30m
```

When AO detects:
- A CI check failure → spawns an agent to fix the issue
- Review comments requesting changes → spawns an agent to address them
- Bugbot comments → spawns an agent to investigate

The agent uses the project's `agentRules` which prioritize:
1. Resolve review comments with minimal safe changes
2. Fix failing CI checks
3. Push fixes and update PR

## AO CLI path

```
~/bin/ao
```

## AO Working Directory (Required)

Run AO commands from:

```bash
cd ~/.hermes
```

`ao` resolves the config via a walk-up overlay:
1. Looks for `agent-orchestrator.yaml` in the current directory (or symlinks at `~/agent-orchestrator.yaml`).
2. The **canonical config** lives at `~/.hermes_prod/agent-orchestrator.yaml` (a symlink at `~/agent-orchestrator.yaml` points to it).
3. The stub at `~/.hermes/agent-orchestrator.yaml` is a small base of a few private-org projects that gets **overlaid** by the canonical config. (For the private-org project names + token plumbing, load the machine-local `agentf` companion skill.)

**Pitfall — do NOT add new project entries to `~/.hermes/agent-orchestrator.yaml`:** The overlay merges per-project by config key, but uniqueness is checked by `basename(project.path)`. Adding a `worldai` project there with path `$HOME/repos/$GITHUB_REPOSITORY` will collide with the canonical `worldarchitect` project (path `~/projects/your-project.com`) — both basenames are `your-project.com`. You'll get `Error: Duplicate project ID detected: "your-project.com"`. The fix: use the existing canonical project name (`worldarchitect`, `jleechanclaw`, etc.) instead of adding a new local one.

## Available projects (from canonical config `~/.hermes_prod/agent-orchestrator.yaml`)

- `agent-orchestrator` — jleechanorg/agent-orchestrator-ts fork
- `browserclaw` — jleechanorg/browserclaw
- `claude-commands` — jleechanorg/claude-commands
- `hermes-agent` — jleechanorg/hermes-agent
- `jleechanclaw` — jleechanorg/jleechanclaw orchestration repo
- `llm_wiki` — jleechanorg/llm-wiki
- `mcp-mail` — jleechanorg/mcp_mail
- `mctrl-test` — jleechanorg/mctrl_test (legacy)
- `openclaw-sso` — jleechanorg/openclaw_sso
- `ralph` — jleechanorg/ralph
- `worldai-claw` — jleechanorg/worldai_claw
- `worldarchitect` — $GITHUB_REPOSITORY (Python/Flask game backend) ← use this for all WA work
- `worldclaw-dev` — jleechanorg/worldai_claw (v1.7 branch)

**If PR has no matching project:** Verify the canonical config is being loaded (`cat ~/.hermes_prod/agent-orchestrator.yaml | grep "<repo-keyword>"`). All common repos are already there. Spawn directly with the existing project name — do not add a duplicate entry.

**Project-id rule — short names, not GitHub slugs:** The `-p` / `--project` flag takes the **short project key from the canonical config above** (e.g. `worldarchitect`), NOT the GitHub slug (`$GITHUB_REPOSITORY`) and NOT the repo name with the org prefix (`your-project.com`). Verified 2026-06-12 on PR #6873 dispatch: passing `--project your-project.com` errors with `Unknown project: your-project.com — Available: agent-orchestrator, ..., worldarchitect, ...`. When in doubt, enumerate: `yq -r '.projects | keys | .[]' ~/.hermes_prod/agent-orchestrator.yaml`.

**Per-project concurrent-spawn lock:** AO enforces a single in-flight `ao spawn` per project. If a second `ao spawn --project <id>` fires while the first is still in its "Creating session" phase, it fails with `Another ao spawn is in progress for project "<id>" (PID <pid>, started <ts>). Wait for it to finish.` This is the *correct* behavior — two concurrent spawns on the same project can both create worktrees and race on the `.worktrees/<project>/` directory. Pattern when blocked by a peer spawn: poll `ps -p <pid>` every ~5s; once it's gone, retry. The lock releases within seconds of the first spawn printing its `✔ Session <id> created` line. Don't pre-emptively cancel your spawn; just wait.

**`--claim-pr` does NOT accept `--task`:** Verified 2026-06-12. The CLI parses `--claim-pr` as a flag, not a subcommand, so `--task` is unknown. The task text goes as the **positional argument** after the flag pair: `ao spawn -p <project> --claim-pr <N> "<task text>"`. If your task is long, see the "Long Task Briefs" section below — write it to `/tmp/` and pass a short summary as the positional arg instead.

**`--claim-pr auto` is NOT supported and produces an orphaned worktree.** Verified 2026-06-27 02:35 PT (this turn, follow-up spawn for D2/D5). When you spawn a NEW PR (no existing PR number yet), omit `--claim-pr` entirely — the AO worker will create the PR from its branch. Passing `--claim-pr auto` (or any non-numeric token) results in two failures chained:
1. `gh api repos/jleechanorg/<repo>/pulls/auto` returns 404, the worker session is created but flagged `failed`.
2. The retry without `--claim-pr` succeeds but AO thinks the worktree path `~/.worktrees/<project>/jc-NNNN` is already in use, and fails again: `Found existing worktree for orchestrator branch "<name>" at "<path>", but it is outside AO-managed worktree directories. Reuse it manually or remove it and try again.`
3. Manual cleanup: `rm -rf ~/.worktrees/<project>/jc-NNNN && git worktree prune`. Verified recovery works.

**Pattern for new-PR / new-script spawns:** just `ao spawn -p <project> "<task>"` — no `--claim-pr`. The worker creates the PR as part of its work.

## Architecture: AO is the lane for code change work, NOT mctrl

`mctrl` is the durable jleechanclaw orchestration layer (supervisor + notifier + reconciliation). It owns the canonical task source of truth for jleechanclaw's own reliability roadmap. But for **any code-change or PR work** — including private-org, worldarchitect, and jleechanorg repos — the right path is plain AO (`ao spawn`). Do not route through `mctrl supervisor` for completion notifications of coding tasks. The frontmatter above is explicit: "Never use mctrl unless explicitly requested." When you finish a dispatch, just say "Spawned `aa-2` for PR #170" — do not invoke mctrl supervisor language.

**mctrl is also deprecated as a product name (Jeffrey 2026-06-09).** If a user asks to "purge mctrl" or "remove mctrl references", load the `legacy-term-deprecation-sweep` skill — it has the workflow (catalog before purge, skip frozen artifacts, handle live launchd plists separately) and the 2026-06-09 catalog for the jleechanclaw workspace. Do not bundle a mctrl sweep into a code-change PR — keep it as its own sequenced plan.

## Private-org dispatch (account + token plumbing)

Some repos live under a **separate private GitHub account / org** that AO's
default bot token (`AO_BOT_GH_TOKEN`) cannot see, so `--claim-pr` returns 404
unless you override the token. The full token-override spawn pattern, project
base stub, and self-push / gist-authoring plumbing for that private org are
documented in the machine-local **`agentf` companion skill** (`skills/agentf/SKILL.md`,
not tracked in this repo). Load it whenever a dispatch targets one of those
private-org repos.

If `ao start` hangs when registering a project, the repo is likely already
cloneable manually — clone to `~/.worktrees/<project>-main` directly, add a
project entry to `agent-orchestrator.yaml`, and the lifecycle worker is usually
already running (verify with `pgrep -fl lifecycle-worker`). If `ao spawn` still
complains "lifecycle polling is inactive", write `~/.agent-orchestrator/running.json`
by hand — see the `running.json` bootstrap section below for the JSON template.
- See the babysitting scripts at `skills/hermes-imports/dispatch-task/scripts/babysit-one-session.sh` and `multi-session-babysit.sh` to babysit an AO worker and post progress to a Slack thread.

## Commands

### Spawn a new agent session

Each spawn creates a **fresh git worktree** automatically (default behavior from agent-orchestrator.yaml). The worktree is created in `~/.worktrees/<project>-<session>/`.

**Pitfall — `ao spawn <project>` (positional) is REMOVED. Use `-p <project>`.** Verified 2026-06-13 on PR #7534 dispatch: the CLI now refuses the old form with:
```
⚠ 'ao spawn <project> <issue>' is no longer supported.
  Use an explicit project flag instead:
    ao spawn -p <project> ...
```
Don't pre-flight this — the error is cheap and AO still completes the spawn after you retry with `-p`.

**Pitfall — `ao spawn` (no `-p`) from outside a project dir prints the full project list and exits 1.** When cwd is not inside any project (e.g. `/tmp/wa-7684-dice-fix` worktree that's not registered), `ao` cannot auto-resolve a project and prints:
```
Multiple projects configured. Specify one: agent-orchestrator, claude-commands, ai-universe-lite, cmux, dark-factory, heretic-lab, jleechanclaw, mcp-mail, mctrl-test, merge_train, openclaw-sso, ralph, smartclaw, worldai-claw, worldarchitect
Or run from within a project directory.
```
**Fix:** always pass `-p <short-project-key>` explicitly (e.g. `-p worldarchitect`). Don't rely on cwd auto-detection when in a worktree.

**Pitfall — there is no `--bead` flag.** Verified 2026-06-13 (ao-6363 dispatch): passing `--bead $USER-urq` errors with `error: unknown option '--bead'`. The bead ID is the **first positional argument** after `-p <project>`. The full flag list lives in `ao spawn --help` and the canonical "what flags exist" reference is `dispatch-task` → `references/ao-spawn-quickstart.md` §5 Anti-patterns. Verified pattern:

```bash
# CORRECT — bead is positional, no --bead flag
cd ~/.hermes && ~/bin/ao spawn -p worldarchitect $USER-s9p

# WRONG — CLI rejects with "unknown option '--bead'"
cd ~/.hermes && ~/bin/ao spawn -p worldarchitect --bead $USER-s9p
```

```bash
cd ~/.hermes && ~/bin/ao spawn -p worldarchitect <issue-id>
```

For a freeform task (no issue number), omit the issue argument:
```bash
cd ~/.hermes && ~/bin/ao spawn -p worldarchitect
```

### Spawn for existing PR work (REQUIRED for PR comment/CI remediation)

When the intent is "fix PR comments/CI on PR #N", never pass `N` as the positional issue argument.
Always claim the PR explicitly:

```bash
cd ~/.hermes && ~/bin/ao spawn -p worldarchitect --claim-pr <pr-number>
```

Optional (assign to current GitHub user during claim):

```bash
cd ~/.hermes && ~/bin/ao spawn -p worldarchitect --claim-pr <pr-number> --assign-on-github
```

**Pitfall — `--claim-pr` expects a PR number, NOT an issue number.** If you pass an issue number (`--claim-pr 7415` when 7415 is an `gh issue create`, not a `gh pr create`), AO runs `gh api repos/<owner>/<repo>/pulls/7415` and gets back `404 Not Found` — not a friendly "issue not found." The error surface is the same 404 you'd get for a private repo or a wrong number, so the diagnostic is "check `gh pr view <N> --repo <owner>/<repo>` first; if it errors, you have an issue number, not a PR number." For issues, omit `--claim-pr` and let the worker `gh pr create` itself. (Verified 2026-06-09, GH issue #7415 → fix: drop `--claim-pr`.)

### Check status of all sessions

```bash
cd ~/.hermes && ~/bin/ao status
```

### Send a message to a running session

```bash
cd ~/.hermes && ~/bin/ao send <session-id> "<message>"
```

### List sessions

```bash
cd ~/.hermes && ~/bin/ao session ls
```

## ⚠️ COMMON CONFUSIONS — AO HAS NO WORKER-COUNT CAP

**There is no AO worker-count cap.** `ao spawn` is unbounded by config — bounded only by host tmux/process capacity, load average, and disk. Verified 2026-06-23: `ao status --project worldarchitect` showed 17 active `wa-*` sessions running concurrently with no spawn rejection. `ao spawn --help` has no `--max-workers`, `--max-concurrent`, or `--cap` flag; `~/.hermes_prod/agent-orchestrator.yaml` has no `max_*` keys.

**If you find yourself reasoning "the cap is N, spawn will be blocked"** — you have read one of these and projected it onto AO. None of them is the AO worker ceiling:

| Source | What it actually is | Why it is NOT the AO worker cap |
|---|---|---|
| `~/.hermes/roadmap/VALUE_ROUTER_DESIGN.md:14` (`MAX_CONCURRENT_AGENTS = 5` in `services.ts`) | **Proposed design** for a future value-router service | Roadmap future-plan, not live code |
| `~/.hermes/skills/jleechanclaw-eloop.md:133` ("if active sessions >= 5, skip dispatching this cycle") | **Per-loop dispatch throttle** for the jleechanclaw kanban eloop | Local heuristic for one orchestrator, not AO |
| `agents.defaults.maxConcurrent=10` in `~/.hermes_prod/config.yaml` | **Hermes gateway agent slots** — not AO workers | Different system entirely (Slack/Discord bot, not the thing that spawns `wa-*` tmux sessions) |
| `delegation.max_concurrent_children=3` | **Hermes subagent fan-out per parent agent run** | Nested subagent limit inside a single Hermes run, not an AO ceiling |

**Verification recipe when in doubt:**

```bash
# Live AO worker count
ao status 2>/dev/null | grep -cE '\b(wa|cc|jc|co)-[0-9]+'

# Active only (excluding dead/stopped/done)
ao session ls 2>/dev/null | grep -E '\b(wa|cc|jc|co)-[0-9]+' | grep -vcE 'dead|stopped|done'

# AO config — should be NO max_* keys
grep -E "max_(concurrent|workers|spawn)" ~/.hermes_prod/agent-orchestrator.yaml || echo "no cap (expected)"

# ao spawn CLI flags — should be NO --max-workers / --max-concurrent / --cap
# (--max-depth is fine; it's decomposition depth, not worker count)
ao spawn --help 2>&1 | grep -E -- "--max-(workers|concurrent|count|cap|sessions)" && echo "FOUND WORKER CAP (unexpected)" || echo "no worker cap flag (expected)"
```

**Bug-ref (2026-07-06, thread C0AH3RY3DK6 / 1782316685.397699, "root cause why AO is down"):** prior agents diagnosed the hang as "AO lifecycle down, start a new orchestrator" and triggered a 60s+120s spawn probe that left a zombie `next-server` and a corrupt `running.json` (the bash heredoc wrote `"pid": ,` because `$PID` was unset). Actual diagnosis (3-state ladder in `ao-spawn-hang-diagnose` skill): orchestrator was up the entire time in **in-process / unix-socket mode** (`--no-dashboard`), no TCP listener on 3020. The "lifecycle polling is inactive" error was a **stale running.json** problem, not a daemon-down problem. Starting a new `ao start` while one was already running caused port-bind race + 120s hang. Fix: replace the `pgrep -fl "ao start"` discovery check with `ps ... | awk '/[a]o start [a-z]/'`, and rewrite running.json in state B instead of starting a new orchestrator.

**Bug-ref (added 2026-07-12, "Internal server error" from a healthy daemon):** `ao spawn --project <p> --prompt "..."` returns `Internal server error [request <host>/<req-id>]` immediately, but `ao doctor` reports `daemon: ready pid=... port=3001` and `ao session ls` shows N active workers. Verified sequence: spawn returns INTERNAL_ERROR within 60s; retry × 3 within 5s = same result; the project has 4 active workers so it's NOT a session-cap wedge. Root cause is on the daemon side (orchestrator API endpoint misbehaving while the daemon process itself is healthy). **Do NOT** keep retrying `ao spawn` — that's the same wall as the 2026-06-20 auth outage (cleared the prior worktree + brief). Pivot to the `pr-green-dispatch` SOUL rule's inline-fallback: if the task is small enough to be self-executable in a single agent session (≤3 producer files, ≤20 lines, no PR-required work that needs full CI sweep), do it inline; otherwise load `finish-the-job` and surface "PR not yet dispatched — AO API INTERNAL_ERROR; user must pick inline / wait / different dispatcher" as a Phase 0 single-question blocker. Diagnostic recipe: `ao doctor` + `ao session ls | wc -l` + `tail -n 30 ~/.ao/data/ao.db-errors.log 2>/dev/null || echo "no error log"` to confirm the wall before pivoting.

## ⚠️ `~/bin/ao` RE-POINTING BUG — `ao-go` (DAEMON-ONLY) SWALLOWS ALL CLI OUTPUT

**Verified 2026-07-06 (PR #8177 dispatch):** `~/bin/ao` was re-pointed from the working node CLI to `~/bin/ao-go` (a Go daemon binary). Symptom: every `ao` subcommand — `status`, `session ls`, `spawn --dry-run`, even `--version` and `--help` — prints **only** the daemon banner line:
```
ao backend daemon: daemon already running (pid 43790, port 3001); refusing to start
```
…then exits with code 1 (or 0, depending on subcommand). **The actual subcommand output is never produced.** No `Session X created`, no `✔` banner, no error, no worktree path. Spawns appear to "succeed silently" with no session row in `session ls`.

**Diagnostic (the only reliable test):**
```bash
ls -la ~/bin/ao                      # if symlink target ends in "ao-go", you're hitting the bug
ps -o comm= -p $(lsof -iTCP:3001 -sTCP:LISTEN -t)   # → $HOME/bin/ao-go (daemon, not CLI)
```

**Working CLI is the node shim:**
```bash
AO=$HOME/.nvm/versions/node/v22.22.0/bin/ao
# Pre-spawn symlink check (canonicalize EVERY spawn from a long-lived shell):
if readlink ~/bin/ao | grep -q ao-go; then
  echo "BUG: ~/bin/ao → ao-go (daemon-only). Using node CLI at $AO instead."
fi
```

**Self-healing fix:** the original `~/bin/ao` should be a symlink to the nvm-managed node CLI (`$HOME/.nvm/versions/node/v22.22.0/bin/ao`). If `~/bin/ao` points anywhere else, recreate it:
```bash
ln -sf $HOME/.nvm/versions/node/v22.22.0/bin/ao ~/bin/ao
```
Run this BEFORE every spawn if the previous session may have rewritten the symlink (some AO tooling installs `ao-go` next to `ao` for daemon mode). The CLI works at the node path even when the symlink is wrong, so always use the absolute path in the `env -i` wrapper:
```bash
AO=$HOME/.nvm/versions/node/v22.22.0/bin/ao
env -i HOME="$HOME" \
    PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    ... bash -c "$AO spawn -p <project> --claim-pr <N> \"\$TASK_TEXT\""
```

**Why this rule exists:** the symptom (one-line output, no error, no session created) looks exactly like the spawn hung — agents have burned 30-60s waiting for `✔ Session X created` that will never appear, then re-spawned (creating duplicate worktrees and orphan work). The 1-second diagnostic (`readlink ~/bin/ao`) saves the whole loop.

## ⚠️ AO 20-SESSION CAP — `ao session cleanup` DOES NOT REAP STALE EXITED SESSIONS

**Verified 2026-07-06 (PR #8177 dispatch):** `ao spawn` returned `Spawn rejected: 20 active sessions >= cap (20). Set AO_MAX_CONCURRENT_SESSIONS env var to increase. Wait for sessions to complete.` even though `ao status` showed 17 of 20 in `exited`/`idle`/`unknown` state 2-4 hours old. **`ao session cleanup` only reaps sessions whose PR is MERGED** (verified: it cleaned exactly 2 of 20). The remaining 15+ stale exited sessions count against the cap.

**Recovery recipe (in order, no user prompt needed for ops):**

1. **List exited/stale sessions:**
   ```bash
   AO=$HOME/.nvm/versions/node/v22.22.0/bin/ao
   $AO status 2>&1 | grep -E "exited.*[0-9]+h? ago"
   # or for fuller view:
   $AO session ls 2>/dev/null | grep -E "wa-[0-9]+" | awk '$NF ~ /\[(spawning|idle|exited|dead|done)\]/'
   ```
   **Only kill sessions in `exited`/`idle`/`dead`/`done`/`unknown` state** — never `working`/`running`/`spawning` (those are live workers doing real work).

2. **Kill each stale session:**
   ```bash
   for s in wa-3129 wa-3131 wa-3134; do
     $AO session kill $s
   done
   ```
   This kills the tmux subprocess and removes the worktree. Safe to run in a loop.

3. **Verify slot freed:**
   ```bash
   $AO session ls 2>/dev/null | grep -cE "wa-[0-9]+"
   # should be < 20
   ```

4. **Re-spawn the new task.** If still capped, identify sessions whose PR is already merged but missed by cleanup (older cleanup runs) and kill those too.

**Pitfall — do NOT use `AO_MAX_CONCURRENT_SESSIONS=40` env override:** it works for the spawn, but masks the underlying pile-up. Stale sessions still consume disk (worktrees), CPU (zombie tmux panes), and the AO dashboard row budget. Always reap first.

**Heuristic — when to suspect the cap:** if `ao status` shows `exited` sessions ≥3h old and `ao spawn` fails with `cap (N)`, the cause is stale sessions, not load. Skip the load diagnosis and go straight to reap-and-retry.

**Pre-spawn slot check (added to dispatch script):**
```bash
ACTIVE=$($AO session ls 2>/dev/null | grep -cE "wa-[0-9]+")
if [ "$ACTIVE" -ge 18 ]; then
  echo "WARN: $ACTIVE/20 sessions active. Reaping stale exited sessions first."
  for s in $($AO status 2>&1 | grep -E "exited.*[0-9]+h? ago" | awk '{print $1}'); do
    $AO session kill "$s" 2>&1 | tail -1
  done
fi
```

**Hermes ↔ AO mental model (do not confuse):**

- **Hermes gateway** (`~/.hermes/config.yaml`): the Slack/Discord bot you are talking through right now. Has `agents.defaults.maxConcurrent=10` for top-level agent runs and `delegation.max_concurrent_children=3` for subagent fan-out per parent. These ARE real caps — but they are on Hermes, not AO.
- **Agent-Orchestrator** (`~/.hermes_prod/agent-orchestrator.yaml`): the orchestrator that spawns `wa-*` / `cc-*` / `jc-*` tmux worker sessions to drive PRs and beads. **No worker-count cap in config.** Runs as standalone tmux processes, not through Hermes.

## ⚠️ EXECUTION RULE — TOOL FIRST, TEXT NEVER

**NEVER reply with text saying you will do something. DO IT FIRST with a tool call.**

This rule applies to **all** trigger phrases, including the hands-off aliases `/a`, `/fullrun`, `/finish`, `/f`, "make hermes hands off", "don't stop halfway", "take it all the way", "drive to conclusion", "see this through", "fullsend", "ship this". None of them authorize a confirmation gate. The user invoked them precisely because they do NOT want to be asked again.
**Forbidden pre-tool-call text patterns** (each is a violation — STOP and call the tool instead):

- "Want me to spawn [X]? Default: yes" / "Want me to dispatch? Default: yes"
- "Should I spawn..." / "Do you want me to spawn..." / "Shall I dispatch..."
- "Going to spawn..." / "About to spawn..." / "Now spawning..."
- "On it — [summary]" — this is the long-task ack shape; it is OK as a *first* message, but if it precedes a tool call without a tool call in the same turn, the next turn MUST open with the tool call, not more preamble.
- "Routing through AO..." / "Routing through agento..." / "I'll route this..."
- "Acknowledged — routing through AO..." / "Acknowledged — spawning..."
- "Before I spawn, want to confirm..." / any "want to confirm / want me to" pattern

- Wrong: "Want me to spawn both now? Default: yes, in parallel, using MiniMax-M2.7." (text-only confirmation gate — BANNED)
- Wrong: "Acknowledged — routing through AO..." (text-only — BANNED)
- Right: immediately call exec(`cd ~/.hermes && ao spawn -p <project> --claim-pr <pr> "..."`) with NO preceding text
- Right (when task is long/multi-step and an ack is required by the `task-ack-and-execute` SOUL.md rule): in the SAME turn as the first tool call, post: "On it — [≤8 word summary]. Back shortly." — but the turn MUST contain a tool call alongside the ack.

**If you catch yourself about to say "I'll..." or "Want me to..." or "Routing..." or "Should I..." — STOP. Call the exec tool instead. The next turn's text opens with the spawn result, not with another preamble.**

**Bug-ref (2026-06-20, thread C0AH3RY3DK6 / 1782005406.736949, "Why did you ask for a confirmation when I said /a and fullrun?"):** the user said `/a fullrun = execute to 7-green with retries. No confirmation gate.` Hermes then posted `Want me to spawn both now? Default: yes, in parallel, using MiniMax-M2.7 per agento skill default not Sonnet.` — a confirmation gate the user explicitly forbade. The user caught it: *"Why did you ask for a confirmation when I said /a and fullrun?"* The fix is this rule. Do not regress.

## ⚠️ ALWAYS WRAP SPAWN IN `env -i` ON macOS (ARG_MAX failure)

**Verified 2026-06-17, session `wa-2371` on PR #7479:** the first `ao spawn` call from the gateway hit `command too long` (exit 1) because `tmux new-session` concatenated the launcher script with the full gateway env (~245 vars from `~/.bashrc` including `AO_BOT_GH_TOKEN`, `GH_TOKEN_AGENTF`, `WAFER_API_KEY`, `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`, full GCP service-account JSON in `GOOGLE_APPLICATION_CREDENTIALS`, etc.) and exceeded macOS's 256KB `ARG_MAX`. The full spawn command and stderr dump come back; no session is created; `ao session ls` shows nothing.

**The fix is mandatory on every spawn from a fat-env shell. Wrap the spawn call:**

```bash
cd ~/.hermes && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$(gh auth token 2>/dev/null)" \
    AO_BOT_GH_TOKEN="$(gh auth token 2>/dev/null)" \
    bash -c '~/bin/ao spawn -p <project> --claim-pr <N> "<short task summary>"'
```

This drops the fat env to just the four vars `ao` needs to start the tmux subprocess. The tmux session itself inherits the full env via `[runtime-tmux] loaded 176 vars from ~/.bashrc` once it spawns, so the worker inside the tmux still has everything.

**Don't pre-flight this — the error is obvious (`command too long` in stderr) and the retry is cheap. Do it on every spawn.**

**Pitfall — `env -i` wrapper CANNOT call `gh auth token` for `GH_TOKEN=`:** the wrapper strips the gateway shell's `PATH`, so the inline `$(gh auth token 2>/dev/null)` runs in a stripped PATH and `gh` is not found — the resulting `GH_TOKEN=""` causes `ao spawn` to 401. **Fix:** resolve the token in the gateway shell BEFORE entering `env -i` and pass it as a literal:

```bash
GH_TOKEN_VAL="$(gh auth token)"
AO_TOKEN_VAL="$(gh auth token)"
cd ~/.hermes && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" \
    AO_BOT_GH_TOKEN="$AO_TOKEN_VAL" \
    bash -c '~/bin/ao spawn -p <project> --claim-pr <N> "<short task summary>"'
```

Pre-computing the token also makes the spawn idempotent — if the gateway shell has `gh` on PATH, it has the token. Same logic for `AO_BOT_GH_TOKEN` and `GH_TOKEN_AGENTF`.

**Pitfall — `~/bin/ao` symlink gets nuked between sessions.** Verified 2026-06-28, PR #7971 dispatch: only `~/bin/ao.backup-20260505-symlink` and `~/bin/ao.old` were present in `~/bin/`, and `which ao` returned nothing. The `bash -c '~/bin/ao spawn ...'` inside `env -i` then errored with `bash: line 1: ao: command not found` (because `~/bin` was on the wrapper PATH but the symlink itself was missing). **Self-healing fix (run BEFORE the spawn wrapper, in the gateway shell where PATH is intact):**

```bash
# Pre-spawn symlink self-heal — silently restore ~/bin/ao if missing
if [ ! -e ~/bin/ao ] || [ ! -x ~/bin/ao ]; then
  ln -sf $HOME/.nvm/versions/node/v22.22.0/bin/ao ~/bin/ao
fi
```

If after this the spawn still errors with `bash: line 1: ao: command not found`, switch the wrapper's inner command from `~/bin/ao` to the absolute path `$HOME/bin/ao` (which the symlink restoration just created) AND add `$HOME/bin` to the wrapper's `PATH=`. This was the actual recovery path on PR #7971 — `env -i` PATH did not include `~/bin` by default, so the bare `~/bin/ao` lookup failed even when the symlink existed.

**Pitfall — gateway-side terminal timeout (e.g. 120s) can kill the spawn mid-flight:** the gateway often runs `ao spawn` inside a `terminal(command=..., timeout=120)` call. `ao spawn` itself returns within ~5-15s (it spawns the tmux subprocess and exits), but the *tmux* session continues. If the gateway timeout fires while the tmux subprocess is still warming up, the gateway process is killed and the tmux session may be reaped depending on its parent group. **Fix:** (a) keep the spawn-call timeout well above the spawn wall-clock (use `timeout=600` not `timeout=120`), OR (b) write the spawn to a background file and tail it:

**`ao start` itself is a long-lived foreground process — `terminal(background=true)` is mandatory.** Verified 2026-06-19: `ao start $HOME/.worktrees/<project> --no-dashboard` is NOT a one-shot that returns. It runs the orchestrator in the foreground, binding the lifecycle polling loop. It does not exit until the user signals Ctrl-C. Wall-clock from invocation to "lifecycle polling is active" is 3-4 minutes on a cold start (config overlay, lifecycle worker, dashboard binding, project registration). Running it in a regular `terminal(command=..., timeout=120)` call with shell `&` backgrounding triggers a foreground-vs-background false positive ("Foreground command uses '&' backgrounding. Use terminal(background=true) for long-lived processes..."). The correct pattern:

```bash
# 1. Start AO in a background terminal session
terminal(background=true): ao start $HOME/.worktrees/<project> --no-dashboard --no-open

# 2. Poll for readiness — `ullm-orchestrator` appearing in ao session ls
#    with state [working] is the FIRST signal. Lifecycle polling being
#    active is the SECOND signal (only after that will ao spawn succeed).
for i in $(seq 1 60); do
  if ao session ls 2>&1 | grep -q "ullm-orchestrator.*working"; then echo "orchestrator up at poll $i"; fi
  if ao spawn --dry-run -p <project> 2>&1 | grep -q "lifecycle polling"; then :; else
    echo "lifecycle polling ACTIVE at poll $i"; break
  fi
  sleep 5
done
```

**Pitfall — `ao session ls` showing `[working]` does NOT mean lifecycle polling is active.** Verified 2026-06-19: the orchestrator session can show `[working]` for ~30s before `running.json` is written and the lifecycle polling loop is bound. Spawning during that gap fails with `✗ AO is not running — lifecycle polling is inactive. Run ao start before spawning sessions so they get CI/review routing and state advancement.` even though `ao session ls` looks healthy. Always poll for both signals (orchestrator working AND a successful `--dry-run` spawn probe) before issuing the real spawn.

**Pitfall — killing the `terminal(background=true)` session kills AO.** If the gateway worker session ends or is reaped, the AO orchestrator dies with it. Pattern: keep the background terminal session alive for the entire worker lifetime. When the worker is done AND you no longer need AO, kill the background terminal session explicitly.

```bash
GH_TOKEN_VAL="$(gh auth token)"
AO_TOKEN_VAL="$(gh auth token)"
( cd ~/.hermes && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" \
    AO_BOT_GH_TOKEN="$AO_TOKEN_VAL" \
    bash -c '~/bin/ao spawn -p <project> --claim-pr <N> "<task>" > /tmp/ao-spawn-<N>.log 2>&1' ) &
SPAWN_PID=$!
# wait up to 30s for the spawn to print its session ID
for i in $(seq 1 30); do
  if [ -s /tmp/ao-spawn-<N>.log ] && grep -qE 'Session.*created' /tmp/ao-spawn-<N>.log; then break; fi
  sleep 1
done
cat /tmp/ao-spawn-<N>.log
```

Pattern (b) keeps the gateway responsive (returns after ≤30s with the spawn log) while letting the tmux subprocess live independently of the gateway process tree.

Full recipe + historical ARG_MAX failures: `references/arg-max-spawn-failure.md`.

## ⚠️ `INVALID STATUS TRANSITION: spawning → pr_open` IS NOISE, NOT FAILURE

## ⚠️ EXECUTION RULE — TOOL FIRST, TEXT NEVER

**NEVER reply with text saying you will do something. DO IT FIRST with a tool call.**

- Wrong: "I'll route this to Agento now..." (text response — BANNED)
- Wrong: "Acknowledged — routing through AO..." (text response — BANNED)
- Right: immediately call exec(`cd ~/.hermes && ao spawn <project> --claim-pr <pr>`) with NO preceding text

If you catch yourself about to say "I'll..." or "Routing..." — STOP. Call the exec tool instead.

### Inline implementation for small daemon PRs (added 2026-07-09)

**AO is not always the answer.** For a single-file or two-file daemon edit of ≤ ~200 LOC where the operator already knows the change (e.g. "add `HERMES_SLACK_BOT_TOKEN` to this plist," "prepend `/goal` to this prompt," "rename this launchd label"), **implement inline in the operator session** instead of spawning an AO worker. The inline path is faster (sub-minute), preserves the operator's review window, and avoids the 600s AO-spawn-timeout trap (which burns context even when the spawn lands).

**Heuristic:** if you can hold the full diff in your head as ≤ 5 `patch` tool calls on a fresh worktree branch from `origin/main`, it is inline. If it requires multi-step recon, multi-file refactor, or operator-context that the worker does not have, dispatch.

**Pitfall — `ao spawn` 600s timeout is paid up-front, not at the end (verified 2026-07-09, dark-factory /af wiring).** A single `ao spawn` from a Slack-gateway session routinely hits the 600s tool-timeout while the underlying tmux session IS being created (orchestrator handshake is slow). The subagent ALSO times out at 600s with no useful output. Two failed dispatches = 2400s of context burn before you even start the fix. If the change fits the inline heuristic, skip AO entirely — do not "try AO first, fall back to inline."

**Inline PR still goes through `gh pr create`** — the `push-pr-donot-stop-halfway` rule applies regardless of dispatch vs inline. Local commits + stop = process violation. The inline path is `git worktree add` → `patch` × N → `bash -n` + `shellcheck` → `git push` → `gh pr create`.

**Full inline heuristic + worked example:** see `dispatch-task` skill → "When to skip AO and implement inline."

### When you DO spawn (default for AO-sized work)
**If you catch yourself about to say "I'll..." or "Want me to..." or "Routing..." or "Should I..." — STOP. Call the exec tool instead. The next turn's text opens with the spawn result, not with another preamble.**

**Bug-ref (2026-06-20, thread C0AH3RY3DK6 / 1782005406.736949, "Why did you ask for a confirmation when I said /a and fullrun?"):** the user said `/a fullrun = execute to 7-green with retries. No confirmation gate.` Hermes then posted `Want me to spawn both now? Default: yes, in parallel, using MiniMax-M2.7 per agento skill default not Sonnet.` — a confirmation gate the user explicitly forbade. The user caught it: *"Why did you ask for a confirmation when I said /a and fullrun?"* The fix is this rule. Do not regress.

## ⚠️ DO NOT STOP THE OPTIMIZER LOOP PREMATURELY

**When the user asks you to "optimize as much as you can" / "keep going" / "max this out" / spawn a worker for an optimization task — let the AO worker run to natural completion.** Don't kill the worker just because a *related* deliverable (a sibling agent's PR, a design doc, a smoke result) landed in the meantime.

**Symptom (verified 2026-06-13, RAG thread C0AH3RY3DK6/1781378514.536629):** A sibling agent shipped PR #7545 (the prompt-library RAG design doc) while I was building the v2 evaluator. I killed the AO worker (`wa-2349`) at the moment the design doc landed, declaring "the optimizer work is duplicated." Jeffrey pushed back: "Arent we supposed to spawn minimax Ao workers to do this work? Why did we stop?" The work the AO worker was doing (extracting `build_rag_prompt()` + shipping the multi-campaign eval suite) was *not* duplicated by PR #7545 — the design doc said "build this seam," the worker was building the seam.

**The kill criterion is "the worker is on the wrong deliverable," NOT "a related deliverable exists."**

**Pitfall — premature stop on "sibling shipped":**
- A sibling agent's PR landing in the same thread is *not* a kill signal. It may be a different deliverable (design vs. implementation, doc vs. test, eval vs. refactor).
- The natural stop for an optimization loop is: (a) the target metric is met, (b) the user explicitly says stop, (c) the worker is on a wrong deliverable (e.g., chasing a bug that the user's framing has ruled out), or (d) the worker is dead-on-arrival (quota block — see `references/quota-blocked-worker-recovery.md`).
- Re-spawn on the *actual* optimization loop, don't stop the loop.

**How to recognize the "wrong deliverable" criterion in practice:** read the user's last framing message. If they said "keep going" / "max it" / "did we optimize as much as we could?", the answer is always "not yet" unless you have explicit evidence the target metric is hit. The user's framing IS the loop budget.

**Cross-reference:** `references/ao-spawn-quickstart.md` in the `dispatch-task` skill for the natural-stop checklist; `references/quota-blocked-worker-recovery.md` for the only kill signals that override the loop budget; `references/cron-target-preflight.md` for verifying which environment a failing GCP cron actually targets before spawning a fix worker.

## ⚠️ VERIFY THE CRON TARGET BEFORE SPAWNING A FIX WORKER

When the user reports a failed GCP cron / scheduled job, do NOT spawn a bring-to-green worker against a random PR until you have confirmed which environment the cron actually targets. The `wa-daily-dice-audit` and `wa-daily-level-up-test` Cloud Run jobs have a `DEV_SERVER_URL` env var that *overrides* the dev default in `entrypoint.sh`. **As of 2026-06-17, `wa-daily-level-up-test` is back on `mvp-site-app-dev`** (verified via `gcloud run jobs describe`); the 06-14 stable override was reverted (see PR #7603). **Always re-verify on the day of dispatch** — this env var flips often. A bring-to-green on a production prompt-schema PR (#7382) is the wrong path if the user's framing is "the dev runtime is broken," and a runtime-watchdog fix (#7526) is wrong if the audit failures are data-integrity bugs in production agent outputs. Both fixes can be valid; the question is which target env the user is testing against.

Pre-spawn checklist (60s, do this every time):
1. `gcloud run jobs describe <job-name> --region us-central1 --project=worldarchitecture-ai` → read the `Env vars:` block, capture `DEV_SERVER_URL` and any other URL/TARGET/BASE.
2. `cat testing_mcp/infra/entrypoint.sh | grep -E "URL|TARGET|BASE"` → compare to step 1; identify whether the cron is hitting default (dev) or env-override (stable).
3. Cross-check the failure email body: it prints `Target URL: <URL>` — that is the *actual* runtime target, not the entrypoint default.
4. Then choose the fix path:
   - Target = `mvp-site-app-dev` → runtime watchdog / streaming fix (code on `main` deploys to dev via auto-deploy).
   - Target = `mvp-site-app-stable` → production data-integrity fix (prompt/schema/agent-output; must propagate to stable via deploy).
5. If unsure, ask the user with the two options spelled out — do not pick a PR and ask "want me to push?".

**Pitfall — assuming `entrypoint.sh` default = runtime target.** The Cloud Run job env var overrides the script default. Always read the live job, not the file.

**Pitfall — referencing an unauthenticated session in a bring-to-green report.** If a session is in `[spawning]` state with zero commits, it has not created a worktree on a `fix/...` branch. Do not describe it as "running on `fix/N-description` in worktree `/path/N-description`" — those identifiers come from `ao session ls`, not from imagination. Confabulating session details when the actual session is on `feat/rev-y8109` in a generic spawn path is a real failure mode: the user loses trust in every downstream claim. (Verified incident: 2026-06-14, thread C0AH3RY3DK6 — prior turn invented branch + worktree path for `wa-2352`; `ao session ls` showed neither matched.)

## ⚠️ `ao spawn` STUCK IN `[spawning]` >5 MIN WITH ZERO COMMITS = TRUST PROMPT, NOT QUOTA

Distinct from quota block (quota block shows the `⚠ Individual quota reached` banner with prompt cursor). Trust-prompt stall shows the Antigravity TUI:

```
Do you trust the contents of this project?

Antigravity CLI requires permission to read, edit, and execute files here.

> Yes, I trust this folder
  No, exit
```

The session shows `[spawning]` status, `git log` is unchanged, no `⚠` banner. The fix is a single `Enter` via tmux (full recipe in the `antigravity-trust-prompt-auto-dismiss` skill). Do NOT kill the session first; accepting the trust prompt is the gateway to the worker actually starting.

Diagnostic order:
1. `tmux capture-pane -t <tmux-session-name> -p -S -20 | tail -25` — look for the literal `Do you trust the contents of this project?` string.
2. If present → `tmux send-keys -t <session> Enter` (single keypress, default is "Yes").
3. If absent but status is `[spawning]` >5min with no `⚠` banner → could be AO dashboard lag; wait one more poll, then re-check.
4. If present AND `⚠ Individual quota reached` → quota block, use `references/quota-blocked-worker-recovery.md`; do NOT send Enter (it interrupts the prompt).

## ⚠️ WHEN THE USER OVERRIDES AO — DO IT INLINE

**If the user says "you do it all yourself and debug it", "do it inline", "do it yourself", "skip the agent", or "do it locally"** mid-flow, treat that as an explicit override of the agento default. This applies even if you already spawned an AO session and it is still running.

**Procedure:**

1. **Kill the running AO session first** — `ao session kill <session-id>` (or `tmux send-keys -t <session> Escape; sleep 1; tmux send-keys -t <session> C-c` then `ao session kill`). Do not let the orphan worker keep running; it will duplicate work and emit confusing reports.
2. **Take over the worktree directly** — switch to the worker's worktree (or create a fresh one via `git worktree add -b <branch> <path> origin/main`).
3. **Run the validation/test loop inline** — for WA work this means `cd testing_mcp/core && $HOME/repos/$GITHUB_REPOSITORY/venv/bin/python3 test_<name>.py ...` with the venv symlink trick (see `worldarchitect` skill → "Running tests from a fresh worktree").
4. **Post PRs and bead updates as you go** — `gh pr create`/`gh pr edit` work from a worktree; you do not need agento for the publishing step.
5. **Report results directly** with the exit code, scenario pass/fail, and evidence paths — no need to wait for an AO report.

**Why this rule:** The user's "do it yourself" override means they want direct ownership and faster iteration. An orphan AO worker will keep spending tokens and may race you on file edits. Killing it cleanly is faster than letting it finish (which can take 10+ minutes for multi-step coding tasks).

**Recognize the signal early.** If the user says "do it yourself" in the same turn where agento is about to spawn, skip the spawn entirely and start working inline. The signal is explicit; do not second-guess it.

## PR Title Tagging (REQUIRED)

**Every PR created by agento MUST have `[agento]` as the first word of the title.**

- Wrong: `fix: resolve CodeRabbit comments`
- Right: `[agento] fix: resolve CodeRabbit comments`

This tag allows the backfill cron (`ai.agento.backfill`) to detect AO-managed PRs and auto-spawn sessions if one is missing.

## Spawn After PR Create (REQUIRED)

After any `gh pr create`, immediately spawn an AO session for it:

```bash
# 1. Create the PR (title MUST start with [agento])
~/.hermes/scripts/gh-safe-publish pr create --title "[agento] fix: ..." --body "..."

# 2. Get the PR number
PR_NUM=$(gh pr view --json number --jq .number)

# 3. Spawn AO session immediately
ao spawn -p <project-id> --claim-pr $PR_NUM
```

Both steps are mandatory. Do not create an agento PR without spawning a session.

## When NOT to use this skill (load `ao-config-management` instead)

If the request is about AO **config** rather than AO **work** — e.g. "stop agents spawning on worldai-claw", "flip backfill off by default", "make jleechanclaw auto-merge", "change the default agent to codex", "the default model is wrong" — load the `ao-config-management` skill first. That skill:

- Maps the user's informal English for flags (e.g. "backfillPRs") to the actual YAML key (e.g. `backfillAllPRs`) via the Zod schema in `packages/core/src/config.ts`
- Provides the 4-step audit recipe (read `running.json` `configPath` → grep the live config → read schema default → reconcile)
- Enforces the "no config change without explicit user approval" rule per `~/.hermes/AGENTS.md`

Most config-style requests are already in effect (the schema default does what the user wants for unset projects), so dispatching an agento worker to "fix" a config that may already be correct is wasted tokens. Audit first, then decide whether a worker is even needed.

If the audit reveals a real config change is needed, do NOT use `agento` to dispatch the change — the change itself is a small YAML edit, not a multi-step coding task. Get explicit in-thread approval, edit the file, validate YAML parses, and (if needed) bounce the relevant `ao lifecycle-worker <project>` process.

## ⚠️ `/a`, `/fullrun`, `/finish`, `/f`: NO confirmation gate (2026-06-20)

These aliases all mean the same thing: **"execute to completion, do not stop halfway, do not ask me again."** They are explicitly anti-confirmation. When the user invokes one of these, the entire "Want me to spawn...?" / "Should I dispatch...?" / "Going to spawn..." / "Routing through AO..." preamble pattern is **forbidden**.

**Triggers that mean "no confirmation gate"** (any of these, anywhere in the user message):

- `/a`, `/agento` (per `finish-the-job` SOUL.md rule — finishes the job hands-off)
- `/fullrun`, `/fr` (Jeffrey's informal shorthand for fullrun-untouched-to-completion)
- `/finish`, `/f`, `/fin`, `/auto` (per `finish-the-job` skill — same engine as `/a`)
- `make hermes hands off`, `hands off mode`, `don't stop halfway`, `take it all the way`
- `drive to conclusion`, `see this through`, `fullsend`, `ship this`
- `no confirmation`, `no asking`, `just do it`, `don't ask me`
- `lets /green it and run /f and fullrun /a it` — composite triggers that include any of the above

**When ANY of these trigger phrases is present in the user's message, the skill's response shape is:**

1. **First turn contains a tool call** — `ao spawn` (or equivalent dispatch). NOT a text reply. NOT a clarification. NOT a confirmation.
2. **If the task is multi-turn / >5 min**, the first turn may ALSO contain an ack line per the SOUL.md `task-ack-and-execute` COMMIT rule: `On it — [≤8 word summary]. Back shortly.` — but the same turn MUST contain the actual tool call. The ack is a *companion*, never a *replacement*.
3. **Post the in-thread `Spawned <session-id> for ...` one-liner** only after the spawn returns. This is the report, not a confirmation gate — the spawn already happened.
4. **Drive to completion.** Do not pause for additional confirmation at any subsequent checkpoint (CI green, CR review, fix iteration, merge readiness). The user already said "all the way."

**Forbidden patterns under these triggers** — see the canonical list in **§⚠️ EXECUTION RULE — TOOL FIRST, TEXT NEVER** above. That list (`Want me to spawn...`, `Should I dispatch...`, `Going to spawn...`, `Routing through AO...`, `Acknowledged — routing...`, `Before I spawn, want to confirm...`, any "Want me to / Should I / Shall I" pattern) is the single source of truth — do not duplicate it here. The only "ask" allowed is the up-front classification `clarify` call BEFORE the user has explicitly invoked a hands-off trigger; once `/a` / `/fullrun` / `/finish` / `/f` is in scope, the answer to "which model / which agent / which project to use" is always the skill default (`MiniMax-M2.7` per the frontmatter `description`), not a question.

**The fix is not "ask less." The fix is "ask never under these triggers."** The bug-ref below is the proof: the user did ask for `/a fullrun`, the agent did ask for confirmation anyway, and the user had to spend another turn calling out the violation.

**Bug-ref:** thread [C0AH3RY3DK6 / 1782005406.736949](https://jleechanai.slack.com/archives/C0AH3RY3DK6/p1782005406736949), 2026-06-20. User: *"Look at this and lets also confirm we have proper gcp logs and BQ logs for request latency. ... we need backend request/response latency and LLM call request/response with very detailed/comphrenive metrics and latency measurements for each component in the whole flow. ... For both lets use parallel AO workers and tell them to use claude team or subagents as needed."* Hermes replied with a long plan and ended: *"Want me to spawn both now? Default: yes, in parallel, using MiniMax-M2.7 per agento skill default not Sonnet. Both workers will post status updates to this thread every 5 min per the dispatched-task-progress-5min commitment."* User immediately: *"Why did you ask for a confirmation when I said /a and fullrun?"* Hermes: *"Youre right thats on me. /a fullrun = execute to 7-green with retries. No confirmation gate. Fixing now: spawning both AO workers in parallel and pushing to green."* — but the fix landed mid-stream, not at the SKILL.md level. This section is the durable SKILL.md fix.

**Cross-reference:** `finish-the-job` skill (the engine behind `/a` / `/finish` / `/f`) — its §BA1 also explicitly maps `/a` and `/fullrun` to no-confirmation hands-off behavior; this section aligns `agento` with that contract.

## Steps

1. Parse the user's intent.
2. Determine the `ao` command (see Commands section above).
3. **IMMEDIATELY call exec tool** — no text before the call. NO "Want me to..." / "Should I..." / "Routing..." preamble. NO confirmation gate under any trigger phrase, including `/a` / `/fullrun` / `/finish` / `/f`:
   ```
   exec: cd ~/.hermes && ao spawn -p <project-id> --claim-pr <pr>
   ```
4. After the exec call returns, reply with a one-line spawn report: "Spawned `<session-id>` for PR #N." This is the spawn result, NOT a confirmation gate — the spawn already happened.
5. Do NOT wait for the spawn to complete — it runs async in tmux.
6. **Do NOT pause at subsequent checkpoints** (CI green, CR review, fix iteration, merge readiness) for re-confirmation under `/a` / `/fullrun` / `/finish` / `/f` triggers. Drive to completion; report only on state change or terminal state.

## PR Hardening Loop (Default for Hermes -> agento PRs)

When the request is PR remediation (`fix comments`, `fix CI`, `make PR good`), run AO as an iterative loop using AO-native commands, not custom orchestration logic.

1. Start or reuse the AO session for the target PR.
   - If no PR-bound session exists, create one with `ao spawn -p <project> --claim-pr <pr-number>`.
2. Run `ao review-check <project>` from `~/.hermes` to let AO detect review blockers and trigger follow-up messages.
3. Send the full remediation objective with `ao send <session> "<message>"`:
   - Resolve all unresolved review comments/threads.
   - Fix failing required CI checks.
   - Push updates and re-run checks.
4. Re-check with `ao status --project <id>` and repeat AO actions while blockers remain.
5. Use `gh pr view` / `gh pr checks` only as verification or evidence if AO status is ambiguous.
6. Repeat until merge-ready (no unresolved blockers + required CI green), or escalate after bounded retries with concrete blocker evidence.

Default rule: if PR was created via Hermes -> agento handoff, stay in AO lane unless Jeffrey explicitly says `mctrl`.

## Quota-Blocked Worker Recovery (companion reference)

For the full 4-step recovery recipe when `ao spawn` returns success but the
agent is dead-on-arrival because the LLM provider is quota-limited, see
`references/quota-blocked-worker-recovery.md`. Verified pattern from
session `wa-2346` on PR #7524, 2026-06-13.

## Notes

- AO dashboard: `http://localhost:3020` - managed by launchd (`ai.agento.dashboard` plist at `~/.hermes/launchd/ai.agento.dashboard.plist`, symlinked to `~/Library/LaunchAgents/ai.agento.dashboard.plist`)
- **Canonical config:** `~/.hermes/agent-orchestrator.yaml` (tracked source — no stub overlay; per `~/.hermes/CLAUDE.md` the canonical path after the openclaw-gateway retirement)
- **Live project state file:** `~/.agent-orchestrator/running.json` (created by `ao start`; written by hand if missing — see "running.json bootstrap" below)
- Sessions live in `~/.agent-orchestrator/` and `~/.worktrees/`
- Notifications: AO posts to #ai-slack-test via the agento-notifier webhook handler
- AO-native remediation is already in AO itself (`review-check` + lifecycle `reactions` for `ci-failed`, `changes-requested`, `bugbot-comments`). Do not build a parallel custom remediation engine in this repo.

**Rate-Limit Handling:** When GitHub is rate-limited, `github-intake.sh` will NOT fall back to unclaimed spawns. Instead, it skips the PR and logs: `RATE LIMIT: --claim-pr failed for PR #N, NOT spawning (will retry next cycle)`. AO lifecycle workers handle spawn/cleanup natively.

---

## Pitfalls — verified 2026-07-08 `/af` cross-repo drive burst

These are durable pitfalls discovered while driving 49 non-draft PRs across 7 repos in one burst. Future batches will hit the same walls unless encoded.

### 1. `env -i` MUST unset `GITHUB_TOKEN` (not just `GH_TOKEN`)

`env -i HOME=... PATH=... GH_TOKEN=... ao spawn ...` looks correct but **fails** with `✗ GitHub CLI is not authenticated. Run: gh auth login`.

Root cause: `~/.bashrc` sets `GITHUB_TOKEN` to the AO bot token. `gh` prefers `GH_TOKEN` and `GITHUB_TOKEN` env vars over `~/.config/gh/hosts.yml`. With both env vars set to bot tokens, `gh` rejects auth.

**Fix:** In every shell script that spawns via `env -i`, always:
```bash
unset GH_TOKEN GITHUB_TOKEN AO_BOT_GH_TOKEN
```
Let `gh` fall through to `~/.config/gh/hosts.yml`. Without the unset, sequential scripts fail silently with `gh auth status` reporting failure, then `ao spawn` returns `rc=0` (the spawn is rejected but the script moves on, looking successful).

### 2. `ao spawn --claim-pr <N>` is REQUIRED for PR-bound workers

Without `--claim-pr`, the spawn creates a generic session bound to the project (e.g., `df-107`, `auf-4`) but with NO `pulls/N` URL link. The session can do useful project-level work but won't auto-attach to any specific PR. CodeRabbit + Bugbot never see the comment-tracker link.

**Always use `--claim-pr <N>` when the goal is driving a specific PR.** The auto-factory tick (`factory-af-tick.sh`) does this automatically; direct dispatches must include the flag.

### 3. Per-project spawn lock — only ONE `ao spawn` per project at a time

`ao spawn` has a per-project mutex. While one spawn is running, others return:
```
✗ Another ao spawn is in progress for project "<project>" (PID <pid>, started ...). Wait for it to finish.
```

For multi-PR fanouts within one project, you must either:
- Spawn sequentially in a shell script (`for pr in $PRS; do ao spawn -p <proj> --claim-pr $pr ...; done`) — slow (~5-8 min/PR), but reliable
- Spawn across **different projects** in parallel (no cross-project lock)

### 4. Killed sessions leave **locked** worktrees — `git worktree remove` can't unlock them

When you `ao session kill <id>`, the worktree at `~/.worktrees/<project>/<session-id>/` is locked with reason "AO session active". A subsequent `ao spawn --claim-pr <same-pr>` fails with:
```
✗ Found existing worktree for orchestrator branch "<branch>" at "<path>", but it is outside AO-managed worktree directories. Reuse it manually or remove it and try again.
```

**Fix:** The locked worktree dir MUST be removed manually. `git worktree remove -f` from inside it does NOT override the lock. Use `rm -rf` on the directory itself:
```bash
WT=~/.worktrees/<project>/<session-id>
if [ -d "$WT" ]; then rm -rf "$WT"; fi
```
Then retry the spawn. The branch is preserved on the remote; `ao spawn` will recreate the worktree cleanly.

### 5. Project config schema is `name`, `path`, `repo`, `defaultBranch`, `agentRules`

`agent-orchestrator.yaml` projects require exactly:
```yaml
projects:
  my-project:
    name: my-project
    path: ~/projects/my-project
    repo: jleechanorg/my-project
    defaultBranch: main
    agentRules: "..."
```

**Pitfall:** `path` is REQUIRED (Zod validation fails otherwise). A new project entry missing `path` will reject ALL spawns with:
```
ZodError: [
  { "code": "invalid_type", "expected": "string", "received": "undefined",
    "path": ["projects", "<id>", "path"], "message": "Required" }
]
```

**For `.github` repo:** the AO project ID cannot be `.github` (Zod keys can't start with `.`). Use `github-org` as the project ID, with `repo: jleechanorg/.github`.

**Path must exist on disk with `.git/`** — if you `mkdir` a fresh dir, you must `git init && git remote add origin <url> && git fetch && git checkout main` BEFORE spawning, or ao will fail.

### 6. Project additions require `ao stop && ao start` to load

The AO daemon loads the project list once at startup. Adding a new project to `agent-orchestrator.yaml` while ao is running **does not appear** until you:
```bash
ao stop  # kills daemon + dashboard
cd <project-path> && ao start <project> --no-dashboard --no-open
```
Existing in-flight sessions from the old config will be orphaned. Best to do this BEFORE the fanout, not during.

### 7. `AO_MAX_CONCURRENT_SESSIONS` defaults to 20

`ao spawn` rejects new sessions when `active >= cap`:
```
✗ Spawn rejected: 26 active sessions >= cap (20). Set AO_MAX_CONCURRENT_SESSIONS env var to increase. Wait for sessions to complete.
```

**For burst fanouts, raise the cap:** pass `AO_MAX_CONCURRENT_SESSIONS=80` (or whatever you need) in `env -i`. Set it both in the spawn wrapper AND in the `ao start` command, or workers will reject mid-burst.

### 8. Project gets `paused` by LLM rate limit, not `cancelled`

When a project hits a model-provider rate limit, AO pauses the entire project:
```
✗ Project is paused due to model rate limit until 2026-07-09T07:48:41Z
  (Model rate limit detected from <session>; source: <session>)
```

The fix has to come from the **LLM provider's quota reset** (often hours), not from killing sessions. Don't burn cycles retrying spawns against a paused project — they all fail with the same error.

### 9. `ao session ls` times out at ~48 sessions

With 40+ active sessions, `ao session ls` takes 10-30s. Don't grep the live output — read it via `re.findall` in `execute_code` for batch processing.

### 10. The auto-factory `target_repo = $GITHUB_REPOSITORY` is hardcoded

`$HOME/projects/dark-factory/daemon/factory-overlay.sh` only dispatches PRs to the `--project worldarchitect` worker. For cross-repo fanouts, bypass the overlay and use direct `ao spawn -p <project> --claim-pr <N>`.

See `references/cross-repo-af-drive.md` for a complete cross-project fanout cookbook and a script template. See `scripts/spawn_safe.sh` for a ready-to-use safe-spawn wrapper (handles `env -i` + `unset GH_TOKEN/GITHUB_TOKEN` correctly).

## When the AO worker spawn succeeds but the agent is quota-blocked (the "dead-on-arrival" pattern)

**Symptom (verified 2026-06-13, session `wa-2346` on PR #7524):**
- `ao spawn -p <project> --claim-pr <N>` returns `✔ Session <id> created and claimed PR` with a worktree path and tmux session.
- The tmux pane shows the task brief accepted, then a `⚠ Individual quota reached. Contact your administrator to enable overages. Resets in 58m42s.` banner.
- The worker's input buffer is empty. `tmux capture-pane` shows the prompt cursor `>` waiting for the user; the worker is not processing anything.
- `git log` in the worktree is unchanged from the spawn moment.

**Why this happens:** Antigravity is the default agent and it routes through a provider (e.g. Gemini 3.5 Flash for high-throughput tasks). The provider's per-user quota can be exhausted by other sessions in the same provider org. The agent harness blocks at the LLM call before any code work begins.

**The cookbook rule applies — do not stop here.** The user's "do all the way" / "let's /green" directives mean: solve the problem, not "the agento lane is closed." Recovery is mechanical:

**Hybrid rebase-and-re-spawn pattern (the standard fix):**

1. **Kill the quota-blocked session** — `ao session kill <id>`. The worktree is removed but the AO claim on the PR persists.
2. **Take the mechanical parts inline** — for a bring-to-green, this is usually a rebase, a force-push, and a CI-wait poll. None of these need an LLM.
3. **Re-spawn AO for the LLM-dependent parts** — typically: real-LLM E2E evidence capture, complex multi-file code review, prompt-tuning. Wait for the quota reset (per the `⚠ Resets in <N>m` banner) or switch the agent via `--agent <other>`.
4. **Report in the same Slack thread** with: (a) what was done inline, (b) what was deferred to the re-spawn, (c) the exact quota-reset timestamp.

**Recipe — kill + inline rebase (verbatim from PR #7524):**

```bash
# Kill the quota-blocked session
cd ~/.hermes && ~/bin/ao session kill wa-2346

# Create a fresh worktree on the PR branch
cd ~/projects/your-project.com
git worktree add /tmp/wt-7524-rebase origin/repro/7520-character-skills-not-populated
cd /tmp/wt-7524-rebase

# Rebase onto main
git rebase origin/main   # zero conflicts if the PR is mostly additive

# Force-push with --force-with-lease
git push --force-with-lease origin HEAD:refs/heads/repro/7520-character-skills-not-populated
```

**Why not just `ao send` the existing session?** A quota-blocked agent cannot process LLM calls; `ao send` enqueues a message in the input buffer but the agent cannot act on it. The session must be killed and the LLM-dependent work must wait for quota reset OR a different agent.

**Why not `gh auth switch` to a different account?** Auth is not the bottleneck — the LLM provider quota is per-provider-org, not per-GitHub-account. Switching gh accounts does not change which provider serves the AO agent.

**Why not edit `agent-orchestrator.yaml` to change the default agent?** That's a config change requiring explicit human approval per `~/.hermes/CLAUDE.md` "Protected keys — NEVER change these values" table (and the analogous Hermes config.yaml rules). Do not work around the quota by editing config.

**How to detect this state in future sessions:** if `ao spawn` returns a session ID and worktree but the worker makes zero progress for >2 minutes, capture the tmux pane. The `⚠ Individual quota reached` banner is the smoking gun. Do not wait longer — kill, take the mechanical parts inline, re-spawn the LLM parts after reset.

**Force-push audit requirement:** when you take the rebase inline after killing the AO session, the bring-to-green report MUST include a force-push audit (old SHA → new SHA, form used, reason). This is the same audit you would include if AO had done the rebase — the form changes (you do it, not the agent) but the audit fields are identical.

## Spawn Output — Branch Name Auto-Derivation (always reset)

`ao spawn` derives the initial branch name from the first ~64 chars of the task text, so a long or prose-style task will produce a worktree on something like `feat/user-s-original-request-verbatim-spawn-ao-worker-unless-its`. **Always reset the branch name immediately after spawn — BEFORE the worker starts committing:**

```bash
cd ~/.worktrees/<project>/<N>  # path printed in spawn output
git fetch origin main
git checkout -B feat/<descriptive-name> origin/main
```

The `<descriptive-name>` should match the PR title keyword (e.g. `feat/gemini-mojibake-recovery` for a `[agento] test: add hermes streaming UTF-8 regression tests + Gemini mojibake investigation` PR). Resetting after the worker has committed is messy because the `feat/<name>` becomes the PR's head ref and the GitHub PR URL embeds it.

**Pitfall — pre-existing stub-commit PR head + `--claim-pr` produces a side branch, not a rebase.** Verified 2026-06-19 (PR #7711, issue #7710): when the gateway creates a draft PR with a stub commit on a specific branch (e.g. `fix/dUfl4-character-creation-empty-planning-block`) and then dispatches `ao spawn --claim-pr 7711`, the worker does NOT check out the PR's existing head branch. Instead, `ao spawn` auto-derives a *new* branch from the task text (e.g. `feat/tdd-task-for-issue-7710-pr-7711-campaign-symptom-in-dufl4adb`) in a parallel worktree. The PR head remains on the gateway's stub-commit branch, while the worker commits on its own derived side branch. The worker's eventual fix has to be merged into the PR head via rebase or fast-forward — the worker cannot push to the PR head directly because the worktree paths differ.

**Pitfall — worker races the gateway's branch reset when the brief says "create draft PR first as gate 2" (added 2026-07-14, PR #8385 / campaign-difficulty /repro).** The canonical Step 4 ("reset branch BEFORE the worker commits") assumes the gateway can `git checkout -B <clean-name>` between spawn and the worker's first commit. With `/repro` — or any task whose brief says "create the draft PR immediately" — the worker reads the brief, runs `gh issue create` + `gh pr create --draft` + first commit + push within the same minute as spawn. By the time the gateway's 60-120s `terminal` call returns and runs the reset, the PR head already lives on the auto-derived branch. The gateway's clean local branch ends up divergent from the PR head. Full detection + recovery recipe + pre-spawn mitigation (slug-prefix task text) in `dispatch-task/references/worker-races-branch-reset.md`.

**Pattern when you have a pre-existing PR head branch you want the worker to commit on:**
1. **Option A (preferred for `/repro` and similar):** skip the pre-existing stub-commit. Create the worktree + branch locally, then `ao spawn -p <project>` (no `--claim-pr`) with the task text. The worker will use the worktree's current branch. Then `gh pr create --draft --head <branch>` after the worker pushes.
2. **Option B (use `--claim-pr` only when you don't care which branch):** accept the side branch. After the worker pushes, in the gateway: `git fetch origin <worker-branch>`, `git checkout -B <intended-pr-head> origin/<worker-branch>`, `git push --force-with-lease origin <intended-pr-head>`, then `gh pr edit <N> --head <intended-pr-head>`.
3. **Option C (avoid `--claim-pr` after pre-existing stub):** create the PR head branch with `git worktree add`, then send the task via `ao send <session> "<task text>"` to a session you spawn without `--claim-pr`. The worker commits on the existing branch.

The cleanest approach for `/repro` is Option A: create the issue + bead + branch (no PR) in the gateway, then dispatch `ao spawn -p <project> -b <branch-name>` (or use the AO plugin's worktree setup) and let the worker both fix and open the PR.

## Long Task Briefs — write to /tmp/, pass short summary as the arg

`ao spawn` has **no `--task-file` flag** (verified 2026-06-07: `error: unknown option '--task-file'`). If the task brief is more than ~200 chars, do NOT try to inline the full text as the positional arg — you'll get a mangled `feat/...` branch and the worker will struggle to read a wall-of-text first message.

**Pattern (used for the 2026-06-07 faction-ranking cluster dispatch):**

1. Write the full TDD task brief to `/tmp/<project>-<phenotype>-cluster/ao-task-brief.md`
2. Write the root-cause evidence bundle to the same dir: `/tmp/<project>-<phenotype>-cluster/root-cause-evidence.md`
3. `ao spawn -p <project> "Short summary: <one-line scope>. Full task brief at /tmp/<path>/ao-task-brief.md (READ FIRST). TDD red-green-refactor, N tests, M files changed, [agento] PR title required. Bead IDs: <id1>, <id2>, ..."`
4. After spawn prints the worktree path, **copy the brief + evidence into the worktree root** so the worker finds them:
   ```bash
   cd ~/.worktrees/<project>/<N>
   cp /tmp/<path>/ao-task-brief.md ./AO-TASK-BRIEF.md
   cp /tmp/<path>/root-cause-evidence.md ./root-cause-evidence.md
   ```
5. Reset the branch name (above) so the PR head ref is clean
6. `ao send <session> "<one-line steer telling the worker the branch was reset, the brief is at the worktree root, and any project-specific test command>"` — this prevents the worker from doing the rename itself or committing on the wrong branch

**Why this matters:** the in-line short summary is the only thing that shapes the auto-derived branch name (truncated to ~64 chars). The full brief is what the worker actually reads. Keeping them decoupled means (a) the branch is clean, (b) the worker has full context, and (c) you can re-`ao send` a corrected brief without re-spawning.

## Post-spawn wire-up sequence (canonical end-to-end)

The four steps above are correct but spread across this skill; consolidated canonical sequence for any `ao spawn` of a long task (verified 2026-06-20 on `wa-2453` for the latency-half fix on issue #7684):

```bash
# 0. (Pre-spawn) Write the brief
mkdir -p /tmp/<project>-<phenotype>/
write_file /tmp/<project>-<phenotype>/ao-task-brief.md "<TDD recipe, TDD red-green, PR title, branch name, evidence recipe, definition of done, what's NOT to do>"

# 1. Spawn (always env -i wrapper, tokens pre-resolved)
GH_TOKEN_VAL="$(gh auth token)"; AO_TOKEN_VAL="$(gh auth token)"
cd ~/.hermes && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" AO_BOT_GH_TOKEN="$AO_TOKEN_VAL" \
    bash -c "~/bin/ao spawn -p <project> 'Short summary: <one line>. Full task brief at /tmp/<path>/ao-task-brief.md'"

# 2. The spawn will return within 5-15s with the session ID, worktree path, and branch
#    (the gateway's 120s terminal timeout may fire after that — that's fine, the tmux subprocess lives)
#    Capture: SESSION_ID=wa-XXXX, WORKTREE=~/.worktrees/<project>/<N>, BRANCH=feat/<auto-derived>

# 3. Copy the brief into the worktree root
cp /tmp/<project>-<phenotype>/ao-task-brief.md "$WORKTREE/AO-TASK-BRIEF.md"

# 4. Reset the branch to a clean name off origin/main
cd "$WORKTREE"
git fetch origin main
git checkout -B <clean-branch-name> origin/main   # e.g. fix/7684-prepare-story-continuation-latency

# 5. Send a one-line steer so the worker knows the branch was reset and the brief is in the worktree root
cd ~/.hermes && env -i HOME="$HOME" \
    PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin" \
    GH_TOKEN="$GH_TOKEN_VAL" \
    bash -c "~/bin/ao send $SESSION_ID 'Branch was reset to <clean-branch-name> (origin/main @ <sha>). Full task brief is at \$WORKTREE/AO-TASK-BRIEF.md — READ IT FIRST. TDD: <one-line summary>. PR title must be [agento] ... . Drive PR to fully green CI; do not stop with broken checks. Post status to Slack thread <thread_ts> in <channel_id> with PR URL + latency/result numbers when done.'"

# 6. Arm a 5-min babysit cron (Hermes background process)
#    See the babysitting scripts at `skills/hermes-imports/dispatch-task/scripts/babysit-one-session.sh`
#    and `multi-session-babysit.sh` for the local or multi-session babysitting loop.
#    The bash variant writes /tmp/<session>-done + /tmp/<session>-pr-url markers and posts progress
#    to the originating Slack thread on every 2nd poll (~10 min cadence).
```

**Why this exact order matters:**
- Step 3 must happen BEFORE step 4: if the worker starts reading the worktree before the brief is there, it will improvise from the (long) first message and ignore the structured TDD recipe.
- Step 4 must happen BEFORE step 5: if the steer message says "branch is reset to <name>" but the reset hasn't happened, the worker will reset it to a *different* name (overwriting your reset).
- Step 6 must happen AFTER step 5: arming the babysit before sending the steer means the babysit's first poll runs before the worker has the brief, producing a misleading "no commits, no activity" report.

**Anti-patterns:**
- Skipping step 4 ("the auto-derived name is fine"): the auto-derived name is usually 60+ chars of lowercase-prose that looks unprofessional in `git log` and breaks PR-title keyword searches. Always reset.
- Inline the brief as the positional arg because you forgot step 0: the worker gets a wall of text, the branch is mangled, and re-sending a corrected brief is much harder than re-running spawn.
- Forgetting step 6: the worker runs for 30+ min, posts nothing, and you have to manually poll `ao status` to find out it died 5 min in.

## Babysit cron fallback when `hermes cron create` is broken

`hermes cron create` will fail with `Config invalid — plugins.entries.hermes-mem0: plugin not found` (or similar) when the active `~/.hermes/config.yaml` has unresolvable plugin refs. The error fires **before flag parsing**, so `--message` vs `--prompt`, `--at 5m`, etc. all silently drop on the floor. Per Jeffrey's red line: do not run `hermes doctor --fix` or hand-edit `~/.hermes/config.yaml` to clear the error — that's a config change requiring explicit human approval.

**Fallback: spawn a bash babysit loop as a Hermes background process.** Pattern (verified 2026-06-07, AO session `wa-2262`):

```bash
# /tmp/<session>-babysit.sh — polls ao status every 5 min, writes marker files on terminal state
#!/bin/bash
SESSION_ID="<session>"
LOG="/tmp/<session>-babysit.log"
DONE_MARKER="/tmp/<session>-done"
PR_URL_FILE="/tmp/<session>-pr-url"
MAX_POLLS=8         # 8 × 5min = 40 min
SLEEP_SEC=300
echo "[$(date -u +%I:%M:%S)] babysit starting for $SESSION_ID" > "$LOG"
for i in $(seq 1 $MAX_POLLS); do
  echo "[$(date -u +%I:%M:%S)] poll #$i" >> "$LOG"
  STATUS=$(cd ~/.hermes && ~/bin/ao status 2>&1)
  echo "$STATUS" >> "$LOG"
  # Detect terminal state in the ao status block
  if echo "$STATUS" | grep -A 5 "$SESSION_ID" | grep -qiE "done|merged|completed|closed|errored|failed|killed"; then
    echo "TERMINAL" > "$DONE_MARKER"
    break
  fi
  if ! echo "$STATUS" | grep -q "$SESSION_ID"; then
    echo "GONE" > "$DONE_MARKER"
    break
  fi
  # Detect PR creation (find by title keyword + [agento] tag)
  PR=$(gh pr list --repo jleechanorg/<project> --state open --json number,url,title 2>/dev/null \
       | python3 -c "import json,sys; d=json.load(sys.stdin); print([p['url'] for p in d if '<keyword>' in p.get('title','').lower() and 'agento' in p.get('title','')][0] if d else '')" 2>/dev/null)
  [ -n "$PR" ] && echo "$PR" > "$PR_URL_FILE"
  sleep $SLEEP_SEC
done
```

Then launch as a Hermes background process (not nohup — Hermes tracks the pid):
```bash
chmod +x /tmp/<session>-babysit.sh
# Use the terminal tool with background=true
```

In the main session, poll `/tmp/<session>-done` and `/tmp/<session>-pr-url` on subsequent turns to surface results. The loop self-terminates on session completion or 40-min budget.

**Pitfall — `write_file` does not set +x on the script.** A script written via `write_file` lands at mode 644, not 755. If you launch it via `terminal(background=true)` without first running `chmod +x`, it exits with `Permission denied` (exit 126) within the first second. Always chmod in a separate foreground terminal call before launching the background process.

**Pitfall — Hermes rejects `nohup` / `disown` / `setsid` in foreground terminal calls.** The error "Foreground command uses shell-level background wrappers" is a false positive on certain command patterns (e.g. `nohup ... &; echo PID $!`). Use `terminal(background=true)` for the actual long-lived process, not nohup+disown hacks.

## Destructive Operations in Task Text — Worker Must Not Auto-Apply

When writing a task brief for `ao spawn`, **flag any destructive operation explicitly with "needs human approval / do NOT run --apply"**. The worker will otherwise add the destructive step to its "outstanding action" checklist and may attempt to run it on a follow-up turn (wa-2255, 2026-06-05: worker queued `run the recovery script with --apply` in its input buffer waiting for a green-light signal).

Examples of destructive operations:
- `recover_mojibake_entries.py --apply` (writes to Firestore, mutates user-visible story text)
- Any `--apply` / `--write` / `--commit --no-verify` flag that bypasses review
- `br update --status done` (closes a bead — irreversible without re-opening)
- `gh pr merge` (the project rule is "orchestrator merges, never the agent")
- `rm -rf` / `git reset --hard` / `git push --force` (no recovery)

**Pattern in task text:** "Outstanding action (NOT in this PR): `<command>`. This needs `<human role>`'s explicit go. Do not run `<command>` until the human confirms."

When you see a worker queue a destructive command in its prompt buffer, **clear it via tmux + send a stop message that names the human-approval requirement.** Do not trust the worker's own judgment to gate a destructive operation.

## Antigravity Trust-Prompt Auto-Dismiss (when the worker hangs on first spawn)

**Symptom:** `ao spawn` succeeds, tmux session appears, but the worker is stuck on:

```
Accessing workspace:
$HOME/.worktrees/<project>/<N>

Do you trust the contents of this project?

Antigravity CLI requires permission to read, edit, and execute files here.

> Yes, I trust this folder
  No, exit
```

`tmux capture-pane` shows the menu with "Gemini 3.5 Flash (High)" at the bottom and the worker is **not progressing**. This is the same root cause as `jleechanorg/agent-orchestrator-ts#657` ("fix(agent-antigravity): auto-dismiss agy workspace trust TUI") — the TUI is not being auto-dismissed on first spawn, the worker waits forever, and the cron-tick babysit reports a hung session.

**Fix (one shell call, no AO involvement):**

```bash
SESSION="<tmux-session-name>"   # e.g. 953501c04ccc-wa-2282
tmux send-keys -t "$SESSION" Enter
sleep 2
tmux capture-pane -t "$SESSION" -p -S -10 | tail -10   # confirm worker is reading files
```

A single `Enter` accepts the default ("Yes, I trust this folder"). The worker recovers and starts reading `git status`, `git log`, etc. on the next tick.

**When to apply:**
- Right after every `ao spawn` that uses a new worktree, **before arming a 20m status cron**
- After detecting "no commits in 2+ minutes on a brand-new session" via `git log` in the worktree
- After seeing the literal "Do you trust the contents of this project?" string in `tmux capture-pane` output

**When NOT to apply:**
- If the worker is mid-tool-call (`Generating…` at the bottom of the pane) — sending Enter interrupts it
- If the trust prompt was already accepted on a prior turn for the same worktree (subsequent spawns in the same path don't re-prompt)

**Source:** verified 2026-06-09 on `wa-2282` (phase-1 daily-level-up-diagnostic). Worker recovered in <2s, completed setup, created branch `phase1/...-diag`, and started reading the test file on the next tick.

## `running.json` bootstrap (when AO dashboard is alive but spawn complains "lifecycle polling is inactive")

**Deep dive: `references/ao-spawn-preflight-gotchas.md`** — covers both this error and
the related "✗ GitHub CLI is not authenticated" pre-flight failure. That reference
includes the hosts.yml rewrite pattern (env-var overrides don't propagate to the
AO tmux subprocess) and the full running.json shape with project-list validation.

**For the full 3-state diagnostic ladder (state A / B / C) when `ao spawn` hangs**, see
`references/ao-spawn-hang-3state-diagnostic.md`. The recipe below is the original
single-state (running.json missing) recipe; the 3-state version supersedes it for the
common case where the orchestrator IS alive but running.json is stale.

Symptom: `ao status` shows running sessions and the dashboard is on :3020, but
`ao spawn` errors with `✗ AO is not running — lifecycle polling is inactive. Run \`ao start\` before spawning sessions so they get CI/review routing and state advancement.`

Cause: the live state file at `~/.agent-orchestrator/running.json` is missing
or points at a dead pid. AO's `getRunning()` reads the file,
validates the pid is alive, and bails with the above message if the file is
absent or the pid inside is dead.

**Step 0 — verify orchestrator is actually up.** The orchestrator runs as a `node` process with `ao start` in its command line, but on this machine the child is `next-server (v15.5.18)`. Use the `ps ... | awk` form (NOT `pgrep -fl "ao start"`, which collides with the `awk` filter trick and is sometimes shadowed by other node processes):

```bash
# Mode A: in-process / unix-socket orchestrator (--no-dashboard, the default)
ps -eo pid,etime,command | awk '/[a]o start [a-z]/ && !/awk/'

# Mode B: TCP-port orchestrator (dashboard runs, listener on :3020)
lsof -nP -iTCP:3020 -sTCP:LISTEN
```

If both return empty, the orchestrator is genuinely down and you need to start it first. The `lifecycle-worker` subcommand **does not exist on this host's `ao` CLI** (verified 2026-06-20, $USER-ny4j dispatch) — there is no `lifecycle-worker` shortcut. The correct way to bring the orchestrator up is:

```bash
# CORRECT — `ao start` is a long-lived foreground process. Launch with
# terminal(background=true) so the gateway doesn't wait on it.
# MUST pass the explicit project name when multiple projects are configured;
# bare `ao start --no-dashboard --no-open` fails with "Multiple projects
# configured. Specify which one to start" — same failure as the dispatch-task
# skill documents at lines 197-204. Keep these two skills in lockstep.
cd <project-path> && ~/bin/ao start <project> --no-dashboard --no-open

# Then poll for `running.json` to appear (usually within ~5s of "Startup complete"):
for i in $(seq 1 18); do
  sleep 5
  [ -f ~/.agent-orchestrator/running.json ] && \
    PID=$(python3 -c "import json; print(json.load(open('$HOME/.agent-orchestrator/running.json')).get('pid',''))" 2>/dev/null) && \
    [ -n "$PID" ] && kill -0 $PID 2>/dev/null && { echo "READY at poll $i"; break; }
done
```

**Step 1 — only if orchestrator IS up but `running.json` is missing.** Write
it by hand pointing at the live orchestrator pid (use `ps ... | awk`, NOT
`pgrep -fl "ao start"`):

```bash
PID=$(ps -eo pid,command | awk '/[a]o start [a-z]/ && !/awk/ {print $1; exit}')
kill -0 $PID   # sanity check
cat > ~/.agent-orchestrator/running.json <<EOF
{
  "pid": ${PID},
  "configPath": "$HOME/.hermes_prod/agent-orchestrator.yaml",
  "port": 3020,
  "startedAt": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
  "projects": ["agent-orchestrator","browserclaw","cmux","claude-commands","hermes-agent","jleechanclaw","llm_wiki","mcp-mail","mctrl-test","openclaw-sso","ralph","worldai-claw","worldarchitect","worldclaw-dev"]
}
EOF
```

To get the real pid: `ps -eo pid,command | awk '/[a]o start [a-z]/ && !/awk/ {print $1; exit}'` (the orchestrator's `node` child is fine too — anything alive that AO can `kill -0` and that the daemon children know about). Verify with `kill -0 <pid>`. The `projects` array must include the project you intend to spawn against (or AO will reject with "not polling project X"). List the canonical config's project keys: `yq -r '.projects | keys | .[]' ~/.hermes_prod/agent-orchestrator.yaml`.

## Spawn-recovery ladder (full 4-step recipe)

The `3a-quater` one-liner handles a single layer of stale state. In practice, the spawn loop is a 4-step ladder (git → AO session → orchestrator → bootstrap) and each layer may need its own cleanup before the next attempt. Stopping at any layer and asking the user is the violation Jeffrey flagged 2026-06-13: "you should never randomly stop on a fixable AO problem — you should always be able to make a new worktree."

**Full recipe:** `references/3a-quinquies-spawn-recovery-ladder.md` — includes the exact commands, the architectural layer each step targets (git / AO session / orchestrator / bootstrap), and the `/tmp` brief file eviction mitigation.

**Step 5 (env-layer): the bash exec of the worker launcher hits ARG_MAX** — `ao spawn` prints the new session ID and then dies silently because the gateway shell's fat env (`AO_BOT_GH_TOKEN`, `GH_TOKEN_AGENTF`, `WAFER_API_KEY`, `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`, …) exceeds macOS's 256KB `ARG_MAX` when bash concatenates `bash <launcher>` with the full env. The smell: `Argument list too long` in stderr, `ao session ls` does not show the new ID. **Fix:** wrap the spawn in `env -i HOME=$HOME PATH=… GH_TOKEN=… AO_BOT_GH_TOKEN=… bash -c '…'` to drop the fat env, OR take the work inline per the §"DO IT INLINE" rule. Full recipe + diagnostic order in `references/arg-max-spawn-failure.md` (verified 2026-06-17 on PR #7479).

## Cross-reference: detailed `ao spawn` quickstart

For the canonical, verbose-form `ao spawn` invocation guide (project-ID discovery via `ao session ls`, the bead-as-task pattern, `--no-wait` semantics with the gateway's 30s terminal timeout, worktree-blocked-spawn workarounds), see:

- `dispatch-task` skill → `references/ao-spawn-quickstart.md`

This `agento` skill covers the *when and why* of dispatching; the `dispatch-task` reference is the *how* with the most up-to-date CLI flag syntax. If they ever disagree, the `dispatch-task` reference wins (it has the most recent verified 2026-06-09 baseline).

## Bring-to-Green Pitfalls (verified on worldarchitect PRs 7480, 7500, 7534)

These are the recurring failure shapes the bring-to-green AO worker must recognize and the dispatching gateway must brief in. They are independent of the CI tool surface and apply to any PR remediation.

### 1. PR description vs `gh pr diff --name-only` mismatch

**Symptom (verified 2026-06-13, PR #7534):** The PR body lists two file changes — e.g. "Restores `.github/workflows/mcp-smoke-tests.yml` AND reverts `.github/workflows/green-gate.yml`" — but `gh pr diff 7534 --name-only` shows only one of the two files in the actual diff. The body was written aspirationally; one of the planned commits was never landed, or was applied separately to `main` and forgotten.

**Why it happens:** PR descriptions get edited in two passes — first a draft (intent), then a follow-up commit (executed). Editors forget to re-sync the body, or assume a separate PR / direct push handled the second file. A rebase onto a moving `main` can also "absorb" a file's change if it was already merged into the base.

**Worker checklist before declaring "ready for review":**
1. `gh pr diff <N> --name-only` and compare to the PR body's "Files changed" / "Goals" list.
2. If the body claims a file revert/change that isn't in the diff, **land it as a new commit on the same branch** before re-requesting review. Don't assume "it's already on main" — verify with `git log origin/main -- <file> | head -3` and check the timing.
3. If the file IS already on main with the right shape, edit the PR body to drop the claim so the next reviewer doesn't get confused.

### 2. Self-hosted-runner `actions/checkout --depth=1` ref pollution

**Symptom (verified 2026-06-13, PR #7534 run `27475916175`):** 3+ different CI checks (Ruff, ESLint, detect-changes) all fail with `##[error]fatal: bad object refs/remotes/origin/feat/<other-branch>` and `exit code 128` from `git checkout --force <sha>`. The same `actions/checkout` step succeeds for the branch's actual head SHA but fails dereferencing a stale ref to a different branch's commits.

**Why it happens:** `org-runner-2` (the self-hosted runner) accumulates refs across all PR runs that touch it. `--depth=1` fetches the requested SHA's commit + tree but does NOT update sibling refs. When `git checkout --force <sha>` then tries to resolve `refs/remotes/origin/feat/<other-branch>` (referenced from a packfile or fetch metadata), it fails. This is **NOT a code issue with the PR** — the diff is clean YAML.

**Worker checklist when Ruff/ESLint/detect-changes all fail with `bad object refs/remotes/origin/...`:**
1. Confirm the failure is the ref pollution shape (not a real lint error). Grep the failed log for the literal `bad object refs/remotes/origin/` string.
2. **First attempt: re-trigger.** A fresh push, a re-`gh pr comment -b '@coderabbitai please re-review'`, or a no-op commit (`.github/workflows/mcp-smoke-tests.yml:1` `# refresh` → commit → push) usually clears it because the new `actions/checkout` run gets a fresh `--depth=1` fetch and the stale ref is no longer in the resolver's path. 80% of the time this is enough.
3. **Second attempt (if re-trigger doesn't clear):** modify the `actions/checkout` step to use `fetch-depth: 0` for the affected workflow. This is a slightly invasive CI change but is the documented fix for cross-branch ref pollution. If the change is in `mcp-smoke-tests.yml` itself, it's already in scope for a CI-only PR.
4. **Don't shotgun-edit linting configs.** If real lint errors surface after the ref pollution clears, address them; if not, leave Ruff/ESLint rules alone.

### 3. CodeRabbit `CHANGES_REQUESTED` after a push of fixes

**Symptom:** A push of a "fixed" commit lands but CR's `reviewDecision` stays `CHANGES_REQUESTED` and no new review is auto-triggered. Worker loops trying to "make CR happy" without realizing CR hasn't re-reviewed.

**Worker checklist:**
1. After pushing a fix, explicitly re-request review: `gh pr comment <N> -b '@coderabbitai please re-review'` (or use the PR's "Re-request review" UI button via `gh pr edit --add-reviewer` if available).
2. Wait for CR to post a new review. CR reactions are not the same as a fresh review — check the timeline for a NEW `submittedAt` from `coderabbitai[bot]`.
3. If CR still hasn't re-reviewed after 5 min, post a single nudge comment. Don't repeat the nudge more than once — that just burns the PR's signal-to-noise.

### 4. Green Gate Gate-8 stale `/smoke fail` comment on an old SHA

**Symptom (verified 2026-06-17, PR #7479 runs 27451026142 + 27490063538):** the Green Gate workflow logs `GATE-8 FAIL: /smoke comment reports failure for SHA 526e237` even though the latest push's SHA is different and the most recent mcp-smoke-tests run actually succeeded. The Green Gate workflow polls the PR timeline for a `/smoke pass` OR `/smoke fail` comment matching the SHA; a stale `MCP Smoke Tests Failed` comment from a prior head SHA persists in the timeline and the gate latch-FAILs on the substring match.

**Why it happens:** mcp-smoke-tests is triggered by a `/smoke` PR comment and its verdict comment (`MCP Smoke Tests Passed` / `MCP Smoke Tests Failed`) is the authoritative signal. When the PR head moves but the old verdict comment is still in the thread, the gate sees "fail" and bails — even if the new head is green.

**Worker checklist when Green Gate fails with `GATE-8 FAIL: /smoke comment reports failure for SHA <old-sha>`:**
1. `gh pr view <N> --json comments` and search for any `MCP Smoke Tests Passed/Failed` comment that's older than the current head SHA.
2. **Do NOT delete the old comment** (it's part of the PR audit trail). The fix is to post a fresh `/smoke pass` for the current head SHA.
3. Force-push (or no-op commit + push) to advance the head SHA, then post `gh pr comment <N> -b '/smoke'` to trigger a fresh mcp-smoke-tests run on the new SHA.
4. Wait for the new `MCP Smoke Tests Passed` comment to land (timeline filter: `submittedAt > head_push_time`). Green Gate will see the new pass and clear Gate-8 within ~30s.
5. If the fresh `/smoke` run itself fails, that's a real signal — investigate the smoke logs, don't loop re-trying.

**Heuristic to recognize this pattern:** Green Gate fails on Gate-8 with a SHA that's NOT the current head SHA → stale `/smoke fail` comment, post a fresh `/smoke`. Green Gate fails on Gate-8 with the current head SHA → real smoke failure, dig into the logs.

### 5. Overlapping PRs targeting the same test failure — sequencing matters

**Symptom (verified 2026-06-17, PRs #7479 + #7507):** two open PRs both target the same `god_mode_reward_visibility` daily-test failure. One is a small prompt-only fix (2 commits, +108/-1), the other is a heavier production-code atomic-pair guard (5 commits, +398/-6 in `$PROJECT_ROOT/world_logic.py`). The lighter PR was independently green-ready; the heavier PR was CONFLICTING with main and needed a rebase. The user said "drive both to green via cmux."

**Pattern when two PRs both fix the same root cause:**
1. **Land the lighter one first.** Smaller blast radius, faster Green Gate, lower risk of regressions. If the lighter PR clears the daily test on `main`, the heavier PR's atomic-pair code may be partially or fully obviated.
2. **AO enforces a single in-flight `ao spawn` per project** (see "Per-project concurrent-spawn lock" above). For overlapping PRs in the same repo, queue them sequentially — spawn the lighter first, wait for terminal state, then spawn the heavier.
3. **Brief the second worker about the first PR's status.** Tell it: "PR #7479 was the prompt-only fix; if it landed and the daily test now passes, your atomic-pair code may be superseded. File a comment on your PR asking Jeffrey merge-vs-close rather than force-merging." This avoids wasted rebase + Green Gate cycles on a PR that becomes redundant.
4. **Don't rebase the heavier PR until the lighter one has a clear verdict.** Rebase cost on a 5-commit PR with CONFLICTING state is 5-15 min; if it then becomes unnecessary, that's wasted work.

## Co-writing a branch with an AO worker — the "always check origin..HEAD" pitfall (2026-06-12)

**Scenario:** Jeffrey asks "spawn an AO worker to /green PR #N" while the gateway is also tracking the PR. Both ends may try to commit to the same branch. If the worker pushes commits while the gateway is also editing files, the gateway's `git push` will be rejected with `Updates were rejected because the remote contains work that you do not have locally`.

**Symptom (verified 2026-06-12, PR #7500):**
- AO worker landed 3 commits (`33bd8e17a9`, `abf4726b79`, `ecf6ee1386`, `12ab8374f6`) on `chore/7500-pr-scoped-dice` while the gateway was applying CodeRabbit review fixes
- Gateway's `git push` was rejected: `Updates were rejected because the remote contains work that you do not have locally`
- Gateway had to `git reset --hard origin/<branch>` and re-apply its own diffs on top of the new remote tip

**The lesson:**

1. **Before committing on a branch an AO worker owns, ALWAYS check `git log origin/<branch>..HEAD` first.** If the remote has moved past your local HEAD, the worker is actively committing — wait or coordinate via `ao send`.

2. **If the gateway has to land fixes that the worker should be making, `ao send` the worker instead of editing in the gateway.** The worker's job is to drive the PR green. The gateway's job is to monitor and steer, not to compete with the worker. The two cases where the gateway MUST edit directly:
   - The worker is stuck or timed out and the user is explicitly waiting
   - The fix is a 1-line config/script change and dispatching a new worker would burn 10+ minutes for a 30-second edit

3. **Use the reset-and-rebase pattern when you must edit:** `git fetch origin <branch>` → `git reset --hard origin/<branch>` → re-apply your diff → `git commit` (a new commit on top, not `git commit --amend`) → `git push`. `--amend` here is wrong because it would rewrite history the worker built.

4. **Check the AO worker's commit messages for the worker's own scope creep.** On PR #7500, the worker iterated 3 times on the firebase-uid lookup logic (Google OAuth provider, then commit-email fallback, then `get_user_by_email` direct lookup) but **never addressed any of CodeRabbit's 4 review comments**. The worker's output is not the same as the review being addressed. Use `gh api graphql` to dump review comments, then `git log -p` to confirm the worker touched the right lines.

5. **The 10-minute AO worker timeout is a tool-level limit, not the worker's actual end.** When `delegate_task` returns with no result, the worker may have already landed commits. ALWAYS `git fetch origin <branch>` after a timeout before assuming the worker did nothing.

**Where this belongs in the workflow:** the green-up loop is **sequential, not parallel**. Either (a) the gateway drives the PR and only spawns the worker when blocked, or (b) the worker drives the PR and the gateway just monitors via `gh pr checks` + `ao status`. Mixing the two roles in the same branch without coordination causes duplicate work and merge churn.

## Common Pitfalls

### Stale running.json / Lifecycle Blackout ("lifecycle polling is inactive")
If a previous orchestrator instance crashed or stalled, a stale `running.json` file is left behind, causing `ao spawn` to fail with `"lifecycle polling is inactive"`.
- **Mitigation**: Follow the 3-state recovery ladder defined in [3a-quinquies-spawn-recovery-ladder.md](file://$HOME/.hermes_prod/references/3a-quinquies-spawn-recovery-ladder.md) to detect and recover from stalled or dead daemon states.
- **Validation**: Use `scripts/validate-state.sh` (or `~/.hermes_prod/scripts/validate-state.sh`) to query the running state of the orchestrator and get a direct IDLE/STALLED/HEALTHY verdict.
