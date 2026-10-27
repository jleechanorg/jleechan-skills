---
name: cmux-cli-restore
description: "Exit a stuck CLI inside a cmux terminal surface and restart it with the resume wrapper (`codexc` = `codex resume --last`, `claudec` = `claude --continue`, `claudewac`, `codexdc`). Use when a lane is wedged on a usage-limit wall, a model-capacity refusal, a 429 retry exhaustion, a stalled model turn, a malformed prompt, or an abandoned background-terminal wait, and the operator says 'restart that lane', 'exit and resume it', 'ctrl-c it and start it again'. Also use when a TUI left the shell holding `9;5u` / `17;5u` CSI-u keystroke garbage after the app quit, when a Codex lane is blocked by a usage limit and should continue on Claude, or when cmux lost surfaces/workspaces (shells killed) and they must be recreated from the session snapshot."
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
   | `agy.real --conversation …` | Antigravity | no resume alias — relaunch `agy --model <slug>` and recover context with `/hr` (see § Swap a usage-limited Claude lane to Gemini) |
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
   session id from the pre-restart process listing and resume it explicitly. If the id cannot be
   resolved, stop — do not fall back to `--last`. `claudec`/`claudewac` cannot be identity-verified this
   way, so a Claude lane is refused rather than resumed blind.
   ```bash
   cmux send --force --workspace <ws> --surface <sf> "codex resume <uuid>"
   cmux send-key --force --workspace <ws> --surface <sf> enter
   ```
   **Do not accept a goal dialog here.** A Codex resume can open `1. Resume goal` / `2. Leave paused`,
   and pressing Enter lets the lane start work immediately. Acceptance happens only in step 5, after the
   resumed conversation has been proven to be the right one.

5. **Verify from the process, not the screen — and require a NEW pid.**
   ```bash
   ps -Ao tty,pid,etime,command | awk '$1=="ttysNNN" && /codex resume|claude/'
   ```
   Snapshot the pids before the restart and require one that was not there, **and** require the resumed
   conversation to be the same id (a `--last` resume into a different session exits 10). **Only after
   that check passes** may a `Resume goal` dialog be accepted — a wrong or unknown session must never
   reach the point where the lane begins work: an old process that
   survived is **not** a restart, and `bash: 5ucodexc: command not found` leaves exactly that
   situation (the old TUI still running while your command never ran). Check the `send` and `Enter`
   exit codes too; a swallowed send failure must not be reported as success.
   Then confirm the *session* is live: its transcript file mtime should be seconds old, not hours.
   Codex: newest `~/.codex/sessions/**/rollout-*<uuid>*.jsonl`. pi: `~/.pi/agent/sessions/*/*.jsonl`.

## What a restart does NOT fix

Report these instead of restarting, because a restart only re-hits the same wall:

| Wall | How it reads | Real unblock |
|---|---|---|
| Usage allowance spent | `You've hit your usage limit … try again at <date>` | wait for the reset, or **swap the lane to Claude** (next section) |
| Model at capacity | `Selected model is at capacity. Please try a different model.` | different model, or wait |
| 429 retry exhaustion | `exceeded retry limit, last status: 429 Too Many Requests` | wait; a restart burns another retry |
| 8-hour autonomy box | `autonomy rule requires a live human renewal` / `eight-hour authorization expired` | a live human renewal, not a restart |
| Human gate | `Goal remains blocked pending human merge approval` | `MERGE APPROVED` |

## Swap a usage-limited Codex lane to Claude (verified 2026-10-27, 9 lanes)

A restart re-hits the Codex wall, so continue the work on Claude instead. Per surface:

1. `ctrl+c` twice (`--force` if a dialog is open); capture and require a shell prompt (`[$%] ?$`). If not at a shell, stop and report.
2. `cmux send ... "ANTHROPIC_MODEL=claude-sonnet-5-5 claude --permission-mode bypassPermissions"` then `send-key enter` (the full-permission mode the Codex lane ran with, e.g. `--yolo`, is preserved).
3. Poll `capture-pane` until `bypass permissions` or `? for shortcuts` appears (≤36 s); a folder-trust prompt means stop and report.
4. `cmux send ... "/hr resume the work this Codex session was doing in this worktree; it stopped at the usage limit; continue until done."` then `send-key enter`.
5. Verify a spinner line (`✻ Thinking… (12s`) within ~60 s, via two captures. A Claude lane that ends its first turn with a recap and "needs MERGE APPROVED" is not stuck: send once, "do not stop at a recap; continue every step that does not need a user-only gate (merge approval, credentials, spend)".

Other Codex traps seen in the same run: a `Hooks need review` menu (`1. Review hooks / 2. Trust all / 3. Continue without trusting`) — pick **3** (`cmux send ... "3"` selects immediately); never choose "Trust all" for the user. A `Resume goal / Leave paused` menu: Enter resumes (only after the session id check in step 5).

## Swap a usage-limited Claude lane to Gemini (agy) — verified 2026-10-27, 20 lanes

When Claude is walled (`You've hit your session limit · resets <time>`) the lane is stuck until the reset, and
a restart re-hits the same account-level wall. Gemini is a different provider and keeps working — `agy models`
currently offers `gemini-4-argon-{high,medium,low}` and `gemini-3.8-flash-*`; never fall back to Gemini 3.1 Pro
or older Pro models. Per surface:

1. **`escape` first — always.** A walled lane re-arms itself (`Continuing automatically at 4:20pm · esc to
   cancel`). Until that wait is cancelled, `/exit` is swallowed and the lane looks unexitable. Require the
   confirmation `Automatic continue cancelled`.
2. `cmux send --force … "/exit"` then `send-key --force … enter`. The three-option menu (`1. Exit and stop
   tasks / 2. Move to background and exit / 3. Stay`) defaults to **1**; Enter accepts it. Prefer **2** only when
   live subagents are worth keeping — on a dead provider quota they are normally already dead.
3. Require a real shell prompt. The pane prints `Resume this session with: claude --resume <uuid>` just above it;
   keep that uuid — it is the only route back to Claude after the reset.
4. `cmux send --force … "agy --model gemini-4-argon-high"` then `send-key --force … enter`.
5. Wait for a frame containing `Gemini 4 Argon` **and** the composer `>` (≈3 s, poll ≤36 s). Do not type into the
   "Meet Gemini 4 Argon" splash — see trap 9.
6. Send the resume brief in ONE line: cwd, branch, PR number, why the previous session died, and the literal words
   `Run the /hr history-resume workflow`. `agy` has no session-resume alias, so `/hr` (or the worktree's own
   `nextsteps`/bead state) *is* the recovery mechanism.
7. Verify the model AND a turn: `Gemini 4 Argon · high` in the footer, plus `● Ran …` / `● Explored …` /
   `Thought for …`, plus a second capture that shows the screen changed.

### What this actually buys you (measured across 20 lanes)

`/hr` is read-heavy by design, so the first turn yields a briefing, not code. After switching 20 lanes: 8 were
running a command or delegating subagents, 12 finished the one step they were given and parked at the composer,
and **0 had edited a file** — no `● Edited`/`● Created`, and every recent worktree mtime was `__pycache__/*.pyc`.
If you want code, make it standing: "work autonomously to the PR's next gate — green CI plus the evidence its
stage needs — take multiple steps without stopping to report; stop only at an operator-only gate". Sending that
to the 12 parked lanes moved 10 of them to `esc to cancel`/`task(s)` within 25 s. The other two were parked
legitimately (an `APPROVED` PR with nothing left but `MERGE APPROVED`; a lane holding on an explicit operator
hold) — read the tail before assuming a parked lane is broken.

## Surfaces lost, not wedged (shells killed, workspace closed)

Different problem: the process is gone, so there is nothing to ctrl-c. Recreate from the autosaved snapshot, never from memory.

- Snapshots: `~/Library/Application Support/cmux/session-history/*.json` (newest before the incident); each terminal panel carries `terminal.resumeBinding.command`, `kind`, `checkpointId`. Events (`~/.cmuxterm/events.jsonl`) rotate within hours; `closed-item-history-*.json` holds only individually closed panels.
- Diff **panel ids**, not just workspace ids. Workspaces that survive on their browser tabs lose all their terminals (a workspace-level diff misses them). After a first restore the ids change, so match by title or a state file or a retry duplicates the workspace.
- Recreate: `cmux workspace create --name=<title> --cwd <dir> --focus false [--command <resume cmd>]` (write `--name=`; a title starting with `-----` is parsed as a flag), extra terminals `cmux new-surface --workspace <ref> --working-directory <dir> --focus false --command …`, browser tabs `new-surface --type browser --url <urlString>`, then `workspace-action --action pin` and `reorder-workspace --index <n>` to snapshot order. Never `select`/focus. Skip a panel whose cwd no longer exists; cloud (VNC) workspaces reject `new-surface`.
- Closing a duplicate you created: pinned workspaces refuse `close-workspace` until unpinned.
- Reference implementation: `~/.cmux-backups/cmux_restore_round2.py` (workspaces) and `cmux_restore_round3_surfaces.py` (surfaces in survivors). Record the order, pins and surfaces in `~/roadmap/cmux-workspace-layout-<date>.md` for the next incident.
- Restore authorization: a clear live user request is enough (relaxed 2026-10-27); never close or replace live workspaces to make it fit.

## Submitting text to a resumed lane

`cmux send` refuses when the agent prompt already holds unsent text ("holds text someone is typing"); the following `send-key enter` then submits the **old** text. Read the composer first; send the message, then Enter, then confirm the composer cleared.

## Traps that have burned this exact procedure

0. **A stale footer is the worst liar in this file.** `⏵⏵ bypass permissions on · ← 2 agents` keeps rendering
   under a pane that is walled on `Usage limit reached · Continuing automatically at 4:20pm`. Bucketing lanes on
   that footer produced a "10 stalled" list when the true number was **15** (2026-10-27, operator caught the
   miss). Classify on the limit text and on `esc to cancel` versus a bare `? for shortcuts`, never on the footer.
1. **An open Codex dialog swallows everything.** If the surface rests on a Codex menu
   (`Press enter to confirm or esc to cancel`, `Enter to select`), plain keystrokes are dropped and
   `cmux send` refuses without `--force` — so your exit *and* your `codexc` both vanish with no error.
   Send `esc --force` first, then use `--force` on the exit and restart keys. Verified live: without it,
   a lane sat on its interrupt menu through three ctrl+c attempts and a codexc.
2. **Stale banners are history, not state.** A lane can display `You've hit your usage limit` in
   scrollback while working perfectly. Prove it by sending one real prompt; do not declare a lane dead
   from a banner that sits above the current composer.
3. **CSI-u garbage.** See step 3. Symptom: `bash: 9: command not found`, `bash: 5ucodexc: command not
   found`. The cause is the terminal still encoding keys as `ESC [ code ; mods u`; `ctrl+c` on the
   shell line is the cheap fix, `printf '\x1b[<u'` pops the mode, and `reset` is the sledgehammer.
4. **A live step timer is not progress.** `(1h 38m • esc to interrupt)` can mean "waiting on a
   background terminal that no longer exists". Check the session-file mtime.
5. **Do not restart a lane that is waiting on a human.** `Goal remains blocked pending human merge
   approval` is not a wedged CLI.
6. **One lane, one writer.** Never restart a lane mid-push, and never restart two surfaces that share
   a worktree concurrently.
7. **Never kill by pattern.** Do not clear a stuck lane with `pkill`/`killall`: macOS `pkill -f x -u me` matches `/usr/bin/login` and closed 20-21 cmux workspaces twice (2026-10-26, 2026-10-27). Use `ctrl+c` on the surface, or `pgrep -f -- '<anchored>'` then `kill <PID>`.
8. **The dialog flag latches after the dialog is gone.** Once a surface has shown a dialog, `cmux send` and
   `send-key` keep refusing with `surface:<id> is waiting on a question or dialog` **while a live shell prompt is
   on screen**. Every write to that surface then needs `--force`. Verified on 20 lanes in one pass.
9. **A parenthesised first prompt lands in bash, not the agent.** If the resume brief reaches the shell (agy still
   on its splash), bash answers `syntax error near unexpected token '('` — the tell that your text never reached
   the agent. Send a paren-free brief, only after the composer appears, and read that error as "check the CLI is
   up", not "the shell is broken".
10. **Delegation is invisible from the footer line.** `? for shortcuts · 1 subagent(s)`, or a
    `● Agent(self: …) Generating · 19m7s` line, means the lane IS working while its composer sits empty. Grep for
    `subagent(s)` and `● Agent(` before labelling a quiet pane idle.

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
