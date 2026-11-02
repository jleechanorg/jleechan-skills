---
name: cmux-goal
description: Set Claude Code's builtin /goal for yourself (the running session) via the cmux socket CLI — types the /goal command into your own composer so the Stop hook + purple UI indicator activate. Use when the user asks you to set your own goal, when /ironclad step 3 needs the builtin set, or when a mission should be Stop-hook-enforced without asking the user to type it.
---

> **Terminal-reading rule (canonical):** before any classification, assessment, or steer of a
> cmux surface, read the surface's FULL available history (~10k words when possible;
> `cmux capture-pane --scrollback --lines 1500`), then the last ~15 lines for current state.
> Never decide from a short tail. Canonical text: `~/.codex/AGENTS.md` section
> "Reading a cmux terminal before deciding (full-buffer rule)".

> **No workspace selection (mandatory):** never run `cmux select-workspace`, `workspace.select`, `workspace-action --action focus`, or any command that selects/focuses/switches a workspace or surface — it steals the operator's active window. Read headless with `cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines <n>` (this skill does not read with `cmux read-screen`; the 2026-10-18 measurement did not see `read-screen` move the selection, but cross-workspace read routing was historically unreliable, so `capture-pane` is the only targeted read). `cmux send`/`send-key --workspace <ws> --surface <sf>` is allowed and must not select.

> **Headless only (measured, 2026-10-18; evidence `/tmp/spicy-search/cmux/focus-test.md`):** `capture-pane` / `read-screen` / `cmux send`+`send-key` / `surface.send_text` were measured NOT to change the operator's selected workspace; always pass `--focus false` to `new-surface`/`new-workspace`; never `select-workspace`/`focus`; do not create/close workspaces/surfaces on the live desktop without asking. Canonical rule: `~/.claude/skills/cmux-steer/SKILL.md` § "Headless only".

## ⚠️ Submit Discipline (MANDATORY — read this before every cmux steer)

`cmux send` only types keystrokes. A send with no explicit submit leaves the
message sitting in the input buffer and never reaches the agent (2026-07-16: the
operator flagged "you always forget to send" after a `/goal` was left in the
composer).

**Single owner.** The general submit ritual, the `cmux send` newline rule, the
repair procedure, and the verification verdicts are owned by
`~/.claude/skills/cmux-steer/SKILL.md` § "Submit Discipline" and § "`cmux send`
newline rule". This skill adds only the `/goal`-specific rules below.

### `/goal`-specific rules

1. **The condition must be ONE line.** A multi-line condition, an interpolated
   multi-line `$VAR`, a heredoc, or `$(cat file)` whose file contains internal
   newlines (only the *trailing* newline is stripped by command substitution)
   puts a real newline into the argument. The installed CLI documents that typed
   keystrokes press Enter at every newline, while the operator's 2026-10-20
   incidents (the `lvl up` notice at 10:04 AM and the `world` `/goal` at 12:10 PM)
   showed the text parked in the composer with the cursor resting on a blank line
   beneath it and never submitted. Treat that blank-line-with-cursor signature as
   the newline trap. Keep the `/goal` line under ~180 characters and push the
   overflow into the bead.
2. **Type one line, then submit with exactly one Enter:**
   Resolve your own surface first: `cmux identify` prints a `caller` block whose
   `surface_ref` (e.g. `surface:1000030005`) is the target, and the app exports the same
   surface as `$CMUX_SURFACE_ID` — as a **UUID** (e.g. `6605549A-…`), not a `surface:N`
   ref. `cmux send --surface` accepts either form.
   Assign the condition to a single-quoted variable so shell metacharacters, `%`, and
   quotes in it stay literal, then pass the quoted variable:
   ```bash
   SURFACE="${CMUX_SURFACE_ID:-surface:<N>}"
   GOAL_TEXT='<single-line condition>'          # single-quote it; write '\'' for an apostrophe
   cmux send --workspace workspace:<N> --surface "$SURFACE" "/goal $GOAL_TEXT" \
     && cmux send-key --workspace workspace:<N> --surface "$SURFACE" enter
   # equivalent: end the same one-line argument with the literal \n escape — that IS
   # the one Enter, so do not also send `send-key`
   ```
3. **Repair, never re-type.** If a capture still shows the `/goal` text at the
   `❯` composer, or shows the blank-line-with-cursor signature, send **one**
   `cmux send-key --workspace workspace:<N> --surface "$SURFACE" enter` and re-capture. Do not re-send the
   text: on builds where the composer already holds a draft `cmux send` refuses
   the send, and on builds where it does not the second send appends a duplicate
   `/goal` line.
4. **Probe every clause against every target before setting the goal.** The Stop
   hook reads the condition literally, so a clause no agent action can satisfy
   loops until the deadline (2026-05-15 merge-approval loop; 2026-10-30 "CI green"
   on a roadmap PR whose repo has no CI). For each gate, run its check on each
   target it names and scope the clause to the targets where it exists; write the
   rest as `N/A - <probe output>` in the bead, not in the condition. CI probe
   (verified 2026-10-30: roadmap PR #182 -> `NEUTRAL=2 SKIPPED=4`,
   worldai_frontend PR #367 -> `... SUCCESS=17`):
   `gh pr view <N> --repo <owner/repo> --json statusCheckRollup --jq '[.statusCheckRollup[]|select(.__typename=="CheckRun")|(.conclusion // .state)]|group_by(.)|map("\(.[0])=\(length)")|join(" ")'`
   -- only advisory bots and skipped runs means that PR has no CI to turn green.
   Count check runs only: a commit status an agent posts itself is not CI. Keep
   human-only items (merge approval, credential changes) out of the condition;
   write "no merge without MERGE APPROVED" as a guard, never as something to
   achieve.

### Success criterion (measured 2026-10-20, Claude Code)

"Submitted" is owned by `cmux-steer` § "`cmux send` newline rule" (churn, a queued
line, or text gone). `/goal` needs **more** than submitted. Accept exactly one of these
three, and nothing else:

1. the composer footer shows `◎ /goal active (Nm)`;
2. the harness prints `Goal set: …`;
3. the harness reports that a session-scoped Stop hook is now active.

The confirmation must be **fresh and matching**: observed after this send, naming the
condition you just set (or at minimum appearing below your send in the capture). A
`Goal set: …` / `◎ /goal active` line that already existed earlier in the required
full-history capture is history, not confirmation — re-read the tail, and if only an old
line is present, report the goal as unverified rather than confirmed.

Neither a socket `ok:true`, the send call returning, nor a leftover churning label is
that check.

Capturing the target surface's full history and tail before you report is still
required; if it is generating, wait until idle and capture again (text typed during
generation can sit in the composer).

### ⚠️ Output Contract — typed text + terminal response (MANDATORY)

Every reply that reports a `cmux send` action MUST include, in the same reply:

1. **The exact text that was typed** — verbatim copy of the string passed to `cmux send`.
2. **The cmux terminal response** — verbatim transcript of what `cmux capture-pane` returned AFTER the submit settle window
   (typically 5-15s, counted from the Enter). Specifically, the agent's first action after
   absorption — for a **queued** submission the agent has not acted yet, so report the
   queued line itself as the observed response and do not claim an action.
3. **Submission status** — explicit verdict: "submitted (churning label X)",
   "not submitted (text still at ❯ prompt)", "queued (Press up to edit queued
   messages — accepted, agent busy)", or "blocked (no Enter accepted, retried N times)".

**Treat as not working until we see a response.** A reply that does NOT include
both the typed text AND a terminal response is invalid evidence that the
steer landed. The operator cannot distinguish a successful send from a failed
send that left text in the input buffer.

Canonical contract + echo-back template: `~/.hermes/skills/cmux/references/output-contract-mandatory.md`.

### ⚠️ LLM-Provenance Caveat (MANDATORY footer)

Every reply that quotes cmux output, terminal text, or agent actions produced
by another LLM (the worker agent OR the assistant's own synthesis of agent
output) MUST end with this verbatim footer:

> *This was generated from another LLM and not the actual user, so feel free
> to push back if you disagree and we can discuss.*

Full caveat rules + scope: `~/.hermes/skills/cmux/references/output-contract-mandatory.md` § "LLM-Provenance Caveat".

### Echo-back proof (MANDATORY)

Every cmux steering action MUST be followed by an **echo-back proof** in the same
turn or the immediate next turn to your operator (Slack thread, terminal reply,
or whichever channel triggered the steer). The proof MUST follow the template
in `~/.hermes/skills/cmux/references/output-contract-mandatory.md` and include
the typed text + terminal response + submission status, not just the
churning label.

> ◀ sent to surface:55 (LEFT/claudec) at <HH:MM:SS PT> — typed: "<first 80 chars>";
> response: "<first 80 chars of the churning label or first agent line>"; status:
> submitted (churning label "Forming… 9s · ↓ 4.9k tokens").

**Banned** (these are the failure modes the user keeps flagging):
- "I sent the message" (no Enter proof)
- "The agent should have received it" (no churning label)
- `cmux send` with no Enter at all — neither a following `cmux send-key enter` nor a trailing literal `\n` (exactly one of the two, never both)
- A real newline in the send argument — it parks the text in the composer (2026-10-20)
- Re-sending text after a non-submit instead of one bare `send-key enter`
- Focusing or selecting a surface to send; always target with explicit `--workspace`/`--surface`

### Worktree-pointer strategy for long briefs

For task briefs >200 chars (e.g. orchestrating iOS app pivot, multi-PR review),
do NOT paste the full text into the input. Write the brief to a file in the
agent's cwd (e.g. `.cmux-<task>-brief.md`) and send a 1-2 line pointer. This
avoids the autocompleter contamination pitfall where shell-style tokens inside
long text trigger tab completion mid-stream. For `/goal` specifically, the
one-line condition rule above still applies — the pointer technique covers the
overflow, not the submitted line.

### Canonical reference

Full recipe + edge cases + the 2026-06-25 worked example live at:
`~/.hermes/skills/cmux/references/send-submit-proof-2026-06-25.md`

This rule was added 2026-07-16 after the fable iOS pivot bootstrap surfaced
"you always forget to send" / "make sure you press submit and the work starts
on the cmux input" (Slack ts 1784185650.528089). Apply it uniformly to every
cmux-touching skill.

# cmux-goal — set the builtin /goal for yourself

**Why this exists:** Claude Code's builtin `/goal <condition>` installs a session-scoped Stop hook (keeps the model working until the condition holds) and lights the purple goal indicator — but builtins are processed only from the composer, and the model has no direct tool for them. When the session runs inside cmux, the socket CLI can type into the session's OWN composer, so the model can set its own goal. Runtime native goal tools are preferred whenever available in the active environment; verify persisted state directly. The cmux composer socket typing mechanism is a fallback for Claude Code sessions where native tool support is unavailable. Proven live 2026-07-12 (DK2D mission; user: "I wanted you to use the builtin goal and set it yourself").

## Procedure

**Step 0 — Context pass, ALWAYS FIRST, unconditional (user directive 2026-07-19, re-affirmed 2026-07-21 after this step was skipped despite existing in prose form).** Before anything else — before even checking cmux hosting — run BOTH, invoked as their own Skill calls (not folded into later prose you might skim past):
   - `/ms <goal keywords>` (memory_search) — memories often hold measured contracts, prior exit criteria, and known traps for exactly this goal.
   - `/history <goal keywords>` — prior attempts, their failure modes, and what's already in flight.
   This applies EVERY time `/cmux-goal` is invoked, even standalone with no other context — the whole point is that invoking this skill alone is enough to ground the goal in real prior work. Do not skip this because you believe you already "have context" from the current conversation; other sessions/machines may hold relevant state this one doesn't.

1. **Query existing goal and choose mechanism:** Query whether an active goal already exists (e.g. inspect runtime goal state or check `/goal active`) before attempting to install one. If an existing goal matches the intended objective, continue execution without replacement (never clear or replace an existing goal without an explicit user request). If a different goal is active, preserve it unless the user explicitly authorizes replacement or has explicitly cleared it. If a new goal is needed, wait until Step 2 has hardened the condition, then choose the mechanism for the active environment: use the runtime's native goal API/tool directly when one is available (for example Codex `create_goal`), rather than printing a `/goal` line or asking the user to paste it. Only when no native goal mechanism is available should Claude Code confirm cmux hosting with `cmux identify` (which must return a `caller` block with `surface_ref`). If the cmux app itself is absent (no socket, no caller block), there is no composer to type into: prepare the exact `/goal ...` command and hand it to the operator as the only fallback. Distinguish that from Step 3's socket fallback, which covers a missing **CLI binary** while the app and its socket are still running — in that case skip `cmux identify` here and go straight to Step 3's socket form. Goal setup failure does not halt an already-authorized mission or claim an active goal; report the warning and continue authorized execution.
2. **Compose the condition.** ALWAYS invoke the `ironclad` skill to harden exit criteria — binary, executable, externally anchored (prefer an EXISTING checker/script/gate as the anchor when one exists), anti-gaming, iterate-until; the bead carries the full criteria superset — the builtin gets the short literal condition. Fold in anything concrete Step 0 surfaced (prior traps, measured contracts, in-flight work on other machines). Keep it short (the UI truncates); avoid shell-hostile characters; single-quote it. **The condition must also be ONE LINE** (see § "`/goal`-specific rules") — under ~180 characters, with any overflow pushed into the bead.
   - **CI-check criteria must not silently mean "poll forever."** If any criterion depends on a remote CI system ("zero failing checks", "N-green", "gate passes"), state in the condition (or the bead) that a slow/backlogged/flaky CI run does NOT block progress by itself: per `~/.claude/CLAUDE.md` § "Slow/backlogged CI runners — run locally + post proof, don't just wait", when a check is stuck 10min+ past its normal runtime, run the equivalent test locally instead of re-polling, and treat a real local pass (with command + output + timestamp + git SHA, explicitly labeled "local run — CI still pending") as satisfying that sub-criterion until CI catches up. Repo-specific local-run invocation contracts live in `~/.claude/skills/testing-infrastructure/SKILL.md` — read it for the exact command shape (don't guess). This prevents the goal from trapping the session in an unbounded retry/poll loop against a shared, externally-contended resource (see `~/.claude/skills/ironclad/SKILL.md` § "Verify the structural precondition BEFORE the first grind" — CI capacity is exactly this class of external producer/blocker).
3. **Create goal once (if needed):** If an existing matching goal was confirmed in Step 1, continue without recreation or replacement. If creating a new goal and the active environment provides a native goal tool, invoke that native tool once with the hardened condition and retain its returned goal identifier/objective for verification. Do not substitute a printed `/goal` command when the native tool is callable. For Claude Code fallback via cmux composer socket typing, type the single-line condition and then submit with one explicit Enter (preferred form, no escaping surface):
   Use the form in § "`/goal`-specific rules" rule 2 (single line, one explicit Enter);
   the surface-resolution notes there also cover `cmux identify`'s `caller.surface_ref`
   versus `$CMUX_SURFACE_ID`.
   Raw socket fallback only when the cmux **CLI binary** is unavailable but the app and its
   socket are running. The surface UUID and socket path come from the environment the app
   exported to your session (`$CMUX_SURFACE_ID`, `$CMUX_SOCKET_PATH`) — do not shell out to
   `cmux identify`, which needs the CLI you are working around. In this mode `capture-pane`
   is unavailable too, so rules 2 and 3 above cannot run as written. Send one single-line
   text, then report the one verdict that is actually supported:
   - `goal sent — UNVERIFIED (shell-level verification unavailable)` when the socket
     returned `ok:true` but none of the three Success-criterion indicators was observed;
   - a confirmed goal ONLY if one of those three indicators is directly observable
     without `capture-pane`.

   "The target later acted on the goal" is **not** an accepted indicator here: acting on a
   goal does not prove the footer/Stop-hook state this skill requires, so it cannot upgrade
   an unverified send. The Output Contract's verbatim `capture-pane` requirement is also
   replaced in this mode — report the verbatim socket response plus the UNVERIFIED status
   instead of claiming a transcript you could not take. The `\n` must be the literal
   two-character escape, never a real newline:
   ```bash
   SURFACE_UUID="${CMUX_SURFACE_ID:?no cmux surface id in this environment}"
   SOCK="${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"
   GOAL_TEXT='<single-line condition>'
   # JSON-encode the payload: a '%' in the condition is a printf directive, and
   # quotes/backslashes would otherwise produce invalid JSON.
   python3 -c 'import json,sys; print(json.dumps({"method":"surface.send_text","params":{"surface_id":sys.argv[1],"text":"/goal "+sys.argv[2]+"\n"}}))' \
     "$SURFACE_UUID" "$GOAL_TEXT" | nc -U -w 3 "$SOCK"
   ```
   **Submission is a separate gate from typing** — apply § "`/goal`-specific rules" above (single-line condition, explicit Enter, then repair-never-re-type); the general submit and newline rules are owned by `~/.claude/skills/cmux-steer/SKILL.md` § "Submit Discipline" and § "`cmux send` newline rule".
4. **Verify persisted query, not tool-layer:** verify persisted state directly. For a native goal tool, query the runtime again and confirm the goal is active and its objective matches the hardened condition (not merely that the tool returned successfully). For cmux, accept exactly the three confirmations listed in § "Success criterion" (`◎ /goal active (Nm)`, `Goal set: …`, or a session-scoped Stop hook reported as active); `OK surface:N` is only the tool layer. If the CLI is unavailable and only the socket path was used, apply Step 3's "shell-level verification unavailable" wording instead of claiming a confirmed goal — the `send-key` repair below needs the CLI, so it does not apply in that mode. If no confirmation arrives and the CLI is available, check whether another prompt was mid-flight (your text may have appended to it) and retry once — one bare `send-key enter` first, per "Repair, never re-type". If setup still does not succeed, proceed with the authorized mission without halting; do not falsely claim an active goal.
5. Acknowledge briefly and keep working — the goal-exit-criteria UserPromptSubmit hook (if installed) auto-injects ironclad hardening on top.

## Cautions

- `/goal clear` / `/goal active` are also typeable this way, but **never clear or replace an existing goal** without an explicit user request.
- Setup failure does not halt an authorized mission: if goal installation fails, do not stop work or claim an active goal; log the setup failure and continue authorized execution.
- Sending text mid-generation appends to the composer; prefer sending while otherwise idle at the end of your turn.
- Works for any builtin in principle; scope this skill to /goal — self-typing other builtins needs its own justification.
- Related: `ironclad` skill (criteria hardening), `~/.claude/hooks/goal-exit-criteria.sh` (hardening hook), memory `reference_builtin_goal_exit_criteria_hook`.
