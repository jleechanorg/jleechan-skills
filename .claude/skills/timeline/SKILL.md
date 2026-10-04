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
4. **Generate, do not hand-edit HTML.** Write a JSON spec and run `${CLAUDE_HOME:-$HOME/.claude}/skills/timeline/scripts/build.py spec.json out.html` (stdlib only; use a `mktemp` dir). It applies the color rule, uses the CSS in `assets/template.html`, computes the header total estimate and projected finish time, and prints the text Gantt to stdout.

```json
{"title": "...", "snapshot": "2026-10-04 12:55 PDT", "subtitle": "...",
 "done": ["finished item"], "span": 70,
 "phases": [{"title": "Phase A", "rows": [
   {"id": "1", "name": "Merge main", "detail": "...", "start": 0, "lo": 15, "hi": 25, "label": "optional"}]}],
 "flow": [["1 Merge", "2 Check"], "→", ["4 Review"], "→", "green", "‖", "3 Audit (dot)"]}
```

`span` is optional (defaults to the latest high end, rounded up to 10). `flow` items: a list = parallel stack, `"→"` = dependency, `"‖"` = independent side work, a string = single node.

## Always open and review (mandatory)

Never report a timeline you have not looked at.

1. Render with `${CLAUDE_HOME:-$HOME/.claude}/skills/timeline/scripts/review.sh <file.html> [height_px]` (headless Google Chrome preferred, Aside account u0 fallback). It prints the PNG path.
2. Read the PNG and check: bars start/end at the right axis positions (spot-check two against ticks), no clipped or overlapping text, no empty band at the bottom (adjust `height_px`), parallel steps actually overlap and dependents start after what they wait on, header total and finish time match the bars.
3. Fix and re-render until it passes.

## Always print it in chat (mandatory)

The user may not open the files. Every reply includes the `build.py` stdout in a fenced block: one row per step, `█` low, `░` low→high, estimate plus color word at the row end, an axis line, and the header totals. Then give the HTML as a clickable link, `[<abs path>](file://<abs path>)`, plus the absolute PNG path, and one line on what you checked. Never omit the HTML link.

## Refresh while work is active (mandatory)

Once /timeline is running for live work, rebuild it every 10 minutes until the tracked deliverable is done or blocked on the user: re-pin live state, build, review the render, and print the text Gantt plus the HTML link each time. Schedule the next refresh before ending the turn (a 600 s wakeup, or `/loop 10m` when available). Fold real-time lane polls (for example the dot's 5-minute poll) into the same tick rather than drawing more often.
