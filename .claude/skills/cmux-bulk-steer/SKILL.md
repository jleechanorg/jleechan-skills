---
name: cmux-bulk-steer
description: "Pure Subagent-Native Zero-Framework Cognition (/zfc) fleet review, deduplication, and steering, with a read-only audit mode. Always `/parallel` — every phase fans out across disjoint subagents because independent work must never be serialized. Captures ~10,000 words per cmux terminal surface mechanically without regex classifiers, fans out /parallel subagents to classify and dedupe overlapping PR/worktree lanes, then steers sole owners — or, in read-only mode, stops after assessment and reports proposed steers instead of sending them. Use when asked to review/audit cmux surfaces, 'see what's off track', 'nudge/steer the terminals', or orchestrate across the fleet. NOT for single-surface work (see cmux-steer)."
---

# cmux-bulk-steer — Subagent-Native `/zfc` Fleet Review, Dedupe, and Steer

Three phases, strictly in order:
**Phase 1: CAPTURE ALL (Mechanical 10,000-Word Dump) → Phase 2: PARALLEL SUBAGENT `/zfc` ASSESSMENT + STRICT DEDUPE → Phase 3: STEER DEDUPED SOLE OWNERS**.
In **read-only mode** the run stops after Phase 2 and reports proposed steers instead of sending them (see
§ Read-only mode).

Never steer from a short tail, never use regex/keyword classifiers to guess terminal state, and never skip cross-surface deduplication.

> **Headless only (measured, 2026-10-18; evidence `/tmp/spicy-search/cmux/focus-test.md`).** **Never select, focus, switch, or reorder a workspace/surface** (`select-workspace`, `workspace-action --action focus`, `focus-window`, `workspace.select`, `surface.focus`). Reads use **`cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines <n>` exclusively** and steers (`cmux send` + `cmux send-key`, or the socket `surface.send_text` call) do **not** change the operator's selected workspace. **Never use `cmux read-screen` as a read path** — the 2026-10-18 measurement shows it does not move the selection, and the installed build accepts `--workspace/--surface`, but cross-workspace read routing was historically unreliable; `capture-pane` is the only read path this skill uses (`scripts/scan.py` already does this). Read-only listings (`cmux tree --all --json`, `cmux list-workspaces`) never select. Always pass `--focus false` to `new-surface` / `new-workspace`. Do **not** create or close workspaces/surfaces on the operator's live desktop without asking first (the only operation that disturbed the view). Never `select-workspace` / `focus` / `workspace-action --action focus`. Canonical rule + evidence: `~/.claude/skills/cmux-steer/SKILL.md` § "Headless only".

**Always `/parallel`. `/parallel` is the default execution mode for every phase, not an optimization.** If two items do not depend on each other, they MUST run concurrently — never as `item N` then `item N+1`. Concretely: assessment fans out across disjoint subagents (Phase 2), dedupe reads every shard concurrently, and steering dispatches to all owners at once (Phase 3). Before any sequential loop over surfaces/shards/lines, ask "can `/parallel` run these at the same time?" and if yes, fan out. The only serialization allowed is a genuine data dependency (a later step needs an earlier step's output) or a bounded resource cap — see `~/.claude/skills/parallelize-to-ceiling/SKILL.md`. Report the degree of parallelism achieved (e.g. "6 shards, 6 subagents") in the final report.

---

## `/parallel` Is the Default (Never Serialize Independent Work)

Apply this at every phase boundary:
- **Capture (Phase 1)**: one mechanical pass; still parallelize per-surface reads when the collector supports it (do not capture surface-by-surface in a shell loop).
- **Assess (Phase 2)**: partition surfaces into `min(surface_count, 10)` disjoint `/parallel` subagents — target 6–10 shards only when the fleet has enough surfaces. Spawn all shards in ONE fan-out call; never assess shard 1, wait, then shard 2.
- **Dedupe (Phase 2)**: build the ownership map from all shard results concurrently.
- **Steer (Phase 3)**: send to all deduped owners concurrently, then verify all of them in one parallel read pass. Do not steer+wait per surface.

If you catch yourself in a sequential per-item loop, stop and convert it to a `/parallel` fan-out.

---

## Read-only mode — capture, assess, report; never steer

For a full read-only **audit** — mechanical scope resolution ("/cmux-bulk-read" above pinned P1"), shard partitioning by
line count, the findings-report contract, and the escalation gate back into this skill — use
`~/.claude/skills/cmux-bulk-read/SKILL.md`. The mode below remains the minimum any read-only pass of this skill
must honor.

Trigger it when the operator asks for an audit, "does anything look off track", a review pass, or says read-only /
don't steer / don't touch the terminals. Read-only mode runs **Phase 1 (capture)** and **Phase 2 (parallel `/zfc`
assessment + dedupe)** at full depth and **skips Phase 3 entirely**. It is a mode of this skill, not a lighter
version of it: the 10,000-word full-buffer rule, the sequential-slice rule, the two-sample `working_surfaces.txt`
gate, the stale-footer rule, and cross-surface dedupe all still apply at 100%. Read-only mode reduces *authority to
act*, never *depth of review*.

**Allowed commands (the complete list).** `cmux tree --all --json`, `cmux list-workspaces`, `cmux top --all
[--flat]`, `cmux top --workspace <ws> --processes`, `cmux capture-pane --workspace <ws> --surface <sf>
--scrollback --lines <n>` (the only read path), read-only `gh pr view|list --json`, read-only `ps` / `lsof -p
<pid>`, and reads of the `/tmp` capture files. Nothing else.

**Forbidden in read-only mode** — every operation that changes a surface or the operator's desktop: `cmux send`,
`cmux send-key` (including `--force`), the socket `surface.send_text` call, `cmux new-workspace` / `new-surface` /
`close-workspace` / `close-surface`, `select-workspace` / `focus` / `workspace-action` / `focus-window`, any `kill`
of a surface's child process, and any edit, commit, or push inside a surface's worktree.

**Verdicts become findings, not actions.** `IDLE_NEEDS_STEER`, `DIALOG_BLOCKED`, `MALFORMED_TOOL_CALL`, and a
stalled Codex `/goal` are still classified — but the action is *reported as a proposed steer* (exact surface, exact
command, exact key sequence), never executed. `/goal resume`, dialog unblocks, and `STOOD_DOWN_DUPLICATE`
stand-downs are Phase 3 actions and are out of scope here. That also makes this the correct mode for any sweep where
the operator has not authorized touching running lanes.

**Provenance.** Pass `--readonly` to `scripts/scan.py` (both sweeps of the two-sample pair). It records `"mode":
"readonly"` in `manifest.json` and prints `mode=readonly`, so a report can cite the manifest as proof the sweep
issued no mutating `cmux` verb. Cite that field together with `working_surfaces.txt` and `closed_surfaces.txt`.

**Converting to a steering pass later** needs a fresh live instruction *and* a fresh two-sample sweep: a read-only
sweep is a snapshot, and a surface can start, finish, or be taken over between the sweep and a later steer. Re-capture,
re-apply the stale-footer rule, then run Phase 3 against the new evidence.

**Report shape.** The Narrow-Screen Vertical Cards contract below still applies, grouped by finding (`OFF_TRACK`,
`WORKING`, `PARKED_OPERATOR`, `QUOTA_BLOCKED`, `IDLE_COMPLETE`, …), with an actionable card carrying a `Proposed
steer:` line. State the review scale (`N surfaces, M shards, K subagents`) and end with the LLM provenance footer.

---

## Stalled-on-question unblock (Claude / Codex) — look for it explicitly

A recurring failure pattern: a Claude Code or Codex surface has **finished its turn and is stopped on a question**, waiting for an answer — so it reads as "idle" but is NOT done. During every read (Phase 2), explicitly scan each surface's tail for this pattern and unblock it.

**Signatures (read the surrounding lines, never a bare keyword):**
- A yes/no confirmation: `Do you want to proceed?`, `(y/n)`, `[y/N]`, `Allow ...?`.
- A numbered / selectable menu: a `❯ 1. ...` highlighted line, `Enter to select`, `↑/↓ to move`.
- An `AskUserQuestion` / plan-approval block: a question followed by 2–4 options, one marked recommended/default.
- A single free-text prompt asking `Should I ...?` / `Which ...?` where the agent states its own recommendation.

**Unblock rule — choose the recommended option (one procedure, no alternatives):**
1. Read the dialog and identify the recommended/default choice — the highlighted `❯` line,
   an option labelled `Recommended` / `(Recommended)` / `Yes`, or the agent's own stated
   recommendation. If the dialog offers no defensible default, stop: it is
   `PARKED_OPERATOR`, not an unblock.
2. Answer it with a **guarded key action** — one key for a highlighted menu, key-then-Enter
   for a yes/no or a navigated list (that Enter is what confirms the dialog, not a second
   unplanned keystroke). A dialog blocks ordinary sends, so every key command must carry
   `--force` (`cmux send-key --help`: `--force  Send even into an open dialog`):
   ```bash
   cmux send-key --force --workspace <ws> --surface <sf> enter   # accept highlighted option
   cmux send-key --force --workspace <ws> --surface <sf> y       # yes/no: then send enter
   cmux send-key --force --workspace <ws> --surface <sf> down    # numbered list: move, then enter
   ```
   `--force` here is decision authority over a dialog you have already judged safe (step 1),
   not permission to bypass one unread.
3. For a **free-text** question where the agent stated its recommendation, type that
   one-line approval and submit it with exactly one Enter, using the dialog-safe key form:
   `cmux send --workspace <ws> --surface <sf> "Yes, do <recommended>." && cmux send-key --force --workspace <ws> --surface <sf> enter`.
   If a question/permission **dialog** (not a free-text prompt) is what is open, `cmux send`
   refuses unless `--force`; in that case use the key procedure in step 2 instead of typing.
4. Verify with `cmux capture-pane` that the dialog cleared and the agent resumed working.
   If the build rejects a key name, the only documented alternative is the socket
   `surface.send_text` call, whose dialog behaviour is **not documented** — use it and apply
   the same `capture-pane` verification, reporting the steer as unverified if the dialog is
   still there.

**Never auto-answer a genuine human decision** — destructive/irreversible actions, production `MERGE APPROVED`, scope/product choices, credential changes, or spend authorizations. Those are `PARKED_OPERATOR`: report them, don't guess.

This augments the `DIALOG_BLOCKED` semantic category below (a stopped coding-agent question is the same failure class).

### Codex `/goal` stall — resume, don't reclassify

A Codex lane whose goal is paused reads as idle but is recoverable without any human decision. Look for a goal-status line near the tail: `Goal stalled (/goal resume)`, `Goal paused`, or a `Goal hit usage limits (/goal resume)` line that has no activity after it.

0. Run the two-sample check first: a growing timer or a changing screen means the lane is working, and a stalled
   footer over a changing screen is stale text that must not trigger `/goal resume`.
1. First confirm the pause was not deliberate: if the operator (or the lane's own thread) paused the goal on purpose, or a hold/stop instruction is visible in the buffer, report it and do not resume. Otherwise send `/goal resume` through the same headless steer path (it resumes the *existing* goal — it authorizes no merge, spend, or scope change).
2. Verify the status line becomes `Pursuing goal (Ns)` / `Pursuing goal (Xh Ym)` with a growing timer before reporting it as WORKING.
3. If it stays stalled, or immediately re-prints the quota wall, classify from the fresh evidence (see next section) — do not retry in a loop.

Live evidence (2026-10-19): a single sweep resumed 8 such lanes (`iOS`, `lvl up`, `auto creation`, `knowledge`, `zfc`, plus idle `strat`/`alerts`), all confirmed `Pursuing goal`/`Working` after the steer.

---

## Stale footer rule — verify before you classify

**Footers are history, not state.** A CLI writes `Goal hit usage limits (/goal resume)` (or `Goal stalled (/goal resume)`, `Working (…)`, a spinner line) once, at the moment it happened, and it survives in the scrollback window long after the condition cleared — including after a quota reset. Reading that line out of a 10,000-word buffer and classifying `QUOTA_BLOCKED` is the single most common misclassification in this skill.

**Gating.** These verdicts require `screen_changed == false` (surface absent from `working_surfaces.txt`) **plus**
the absence of post-footer output, live timer growth, and CPU: `IDLE_NEEDS_STEER`, `IDLE_COMPLETE`,
`PARKED_OPERATOR`, `DIALOG_BLOCKED`, `MALFORMED_TOOL_CALL`, `QUOTA_BLOCKED`. `STOOD_DOWN_DUPLICATE` (a duplicate
writer can be actively churning) and `WEDGED_PROCESS` (proved from the process tree, not the screen) are
**independent of this gate**. For the gated verdicts, confirm all of:
1. **No activity after the footer.** Look for tool-call lines, assistant text, or user input lines that appear *below* the quota footer in the buffer. Any post-footer activity means the wall is not current.
2. **No live progress label.** A `Working (1h33m)` / `Pursuing goal (…)` label with a timer longer than the footer's age is proof the lane is running.
3. **Not just a scrolled artifact.** The quota line must be the last substantive line, not one of several historical occurrences deeper in the buffer.
4. **Corroborate from outside the pane.** Check `top_flat.tsv` CPU for the surface and any provider meter (weekly/5h percentage) visible on a sibling surface or the operator's quota line. A healthy meter (e.g. 49% on a fresh window) falsifies `QUOTA_BLOCKED` outright; a meter at/near 100% corroborates it.

If the checks disagree, prefer the fresher signal: post-footer activity and a healthy meter beat a stale paragraph.

**Real incident (2026-10-19, operator-caught).** A fleet report labelled `zfc` and `world` as `QUOTA_BLOCKED` from a `Goal hit usage limits (/goal resume)` footer that predated that day's reset. Both were actively working (`Working (1h33m)`, live `ssh`/pytest and dot ACK activity) and the weekly meter was 49% — the footer was stale. Two surfaces were wrongly written off as dead in one report. Verify first.

Conversely, a quota footer with **no** post-footer activity plus a meter at/near 100% is a genuine `QUOTA_BLOCKED`, and `/goal resume` will not help until the window resets — report it, don't steer it.

---

## Why Regex / Keyword Classifiers Are Banned (`/zfc`)

Per `~/.claude/skills/zero-framework-cognition/SKILL.md` (`/zfc`), `scripts/scan.py` is strictly a **mechanical I/O collector** (`cmux tree --all --json`, `cmux top --all --flat`, `cmux capture-pane --scrollback --lines 4000`, and 10,000-word file slicing). All regex/keyword classifiers (`CHURN_RE`, `DEAD_RE`, `PARK_RE`, `QUESTION_RE`, `FOOTER_RE`) are permanently banned because static pattern matching repeatedly failed on real terminal scrollback:
1. **Quoted bot/review text**: A terminal displaying `cursor[bot]: usage limit reached` in a PR comment was misclassified as `DEAD` by `DEAD_RE`.
2. **Scrolled spinners and custom status bars**: Multi-line status bars or subagent tool outputs pushed spinner lines past fixed tail-line windows.
3. **Malformed raw XML tool calls**: An agent that emitted raw `<parameter name="bash">` text instead of invoking a tool had no question mark or quota banner and was misclassified as `IDLE`.
4. **Cross-surface PR takeovers**: After a quota reset, formerly blocked `agy` surfaces and newly spawned `pi`/`codex` surfaces worked the same PR simultaneously — something no single-pane regex can detect.

---

## Phase 1 — CAPTURE ALL (Mechanical 10,000-Word Dump, Zero Regexes)

Capture every terminal surface's deep scrollback (`~10,000` trailing words, preserving line breaks) to `/tmp` alongside `cmux top --all --flat`:

```bash
# Two-sample sweep: ONE fleet-wide 20 s wait (never a per-verdict sleep).
# Add --readonly to BOTH calls for a read-only audit (recorded in manifest.json as "mode": "readonly").
OUT_DIR="/tmp/cmux_fleet_$(date +%H%M%S)"
FIRST="$OUT_DIR/first"
python3 ~/.claude/skills/cmux-bulk-steer/scripts/scan.py --out-dir "$FIRST"   # no --with-gh: one GitHub query per sweep
sleep 20
python3 ~/.claude/skills/cmux-bulk-steer/scripts/scan.py --out-dir "$OUT_DIR" --with-gh
: > "$OUT_DIR/working_surfaces.txt"; : > "$OUT_DIR/closed_surfaces.txt"
for f in "$FIRST"/ws_*_sf_*.txt; do
  b=$(basename "$f")
  if [ ! -f "$OUT_DIR/$b" ]; then echo "$b" >> "$OUT_DIR/closed_surfaces.txt"; continue; fi
  cmp -s "$f" "$OUT_DIR/$b" || echo "$b" >> "$OUT_DIR/working_surfaces.txt"
done
```

**Phase 2 must read `$OUT_DIR/working_surfaces.txt` and `closed_surfaces.txt` before classifying any surface.** A
surface in `working_surfaces.txt` is `WORKING` unless it is `STOOD_DOWN_DUPLICATE` or `WEDGED_PROCESS`, and may
otherwise receive no other label. A surface in `closed_surfaces.txt` was captured once, not twice, and is not
classifiable from this sweep.

What `scripts/scan.py` writes to `$OUT_DIR`:
- `manifest.json`: deterministic inventory of all terminal surfaces (`workspace`, `workspace_ref`, `surface`, `surface_ref`, `surface_title`, `cpu_percent`, `file_10k`, `pi_session_jsonl`, `total_words`, `captured_words`, `lines_read`, `tail_lines`). Non-terminal browser surfaces (`Surface is not a terminal`) are skipped automatically.
- `ws_<ws_id>_sf_<sf_id>.txt`: up to `10,000` trailing words of scrollback per terminal surface. For alternate-screen `pi` (`π`) TUI panes (where `cmux capture-pane` only sees the `35`-row TUI screen), `scan.py` automatically matches the pane's `cwd` footer to the newest session file in `~/.pi/agent/sessions/*/*.jsonl` and prepends `=== PI SESSION TRANSCRIPT (<jsonl_path>) ===` ahead of `=== LIVE TERMINAL PANE ===` so every `pi` surface also receives a full `10,000`-word capture.
- `top_flat.tsv`: raw `cmux top --all --flat` output (`CPU%`, memory, process count per workspace/pane/surface).
- `gh_prs.json` (when `--with-gh` is passed): live open PR metadata.

Rules:
- **The full-read rule binds every substantive surface.** A surface whose whole capture is under ~`100` words has nothing to slice (a shell, or a session that just started); classify it from its complete capture and record it as `SHELL`/`IDLE_*` rather than forcing the four-slice ritual — but never use "short capture" as a reason to skip a surface that does have content.
- **Read 100% of the 10,000-word buffer before any decision (Sequential Slice Rule)** — canonical rule in `~/.codex/AGENTS.md` § "Reading a cmux terminal before deciding (full-buffer rule)": because `view_file` / `Read` tools cap at `800` lines per call while a `10,000`-word `ws_<ws_id>_sf_<sf_id>.txt` file spans `1,000–3,500` lines, each subagent MUST read sequential line slices (`1..800`, `801..1600`, `1601..2400`, `2401..end`) until `lines_read` is 100% covered. Never rely on a single `view_file` call or a short tail!
- Use `capture-pane` for every read.

---

## Phase 2 — PARALLEL SUBAGENT `/zfc` ASSESSMENT + STRICT DEDUPE

Partition the captured `ws_*_sf_*.txt` files from `$OUT_DIR/manifest.json` across disjoint `/parallel` subagents (e.g., 6–10 surfaces per subagent). Each subagent MUST read all sequential line slices (`1..800`, `801..1600`, `1601..2400`, `2401..end`) of every `ws_*_sf_*.txt` file in its shard (covering 100% of the captured `10,000` words, including any `=== PI SESSION TRANSCRIPT ===` section) plus live GitHub PR statuses (`gh pr view <N> --json state,isDraft,mergeable,mergeStateStatus,statusCheckRollup`) and return a structured semantic assessment per surface:

### Identify the CLI before judging the tail

The same line means different things per CLI, so each subagent names the surface's CLI from its capture first: **`pi` TUI** (`π` title, alternate screen — state lives in the prepended `=== PI SESSION TRANSCRIPT ===` section, not the `35`-row live pane), **Codex** (goal-status line above the composer), **Claude Code**, **`agy`**, or a **plain shell** (`SHELL`). A `Goal …` footer only ever belongs to a Codex/`pi` goal lane; a bare `❯` prompt under a shell footer is a shell, not an idle agent.

### Semantic Categories (Model-Decided, Never Regex-Guessed)
- `WORKING`: Actively executing a turn, tool call, test run, or subagent wait with live progress.
- `IDLE_NEEDS_STEER`: Agent finished a turn or stopped mid-workflow while ungated next steps remain on its assigned PR/task.
- `IDLE_COMPLETE`: Agent's assigned PR is merged or its task is genuinely 100% complete.
- `PARKED_OPERATOR`: Agent is waiting on a genuine human product/scope/merge decision (not a routine reversible check).
- `DIALOG_BLOCKED`: Interactive TUI confirmation/selection menu is blocking the composer (`Enter to select · Esc to cancel`).
- `MALFORMED_TOOL_CALL`: Agent emitted raw tool-call XML/JSON (e.g. `<parameter name="bash">`) as plain text and stalled at the prompt.
- `QUOTA_BLOCKED`: Current turn is genuinely blocked by an active, unexpired quota/rate-limit wall at the bottom of the buffer. The wall must be the *current* state — a `Goal hit usage limits (/goal resume)` footer left in scrollback after a reset is stale; apply the Stale footer rule before using this category.
- `STOOD_DOWN_DUPLICATE`: Another active surface is the canonical owner of the same PR/branch/worktree.
- `WEDGED_PROCESS`: Process tree (`cmux top --workspace <ws> --processes` / `ps` / `lsof -p <pid>`) shows a hung child or busy-wait loop with a frozen screen.
- `SHELL`: Session exited to a plain shell prompt (`zsh`/`bash`).

### Mandatory Cross-Surface Deduplication Rules
1. **Build the global Work-Item → Surface ownership map** before sending a single steer:
   - Group all surfaces by **PR number**, **branch**, and **worktree path**.
   - **Never wake a formerly quota-blocked surface onto a PR that another surface took over** while it was blocked. If Surface A (`agy`) was quota-blocked on PR `#NNNN` and Surface B (`codex`/`pi`) took over PR `#NNNN`, keep Surface B as sole owner and stand down Surface A (`STOOD_DOWN_DUPLICATE`).
   - Verify live PR state (`OPEN` vs `MERGED` vs `CLOSED`): any surface still working an already-`MERGED` PR gets an immediate stand-down citing the merge commit SHA.
2. **Assign new work ONLY to a terminal RELATED to the task**:
   - A candidate terminal must already own the PR/branch/worktree or same feature family in its scrollback. Never borrow an idle unrelated terminal. If no related terminal exists, spawn a dedicated one (see Phase 3).
3. **Wedge forensics before interrupting**:
   - Inspect `cmux top --workspace <ws> --processes`, `ps -eo pid,ppid,etime,command`, and `lsof -p <pid>`. Kill only the stuck child process (`cat`/`grep`/hung hook subshell), never `killall`, and verify CPU drops.

---

## Phase 3 — STEER DEDUPED SOLE OWNERS (3-Step Ritual + Narrow-Screen Cards)

**Skipped entirely in read-only mode** (argv `--readonly` / operator says don't steer): report proposed steers here
instead of executing them — see § Read-only mode.

### Blocker-authority check (before any steer that names a blocker)

Apply the canonical rule and its loophole closers in `harness-engineering` § "Coordinator-gate variant"
(do not restate it). Operationally: cite the governing instruction by `file:line`; a shared account has no
cross-lane limit and only same-mutable-target mutation is a conflict; unknown occupancy proceeds to
preflight; never relay a peer's blocker as your own conclusion.

This check creates no exemptions: credential/identity bans, environment and deploy gates, active quota
walls, explicit operator holds, `PARKED_OPERATOR`, and `STOOD_DOWN_DUPLICATE` one-writer ownership of a
branch/PR all still block.

For every surface that needs action after deduplication, execute the mandatory 3-step ritual (the socket `text` must end in the literal `\n`, or the CLI form follows with an explicit `send-key enter`). The heading said "4-Step" until 2026-10-20, when step 1 was rewritten to issue type and Enter together (chained or socket); it is the same keystroke contract, with one fewer decision point — canonical owner: `~/.claude/skills/cmux-steer/SKILL.md` § "Submit Discipline". **Dispatch every surface's ritual concurrently** (`/parallel`): send to all owners in one fan-out, then do a single parallel verify pass — never send→sleep→verify one surface at a time.

```bash
printf '{"method":"surface.send_text","params":{"surface_id":"<SURFACE-UUID>","text":"<message>\\n"}}\n' | nc -U -w 3 "${CMUX_SOCKET_PATH:-$HOME/.local/state/cmux/cmux.sock}"
# or, preferred CLI form (route both commands):
#   cmux send --workspace <ws> --surface <sf> "<message>" && cmux send-key --workspace <ws> --surface <sf> enter
sleep 10
cmux capture-pane --workspace <ws_ref> --surface <sf_ref> --scrollback --lines 120
```

- **DIALOG_BLOCKED**: use the guarded key procedure in "Unblock rule" above (`cmux send-key --force --workspace <ws> --surface <sf> enter|y|down` — route both ids: an omitted `--workspace` falls back to the caller's workspace). A bare socket `"\n"` is the undocumented-behaviour fallback, allowed ONLY when the option text proves it is the agent's own recommended safe choice, and it must be verified with `capture-pane`.
- **Submit rule (`cmux send`)**: send one single-line message and submit it explicitly with `cmux send-key --workspace <ws> --surface <sf> enter` (or a **literal** `\n` escape on builds whose send interprets escapes). A real newline in the argument put the text in the composer unsent in both 2026-10-20 operator-caught incidents. Repair with one bare Enter — never re-send the text. Verify the composer cleared before reporting "sent" — canonical: `~/.claude/skills/cmux-steer/SKILL.md` § `cmux send` newline rule.
- **MALFORMED_TOOL_CALL**: Nudge the surface to re-invoke the tool properly instead of printing raw XML/text.
- **Long briefs (>200 chars)**: Write the brief to `/tmp/<task>_brief.md` and send a one-line pointer.
- **Spawning a dedicated surface** (when no related terminal exists):
  1. Create an isolated worktree under `~/.worktrees/<repo>/<name>` (`diskm worktree-new <repo> <branch>`).
  2. Launch a dedicated surface via `cmux new-workspace --focus false --name "<task>" --cwd <worktree> --command "<agent>"` or `cmux new-surface --focus false --type terminal --workspace <ws> --command "<agent>"`.
  3. Follow `~/.codex/AGENTS.md` § "Shared provider & review-gate policy (canonical)" for current provider routing.

### Report Contract (Narrow-Screen Vertical Cards, `<= 65 chars/line`)

Wide markdown tables wrap and clip inside split `cmux` panes. Present the fleet report using **Narrow-Screen Vertical Cards** (`<= 65 chars/line`), grouped by action (`STEERED`, `WORKING`, `PARKED_OPERATOR`, `STOOD_DOWN_DUPLICATE`, `QUOTA_BLOCKED`):

**Always name the workspace and surface. Never identify a surface to the operator by its numeric ref alone.** Numeric refs (`workspace:1000010002` / `surface:1000010241`) are not useful to a human — lead every line, card, table, and steer confirmation with the workspace **name** and the surface **title**, and treat the numeric ref as optional secondary detail (append it only when a steer needs a machine-exact target, e.g. `lvl up › c-big (surface:1000010241)`). If a surface title is generic (e.g. `c`, `agy`, `wiki`), disambiguate with the workspace name, the cwd/branch from the footer, or the PR it owns — never fall back to the bare number.

```markdown
### <workspace name> › <surface title> (<cli>)
- **PR / Task**: PR #10379 (branch `fix/...`)
- **State**: STEERED -> WORKING
- **Sent**: "Re-run Green Gate check and report readiness..."
- **Echo-back (10s)**: "Running gh pr view 10379..."
```

End reports quoting agent output with the LLM-provenance footer:

> *This was generated from another LLM and not the actual user, so feel free to push back if you disagree and we can discuss.*

---

## Syncing copies (repo ↔ hosts)

Published source of truth: `jleechanorg/jleechan-skills` → `.claude/skills/cmux-bulk-steer/`.
Live working copies: `~/.claude/skills/cmux-bulk-steer/` on Mac and on `jeff-ubuntu`.

**Sync direction is one-way: repo -> live.** Edit the repo worktree first; a live copy is never a source.

**Baseline before editing** - confirm both live copies already match the committed file, so foreign drift is caught
before your edit can hide it:

```bash
git -C <repo> show HEAD:.claude/skills/cmux-bulk-steer/SKILL.md > /tmp/baseline.skill.md
diff -u /tmp/baseline.skill.md ~/.claude/skills/cmux-bulk-steer/SKILL.md
ssh jeff-ubuntu cat ~/.claude/skills/cmux-bulk-steer/SKILL.md | diff -u /tmp/baseline.skill.md -
```

Any non-empty baseline diff is foreign drift: stop and report it. Then edit and propagate:

```bash
git -C <repo> status --porcelain     # repo-wide: is anything else dirty?
git -C <repo> diff -- <path>         # the intended change only?
diff -u <repo-file> ~/.claude/skills/cmux-bulk-steer/SKILL.md
ssh jeff-ubuntu cat <remote-live-file> | diff -u <repo-file> -
```

Stage by explicit path (`git add <path>`), never a directory or wildcard glob. After propagating, confirm all six
SHA-256 digests match, covering exactly these two files in each of the three copies:
`.claude/skills/cmux-bulk-steer/SKILL.md` and `.claude/skills/cmux-bulk-steer/scripts/scan.py`.
