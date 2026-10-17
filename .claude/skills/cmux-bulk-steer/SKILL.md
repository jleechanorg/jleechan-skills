---
name: cmux-bulk-steer
description: "Pure Subagent-Native Zero-Framework Cognition (/zfc) fleet review, deduplication, and steering. Always `/parallel` — every phase fans out across disjoint subagents because independent work must never be serialized. Captures ~10,000 words per cmux terminal surface mechanically without regex classifiers, fans out /parallel subagents to classify and dedupe overlapping PR/worktree lanes, then steers sole owners. Use when asked to review/audit cmux surfaces, 'see what's off track', 'nudge/steer the terminals', or orchestrate across the fleet. NOT for single-surface work (see cmux-steer)."
---

# cmux-bulk-steer — Subagent-Native `/zfc` Fleet Review, Dedupe, and Steer

Three phases, strictly in order:
**Phase 1: CAPTURE ALL (Mechanical 10,000-Word Dump) → Phase 2: PARALLEL SUBAGENT `/zfc` ASSESSMENT + STRICT DEDUPE → Phase 3: STEER DEDUPED SOLE OWNERS**.

Never steer from a short tail, never use regex/keyword classifiers to guess terminal state, and never skip cross-surface deduplication.

**Always `/parallel`. `/parallel` is the default execution mode for every phase, not an optimization.** If two items do not depend on each other, they MUST run concurrently — never as `item N` then `item N+1`. Concretely: assessment fans out across disjoint subagents (Phase 2), dedupe reads every shard concurrently, and steering dispatches to all owners at once (Phase 3). Before any sequential loop over surfaces/shards/lines, ask "can `/parallel` run these at the same time?" and if yes, fan out. The only serialization allowed is a genuine data dependency (a later step needs an earlier step's output) or a bounded resource cap — see `~/.claude/skills/parallelize-to-ceiling/SKILL.md`. Report the degree of parallelism achieved (e.g. "6 shards, 6 subagents") in the final report.

---

## `/parallel` Is the Default (Never Serialize Independent Work)

Apply this at every phase boundary:
- **Capture (Phase 1)**: one mechanical pass; still parallelize per-surface reads when the collector supports it (do not `read-screen` surface-by-surface in a shell loop).
- **Assess (Phase 2)**: partition surfaces into `min(surface_count, 10)` disjoint `/parallel` subagents — target 6–10 shards only when the fleet has enough surfaces. Spawn all shards in ONE fan-out call; never assess shard 1, wait, then shard 2.
- **Dedupe (Phase 2)**: build the ownership map from all shard results concurrently.
- **Steer (Phase 3)**: send to all deduped owners concurrently, then verify all of them in one parallel read pass. Do not steer+wait per surface.

If you catch yourself in a sequential per-item loop, stop and convert it to a `/parallel` fan-out.

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
OUT_DIR="/tmp/cmux_fleet_$(date +%H%M%S)"
python3 ~/.claude/skills/cmux-bulk-steer/scripts/scan.py --out-dir "$OUT_DIR" --with-gh
```

What `scripts/scan.py` writes to `$OUT_DIR`:
- `manifest.json`: deterministic inventory of all terminal surfaces (`workspace`, `workspace_ref`, `surface`, `surface_ref`, `surface_title`, `cpu_percent`, `file_10k`, `pi_session_jsonl`, `total_words`, `captured_words`, `lines_read`, `tail_lines`). Non-terminal browser surfaces (`Surface is not a terminal`) are skipped automatically.
- `ws_<ws_id>_sf_<sf_id>.txt`: up to `10,000` trailing words of scrollback per terminal surface. For alternate-screen `pi` (`π`) TUI panes (where `cmux capture-pane` only sees the `35`-row TUI screen), `scan.py` automatically matches the pane's `cwd` footer to the newest session file in `~/.pi/agent/sessions/*/*.jsonl` and prepends `=== PI SESSION TRANSCRIPT (<jsonl_path>) ===` ahead of `=== LIVE TERMINAL PANE ===` so every `pi` surface also receives a full `10,000`-word capture.
- `top_flat.tsv`: raw `cmux top --all --flat` output (`CPU%`, memory, process count per workspace/pane/surface).
- `gh_prs.json` (when `--with-gh` is passed): live open PR metadata.

Rules:
- **Read 100% of the 10,000-word buffer before any decision (Sequential Slice Rule)** — canonical rule in `~/.codex/AGENTS.md` § "Reading a cmux terminal before deciding (full-buffer rule)": because `view_file` / `Read` tools cap at `800` lines per call while a `10,000`-word `ws_<ws_id>_sf_<sf_id>.txt` file spans `1,000–3,500` lines, each subagent MUST read sequential line slices (`1..800`, `801..1600`, `1601..2400`, `2401..end`) until `lines_read` is 100% covered. Never rely on a single `view_file` call or a short tail!
- Use `capture-pane`, NOT `read-screen` — cross-workspace `read-screen` can return the focused surface's content.

---

## Phase 2 — PARALLEL SUBAGENT `/zfc` ASSESSMENT + STRICT DEDUPE

Partition the captured `ws_*_sf_*.txt` files from `$OUT_DIR/manifest.json` across disjoint `/parallel` subagents (e.g., 6–10 surfaces per subagent). Each subagent MUST read all sequential line slices (`1..800`, `801..1600`, `1601..2400`, `2401..end`) of every `ws_*_sf_*.txt` file in its shard (covering 100% of the captured `10,000` words, including any `=== PI SESSION TRANSCRIPT ===` section) plus live GitHub PR statuses (`gh pr view <N> --json state,isDraft,mergeable,mergeStateStatus,statusCheckRollup`) and return a structured semantic assessment per surface:

### Semantic Categories (Model-Decided, Never Regex-Guessed)
- `WORKING`: Actively executing a turn, tool call, test run, or subagent wait with live progress.
- `IDLE_NEEDS_STEER`: Agent finished a turn or stopped mid-workflow while ungated next steps remain on its assigned PR/task.
- `IDLE_COMPLETE`: Agent's assigned PR is merged or its task is genuinely 100% complete.
- `PARKED_OPERATOR`: Agent is waiting on a genuine human product/scope/merge decision (not a routine reversible check).
- `DIALOG_BLOCKED`: Interactive TUI confirmation/selection menu is blocking the composer (`Enter to select · Esc to cancel`).
- `MALFORMED_TOOL_CALL`: Agent emitted raw tool-call XML/JSON (e.g. `<parameter name="bash">`) as plain text and stalled at the prompt.
- `QUOTA_BLOCKED`: Current turn is genuinely blocked by an active, unexpired quota/rate-limit wall at the bottom of the buffer.
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

## Phase 3 — STEER DEDUPED SOLE OWNERS (4-Step Ritual + Narrow-Screen Cards)

For every surface that needs action after deduplication, execute the mandatory 4-step ritual (`cmux send` does NOT press Enter). **Dispatch every surface's ritual concurrently** (`/parallel`): send to all owners in one fan-out, then do a single parallel verify pass — never send→sleep→verify one surface at a time.

```bash
cmux send --workspace <ws_ref> --surface <sf_ref> "<message>"
cmux send-key --workspace <ws_ref> --surface <sf_ref> enter
sleep 10
cmux capture-pane --workspace <ws_ref> --surface <sf_ref> --scrollback --lines 120
```

- **DIALOG_BLOCKED**: `cmux send-key --workspace <ws_ref> --surface <sf_ref> --force enter` selects the highlighted option ONLY when the option text proves it is the agent's own recommended safe choice.
- **MALFORMED_TOOL_CALL**: Nudge the surface to re-invoke the tool properly instead of printing raw XML/text.
- **Long briefs (>200 chars)**: Write the brief to `/tmp/<task>_brief.md` and send a one-line pointer.
- **NEVER `select-workspace`** (steals the operator's active window focus).
- **Spawning a dedicated surface** (when no related terminal exists):
  1. Create an isolated worktree under `~/.worktrees/<repo>/<name>` (`diskm worktree-new <repo> <branch>`).
  2. Launch a dedicated surface via `cmux new-workspace --name "<task>" --cwd <worktree> --command "<agent>"` or `cmux new-surface --type terminal --workspace <ws> --command "<agent>"`.
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

Keep all three byte-identical. Verify with:

```bash
# Repo vs Mac live
shasum -a 256 .claude/skills/cmux-bulk-steer/SKILL.md \
  .claude/skills/cmux-bulk-steer/scripts/scan.py \
  ~/.claude/skills/cmux-bulk-steer/SKILL.md \
  ~/.claude/skills/cmux-bulk-steer/scripts/scan.py
# Linux live
ssh jeff-ubuntu 'sha256sum ~/.claude/skills/cmux-bulk-steer/SKILL.md \
  ~/.claude/skills/cmux-bulk-steer/scripts/scan.py'
```

After editing ANY copy, propagate to the other two in the same session and confirm all six SHA-256 digests match (3 copies × 2 files).
