---
name: agent-orchestrator
description: "Use this skill when working in repositories managed by Agent Orchestrator or when the user asks how to use `ao` properly. Covers the default AO workflow: bootstrap with `ao start`, dispatch work with `ao spawn`, inspect progress with `ao status` or `ao session ls`, steer sessions with `ao send`, and recover or clean up sessions safely. Includes strict parameter fidelity, pre-spawn cap cleanup, quota-wall fallback, and post-spawn verification."
---

# Agent Orchestrator

Use AO for durable coding work instead of manually creating worktrees or running agent CLIs directly. User-specified AO constraints (`--agent`, `--runtime`, `--project`, `--claim-pr`, target PR/branch/evidence standard) are mandatory — never substitute another agent/runtime because defaults exist.

## Default workflow

1. Bootstrap the repo or project with `ao start`.
2. Dispatch non-trivial coding work with `ao spawn`.
3. Inspect live state with `ao status` or `ao session ls`.
4. Send follow-up instructions with `ao send`.
5. Recover or clean up sessions with `ao session restore` and `ao session cleanup`.

## Commands to prefer

```bash
# Start AO in the current repo
ao start

# Start AO for another local repo or clone from GitHub
ao start ~/path/to/repo
ao start https://github.com/owner/repo

# Dispatch work
ao spawn "fix the flaky GitHub SCM retry path"
ao spawn -p agent-orchestrator bd-1234
ao spawn --project agent-orchestrator --claim-pr 456

# Inspect and steer work
ao status
ao session ls
ao send <session-id> "Also update the failing test coverage."

# Recovery and cleanup
ao session restore <session-id>
ao session cleanup --dry-run
```

## Read first

- `~/.hermes/agent-orchestrator.yaml` — **ALWAYS read this first** to resolve `--agent` shorthands (e.g. `agy`=`antigravity`); `defaults.agent` is the default when none specified.
- `references/config.md` — config schema for editing `agent-orchestrator.yaml`.
- `~/.claude/skills/ao-worker-dispatch/SKILL.md` — pre-dispatch checklist (venv, commit discipline, branch drift, CodeRabbit verify).
- `~/.claude/skills/ao-operator-discipline/SKILL.md` — strict parameter fidelity + post-spawn verification.
- `~/.claude/skills/ao-spawn-gate/SKILL.md` — pre-spawn safety gate.
- `~/.claude/skills/ao-session-monitor/SKILL.md` — proper tmux inspection for live workers.
- `~/.claude/skills/ao-model-override/SKILL.md` — override the worker's model (e.g. claude-sonnet-4-6, claude-opus-4-7) WITHOUT editing `~/.hermes/agent-orchestrator.yaml`. Use whenever the user names a specific model and the project default isn't it (e.g. "use claude sonnet with AO"). `ao spawn` has NO `--model` flag; the only inline override is `AO_CONFIG_PATH` pointing at a temp copy of the config — the skill ships `spawn-with-model.sh` for this.

## Working rules

- Prefer `ao spawn` for coding, debugging, CI fixes, review follow-up, and multi-step work.
- Use direct shell commands only for quick diagnostics or when AO itself is unavailable.
- If multiple projects are configured and cwd does not disambiguate, pass `-p, --project`.
- Prefer the existing AO session lifecycle over ad hoc worktrees and hand-run agent CLIs.
- When editing AO config, read `references/config.md`.

## When not to use AO

- Tiny read-only checks: `git status`, `gh pr view`, `rg`, simple file inspection.
- One-off local diagnostics where starting a full worker would be slower than the task.

## Spawn admission and resource handling

Before a spawn, follow `ao-spawn-gate/SKILL.md`; for bulk or iterative spawn
sequences, also follow `ao-spawn-safety/SKILL.md`. Those are the current
owners for the live channel setting, AO worker cap, batch size, and GitHub API
quota handling. Do not copy their mutable values into a local environment
variable or treat old defaults/history as the current setting.

If an applicable worker/channel limit is reached, defer only the new spawn and
report the measured count and resumption condition. Do not run `ao session
cleanup`, kill workers, or raise a cap automatically. Preserve unrelated
sessions and continue independent authorized work.

An activity or quota statement in a worker pane is only a lead. Before
classifying a worker or provider as blocked, use the full-history, two-sample
procedure in `ao-session-monitor/SKILL.md` and record the current provider
status with its source and timestamp. Do not classify from a grep/tail result,
count matching keywords, or route to a different provider automatically.
Honor explicit user-selected agent/runtime/model constraints. Consider an
alternative only when the task permits it and current evidence confirms the
requested provider cannot complete the specific operation.

Historical provider-quota incidents are dated diagnosis context, not current
provider defaults or authorization to clean up sessions or change the worker.

## Parameter fidelity and post-spawn verification rules

1. Respect explicit AO parameters exactly:
   - `--agent`
   - `--runtime`
   - `--project`
   - `--claim-pr`
   - target PR / branch / evidence standard

2. Never substitute another agent/runtime because defaults exist.

3. After every `ao spawn`, verify the spawned session file under `~/.agent-orchestrator/.../sessions/<session>`:
   - `agent=<expected>`
   - `runtimeHandle.data.launchCommand` contains the expected CLI

4. If the user asked for Codex workers, the session must show:
   - `agent=codex`
   - `launchCommand` contains `codex`

5. After metadata verification, inspect the tmux pane with at least 20 lines:
   - `tmux capture-pane -pt <tmux-session>:0.0 -S -40`

6. If verification fails, kill and replace the worker. Do not continue with a mismatched worker.

## Output requirements

When reporting AO setup or supervision, include:
- the exact session ids
- the target PR URLs
- proof of `agent=<expected>`
- proof of `launchCommand`
- whether each worker is productive, drifting, or dead
- **the preflight cap-check output (active count, dry-run, post-cleanup count)**

## Related files

- Config reference: `references/config.md`
- CLI help: `ao --help`, `ao spawn --help`, `ao start --help`
- Repo policies: `AGENTS.md`, `CLAUDE.md`
- **Binary installation norms:** [Binary Installation — Canonical Install Paths](../../AGENTS.md#binary-installation--canonical-install-paths) — `scripts/setup.sh` for repo maintainers, `npm install -g @jleechanorg/ao-cli` for others; `ao doctor` must pass after any install or update
