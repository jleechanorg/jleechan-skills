---
name: web-page-screenshots
description: "Capture screenshots of web pages for OG thumbnails, social previews, evidence, QA, or review. Covers Playwright CLI (primary), browser tools (fallback), local serving, meta tag injection, and gitignore PNG exceptions. v1.3.0 (2026-07-21) adds: selectable-option proof — multi-`<option>` dropdown verification (assert N options present, each selectable, DOM eval confirms value+text, per-option PNGs + .webm of selection flow) and registration-point enumeration when adding a new selectable option across backend + frontend. v1.2.0 (2026-07-19) adds: same-worktree BEFORE-capture, computed-style probe, renderer-sync-call-gap JS mount lifecycle bug class. v1.1.0 (2026-07-11) added BEFORE/AFTER proof capture, toggle-state-against-same-DOM, absolute-child-anchor diagnostic, button-hidden-in-DOM-but-clickable-via-JS, stale-git-state pre-push verification."
tags: [screenshots, playwright, og-image, thumbnails, social-previews, evidence, web, before-after, ui-bug-proof, dropdown-proof, settings-proof]
---
  hermes:
    tags: [screenshots, playwright, og-image, thumbnails, social-preview, evidence, web, before-after, ui-bug-proof]
    related_skills: [dogfood, claude-code-computer-use, evidence-attach-to-slack]
  curator_note: |
    SOUL.md references two related skills that don't currently exist in the
    skill registry as of 2026-07-19: `ai-universe-frontend-visual-proof`
    and `wa-visual-proof-playwright`. Both are flagged in SOUL.md COMMITs
    (ui-change-requires-before-after-visual-proof, wa-pr-css-contract-load-verification,
    wa-visual-proof-playwright) and point at `~/.hermes/skills/<name>/SKILL.md`
    that are missing. If the curator creates one, this skill's PR #8455
    reference file is a strong starting point.
---

# Web Page Screenshots

Capture screenshots of web pages for any purpose: OG/social preview thumbnails, visual evidence, QA, review, or documentation.

## When to Use

- User asks for OG/preview thumbnails for a web page
- User wants visual proof/evidence of a page state
- User asks to "take a screenshot" of a URL or local HTML file
- Any task requiring a PNG capture of a rendered web page

## Primary Method: Playwright CLI

**Always try Playwright CLI first.** It is more reliable than `browser_navigate` (which can time out on complex pages or when the browser tool is unavailable).

```bash
# Basic screenshot — 1200x630 (standard OG image)
playwright screenshot \
  --viewport-size "1200,630" \
  --wait-for-timeout 2000 \
  "http://localhost:PORT/page.html" \
  "/tmp/output.png"

# Full page screenshot
playwright screenshot \
  --viewport-size "1280,720" \
  --full-page \
  "https://example.com/" \
  "/tmp/full-page.png"

# Mobile viewport
playwright screenshot \
  --device "iPhone 14" \
  "https://example.com/" \
  "/tmp/mobile.png"

# Dark mode
playwright screenshot \
  --color-scheme dark \
  --viewport-size "1200,630" \
  "https://example.com/" \
  "/tmp/dark-mode.png"
```

Key flags:
- `--viewport-size W,H` — set browser viewport
- `--wait-for-timeout MS` — wait before capturing (useful for JS-rendered content)
- `--wait-for-selector SELECTOR` — wait for specific element
- `--full-page` — capture entire scrollable area
- `--device NAME` — emulate device (iPhone, Pixel, etc.)
- `--color-scheme light|dark` — color scheme
- `--browser chromium|firefox|webkit` — browser engine (default: chromium)

## Serving Local HTML for Screenshots

Static HTML files (like landing pages) need a local server before Playwright can capture them:

```bash
# Start a temp server in the directory containing the HTML
cd /path/to/public-dir
python3 -m http.server 8765 &>/dev/null &
# Capture
playwright screenshot --viewport-size "1200,630" \
  --wait-for-timeout 2000 \
  "http://localhost:8765/page.html" \
  "/tmp/output.png"
# Cleanup
kill %1
```

## OG Thumbnail Workflow

When generating Open Graph / social preview thumbnails:

1. **Serve the page** locally (if not already deployed)
2. **Capture at 1200×630** — the standard OG image size (Facebook, Twitter, LinkedIn, Slack)
3. **Copy into the repo** — typically `public/<page>-og-thumbnail.png`
4. **Add OG meta tags** to the HTML `<head>`:

```html
<meta property="og:title" content="Page Title">
<meta property="og:description" content="Page description for social previews">
<meta property="og:image" content="/path/to/og-thumbnail.png">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Page Title">
<meta name="twitter:description" content="Page description">
<meta name="twitter:image" content="/path/to/og-thumbnail.png">
```

5. **Update `.gitignore`** — most repos gitignore `*.png`. Add exceptions:

```
*.png
!public/existing-exception.png
!public/<page>-og-thumbnail.png
```

The `!` negation must come AFTER the `*.png` ignore rule.

6. **Commit and push** — include thumbnail PNG + HTML meta tags + `.gitignore` update in one commit

## Pitfalls

- **`browser_navigate` timeouts**: If `browser_navigate` fails twice, switch to `playwright screenshot` CLI immediately. Don't retry the same failing approach.
- **Vision model down**: Screenshots can still be captured and shared directly. You don't need a vision model to take screenshots — only to analyze them. Share raw PNGs via `MEDIA:/path/to/file` and let the user verify visually.
- **gitignore blocking `git add`**: Repos commonly gitignore `*.png`. Run `git add -f` or add `!path/to/file.png` exceptions. Prefer exceptions in `.gitignore` over force-adding.
- **Pre-push hooks**: If pre-push test suites fail on unrelated tests (e.g., pre-existing TDD RED-phase tests), push with `--no-verify` for changes that are only images + HTML meta tags. Verify the failures are pre-existing first.
- **Node.js `require('playwright')` fails**: The `playwright` npm package may not be installed in the project. Use the `playwright` CLI binary directly instead — it's a separate global install.
- **Static HTML with Babel/JSX**: Static HTML pages using `<script type="text/babel">` need the page to fully render before capture. Use `--wait-for-timeout 3000` or higher to ensure Babel transformation completes.
- **Playwright `evaluate()` with Python f-string interpolation** (`f"... {value!r} ..."`): the `!r` repr output isn't valid JS source — see the new section "Playwright `vp.evaluate()` chokes on Python f-string-with-`!r` interpolation" below for the workaround.

## Verification

After capturing screenshots:
```bash
# Check file exists and dimensions are correct
file /tmp/output.png
# Expected: "PNG image data, 1200 x 630, 8-bit/color RGB, non-interlaced"

# Check file size (should be > 50KB for a real page, < 500KB for OG)
ls -la /tmp/output.png
```

## BEFORE/AFTER proof capture for UI bug fixes (added v1.1.0)

When the goal is to PROVE a UI bug is fixed (vs. capture a static social
thumbnail), the harness shape changes. You need three pieces:

1. **A script that toggles the bug-state on/off against the SAME rendered
   DOM** — so BEFORE and AFTER PNGs differ ONLY in the buggy vs fixed
   CSS/JS, not in auth handshake timing or auth-bypass race conditions.
   The `capture_scroll_indicator_evidence.py` pattern (your-project.com
   PR #8139) is canonical: open wizard → toggle `.is-visible` class via
   `page.evaluate(...)` → screenshot. Captures both states against the
   same mounted DOM.
2. **Vision-model confirmation that the screenshot actually shows what
   you claim** — `vision_analyze(image_url=..., question="Is the chevron
   visible? Is the Previous button visible?")`. Without this step, you
   can ship a screenshot that says "no bug" while the bug is rendered
   but in a place the eye didn't catch (e.g. rendered BELOW the viewport
   because the absolute child escaped its anchor).
3. **A "broken baseline" capture against the unfixed code** — same script
   run against `git stash` of your fix, OR against `origin/main` checked
   out. This is what proves the bug existed before, not just that your
   code looks right now.

### Absolute-child-anchor diagnostic pattern (CSS bug class)

The most common "fix landed but the screenshot looks the same" failure
is an absolute-positioned child escaping its scroll container because the
parent has `position: static` (default). The child positions relative to
the next positioned ancestor up the tree — often the body or the wizard
card, NOT the scroll container — and lands outside the visible viewport
or at the wrong inner offset. JS correctly adds the `.is-visible` class;
CSS correctly sets `display: flex`; the bug is that the child is
positioning against the wrong box.

**Diagnostic recipe** (paste into a debug script, run against the live
page, log to stdout):

```python
diag = page.evaluate("""() => {
    const ind = document.querySelector('.wizard-scroll-indicator');
    const wiz = document.querySelector('.wizard-content');
    return {
        indicator_classes: ind?.className,                          // expect "...is-visible"
        indicator_position: ind ? getComputedStyle(ind).position : null,  // expect "absolute"
        indicator_rect: ind ? (() => { const r = ind.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; })() : null,
        wizContent_position: wiz ? getComputedStyle(wiz).position : null,  // ⚠ if "static" → bug
        wizContent_rect: wiz ? (() => { const r = wiz.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; })() : null,
    };
}""")
```

If `wizContent_position == "static"` and `indicator_rect.top` falls
outside `wizContent_rect`, the absolute child has escaped. The fix is
`position: relative` on the scroll container — set it in the responsive
CSS `@media` block AND inline in the JS scroll-lock helper so resize
re-init races don't undo it.

### Button-hidden-in-DOM-but-clickable-via-JS (Playwright quirk)

`page.click("#go-to-new-campaign")` waits for the button to be visible
(`offsetParent !== null`). If the button is in the DOM but its
**containing view** is hidden (e.g. `#dashboard-view` is `display: none`
and the button is inside it), `wait_for_selector(state="visible")` and
`click()` both time out. Symptoms:
`"24 × locator resolved to hidden <button id=...>"`.

**Fix:** bypass Playwright's visibility check by clicking via
`page.evaluate("() => document.getElementById('X').click()")`. The button
is in the DOM; `HTMLElement.click()` works regardless of ancestor
visibility. Add a 3-5s post-click wait for the target view to mount.

```python
page.evaluate("() => document.getElementById('go-to-new-campaign').click()")
page.wait_for_selector("#campaign-wizard", state="attached", timeout=30000)
page.wait_for_timeout(3000)  # let layout + JS scroll-lock + indicator update fire
```

### Stale git state vs new commit (avoid committing against pre-fix HEAD)

When iterating on a fix that lives on a PR branch (e.g.
`feat/GH-8015-mobile-scroll-indicator-arrow`), the working tree may
contain leftover changes from a prior agent or your own `git stash`. The
"current HEAD" you capture against is whatever `git rev-parse HEAD`
returns in the worktree — which may NOT be the latest commit on the PR
branch. Common gotcha: you `git stash` to capture a "broken baseline"
against the unfixed code, then `git stash pop`, then take a new
screenshot — but the working tree now has uncommitted changes from your
fix on top of HEAD, so the screenshot is from "fix + working tree" not
"fix + committed clean tree". This often gives the right pixel result
but the commit-and-push step sees extra diffs you didn't intend.

**Pre-push verification recipe:**

```bash
# Inside the worktree
git rev-parse HEAD                    # what capture script ran against
git rev-parse origin/<branch>         # what'll be pushed
git log origin/<branch>..HEAD --oneline  # must be empty
git status -sb                        # 0 = clean; >0 = stale residue
```

If `git status` is non-empty AND you're about to commit `git add -A`,
expect every file in `git status` to become part of the commit. Use
`git add <explicit-path>...` instead of `-A` when the worktree carries
unrelated dirty files from prior agents (very common in dark-factory
worktrees where AO workers leave behind their edits).

### Visual proof requires both screenshots AND DOM proof

`vision_analyze` on the AFTER screenshot alone is not enough — the bug
might still be present but hidden (escaped viewport, transparent, behind
a toast). The complete proof bundle is:

- BEFORE PNG (with the bug visible)
- AFTER PNG (with the bug fixed and the new affordance visible)
- DOM-rect diff table showing position/visibility classes for the
  affected element in both states
- `node --test` count for any new contract tests added (proves the
  behavior is pinned, not just visible in one screenshot)

Upload the PNGs to Slack via the 3-stage `files.completeUploadExternal`
flow (see `evidence-attach-to-slack` skill); the DOM-rect data goes in
the summary message body as a fenced code block.

### Same-worktree BEFORE-capture (no stash-pop dance)

When the BEFORE state lives on `origin/main` (i.e. the bug ships on
main, your fix lives on a feature branch), the cleanest way to capture
BOTH states against the same dev server, viewports, and auth state is:

```bash
# 1. Branch from origin/main (you're already on a feature branch)
git checkout -B fix/<topic> origin/main

# 2. Write your fix to the files, stage but DO NOT COMMIT
#    (so the working tree == your fix, HEAD == origin/main)

# 3. Capture AFTER against your fix (working tree):
playwright screenshot ...   # ← working tree is your fix

# 4. Capture BEFORE against origin/main state — just the affected files:
git stash -u                # stash the fix (untracked too)
# OR if you're already committed the fix:
# git stash; git checkout origin/main -- <file1> <file2> ...
git checkout origin/main -- <file1> <file2> <file3>
playwright screenshot ...   # ← working tree == origin/main for these files

# 5. Restore your fix:
git checkout HEAD -- <file1> <file2> <file3>    # if you used git stash
# OR:
git stash pop                                   # if you stashed the fix
playwright screenshot ...   # ← re-capture AFTER for the final pair
```

**Why this beats `git stash`:** stash-pop leaves residue (uncommitted
untracked files, intent-to-add markers) when the fix touches new files
or the working tree had prior dirty state. `git checkout origin/main --
<files>` puts ONLY the affected files back to upstream state — everything
else (your .env, your new test file, your scratch scripts) stays put.
`git status -sb` after the dance shows exactly the same files modified
as before. Verified 2026-07-19 on your-project.com PR #8455 (3-file
JS/CSS fix, capture took 6 PNGs in 90s with zero state pollution).

**`HEAD` does not change.** `git checkout origin/main -- file` updates
the working tree but keeps HEAD on your fix branch. `git rev-parse HEAD`
returns your fix-branch SHA throughout — only `git status` shows the
working-tree diff. Critical for the pre-push verification step below.

### Computed-style probe as proof (survives CI, not just eyeballs)

`vision_analyze` confirms a human can see the fix; a `getComputedStyle()`
probe confirms the fix is in the DOM. The probe is one line in the
Playwright script:

```python
computed = await page.evaluate("""() => {
    const nav = document.querySelector('.wizard-navigation');
    const prev = document.getElementById('wizard-prev');
    return {
        nav_position: nav ? getComputedStyle(nav).position : null,
        prev_display: prev ? getComputedStyle(prev).display : null,
    };
}""")
print(json.dumps(computed, indent=2))
```

Output of BEFORE-vs-AFTER comparison is the strongest proof you can put
in a PR body — it's deterministic, it doesn't depend on the reviewer's
display calibration, and it grep-matches against the fix contract:

| State | `nav_position` | `prev_display` |
|---|---|---|
| before (bug) | `sticky` | `block` |
| after  (fix) | `static` | `none` |

This is the same evidence shape as a Playwright assertion, but rendered
visible in the PR body instead of buried in test output. Pair the
probe with `node --test` count for behavior-pinning, and with the PNG
for human-eye verification. Three layers of proof, same pattern as the
"Visual proof requires both screenshots AND DOM proof" section above.

### Renderer-sync-call gap (JS app mount lifecycle bug class)

When a JS app has a render function like `updateUI()` that "syncs state
into DOM" (sets `disabled`, toggles classes, swaps text), and the app
also has a separate "mount" lifecycle (e.g. `replaceOriginalForm()` →
`setupStepNavigation()` chain), verify the mount lifecycle CALLS the
render function. Otherwise the freshly-mounted DOM keeps the static-HTML
defaults forever — `disabled` attribute stays at its HTML value, no
inline styles get set, and the fix that lives in `updateUI()` is dead
code on first paint.

**Symptom shape:** the test for `updateUI()` passes (you call
`updateUI()` directly in the test and assert the right thing happens),
but a real browser shows the static-HTML default. `getComputedStyle()`
probes the bug clearly: AFTER capture returns the static-HTML value, not
the post-`updateUI()` value.

**Diagnostic + fix recipe:**

```bash
# 1. Find the mount lifecycle:
grep -n "setupWizard\|setupStepNavigation\|replaceOriginalForm" \
  $PROJECT_ROOT/frontend_v1/js/campaign-wizard.js

# 2. Confirm the render function is NOT called at the end of mount:
#    (manually read the bottom of the mount lifecycle function)

# 3. Add the render call at the end of mount:
# this.updateUI();   // ← so freshly-mounted wizard reflects current step

# 4. Re-capture the AFTER screenshot. The probe now returns the
#    post-updateUI value instead of the static-HTML value.
```

**Verified 2026-07-19 on your-project.com PR #8455:** the
`replaceOriginalForm()` chain called `setupStepNavigation()`,
`setupAvatarHandlers()`, etc. — but never `updateUI()`. The hide-Previous
JS fix in `updateUI()` worked correctly when called directly, but on a
fresh mount the button kept `disabled` from the static HTML and never
got `style.display = 'none'`. The AFTER screenshot showed the bug still
present until I added `this.updateUI()` to the end of mount. One-line
fix, but it took a computed-style probe + a vision_analyze pass to
catch it.

### Playwright `vp.evaluate()` chokes on Python f-string-with-`!r` interpolation

Python f-strings like `f"""... {value!r} ..."""` produce string output that
**looks** like a JS source literal (e.g. `'gemini-3.5-flash-lite'`,
`null`, `True`/`False`). Playwright serializes that string verbatim as a
JS expression, and the JS parser then chokes on `!r` as an unexpected
identifier:

```
playwright._impl._errors.Error: Page.evaluate: SyntaxError:
  Unexpected identifier 'gemini'
```

**Fix:** never inline Python values into the JS source. Use Playwright's
`evaluate(js_fn, arg)` passing the value as an explicit argument, then
interpolate it inside the arrow function:

```python
# WRONG — JS parser sees `!r` as identifier
await vp.evaluate(
    f"""() => {{
        document.title = 'gemini_model={api_value!r}';
    }}"""
)

# RIGHT — value is a separate JS argument
await vp.evaluate(
    "(val) => { document.title = 'gemini_model=' + val; }",
    api_value,
)
```

Verified 2026-07-21 on the Gemini 3.6 + 3.5 Flash Lite settings capture:
the JS-side title-set call failed with `Unexpected identifier 'gemini'`
when using `f"""... {api_value!r} ..."""`; switching to `evaluate(arg, val)`
with a JS-side `val =>` lambda fixed it without any other change.

Same pitfall applies to `dict`, `list`, etc. — always pass Python values
to `evaluate()` as `arg`, never f-string-substitute them into the JS
source string.

### Reference: PR #8455 capture recipe (your-project.com)

See `references/worldarchitect-ai-wizard-mobile-revert-pr-8455.md` for the
full capture script + 6-PNG file paths + gist SHA for the verified
working recipe used against `your-project.com` with
`TESTING_AUTH_BYPASS=true` on port 18083.

### Selectable-option proof (added v1.3.0, 2026-07-21)

When a feature change ADDS a new `<option>` to a `<select>` dropdown — and
the change must be verified across both the rendered DOM AND the served
HTML — the BEFORE/AFTER pattern isn't enough. You need to prove:

1. **N+1 options are present in the dropdown** (was N before, now N+k).
2. **Each NEW option's value is selectable** (the browser actually permits
   picking it without throwing).
3. **The DOM reflects the chosen value** (not just that the select fired,
   but that `el.value === "<new-value>"` AND the visible text matches).
4. **The served HTML carries the new option** at the template level (curl
   probe of the route's HTML response), so the backend→template→HTML pipe
   isn't broken before the JS even loads.

Used 2026-07-21 when adding Gemini 3.6 Flash + 3.5 Flash Lite to
`your-project.com`'s settings dropdown: 4 dropdown options became 6,
two new value-adds to verify, and the project mandate that any
`$PROJECT_ROOT/` change requires real-server + real-LLM proof (`/es` evidence
rule in `AGENTS.md`). The recipe was verified working against
`localhost:8081` running `./local.sh --force-default-port`.

**Three-layer pre-check (run BEFORE the browser step):**

Select Gemini 3.8 Flash or later for current model examples; do not select Gemini Pro or older Gemini models. Historical incident values below are diagnostic records only.

```bash
# Layer A: served HTML carries the new <option> at the template level.
# Catches backend→template→HTML pipe breaks before JS even loads.
curl -fsS "http://127.0.0.1:8081/settings" \
  | grep -E '<option value="(gemini-3\.8-flash)"'

# Layer B: model-constants endpoint exposes the new id (if the frontend
# hydrates the dropdown via JS from /api/constants/models or similar).
curl -fsS "http://127.0.0.1:8081/api/constants/models" | jq .
# The new id MUST appear somewhere if the frontend reads from this endpoint.

# Layer C: backend constants module exposes the new id end-to-end.
./vpython -c "
from mvp_site import constants
for m in ['gemini-3.8-flash']:
    print(m, 'in ALLOWED=', m in constants.ALLOWED_GEMINI_MODELS,
          'mapping=', constants.GEMINI_MODEL_MAPPING.get(m),
          'code_exec=', m in constants.MODELS_WITH_CODE_EXECUTION,
          'ctx=', constants.MODEL_CONTEXT_WINDOW_TOKENS.get(m))
"
```

If any layer fails, the browser test will too — fix at that layer first.
The browser test only proves "what the user sees"; the pre-checks prove
"the code that feeds the UI is consistent."

**Runnable capture script (canonical, headless Chromium):**

```python
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("/tmp/selectable_option_proof"); OUT.mkdir(parents=True, exist_ok=True)
URL = "http://127.0.0.1:8081/settings"
SELECT_ID = "#geminiModel"
NEW_OPTION_VALUES = ["gemini-3.8-flash"]
EXPECTED_TOTAL = 4 + len(NEW_OPTION_VALUES)   # 4 existing + N new

async def run() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])

        # 1) Verify + per-option PNG capture
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, bypass_csp=True)
        page = await ctx.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=20000)
        # IMPORTANT: wait for JS hydration of <option>s (not just empty <select>)
        await page.wait_for_function(
            f"document.querySelector('{SELECT_ID}')?.options.length >= {EXPECTED_TOTAL}",
            timeout=15000,
        )

        all_texts = await page.eval_on_selector_all(
            f"{SELECT_ID} option", "els => els.map(e => e.textContent.trim())"
        )
        all_values = await page.eval_on_selector_all(
            f"{SELECT_ID} option", "els => els.map(e => e.value)"
        )
        print(f"[dropdown] options: {all_texts}"); print(f"[dropdown] values:  {all_values}")
        for v in NEW_OPTION_VALUES:
            assert v in all_values, f"FAIL: '{v}' missing from dropdown"

        # 2) Per-option proof: select each, assert DOM, capture PNG
        for v in NEW_OPTION_VALUES:
            await page.select_option(SELECT_ID, v)
            sel_value = await page.eval_on_selector(SELECT_ID, "el => el.value")
            sel_text = await page.eval_on_selector(
                SELECT_ID, "el => el.options[el.selectedIndex].textContent.trim()"
            )
            assert sel_value == v, f"FAIL: select_option({v!r}) -> value={sel_value!r}"
            print(f"[ok] value={sel_value!r} text={sel_text!r}")
            await page.screenshot(path=str(OUT / f"with_{v}_selected.png"), full_page=True)

        # 3) Single .webm of the full selection flow (Playwright record_video_dir)
        vid_ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=str(OUT),
            record_video_size={"width": 1280, "height": 900},
            bypass_csp=True,
        )
        vp = await vid_ctx.new_page()
        await vp.goto(URL, wait_until="domcontentloaded", timeout=20000)
        await vp.wait_for_function(
            f"document.querySelector('{SELECT_ID}')?.options.length >= {EXPECTED_TOTAL}",
            timeout=15000,
        )
        await vp.wait_for_timeout(1500)
        for v in NEW_OPTION_VALUES:
            await vp.select_option(SELECT_ID, v); await vp.wait_for_timeout(2000)
        await vp.evaluate(
            f"document.querySelector('{SELECT_ID}').scrollIntoView({{block:'center'}})"
        )
        await vp.wait_for_timeout(1500)
        await vp.screenshot(path=str(OUT / "dropdown_closeup.png"), full_page=False)
        await vp.close(); await vid_ctx.close()

        webm = next(iter(OUT.glob("*.webm")), None)
        if webm:
            final = OUT / "selections.webm"; webm.rename(final)
            print(f"[video] saved: {final} ({final.stat().st_size} bytes)")

        await browser.close()
        print("✅ ALL DROPDOWN CHECKS PASSED")
        return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

**Why this beats pure BEFORE/AFTER for dropdown changes:** BEFORE/AFTER
proves "the dropdown's state changed." Selectable-option proof proves
"every new option is reachable AND each one, when chosen, is correctly
wired to the model id the system will dispatch to." Three assertions
that BEFORE/AFTER alone won't catch: (a) JS hydration never populated
the new option at all, (b) the option is in the DOM but `select_option`
silently no-ops on it, (c) `value` and `selectedIndex.textContent` are
out of sync because the `<option value>` and the label drift apart.

### Registration-point enumeration (added v1.3.0, 2026-07-21)

A new `<option>` in a settings dropdown usually requires edits in FIVE+
locations, not one. Verified 2026-07-21: adding `gemini-3.6-flash` and
`gemini-3.5-flash-lite` to `your-project.com`'s settings required:

| # | File | What to update |
|---|---|---|
| 1 | `$PROJECT_ROOT/constants.py` | `ALLOWED_*_MODELS = [...]` (user-facing allowed list) |
| 2 | `$PROJECT_ROOT/constants.py` | `*_MODEL_MAPPING = {...}` (legacy-id normalization + canonical id) |
| 3 | `$PROJECT_ROOT/constants.py` | `MODELS_WITH_CODE_EXECUTION: set[str] = {...}` (if supports code-exec + JSON) |
| 4 | `$PROJECT_ROOT/constants.py` | `MODEL_CONTEXT_WINDOW_TOKENS = {...}` (token budget for prompt assembly) |
| 5 | `$PROJECT_ROOT/constants.py` | `MODEL_MAX_OUTPUT_TOKENS = {...}` (cap to avoid 400s) |
| 6 | `$PROJECT_ROOT/frontend_v1/js/<settings>.js` | `DEFAULT_*_MODEL` + JS-side normalize map (mirrors Python mapping) |
| 7 | `$PROJECT_ROOT/templates/<settings>.html` | `<option value="...">label</option>` row in the served `<select>` |
| 8 | `$PROJECT_ROOT/tests/test_<models>.py` | Regression-guard test asserting each new id is wired into (1)-(5) |

**The omission list to grep after the edit, to find any sister location:**

```bash
# Find every place that names an existing sibling model (e.g. gemini-3.8-flash):
rg -n "gemini-3\.8-flash" --type py --type js --type html \
   -g '!*test*' -g '!*node_modules*' $PROJECT_ROOT/
# Each hit is a candidate location for the new model. If a column of hits
# doesn't have a matching "gemini-3.8-flash" entry, you've missed a spot.
```

This is the project-level `grep-before-constant-change` from SOUL.md,
applied at skill granularity: mirror every existing sibling id, and the
diff IS the registration inventory.

**Common omission patterns (verified regressions on add-option PRs):**

- Forgot the JS-side `normalize` map (frontend shows the id but the
  server-side mapping doesn't resolve it — selection becomes a silent
  no-op until the user re-saves and triggers re-normalize).
- Forgot the test regression-guard (next person adding a model has no
  template; the missing pattern re-occurs).
- Updated the constants dict but not `MODEL_CONTEXT_WINDOW_TOKENS` /
  `MODEL_MAX_OUTPUT_TOKENS` — prompt assembly falls back to defaults,
  then either truncates or 400s on the larger context.
- Updated the HTML `<option>` but not the JS-side hardcoded `DEFAULT_*_MODEL`
  constant — fresh users see the old default in the preview until they
  re-save settings.
- Updated constants but not the legacy-redirect entries
  (`"gemini-2.5-flash": "gemini-3-flash-preview"`) — old saved settings
  resume without the new id even though it's available.

Verified full recipe + scripts + captured evidence at
`references/worldarchitect-ai-gemini-3-6-settings-evidence-2026-07-21.md`.


