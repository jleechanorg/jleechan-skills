---
name: design-fidelity-diff
description: Use when implementing or reviewing UI against an approved design mock. Compare rendered artifacts, measure their geometry and visible properties, and itemize concrete deltas instead of judging against a remembered summary.
---

# Design fidelity diff

## The rule

**Never compare an implementation against your *summary* of a mock. Compare it
against the *rendered mock*.**

A summary is lossy by construction. You extract "Option C = one bordered
surface, no Custom Action button, pencil marker" — and every property you did
not extract is now invisible to you forever. You cannot self-detect the loss,
because the check ("does it look like my summary?") is evaluated against the
same lossy artifact that caused it. This is why "it matches" feels true right up
until someone opens the screenshot.

The runtime-evidence harness does **not** cover this. `/es`, before/after
captures, and captioned video all prove the change is **real and works**. None
of them proves it is **right**. A UI change can pass every existing gate while
diverging from the approved design on every visual property.

## When this is mandatory

Any time an approved design artifact exists and you are implementing or
reviewing against it. Specifically:

- Implementing from a Claude Design project, Figma frame, or HTML mockup
- The operator says "follow the mock" / "match the design" / "like option C"
- Reviewing a PR whose description cites a design mock
- Any time you are about to claim "matches the mock" / "faithful to the design"

If the operator selected an option **plus a refinement** ("I like C but make the
custom action clearer"), the target is **C + the refinement**, not C. Diff
against the refinement artifact — it is the operative spec.

## Procedure

### 1. Render the mock — do not read it

Get pixels, not source. Reading the mock's HTML/CSS and summarizing it is the
failure mode this skill exists to prevent.

Use the design tool's supported export or preview mechanism. Keep token-scoped
preview URLs out of user-facing text and logs. Store temporary captures in a
unique task-scoped directory under `/tmp`.

```python
from pathlib import Path
from tempfile import mkdtemp
from playwright.sync_api import sync_playwright
scratch = Path(mkdtemp(prefix="design-fidelity-", dir="/tmp"))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1440,"height":900}, device_scale_factor=2)
    pg.goto(Path("path/to/mock.html").resolve().as_uri(), wait_until="load")
    pg.query_selector("section.opt").screenshot(
        path=str(scratch / "mock_section.png")
    )
```

Isolate the relevant option. If the mock file holds several candidates, hide the
others (`el.style.display='none'`) and screenshot — cropping by computed
coordinates is fragile and silently produces the *wrong option*, which then gets
"verified" against.

### 2. Render the implementation the same way

Same viewport, same flow, real server. Reuse the repo's existing capture script
if one exists so mock and impl differ only in what you are testing.

### 3. MEASURE — do not eyeball, and do not ask a model to eyeball

This is the step that actually finds things. For every geometric or structural
claim, query the live DOM:

```python
pg.evaluate("""() => {
  const dock = document.getElementById('composer-stack');
  const send = document.querySelector('.composer-send');
  const btn  = document.querySelector('.choice-button');
  const d = dock.getBoundingClientRect(), s = send.getBoundingClientRect();
  const cs = getComputedStyle(btn), before = getComputedStyle(btn, '::before');
  return {
    send_pct_of_dock: +(s.height / d.height * 100).toFixed(1),
    send_is_outside_dock: !dock.contains(send),
    badge_left: btn.getBoundingClientRect().left + parseFloat(cs.paddingLeft),
    badge_width: parseFloat(before.width),
  };
}""")
```

`getBoundingClientRect` + `getComputedStyle` (including `::before`/`::after`)
answer containment, alignment, size, and ratio questions **exactly**. Use them
for anything you would otherwise squint at.

**Pixel-color heuristics are a trap.** Scanning for "purple-ish pixels" to find a
border or button will happily match an unrelated element elsewhere on the page
and hand you a confident wrong number. If a measurement result is implausible
(a 721px-tall dock in a 275px region), it is measuring the wrong thing — throw it
out and query the DOM instead.

**A multi-model panel is not a substitute either.** Asking a vision model
"does this match?" produces confident, specific, wrong answers on low-contrast
geometry — e.g. a seat returning `MAJOR_DEVIATION: the textarea and Send sit
outside the bordered surface` when a DOM probe proved `send_is_outside_dock`
was the *intended* state and the border demonstrably wrapped the textarea. Use
models for judgment ("is this affordance confusing?"), never for measurement.

**Measuring is not looking.** A measurement covers only the properties you
chose to measure; an all-pass scorer still misses a label drawn over content,
a toast clipping "Cancel" to "Canc", or a header scrolled off-screen. Before any
fidelity pass, open every final-state frame and the matching mock render as
images yourself and list what you see that the measured list did not cover
(overlap, occlusion, clipping, off-screen chrome). A measured pass with unopened
frames is not a fidelity pass.

### 3b. A matching attribute is not a matching pixel

Comparing a **value** proves the value; it does not prove the user can see it.
A row like `placeholder | "Custom Action: type whatever you want…" | (same) |
MATCH` is satisfied by a string comparison while the text renders at **1.05:1
contrast** and is invisible on screen — which is exactly how an unreadable
placeholder survived a 12-row all-MATCH fidelity table on this repo.

For any property whose whole purpose is to be *read or seen*, add a second row
asserting it is actually perceivable:

- **Text**: compute the contrast ratio of the *composited* colours (resolve
  `rgba` over its real backdrop — an alpha colour compared against a token is
  meaningless). [WCAG AA text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
  requires 4.5:1 for normal text, including UI labels and placeholders, and
  3:1 for large text (at least 18 pt, or 14 pt bold), subject to its stated
  exceptions. Being UI text does not qualify for the large-text threshold.
- **Meaningful non-text controls, states and graphics**: apply the separate
  [3:1 non-text rule](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
  against adjacent colours, including its exceptions for inactive controls,
  unmodified user-agent appearance and essential graphical presentation.
  Decorative borders and dividers are not automatically subject to this rule.
- **Anything positioned**: confirm it is inside the viewport and not clipped by
  an `overflow: hidden` ancestor.

Watch for framework defaults leaking across themes: Bootstrap's
`.form-control::placeholder` is a light-theme grey, so any dark surface that
never overrides it renders dark-on-dark while every attribute assertion passes.

Rule of thumb: **if a screenshot row looks empty, do not assume it is empty by
design — measure it.** An apparently blank row is either genuinely blank (a
bug) or invisible content (also a bug).

### 4. Itemize the delta as a table

One row per property. Every row is `MATCH` or a concrete number-vs-number.

| Property | Mock | Impl | Verdict |
|---|---|---|---|
| Outer border token | `--border-color` purple | `--accent-color` gold | **DELTA** |
| Send inside border | no | yes | **DELTA** |
| Send height % of dock | 75% | 5% | **DELTA** |
| Choice badge gutter | `1/2/3` at x=12 | absent | **DELTA** |
| Free-form marker | pencil, same gutter | pencil, inline | **DELTA** |
| Separate Custom Action row | absent | absent | MATCH |

Enumerate properties **from the mock's own source**, not from memory: every
token it sets, every element's containment, every explicit size. That is what
makes the list exhaustive rather than "the things I happened to notice."

### 5. Read the mock's prose as spec, not decoration

Mock captions state mechanisms and constraints. They are binding.

- *"the input keeps the same left gutter as the choice rows, but its marker is a
  pencil instead of a number — so it reads as the final item in the same list"* —
  the shared gutter **is** the mechanism. Shipping the pencil without the gutter
  ships the label, not the feature.
- Theme files state conventions: *"Gold for text/links. Purple for borders,
  glows, button bg."* Check the token you are about to use against the stated
  rule.

### 6. Do not launder a deviation as pre-authorized liberty

A caption like *"the portrait is treated as movable/resizable"* authorizes
**position and size**. It does **not** authorize **containment** — moving an
element from outside a border to inside one is a structural change the mock never
showed. When tempted to classify a difference as covered by a liberty clause,
state the clause and the difference side by side and check they are the same
kind of thing. If the difference changes what contains what, it is a delta.

## Implementation notes

**Prefer presentational mechanisms that keep the DOM identical.** Numbering
choice rows via a CSS counter + `::before` matches the mock without changing
rendered text or accessible names — which keeps any "renderer output is
byte-identical" guard meaningful instead of quietly defeating it. Reach for
markup only when the mock's behavior genuinely requires it.

**Encode the fidelity claim as an assertion**, so the delta cannot silently
reopen:

```python
"insideDock": dock.contains(pip),        # must stay False
"pipWidth": pip.getBoundingClientRect().width,   # must stay <= 60
```

Guard the *mechanism*, not just the current value — assert the dead layout rule
cannot come back, and strip comments before grepping CSS so prose explaining a
removal does not trip the guard.

## Failure signature this prevents

Four operator-caught rounds on one PR, each found by the operator opening a
screenshot, none by the agent: wrong border token → structurally misplaced
element → missing gutter mechanism → wrong button geometry. When the procedure
above was finally run, it found every remaining delta in **one pass** with exact
numbers, and refuted a wrong external verdict at the same time.

If you are on round two of "actually, that doesn't match the mock" — stop
patching the reported symptom and run this whole procedure. The next delta is
already there; you just have not measured it yet.
