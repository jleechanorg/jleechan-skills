---
name: cmux-goal
description: Set Claude Code's builtin /goal for yourself (the running session) via the cmux socket CLI — types the /goal command into your own composer so the Stop hook + purple UI indicator activate. Use when the user asks you to set your own goal, when /ironclad step 3 needs the builtin set, or when a mission should be Stop-hook-enforced without asking the user to type it.
---

# cmux-goal — set the builtin /goal for yourself

Builtin `/goal <condition>` installs a session-scoped Stop hook (keeps the model working until the condition holds) and lights the purple goal indicator, but builtins run only from the composer. Prefer the runtime's native goal tool when one exists; otherwise, inside cmux, type the `/goal` into your OWN composer via the socket CLI. Either way, verify persisted state directly. (Proven live 2026-07-12; user: "I wanted you to use the builtin goal and set it yourself".)

## Procedure

**Step 0 — Context pass, ALWAYS FIRST, unconditional** (user directive 2026-07-19, re-affirmed 2026-07-21 after it was skipped). Before anything else, even before checking cmux hosting, run BOTH as their own Skill calls, not folded into later prose:
- `/ms <goal keywords>` (memory_search) — measured contracts, prior exit criteria, known traps.
- `/history <goal keywords>` — prior attempts, failure modes, work already in flight.

This runs on EVERY invocation, even standalone. Do not skip it because the current conversation seems to give you context; other sessions and machines may hold state this one doesn't.

1. **Query the existing goal, then choose the mechanism.** Check current-session goal state with a read-only runtime API when available; otherwise verify the source and interface of `bin/self_goal.py status` before using it. Never type `/goal active`: it mutates state by setting the condition `active`; bare `/goal` is read-only only where verified. Never run a suspected query against the user's session; if no compatible read-only query is available, preserve state and report it unverified. A request for a new objective alone does not authorize replacing a different existing active or paused goal. Replace or clear that goal only when the latest live user request clearly asks for that replacement or clear; when that authorization is already explicit, proceed without asking again. Otherwise preserve the existing goal, prepare the requested condition, report the exact unresolved goal conflict, and continue independent authorized work. Reuse a matching goal; a status-only invocation never clears one. Harden the new condition in Step 2 before clearing anything, then:
   - use the supported native clear/cancel operation, or Claude Code's builtin `/goal clear` in your verified own composer, and verify the cleared state before setting the replacement. Preserve the previous objective and actual unfinished status in the existing goal record. Clear no other session's goals;
   - never mark unfinished work complete to unlock creation, edit runtime databases/transcripts, or invent a clear API. If the runtime exposes no clear operation and no verified own-composer route exists, report replacement blocked, keep the durable objective, and continue independent authorized work;
   - for a matching paused goal, a new request to pursue that objective authorizes resume through a supported resume operation. Verify active readback; if resume is unavailable, report the paused controller without claiming activation;
   - use the runtime's native goal API/tool directly when available (e.g. Codex `create_goal`), not a printed `/goal` line or a request that the user paste it;
   - only with no native mechanism, run `bin/self_goal.py host` (env detection: `cmux` if `CMUX_SURFACE_ID`/`CMUX_SOCKET_PATH`, `tmux` if `TMUX`+`TMUX_PANE`, `warp` if `TERM_PROGRAM=WarpTerminal`, else `none`). `tmux` -> Step 3 "tmux" form; `cmux` -> confirm hosting with `cmux identify` (must return a `caller` block with `surface_ref`);
   - cmux **app** absent (no socket, no caller block) = no verified own composer. With no existing goal, prepare the exact `/goal ...` command as the fallback; with an existing goal requiring replacement, report the unsupported clear route instead. Never target the focused surface as a substitute for a caller;
   - only the cmux **CLI binary** missing while the app and socket run: skip `cmux identify` and use Step 3's socket form.

   Setup failure never halts an already-authorized mission and never justifies claiming an active goal: report the warning and continue.
2. **Compose the condition.** ALWAYS invoke the `ironclad` skill to harden exit criteria — binary, executable, externally anchored (prefer an EXISTING checker/script/gate), anti-gaming, iterate-until. The bead carries the full criteria superset; the builtin gets the short literal condition. Fold in what Step 0 surfaced (prior traps, measured contracts, in-flight work elsewhere). Keep it short (the UI truncates), avoid shell-hostile characters, single-quote it, ONE LINE under ~180 characters (rule 1).
   - **CI criteria must not silently mean "poll forever."** If a criterion depends on remote CI ("zero failing checks", "N-green", "gate passes"), state in the condition or bead that slow/backlogged/flaky CI does NOT block progress by itself: per `~/.claude/CLAUDE.md` § "Slow/backlogged CI runners — run locally + post proof, don't just wait", once a check is stuck 10min+ past its normal runtime, run the equivalent test locally instead of re-polling; a real local pass (command + output + timestamp + git SHA, labeled "local run — CI still pending") satisfies that sub-criterion until CI catches up. Exact local command shapes: the installed product plugin's `testing-infrastructure` skill or the repository's own testing docs (don't guess). CI capacity is the external-blocker class in `~/.claude/skills/ironclad/SKILL.md` § "Verify the structural precondition BEFORE the first grind".
3. **Create the goal once (if needed).** Reuse a matching goal. For a replacement, complete Step 1's supported clear and readback first. `self_goal.py set` does not clear a different active goal; after an authorized builtin clear, its documented `--force-after-clear` flag permits setting the replacement.
   - **Native tool:** invoke it once with the hardened condition; keep the returned goal identifier/objective for Step 4. Never substitute a printed `/goal` when the tool is callable.
   - **tmux or cmux (preferred, one call):** the same helper handles `host==cmux`: it resolves your own surface from `cmux identify` (caller refs), checks the composer, types with `cmux send`, submits with `cmux send-key ... enter`, and does the same readback; conditions containing a backslash are refused there (`cmux send` expands escapes). Tmux details: `python3 ~/.claude/skills/cmux-goal/bin/self_goal.py set '<single-line condition>'` from your own Bash tool. It types `/goal <cond>` into `$TMUX_PANE` with `send-keys -l` (no shell, literal), then a separate `Enter`. No delay is needed: a slash command typed while a turn is running executes immediately (measured: footer `◎ /goal active` within 1s, `Goal set:` printed, persisted `goal_status` sentinel written); the goal is evaluated when the turn ends. The helper already enforces Step 1 (exit 0 reuse of a matching active goal, 4 preserve a different active goal, 5 user-cleared: never revive unless the user freshly instructs, then add `--force-after-clear`), refuses to append to a draft already in the composer (6), and prints `Goal: activated via tmux (readback ok)` only when a fresh persisted `goal_status` for exactly this condition AND the footer/`Goal set:` line are observed; otherwise `Goal: ... unverified/unsupported (...)`. Report that line verbatim; never claim activation without it. Warp: see § Warp (agent-side, needs cmux-cua; the helper cannot do it). `none` hosts: `Goal: unsupported (none)`.
   - **cmux CLI:** rule 2's form (one line, exactly one explicit Enter).
   - **Raw socket** — only when the CLI binary is unavailable but the app and socket run. Take the surface UUID and socket path from the app-exported `$CMUX_SURFACE_ID` / `$CMUX_SOCKET_PATH`; do not call `cmux identify` (it needs the missing CLI). The `\n` must be the literal two-character escape, never a real newline:
     ```bash
     SURFACE_UUID="${CMUX_SURFACE_ID:?no cmux surface id in this environment}"
     SOCK="${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"
     GOAL_TEXT='<single-line condition>'
     # JSON-encode the payload: a '%' in the condition is a printf directive, and
     # quotes/backslashes would otherwise produce invalid JSON.
     python3 -c 'import json,sys; print(json.dumps({"method":"surface.send_text","params":{"surface_id":sys.argv[1],"text":"/goal "+sys.argv[2]+"\n"}}))' \
       "$SURFACE_UUID" "$GOAL_TEXT" | nc -U -w 3 "$SOCK"
     ```
     `capture-pane` and `send-key` are unavailable here, so rules 2–3 cannot run as written. Send one single-line text, then report `goal sent — UNVERIFIED (shell-level verification unavailable)` when the socket returned `ok:true` but no Success-criterion indicator was seen; claim a confirmed goal ONLY if one is directly observable without `capture-pane`. "The target later acted on the goal" does **not** count — acting does not prove the footer/Stop-hook state. Instead of the Output Contract's `capture-pane` transcript, report the verbatim socket response plus the UNVERIFIED status.
4. **Verify persisted state, not the tool layer.** Native tool: query the runtime again and confirm the goal is active with an objective matching the hardened condition (a successful return is not enough). cmux: only the § "Success criterion" confirmations count; `OK surface:N` is just the tool layer. Socket-only: use Step 3's UNVERIFIED wording. No confirmation and the CLI is available: check whether another prompt was mid-flight (your text may have appended to it) and retry once — one bare `send-key enter` first (rule 3). Still failing: proceed with the authorized mission, without claiming an active goal.
5. **Acknowledge briefly and keep working.** The goal-exit-criteria UserPromptSubmit hook (if installed) auto-injects ironclad hardening on top.

## Mandatory rules

### Reading and focus (headless only)

- **Full-buffer read:** before any classification, assessment, or steer of a surface, read its FULL available history (~10k words when possible; `cmux capture-pane --scrollback --lines 1500`), then the last ~15 lines for current state. Never decide from a short tail. Canonical: `~/.codex/AGENTS.md` section "Reading a cmux terminal before deciding (full-buffer rule)".
- **Never select or focus:** no `cmux select-workspace`, `workspace.select`, `workspace-action --action focus`, or anything that selects/focuses/switches a workspace or surface — it steals the operator's active window. Read only with `cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines <n>` (not `cmux read-screen`: cross-workspace read routing was historically unreliable). `cmux send`/`send-key --workspace <ws> --surface <sf>` is allowed and must not select. Always pass `--focus false` to `new-surface`/`new-workspace`; do not create/close workspaces or surfaces on the live desktop without asking. (Measured 2026-10-18: `capture-pane`, `read-screen`, `cmux send`/`send-key`, `surface.send_text` did not move the selection; evidence `/tmp/spicy-search/cmux/focus-test.md`.) Canonical: `~/.claude/skills/cmux-steer/SKILL.md` § "Headless only".

### Submit Discipline

`cmux send` only types keystrokes; without an explicit submit the text sits in the composer and never reaches the agent. The general submit ritual, newline rule, repair procedure, and verification verdicts are owned by `~/.claude/skills/cmux-steer/SKILL.md` § "Submit Discipline" and § "`cmux send` newline rule" (full recipe: `~/.hermes/skills/cmux/references/send-submit-proof-2026-06-25.md`); apply them uniformly to every cmux-touching skill. This skill adds only:

#### `/goal`-specific rules

1. **The condition must be ONE line.** A multi-line condition, interpolated multi-line `$VAR`, heredoc, or `$(cat file)` with internal newlines (command substitution strips only the trailing one) puts a real newline in the argument. The CLI documents typed newlines as Enter, yet on 2026-10-20 such sends parked in the composer with the cursor on a blank line beneath and never submitted — treat that blank-line-with-cursor signature as the newline trap. Keep it under ~180 characters; push overflow into the bead.
2. **Type one line, then submit with exactly one Enter.** Your own surface: `cmux identify`'s `caller.surface_ref` (e.g. `surface:1000030005`; `bin/resolve_caller_target.sh` prints the caller's `workspace_ref` and `surface_ref` as TSV), or the app-exported `$CMUX_SURFACE_ID`, which is a **UUID** (e.g. `6605549A-…`), not a `surface:N` ref; `cmux send --surface` accepts either. Single-quote the condition into a variable so metacharacters, `%`, and quotes stay literal:
   ```bash
   SURFACE="${CMUX_SURFACE_ID:-surface:<N>}"
   GOAL_TEXT='<single-line condition>'          # single-quote it; write '\'' for an apostrophe
   cmux send --workspace workspace:<N> --surface "$SURFACE" "/goal $GOAL_TEXT" \
     && cmux send-key --workspace workspace:<N> --surface "$SURFACE" enter
   # equivalent: end the same one-line argument with the literal \n escape — that IS
   # the one Enter, so do not also send `send-key`
   ```
3. **Repair, never re-type.** If a capture still shows the `/goal` text at the `❯` composer, or the blank-line-with-cursor signature, send **one** `cmux send-key --workspace workspace:<N> --surface "$SURFACE" enter` and re-capture. Never re-send the text: builds whose composer holds a draft refuse the send; others append a duplicate `/goal` line.
4. **Probe every clause against every target before setting the goal.** The Stop hook reads the condition literally, so an unsatisfiable clause loops until the deadline (2026-05-15 merge-approval loop; 2026-10-30 "CI green" on a repo with no CI). Run each gate's check on each target it names, scope the clause to targets where it exists, and record the rest as `N/A - <probe output>` in the bead, not the condition. CI probe (measured: a no-CI repo returned `NEUTRAL=2 SKIPPED=4`, a real-CI repo `... SUCCESS=17`):
   `gh pr view <N> --repo <owner/repo> --json statusCheckRollup --jq '[.statusCheckRollup[]|(.conclusion // .state // .context)]|group_by(.)|map("\(.[0])=\(length)")|join(" ")'`
   Do not filter to check runs; CI also arrives as legacy commit statuses, so read both. Skipped, neutral, or empty results do not prove there is no required CI: treat them as unknown and probe the repo's workflow config before declaring `N/A`. A commit status the reviewing agent posted itself is not CI. Keep human-only items (merge approval, credential changes) out of the condition; write "no merge without MERGE APPROVED" as a guard, never as something to achieve.

### Success criterion

"Submitted" (churn, a queued line, or text gone) is defined by `cmux-steer` § "`cmux send` newline rule"; `/goal` needs more. Accept exactly one of these, and nothing else:

1. the composer footer shows `◎ /goal active (Nm)`;
2. the harness prints `Goal set: …`;
3. the harness reports that a session-scoped Stop hook is now active.

It must be **fresh and matching**: observed after this send and naming the condition you just set (at minimum, below your send in the capture). A matching line that already existed earlier in the full-history capture is history — re-read the tail; if only an old line is present, report the goal unverified. A socket `ok:true`, the send call returning, or a leftover churning label is not confirmation. Capture full history and tail before reporting; if the surface is generating, wait until idle and capture again. Text sent mid-generation sits in or appends to the composer, so prefer sending while otherwise idle at the end of your turn.

### Output Contract and Echo-back proof

Every reply reporting a `cmux send` action MUST include, in the same turn (or the immediate next turn, on the channel that triggered the steer):

1. **The exact typed text** — verbatim string passed to `cmux send`.
2. **The terminal response** — verbatim `cmux capture-pane` output after the submit settle window (typically 5–15s from the Enter): the agent's first action after absorption. For a **queued** submission, report the queued line itself and claim no action.
3. **Submission status** — one of: "submitted (churning label X)", "not submitted (text still at ❯ prompt)", "queued (Press up to edit queued messages — accepted, agent busy)", "blocked (no Enter accepted, retried N times)".

Treat the steer as not working until a response is seen: a reply missing the typed text or the terminal response is invalid evidence, and a churning label alone is not enough. Template (canonical: `~/.hermes/skills/cmux/references/output-contract-mandatory.md`):

> ◀ sent to surface:55 (LEFT/claudec) at <HH:MM:SS PT> — typed: "<first 80 chars>";
> response: "<first 80 chars of the churning label or first agent line>"; status:
> submitted (churning label "Forming… 9s · ↓ 4.9k tokens").

**LLM-provenance footer.** Every reply quoting cmux output, terminal text, or agent actions produced by another LLM (the worker OR your own synthesis of its output) MUST end verbatim with (scope: same reference, § "LLM-Provenance Caveat"):

> *This was generated from another LLM and not the actual user, so feel free
> to push back if you disagree and we can discuss.*

**Banned:** "I sent the message" (no Enter proof); "The agent should have received it" (no churning label); a `cmux send` with no Enter — use exactly one of a following `cmux send-key enter` or a trailing literal `\n`, never neither or both; a real newline in the send argument; re-sending text after a non-submit instead of one bare `send-key enter`; focusing or selecting a surface instead of explicit `--workspace`/`--surface`.

### Long briefs (worktree pointer)

For briefs >200 chars, do NOT paste the text: write it to a file in the agent's cwd (e.g. `.cmux-<task>-brief.md`) and send a 1–2 line pointer, which avoids autocompleter contamination from shell-style tokens in long text. For `/goal`, the one-line rule still applies — the pointer carries the overflow, not the submitted line.

### Warp (agent-side; cmux-cua MCP tools, not `self_goal.py`)

Robust route (untested): run Claude inside tmux within Warp, then use the tmux form. Native Warp (no tmux) is proven on the Mac, single tab only (2026-11-07); multi-tab is UNVERIFIED, so report `Goal: unsupported (warp)` if you cannot target your tab.

1. Self-target: get your tty (`ps -o tty= -p <pid>`, pid from `~/.claude*/sessions/*.json`), write a unique title `printf '\033]0;WARP-SELF-<uniq>\007' > /dev/<tty>`, then `list_windows(pid=<Warp pid>)` and take the window whose title equals the marker. Launch/identify the Warp pid first.
2. Type: `type_text(pid, window_id, "/goal <cond>", x, y)` with a pixel click on the composer. The `element_index` form on the AXTextArea drops ~70 leading characters; do not use it. Then `press_key(pid, window_id, return)`.
3. Verify (not the tool result; `press_key` says "unverifiable" even when it lands): a screenshot showing `Goal set: <cond>` AND a fresh `goal_status` record (`bin/self_goal.py status` also works if the transcript is reachable). Report `Goal: activated via warp (readback ok)` or `Goal: unverified (...)`.

Caveats: a folder-trust dialog defaults to "No, exit" (send down, then return); Warp may auto-update and quit mid-run; its AX tree can go empty or stale, so prefer screenshots; background ctrl+c did not land.

### Scope and cautions

- `/goal clear` is typeable the same way (stdout `Goal cleared: <cond>`); Step 1's current-session replacement rule applies. Persisted goal state lives in the session transcript (`$CLAUDE_CONFIG_DIR/projects/*/<sessionId>.jsonl`) as `attachment.type=goal_status` records: `sentinel:true,met:false` = set, `met:true` (no sentinel) = achieved, `failed:true` = ended unmet, and a `Goal cleared:` stdout = user cleared.
- A user skill named `goal` (e.g. a Codex-style `~/.claude/skills/goal` that calls `CreateGoal`) shadows the builtin `/goal`: typing it yields "CreateGoal not available" and no goal. Seen 2026-11-07; if readback fails, check `ls ~/.claude/skills/goal` first.
- Works for any builtin in principle; this skill is scoped to `/goal` — self-typing other builtins needs its own justification.
- Related: `ironclad` skill (criteria hardening), `~/.claude/hooks/goal-exit-criteria.sh` (hardening hook), memory `reference_builtin_goal_exit_criteria_hook`.

Provenance: submit and echo-back rules added 2026-07-16 after "you always forget to send" (Slack ts 1784185650.528089); newline rule measured 2026-10-20.
