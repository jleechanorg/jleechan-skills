---
name: cmux-cli-restore
description: "Exit a stuck CLI inside a cmux terminal surface and restart it with the resume wrapper (`codexc` = `codex resume --last`, `claudec` = `claude --continue`, `claudewac`, `codexdc`). Use when a lane is wedged on a usage-limit wall, a model-capacity refusal, a 429 retry exhaustion, a stalled model turn, a malformed prompt, or an abandoned background-terminal wait, and the operator says 'restart that lane', 'exit and resume it', 'ctrl-c it and start it again'. Also use when a TUI left the shell holding `9;5u` / `17;5u` CSI-u keystroke garbage after the app quit."
---

# cmux-cli-restore — exit the CLI, restart it with the resume wrapper

The whole procedure in one line: **exit the app cleanly, sanitize the shell line, restart with
`codexc` / `claudec`, verify at the process level.**

That is all this skill does. It is not a session-recovery framework, it does not restore work, and it
does not pretend a restart clears a wall the wall itself has not cleared.

## What "restart" means here (say it precisely)

`codexc` is `codex resume --last` and `claudec` is `claude --continue`. So a "restart" is:

- a **new CLI process** on the surface's tty, and
- the **same conversation**, resumed from its own session file.

Nothing is lost and nothing starts over. Verified on 9 Codex lanes at once: each tty showed a fresh
`/usr/bin/command codex resume <uuid>` while the long-lived session stayed intact.

## Procedure

1. **Resolve the surface and its CLI.** Never guess from the title.
   ```bash
   cmux top --workspace <ws> --processes | grep "surface surface:<sf>"   # gives tty=ttysNNN
   ps -Ao pid,tty,etime,command | awk '$2=="ttysNNN"'
   ```
   | process on the tty | CLI | restart with |
   |---|---|---|
   | `/usr/bin/command codex resume …` or `node …/@openai/codex` | Codex | `codexc` |
   | `claude` (with `CLAUDE_CONFIG_DIR=~/.claude-wa` in its env) | claudewa | `claudewac` |
   | `claude` | Claude Code | `claudec` |
   | `agy.real --conversation …` | Antigravity | no resume alias — relaunch `agy` and pick the conversation |
   | `pi` | pi | no wrapper — relaunch `pi` |
   | only a shell | nothing to restore | stop; it is a `SHELL` surface |

2. **Exit it.** `cmux send-key --workspace <ws> --surface <sf> ctrl+c`, wait ~3 s, then check for the
   shell prompt. Codex sometimes needs a second `ctrl+c`. Do not proceed until you can see the prompt.

3. **Sanitize the shell line — this step is not optional.** A TUI that enabled the enhanced keyboard
   protocol can leave CSI-u fragments (`9;5u`, `17;5u`, `5u`) sitting on the shell line after the app
   quits. Typing on top of that produces `bash: 5ucodexc: command not found`. Send `ctrl+c` (bash
   cancels the line) and confirm the prompt is clean *before* typing anything.

4. **Restart with the wrapper — aimed at THIS conversation.** `codexc` is `codex resume --last`, and
   "last" is not "this one": a newer conversation in the same directory wins. So resolve the lane's
   session id from the pre-restart process listing and resume it explicitly (`codex resume <uuid>`).
   If the id cannot be resolved, stop — do not fall back to `--last`. Then submit with an explicit Enter:
   ```bash
   cmux send --workspace <ws> --surface <sf> "codexc"   # or claudec / claudewac
   cmux send-key --workspace <ws> --surface <sf> enter
   ```
   A Codex resume can open a goal dialog (`1. Resume goal` / `2. Leave paused`). It lands on
   `1. Resume goal` — one `enter` accepts it.

5. **Verify from the process, not the screen — and require a NEW pid.**
   ```bash
   ps -Ao tty,pid,etime,command | awk '$1=="ttysNNN" && /codex resume|claude/'
   ```
   Snapshot the pids before the restart and require one that was not there, **and** require the resumed
   conversation to be the same id (a `--last` resume into a different session exits 10): an old process that
   survived is **not** a restart, and `bash: 5ucodexc: command not found` leaves exactly that
   situation (the old TUI still running while your command never ran). Check the `send` and `Enter`
   exit codes too; a swallowed send failure must not be reported as success.
   Then confirm the *session* is live: its transcript file mtime should be seconds old, not hours.
   Codex: newest `~/.codex/sessions/**/rollout-*<uuid>*.jsonl`. pi: `~/.pi/agent/sessions/*/*.jsonl`.

## What a restart does NOT fix

Report these instead of restarting, because a restart only re-hits the same wall:

| Wall | How it reads | Real unblock |
|---|---|---|
| Usage allowance spent | `You've hit your usage limit … try again at <date>` | wait for the reset, or switch plan/proxy |
| Model at capacity | `Selected model is at capacity. Please try a different model.` | different model, or wait |
| 429 retry exhaustion | `exceeded retry limit, last status: 429 Too Many Requests` | wait; a restart burns another retry |
| 8-hour autonomy box | `autonomy rule requires a live human renewal` / `eight-hour authorization expired` | a live human renewal, not a restart |
| Human gate | `Goal remains blocked pending human merge approval` | `MERGE APPROVED` |

## Traps that have burned this exact procedure

1. **Stale banners are history, not state.** A lane can display `You've hit your usage limit` in
   scrollback while working perfectly. Prove it by sending one real prompt; do not declare a lane dead
   from a banner that sits above the current composer.
2. **CSI-u garbage.** See step 3. Symptom: `bash: 9: command not found`, `bash: 5ucodexc: command not
   found`. The cause is the terminal still encoding keys as `ESC [ code ; mods u`; `ctrl+c` on the
   shell line is the cheap fix, `printf '\x1b[<u'` pops the mode, and `reset` is the sledgehammer.
3. **A live step timer is not progress.** `(1h 38m • esc to interrupt)` can mean "waiting on a
   background terminal that no longer exists". Check the session-file mtime.
4. **Do not restart a lane that is waiting on a human.** `Goal remains blocked pending human merge
   approval` is not a wedged CLI.
5. **One lane, one writer.** Never restart a lane mid-push, and never restart two surfaces that share
   a worktree concurrently.

## Automation

`scripts/cmux-cli-restore.sh` does steps 1-5 for one surface, and supports `--dry-run` (report the CLI
and the plan, touch nothing) and `--list-above-p1` (enumerate in-scope terminal surfaces with their CLI
and last session-write age, so you can pick the wedged ones instead of restarting everything).

```bash
scripts/cmux-cli-restore.sh --dry-run --workspace workspace:1000120002 --surface surface:1000120005
scripts/cmux-cli-restore.sh --list-above-p1
scripts/cmux-cli-restore.sh --workspace workspace:1000120002 --surface surface:1000120005
```

The script refuses to type into a surface whose prompt line still contains CSI-u residue, and it
verifies the restart at the process level before reporting success.
