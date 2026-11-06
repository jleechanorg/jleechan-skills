---
name: cmux-cli-restore
description: "Exit a stuck CLI inside a cmux terminal surface and restart it with the resume wrapper (`codexc` = `codex resume --last`, `claudec` = `claude --continue`, `claudewac`, `codexdc`). Use when a lane is wedged on a usage-limit wall, a model-capacity refusal, a 429 retry exhaustion, a stalled model turn, a malformed prompt, or an abandoned background-terminal wait, and the operator says 'restart that lane', 'exit and resume it', 'ctrl-c it and start it again'. Also use when a TUI left the shell holding `9;5u` / `17;5u` CSI-u keystroke garbage after the app quit, when a Claude lane is walled and should continue on Gemini (agy), when a Codex lane is blocked by a usage limit and should continue on Claude, or when cmux lost surfaces/workspaces (shells killed) and they must be recreated from the session snapshot."
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
   | `agy.real --conversation …` | Antigravity | no resume alias — relaunch `agy --model gemini-3.8-flash-high` and recover context with `/hr` (see § Swap a usage-limited Claude lane to Gemini) |
   | `pi` | pi | no wrapper — relaunch `pi` |
   | only a shell | nothing to restore | stop; it is a `SHELL` surface |

2. **Exit it.** First confirm the limit/wedge text is the lane's current state: full scrollback plus two captures 20-30 s apart, no live spinner or subagent growth; a stale banner above active work means leave it. Then `cmux send-key --workspace <ws> --surface <sf> ctrl+c`, wait ~3 s, then check for the
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
   Then confirm the *session* is live from its transcript or session record. A fresh mtime alone, a timer, spinner,
   banner, or changed screen does not prove progress; require a new non-timer transcript/session event. If that
   evidence is unavailable, report the resume as unverified.
   Codex: newest `~/.codex/sessions/**/rollout-*<uuid>*.jsonl`. pi: `~/.pi/agent/sessions/*/*.jsonl`.

## What a restart does NOT fix

Report these instead of restarting, because a restart only re-hits the same wall:

| Wall | How it reads | Real unblock |
|---|---|---|
| Usage allowance spent | `You've hit your usage limit … try again at <date>` | wait for the reset, or **swap the lane**: Codex lane to Claude, Claude lane to Gemini (next two sections) |
| Model at capacity | `Selected model is at capacity. Please try a different model.` | different model, or wait |
| 429 retry exhaustion | `exceeded retry limit, last status: 429 Too Many Requests` | wait; a restart burns another retry |
| 8-hour autonomy box | `autonomy rule requires a live human renewal` / `eight-hour authorization expired` | a live human renewal, not a restart |
| Human gate | `Goal remains blocked pending human merge approval` | `MERGE APPROVED` |

## Swap a usage-limited Codex lane to Claude (verified 2026-10-27, 9 lanes)

A restart re-hits the Codex wall, so continue the work on Claude instead. Per surface:

0. **Confirm the wall is current before touching the lane.** Follow `cmux-steer`'s full-buffer rule and use independent process/session evidence; never decide from a tail or grep. If the lane shows active work, a dialog, or the evidence is inconclusive, leave it. Record the Codex session id so the lane can return to Codex after the reset.
1. `ctrl+c` twice (`--force` if a dialog is open); capture and require a shell prompt (`[$%] ?$`). If not at a shell, stop and report.
2. `cmux send ... "ANTHROPIC_MODEL=claude-sonnet-5-5 claude --permission-mode bypassPermissions"` then `send-key enter` (match the old lane's mode: that flag is for a lane that ran full-permission, e.g. `--yolo`; if the Codex lane was approval-gated, launch `claude` with no permission flag).
3. Poll `capture-pane` until `bypass permissions` or `? for shortcuts` appears (≤36 s); a folder-trust prompt means stop and report.
4. `cmux send ... "/hr resume the work Codex session <id from step 0> was doing in this worktree; it stopped at the usage limit; continue until done."` then `send-key enter`. Where `/hr` is not installed, brief the new lane to read the worktree's `nextsteps`/bead state and the git log instead.
5. Verify a spinner line (`✻ Thinking… (12s`) within ~60 s, via two captures. A Claude lane that ends its first turn with a recap and "needs MERGE APPROVED" is not stuck: send once, "do not stop at a recap; continue every step that does not need a user-only gate (merge approval, credentials, spend)".

Other Codex traps seen in the same run: a `Hooks need review` menu (`1. Review hooks / 2. Trust all / 3. Continue without trusting`) — pick **3** (`cmux send ... "3"` selects immediately); never choose "Trust all" for the user. A `Resume goal / Leave paused` menu: Enter resumes (only after the session id check in Procedure step 5).

## Swap a usage-limited Claude lane to Gemini (agy) — verified 2026-10-27, 20 lanes

When Claude is walled (`You've hit your session limit · resets <time>`) the lane is stuck until the reset, and
a restart re-hits the same account-level wall. Gemini is a different provider and keeps working — `agy models`
currently offers `gemini-4-argon-*` and `gemini-3.8-flash-*`; use only `gemini-3.8-flash-high` (or `-medium`) per the Gemini model invariant, and never fall back to Gemini 3.1 Pro
or older Pro models. Per surface:

0. **Confirm the wall is current before touching the lane.** Follow `cmux-steer`'s full-buffer rule and use independent process/session evidence; never decide from a tail or grep. If the lane shows active work, a dialog, or the evidence is inconclusive, leave it.
1. **`escape` first — always.** A walled lane re-arms itself (`Continuing automatically at 4:20pm · esc to
   cancel`). Until that wait is cancelled, `/exit` is swallowed and the lane looks unexitable. Require the
   confirmation `Automatic continue cancelled`.
2. `cmux send --force … "/exit"` then `send-key --force … enter`. The three-option menu (`1. Exit and stop
   tasks / 2. Move to background and exit / 3. Stay`) defaults to **1**; Enter accepts it. Prefer **2** only when
   live subagents are worth keeping — on a dead provider quota they are normally already dead.
3. Require a real shell prompt. The pane prints `Resume this session with: claude --resume <uuid>` just above it;
   keep that uuid — it is the only route back to Claude after the reset.
4. `cmux send --force … "agy --model gemini-3.8-flash-high --dangerously-skip-permissions"` (match the old lane's mode: pass `--dangerously-skip-permissions` only if the Claude lane ran full-permission, otherwise omit it) then `send-key --force … enter`.
5. Wait for a frame containing `Gemini 3.8 Flash` **and** the composer `>` (≈3 s, poll ≤36 s). Do not type into the
   model splash — see trap 9.
6. Send the resume brief in ONE line: cwd, branch, PR number, why the previous session died, and the literal words
   `Run the /hr history-resume workflow`. `agy` has no session-resume alias, so `/hr` (or the worktree's own
   `nextsteps`/bead state) *is* the recovery mechanism.
7. Verify the model AND a turn: `Gemini 3.8 Flash · high` in the footer, plus `● Ran …` / `● Explored …` /
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
- Recreate: `cmux workspace create --name=<title> --cwd <dir> --focus false` (write `--name=`; a title starting with `-----` is parsed as a flag), extra terminals `cmux new-surface --workspace <ref> --working-directory <dir> --focus false`, browser tabs `new-surface --type browser --workspace <ref> --focus false --url <urlString>`, then `workspace-action --workspace <ref> --action pin` and `reorder-workspace --workspace <ref> --index <n>` to snapshot order. Always pass the restored workspace ref explicitly: `new-surface` and `workspace-action` default to the current workspace, which would modify the operator's live one. Recreate shells only: never pass a snapshot's recorded `resumeBinding.command` (or any recorded text) as `--command`. Never `select`/focus. Skip a panel whose cwd no longer exists; cloud (VNC) workspaces reject `new-surface`.
- Resuming an agent in a restored shell: only by explicit id, never `codexc`/`claudec` (they take the newest conversation in that directory, which in a shared worktree may belong to another lane). Read the conversation uuid from the snapshot panel (`checkpointId`, or the uuid inside `resumeBinding.command`, read as data and never executed), run `codex resume <uuid>` / `claude --resume <uuid>`, and apply Procedure step 5's checks (new pid, same session id). No uuid, or another writer on the worktree: leave the shell bare and report it.
- Closing a duplicate you created: pinned workspaces refuse `close-workspace` until unpinned.
- Optional local helpers (machine-local, not shipped; reimplement from the recipe above elsewhere): `~/.cmux-backups/cmux_restore_round2.py` (workspaces) and `cmux_restore_round3_surfaces.py` (surfaces in survivors). Record the order, pins and surfaces in `~/roadmap/cmux-workspace-layout-<date>.md` for the next incident.
- Restore authorization: a clear live user request is enough (relaxed 2026-10-27); never close or replace live workspaces to make it fit.

## Submitting text to a resumed lane

`cmux send` refuses when the agent prompt already holds unsent text ("holds text someone is typing"); the following `send-key enter` then submits the **old** text. Read the composer first; send the message, then Enter, then confirm the composer cleared.

## Traps that have burned this exact procedure

0. **A stale footer is not lane state.** Follow `cmux-steer`'s full-buffer rule and confirm current activity from
   independent process/session evidence. Never classify a lane from its footer, tail, or grep result.
1. **An open Codex dialog swallows everything.** If the surface rests on a Codex menu
   (`Press enter to confirm or esc to cancel`, `Enter to select`), plain keystrokes are dropped and
   `cmux send` refuses without `--force` — so your exit *and* your `codexc` both vanish with no error.
   Send `esc --force` first, then use `--force` on the exit and restart keys. Verified live: without it,
   a lane sat on its interrupt menu through three ctrl+c attempts and a codexc.
2. **Stale banners are history, not state — and a pane banner is NOT a quota reading.** A lane can display
   `You've hit your usage limit ... try again at <date>` while working perfectly. Never accept the banner,
   and never accept the *date in the banner*, as the fleet's quota state: on 2026-11-04 six panes still read
   "try again Nov 9th / Nov 10th" while quota had already reset.
   **Decide quota from the account, not from the pane.** Run three cheap non-interactive probes, recording each
   command's exit status and exact final reply in its own temporary file:
   ```bash
   for i in 1 2 3; do
     reply_file=$(mktemp) || exit 1
     if codex exec --skip-git-repo-check --output-last-message "$reply_file" "reply P$i"; then
       status=0
     else
       status=$?
     fi
     printf 'P%s exit=%s final reply:\n' "$i" "$status"
     cat "$reply_file"
     printf '\n'
     if [ "$status" -eq 0 ] && cmp -s "$reply_file" <(printf %s "P$i"); then
       printf 'P%s: clean\n' "$i"
     fi
     rm -f -- "$reply_file"
   done
   ```
   Count a probe clean only when its exit status is 0 and its exact final reply is `P1`, `P2`, or `P3` as
   requested. Count a failure toward a genuine wall only when its nonzero exit and saved final reply confirm an
   account usage limit; other failures or missing replies are inconclusive. Three clean replies mean quota is
   available and future-dated pane banners are stale. Three confirmed limit failures mean a genuine account
   wall; stop and report the reset time. Any other result is inconclusive, so do not infer quota state from it.
   Do not dispatch one `codex exec` fan-out per lane to test this; one probe answers it fleet-wide.
3. **CSI-u garbage.** See step 3. Symptom: `bash: 9: command not found`, `bash: 5ucodexc: command not
   found`. The cause is the terminal still encoding keys as `ESC [ code ; mods u`; `ctrl+c` on the
   shell line is the cheap fix, `printf '\x1b[<u'` pops the mode, and `reset` is the sledgehammer.
4. **A live step timer is not progress.** `(1h 38m • esc to interrupt)` can mean "waiting on a
   background terminal that no longer exists". Confirm progress from a new non-timer event in the session
   transcript/record; an mtime change alone is insufficient.
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
10. **Delegation may be invisible from a short capture.** Follow `cmux-steer`'s full-buffer rule before assessing
    a lane; a footer or grep result cannot establish that it is idle.
11. **`codexc` / `claudec` are shell ALIASES, not executables — they do not exist in a script.** Both are
    defined in `~/.bashrc` (`alias codexc='codex resume --last'`), so a Bash tool call, a cron job, or any
    non-interactive shell reports "command not found" (or silently does nothing). Inside `cmux send` the target
    is an interactive login shell so the alias resolves, but never rely on it from a script: dispatch
    `codex resume <uuid>` / `claude --resume <uuid>` explicitly. This is also why the explicit-id rule above
    matters — the alias additionally hardcodes `--last`, which is the wrong conversation wherever lanes share a
    directory.
12. **Enumerate workspaces fresh every session; do not reuse refs.** cmux workspace and surface refs are
    session-scoped and are **re-numbered** on restart. After one restart the same lane moved from
    `workspace:1000250001` to `workspace:1000260001`. Re-run `cmux list-workspaces` and `cmux tree --all` and
    re-derive the surface list, or a steer lands on an unrelated lane. Record the batch in a scratch dir so the
    capture, the decision and the verification all reference the same generation.

## Automation

`scripts/cmux-cli-restore.sh` does steps 2-5 for one surface, and supports `--dry-run` (report the CLI
and the plan, touch nothing) and `--list-above-p1` (enumerate in-scope terminal surfaces with their CLI
and last session-write age, so you can pick the wedged ones instead of restarting everything).

```bash
scripts/cmux-cli-restore.sh --dry-run --workspace workspace:1000120002 --surface surface:1000120005
scripts/cmux-cli-restore.sh --list-above-p1
scripts/cmux-cli-restore.sh --workspace workspace:1000120002 --surface surface:1000120005
```

The script does not do step 2's live-state check (full scrollback plus two captures 20-30 s apart): run that preflight yourself before any non-`--dry-run` invocation, and never run it on a surface you have not confirmed is wedged.

The script refuses to type into a surface whose prompt line still contains CSI-u residue, and it
verifies the restart at the process level before reporting success.

### Fleet recovery (many wedged lanes at once) — measured on 14 lanes, 2026-11-04

Recover lanes on distinct worktrees in parallel; serialize lanes that share a worktree (trap 6). Settle quota
once for the fleet and verify each resumed session from its transcript, not a screen diff or timer.

1. **Settle quota first** (trap 2): three probes. Do not touch 14 lanes on a wall a restart cannot clear.
2. **Enumerate generations fresh** (trap 12) and identify each lane by its own full capture and process/session
   evidence. Do not use a tail, grep, footer, or banner alone to select a lane; if activity is ambiguous, leave it.
3. **Per lane, in worktree order:** capture the pre-restart process/session identity; `ctrl+c` x2; confirm the
   shell prompt; cancel any CSI-u residue with `ctrl+c` and confirm a clean prompt before typing. Read that pane's
   own `codex resume <uuid>` hint; dispatch that exact id (never `codexc`), checking both `cmux send` and Enter
   exit codes. Before sending `continue` or accepting a goal dialog, verify a new PID and the same session id.
   On a failed, missing, or mismatched check, send nothing further and report unverified.
4. After sending `continue`, require a new non-timer transcript/session event to report progress. Take the
   two-sample full-buffer captures required by `cmux-steer`; a changed screen alone is not proof of recovery.
5. Report each lane's UUID, process/session verification, transcript progress evidence, and any remaining wall
   as unverified unless independently confirmed at the account level.

A resumed lane that immediately re-prints the wall on its next long turn is a genuine wall, not a bad resume:
stop that lane and report the reset time rather than looping the restart.
