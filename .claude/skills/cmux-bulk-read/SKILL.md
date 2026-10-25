---
name: cmux-bulk-read
description: "Read-only cmux fleet audit: resolve a surface SCOPE mechanically, capture every in-scope terminal's deep scrollback with a no-mutation sweep (`scan.py --readonly`, two samples), assess it with `/parallel` subagents against the full-buffer / stale-footer / two-sample gates, build the cross-surface ownership map, and report OFF_TRACK findings with PROPOSED steers — never send one. Use when asked to review/audit cmux surfaces, 'does anything look off track', 'check the terminals above/below P1', 'read the fleet', or any sweep the operator has not authorized touching running lanes. To actually steer, see cmux-bulk-steer."
---

# cmux-bulk-read — Read-Only Fleet Audit

Three steps, strictly in order:
**0 SCOPE (mechanical) → 1 CAPTURE (no-mutation two-sample sweep) → 2 PARALLEL `/zfc` ASSESSMENT → 3 FINDINGS REPORT (nothing is sent)**.

This skill is the read-only sibling of `~/.claude/skills/cmux-bulk-steer/SKILL.md`. That skill owns *steering*
(Phase 3, the submit/dialog/message mechanics). This skill owns *reading*: scope resolution, capture, parallel
assessment, and a findings report whose actionable items are **proposed** steers, not executed ones. Never restate
or improvise steering mechanics here — point at `cmux-steer`.

Read-only mode reduces **authority to act**, never **depth of review**: the 10,000-word full-buffer rule, the
sequential-slice rule, the two-sample `working_surfaces.txt` gate, the stale-footer rule, and cross-surface dedupe
all apply at 100%.

## Read-only contract — the complete command list

**Allowed:** `cmux tree --all --json`, `cmux workspace list [--json]`, `cmux top --all [--flat]`,
`cmux top --workspace <ws> --processes`, `cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines <n>`
(the only read path), read-only `gh pr view|list --json`, read-only `ps` / `lsof -p <pid>`, and reads of the `/tmp`
capture files. Nothing else.

**Forbidden:** `cmux send`, `cmux send-key` (including `--force`), the socket `surface.send_text` call, `cmux
new-workspace` / `new-surface` / `close-workspace` / `close-surface`, `select-workspace` / `focus` /
`workspace-action` / `focus-window`, any `kill` of a surface's child process, and any edit, commit, or push inside a
surface's worktree. A read-only audit is a snapshot; a surface can start, finish, or be taken over before anyone acts
on the report.

Canonical no-focus/no-select rule and its measurement: `~/.claude/skills/cmux-steer/SKILL.md` § "Headless only".

## Step 0 — Resolve the scope mechanically, then echo it back

Operator scope language ("above pinned P1", "the P0 workspaces", "everything but the dock", "the first eight
pinned") is **sidebar order**, and sidebar order is the `index` field — never the order you happened to see, and
never a title guess.

```bash
cd /tmp && cmux workspace list --json > /tmp/cmux_ws.json
python3 - <<'PY'
import json
for w in json.load(open('/tmp/cmux_ws.json'))['workspaces']:
    print(w['index'], w['ref'], 'PINNED' if w['pinned'] else '      ', w['title'])
PY
```

Then fix the scope by rule and write it down:
- "above pinned X" / "before X" → every workspace with `index` **less than** X's index.
- "below X" → greater than. "the pinned ones" → `pinned == true`. A list of names → resolve each to a `ref`.
- Store the resolved `workspace_ref` set in `$OUT_DIR/scope.txt` (one `ref` per line) **and** echo the resolved
  titles back to the operator in the first progress line. If a named scope token does not resolve to exactly one
  workspace, stop and report the ambiguity — never silently pick one.

Assessment is bounded to `scope.txt`. The collector captures the whole fleet (it has no workspace filter), so every
later filter is `row['workspace_ref'] in scope`.

## Step 1 — Capture: one no-mutation two-sample sweep

```bash
OUT_DIR="/tmp/cmux_readonly_$(date +%H%M%S)"; FIRST="$OUT_DIR/first"
python3 ~/.claude/skills/cmux-bulk-steer/scripts/scan.py --out-dir "$FIRST" --readonly
sleep 20                       # ONE fleet-wide wait, never a per-verdict sleep
python3 ~/.claude/skills/cmux-bulk-steer/scripts/scan.py --out-dir "$OUT_DIR" --with-gh --readonly
: > "$OUT_DIR/working_surfaces.txt"; : > "$OUT_DIR/closed_surfaces.txt"
for f in "$FIRST"/ws_*_sf_*.txt; do
  b=$(basename "$f")
  if [ ! -f "$OUT_DIR/$b" ]; then echo "$b" >> "$OUT_DIR/closed_surfaces.txt"; continue; fi
  cmp -s "$f" "$OUT_DIR/$b" || echo "$b" >> "$OUT_DIR/working_surfaces.txt"
done
```

Reuse the existing collector — do not write a second one. `scan.py` writes `manifest.json` (per-surface
`workspace_ref`/`surface_ref`/`surface_title`/`cpu_percent`/`file_10k`/`lines_read`, plus `"mode": "readonly"`),
`ws_<ws>_sf_<sf>.txt` (≤10,000 trailing words; `pi` TUI panes get the prepended
`=== PI SESSION TRANSCRIPT ===` section), `top_flat.tsv`, and `gh_prs.json`. Cite `mode=readonly` plus
`working_surfaces.txt` / `closed_surfaces.txt` as proof the sweep issued no mutating `cmux` verb.

Build the in-scope surface list from the manifest filtered by `scope.txt`, and print its scale (surfaces, words,
lines) before spawning anything.

## Step 2 — Parallel shard assessment (`/parallel`, never a per-surface loop)

Partition the in-scope `ws_*_sf_*.txt` files by **line count**, not surface count: put a lone 3,000-line surface in
its own shard, then pack the rest. Target `min(surface_count, 10)` shards (6–10 once the fleet supports it). One
`runs.all` fan-out per batch — never "shard 1, wait, shard 2". Canonical parallelism rules:
`~/.claude/skills/parallelize-to-ceiling/SKILL.md`.

Every child brief must carry, verbatim, the following contract (children do not inherit this skill):

1. **Read-only contract** — the allowed/forbidden command lists above, plus "you never nudge anything".
2. **Read protocol** — `wc -l`, then sequential `read` slices (`offset`/`limit`, ≤800 lines) until 100% of the file
   is read; record `lines_read`/`total_lines`; read both the `PI SESSION TRANSCRIPT` and `LIVE TERMINAL PANE`
   sections; never read another shard's files. Full-buffer rule owner: `~/.codex/AGENTS.md` § "Reading a cmux
   terminal before deciding".
3. **Two-sample gate** — in `working_surfaces.txt` ⇒ screen changed ⇒ `WORKING`, and nothing in the buffer may
   override it (only `STOOD_DOWN_DUPLICATE` / `WEDGED_PROCESS` proved from the process tree may). In
   `closed_surfaces.txt` ⇒ `UNCLASSIFIED_CLOSED`. Identical screens ⇒ an idle-class label additionally requires the
   three checks in § The three idle-gate checks.
4. **CLI identification before judging the tail** — `pi` TUI (`π`, state lives in the prepended transcript), Codex
   (goal-status line), Claude Code, `agy`, or plain shell. A `Goal …` footer belongs only to a Codex/`pi` goal lane;
   a bare `❯` under a shell footer is a `SHELL`, not an idle agent.
5. **Finding labels** — `WORKING`, `IDLE_NEEDS_STEER`, `IDLE_COMPLETE`, `PARKED_OPERATOR`, `DIALOG_BLOCKED`,
   `MALFORMED_TOOL_CALL`, `QUOTA_BLOCKED`, `STOOD_DOWN_DUPLICATE`, `WEDGED_PROCESS`, `SHELL`.
6. **What to extract** — open PR numbers + titles, branch, worktree/cwd from the footer, repo, the assigned task,
   whether it duplicates another surface's PR/branch, and the last substantive activity with recency evidence.
7. **Output shape** — one block per surface: workspace › surface title (CLI), file + lines_read/total, two-sample
   plus gate checks, class, PR/branch/worktree, ≤3 verbatim evidence quotes with line numbers, off-track yes/no with
   one-sentence reason, and `Proposed steer:` (exact command, or `none`). End with
   `SHARD_OFF_TRACK_COUNT=<n>` / `SHARD_WORKING_COUNT=<n>`.

Proven shape for reuse: write the brief as a workflow script and pass the shard map in `args`, e.g.
`subagent({ workflow: "/tmp/cmux_read_shards.js", cwd: "/tmp", async: true, args: { out: OUT_DIR, shards: {...} } })`.
A child launch/prompt failure is a lane failure: report it, do not fall back to a foreground CLI silently.

## The three idle-gate checks (identical screens only)

An idle-class label (`IDLE_NEEDS_STEER`, `IDLE_COMPLETE`, `PARKED_OPERATOR`, `DIALOG_BLOCKED`,
`MALFORMED_TOOL_CALL`, `QUOTA_BLOCKED`) requires **all** of:

1. **No post-footer activity** — no tool-call line, assistant text, or user input below the footer.
2. **No live progress label** — no `Working (1h33m)` / `Pursuing goal (…)` timer still growing.
3. **No CPU** — the surface's `top_flat.tsv` CPU row is idle.

`STOOD_DOWN_DUPLICATE` (a duplicate writer may be churning) and `WEDGED_PROCESS` (proved from the process tree) are
independent of this gate. If the checks disagree, prefer the fresher signal and say which check you could not
confirm — `WORKING_OR_UNVERIFIED` beats a guessed verdict.

**Stale footer rule.** `Goal hit usage limits (/goal resume)`, `Goal stalled (/goal resume)`, `CH100%`, and spinner
lines are *history*: they persist in scrollback after the condition cleared, including after a quota reset. Before
`QUOTA_BLOCKED` or `/goal resume`, confirm the wall is the current state (no post-footer activity, no growing timer,
meter at/near 100%). Canonical text and the 2026-10-19 incident where two working surfaces were wrongly written off:
`~/.claude/skills/cmux-bulk-steer/SKILL.md` § "Stale footer rule". A footer you cannot re-verify is `UNVERIFIED`, not
a verdict.

Two readers of one surface are **one** unverified claim: a sibling surface, a peer agent, or a monitor reading the
same capture is not corroboration. Independence needs a different source (a fresh two-sample capture, a process/CPU
probe, a GitHub API read).

## Step 3 — Findings report (nothing is sent)

**Ownership map first.** Group every in-scope surface by PR number, branch, and worktree path. Where two surfaces
own the same PR/branch/worktree, name the one with the fresher accepted work as canonical and list the other with a
`Proposed stand-down:` line and the evidence (merge SHA, newer push, later accepted turn). Check live state with
read-only `gh pr view <N> --json state,isDraft,mergeable,mergeStateStatus,statusCheckRollup`: a surface still working
an already-`MERGED` PR is a finding.

**Then the cards.** Narrow-Screen Vertical Cards, `<= 65 chars/line` (wide tables clip inside split panes), grouped
by finding. Always lead with the workspace **name** and the surface **title**; a numeric ref alone
(`surface:1000010241`) is not an identifier the operator can use — append it only when a proposed steer needs a
machine-exact target.

```markdown
### <workspace name> › <surface title> (<cli>)
- **PR / Task**: PR #10379 (branch `fix/...`)
- **Class**: IDLE_NEEDS_STEER (two-sample: identical; gate 1/2/3 clear)
- **Off track**: yes — finished its turn with the review unpublished
- **Proposed steer**: cmux send ... && cmux send-key ... enter
```

Close with the scale line (`N surfaces, M shards, K subagents`, scope rule and resolved titles, capture dir, and the
`mode=readonly` citation) and the provenance footer:

> *This was generated from another LLM and not the actual user, so feel free to push back if you disagree and we can discuss.*

## Escalating to a real steer

Only on a fresh live instruction from the operator. Then run `~/.claude/skills/cmux-bulk-steer/SKILL.md` from Phase 1
with a **new** two-sample sweep — a read-only capture is a snapshot and cannot authorize a send. Re-read this report's
cards against the new evidence, apply the stale-footer rule again, and let that skill own the submit/dialog mechanics.

## Anti-patterns (each one has burned a real audit)

- Classifying from a short tail or a single `read` call instead of the full buffer.
- Regex/keyword/exit-code classifiers for terminal state — banned by
  `~/.claude/skills/zero-framework-cognition/SKILL.md` (`/zfc`); quoted bot text and scrolled spinners mislead them.
- Treating a quota/goal footer in scrollback as current state.
- Reading a surface's *tail* while skipping its prepended `pi` transcript (or the reverse).
- One surface per shard sequentially; shards must fan out in one call.
- Reporting a proposed steer with only a numeric surface ref.
- Executing anything "because the fix is obvious" — the audit's authority ends at the report.
