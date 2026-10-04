---
name: timeline
description: Use when the user invokes /timeline or asks for a visual timeline, Gantt chart, or HTML diagram of remaining steps, parallelism, and time estimates. Builds a self-contained HTML Gantt plus a flow strip, renders and visually reviews it, and always prints a text Gantt in chat.
---

# /timeline

Turn a plan into an HTML Gantt (bars, parallelism, time estimates) plus a flow strip of the remaining steps, render it and look at it, and print the same diagram in chat.

## Build

1. **Re-pin live state first.** Immediately before drawing, re-read git SHAs, `gh pr checks`, and lane status from their sources; never copy them from earlier prose. Snapshot time is absolute with timezone (`2026-10-04 12:55 PDT`).
2. **Schedule for maximum parallelism, from true dependencies, not list order.** A step starts when what it truly waits on is done.
   - Read-only review or verification never blocks a reversible step (push, CI start); run them side by side.
   - Start the longest pole first.
   - Show work handed to other lanes (subagents, CLI delegates, the dot) as its own row, labelled with the owner.
   - Say in the subtitle when the plan changed because of this.
3. **Estimates.** Each row has a start offset, a low estimate and a high estimate in minutes (`hi: null` = unknown). Color is by the HIGH estimate: green < 10 min, yellow 10–30, red 30+, grey unknown. Solid bar = low estimate; faded extension = up to high. The legend states this.
4. **Generate, do not hand-edit HTML.** Write a JSON spec and run `${CLAUDE_HOME:-$HOME/.claude}/skills/timeline/scripts/build.py spec.json` (stdlib only; spec in a `mktemp` dir). It applies the color rule, uses the CSS in `assets/template.html`, computes the header total estimate and projected finish time, and prints the text Gantt to stdout.
5. **Every row names its owner** (main session, lane, subagent, CLI delegate, CI) and, when the step has its own bead, that bead id. `build.py` warns on a row without an owner.

```json
{"title": "...", "snapshot": "2026-10-04 12:55 PDT", "subtitle": "...",
 "branch": "feat/x", "pr": 10097, "done": ["finished item"], "span": 70,
 "phases": [{"title": "Phase A", "rows": [
   {"id": "1", "name": "Merge main", "owner": "main session", "bead": "rev-abc",
    "detail": "...", "start": 0, "lo": 15, "hi": 25, "label": "optional"}]}],
 "flow": [["1 Merge", "2 Check"], "→", ["4 Review"], "→", "green", "‖", "3 Audit (dot)"]}
```

`span` is optional (defaults to the latest high end, rounded up to 10). `flow` items: a list = parallel stack, `"→"` = dependency, `"‖"` = independent side work, a string = single node.

## Stable path, gist, and bead

- **One file per PR, overwritten in place.** With no `out.html`, the path is `/tmp/timeline/<branch with / → ->-pr<N>.html` (from spec `branch`/`pr` or `--branch`/`--pr`), e.g. `/tmp/timeline/feat-same-turn-mandatory-audit-pr10097.html`; the PNG sits beside it. Never mint a new path on refresh. `<html>.owner` records the repo (origin URL without credentials, else the git toplevel; outside any git repo, pass `out.html`), branch and PR that own the path; a build from a different repo, or a colliding branch name (`foo/bar` vs `foo-bar`) exits with an error instead of overwriting that gist, so pass an explicit `out.html` then.
- **Gist (default).** Every build publishes unless `--no-publish` is passed. It scans the HTML for tokens and keys and refuses to upload on a hit, then creates a secret (unlisted) gist on the first run and edits the same gist afterwards; the id lives in `<html>.gist`. `gh gist` rejects binary files, so only the HTML is uploaded. The preview link is `https://gistpreview.github.io/?<gist id>/<file>` (always the latest gist revision). Tested 2026-10-04 in headless Chrome: gistpreview, htmlpreview.github.io and cdn.statically.io render the timeline directly; gist.githack.com and gistcdn.githack.com show a "One more step" interstitial and must not be used. `build.py` shortens it once via tinyurl, then cleanuri, then spoo.me, accepting only a short URL whose HEAD answers 3xx straight to the preview URL (interstitial shorteners such as da.gd are rejected; tinyurl and is.gd reject `htmlpreview.github.io` targets, but accept gistpreview). The result is cached in `<html>.short` (reused on refresh while the preview URL is unchanged) and printed first; if every shortener fails it prints the long link only. Refresh latency measured 2026-10-04: gistpreview served the new revision within 5 s of a gist edit (one render seconds after an edit still showed the previous revision), while the unversioned gist raw URL updates immediately.
- **Bead.** Each timeline is tied to exactly one bead, id in `<html>.bead` (or spec `bead` to reuse an existing one). The first run creates it with `br`; every run appends the gist URL, preview link, and HTML path to its notes with `--append-notes` (existing notes are kept; an unchanged refresh is a no-op). The DB comes from spec `bead_db` or `br info --json` in the cwd, and every call pins `--db` (beads-issue-tracking skill). Measured 2026-10-04 on the 85 MB worldarchitect.ai DB: create 0.7 s, update 0.6–0.7 s, close 1.1 s, so the step runs inline; a bead failure is reported without blocking the drawing.

## Always open and review (mandatory)

Never report a timeline you have not looked at.

1. Render with `${CLAUDE_HOME:-$HOME/.claude}/skills/timeline/scripts/review.sh <file.html> [height_px]` (headless Google Chrome preferred, Aside account u0 fallback). It prints the PNG path.
2. Read the PNG and check: bars start/end at the right axis positions (spot-check two against ticks), no clipped or overlapping text, no empty band at the bottom (adjust `height_px`), parallel steps actually overlap and dependents start after what they wait on, header total and finish time match the bars.
3. Fix and re-render until it passes.

## Always print it in chat (mandatory)

The user may not open the files. Every reply includes the `build.py` stdout in a fenced block: one row per step, `█` low, `░` low→high, estimate plus color word at the row end, an axis line, and the header totals. Then give, in this order: the short link (`Timeline:` line, the primary link the user opens), the full preview link (`Preview (full):`), the gist URL, the local HTML as a bare absolute path alone on its own line (secondary; terminals such as cmux linkify bare paths but not markdown `file://` links), the bead id, and one line on what you checked. Never omit the `Timeline:` link.

## Refresh while work is active (mandatory)

Once /timeline is running for live work, rebuild it every 10 minutes until the tracked deliverable is done or blocked on the user: re-pin live state, build with `--publish` (same path, gist, and bead), review the render, and print the text Gantt plus the HTML and gist links each time. Schedule the next refresh before ending the turn (a 600 s wakeup, or `/loop 10m` when available). Fold real-time lane polls (for example the dot's 5-minute poll) into the same tick rather than drawing more often.
