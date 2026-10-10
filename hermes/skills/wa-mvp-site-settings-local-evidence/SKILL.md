---
name: wa-mvp-site-settings-local-evidence
description: "Recurring your-project.com workflow for editing `$PROJECT_ROOT/` settings surface (dropdowns, models, BYOK, provider selection) — edit code, run local server, capture browser+API proof. Trigger when the user says 'add a model to settings', 'change a settings option', 'add a toggle', or any change to `$PROJECT_ROOT/templates/settings.html`, `frontend_v1/js/settings.js`, `constants.py` (model sections), or `settings_validation.py`. Covers the 7-place registration map (HTML option + JS normalize + constants allowed/mapping/code-exec/limits + regression test), the `POST /api/settings` raw-payload trap, the `local.sh` exit-0 trap (verify with lsof), `main.py serve` reads port from `PORT` env only, and the AGENTS.md `/es` mandate (real server + browser/video proof for `$PROJECT_ROOT/**`). Distinct from `web-page-screenshots` (generic Playwright capture — this is the project-specific edit+run+prove shape). Verified 2026-07-21 on `feat/gemini-3-5-flash-lite-3-6-flash`."
tags: [worldarchitect, settings-page, mvp_site, evidence, /es, gemini-models, byok, local-server, settings-evidence, dropdown-proof]
category: worldarchitect
---

# Your Project — MVP Site Settings Local-Evidence Workflow

When you change anything in `$GITHUB_REPOSITORY`'s user-facing
settings surface, `AGENTS.md` mandates `/es` evidence before the work is
"complete." This skill captures the recurring edit + run + prove shape so
future settings PRs don't have to re-derive it.

## When to load this skill

- Adding/removing a `<option>` from any settings dropdown (provider, model, theme, rag_mode, etc.).
- Adding/removing a setting field anywhere in `$PROJECT_ROOT/templates/settings.html`.
- Changing `ALLOWED_*_MODELS`, `*_MODEL_MAPPING`, `MODELS_WITH_CODE_EXECUTION`,
  `MODEL_CONTEXT_WINDOW_TOKENS`, or `MODEL_MAX_OUTPUT_TOKENS` in `$PROJECT_ROOT/constants.py`.
- Adding/changing a BYOK input or any `gemini_api_key` /
  `openrouter_api_key` field logic.
- Changing `$PROJECT_ROOT/settings_validation.py` (the validator the `POST /api/settings`
  path runs first).
- Touching `$PROJECT_ROOT/frontend_v1/js/settings.js`, the v1 settings client
  (which keeps parallel `GEMINI_MODEL_MAPPING` / normalize maps).

If you're doing any of the above, this skill applies even if the user
didn't explicitly say "settings" — the surface area is wide enough that
"edit constants.py model list" or "add a new environment knob" both land
here.

## The 7+1 registration map (gemini-model example, but applies broadly)

The v1 frontend serves a settings dropdown from **the served HTML
template** (not from JS hydration — the `<option>` rows are static in
`$PROJECT_ROOT/templates/settings.html`). The dropdown's selected value
flows through JS-side `normalize()` (`$PROJECT_ROOT/frontend_v1/js/settings.js`)
and server-side `GEMINI_MODEL_MAPPING` (`$PROJECT_ROOT/constants.py`), with
five Python registration points that ALL need to know the new id:

| # | File | What to update | Why |
|---|---|---|---|
| 1 | `$PROJECT_ROOT/constants.py` | `ALLOWED_GEMINI_MODELS = [...]` | Without this, `settings_validation.py` rejects the saved value with "Invalid pre-spicy model selection" |
| 2 | `$PROJECT_ROOT/constants.py` | `GEMINI_MODEL_MAPPING = {...}` | Legacy-id normalization + canonical id (pass-through `{"new-id": "new-id"}`) |
| 3 | `$PROJECT_ROOT/constants.py` | `MODELS_WITH_CODE_EXECUTION: set[str] = {...}` | Server-side dice path checks this for code-exec+JSON single-pass support |
| 4 | `$PROJECT_ROOT/constants.py` | `MODEL_CONTEXT_WINDOW_TOKENS = {...}` | Prompt-assembly token budget |
| 5 | `$PROJECT_ROOT/constants.py` | `MODEL_MAX_OUTPUT_TOKENS = {...}` | Output cap to avoid 400s |
| 6 | `$PROJECT_ROOT/frontend_v1/js/settings.js` | `GEMINI_MODEL_MAPPING = {...}` (JS-side normalize mirrors Python) | Without this, the dropdown renders the new `<option>` but the JS normalizer silently no-ops |
| 7 | `$PROJECT_ROOT/templates/settings.html` | `<option value="new-id">Label</option>` in the `<select id="geminiModel">` | The actual rendered option in the served HTML |
| 8 | `$PROJECT_ROOT/tests/test_centralized_model_selection.py` | Regression-guard `TestXxxRegistration` class | Pins the registration so the next model-add doesn't re-omit a column |

For non-model settings (e.g. a new theme), the map collapses to (8) the
`validate(...)` addition in `settings_validation.py` + (7) the
`<select>` template row + (8) a regression test — but the principle
holds: every registration point must be enumerated before commit.

**Verified 2026-07-21 on `feat/gemini-3-5-flash-lite-3-6-flash`
worktree:** PR added 2 models × 7 places = 14 edits + 1 new regression
test class with 5 tests. Diff was 18 lines constants.py + 2 lines
settings.js + 2 lines settings.html + 60 lines test file. See the full
recipe in `web-page-screenshots` / `references/worldarchitect-ai-gemini-3-6-settings-evidence-2026-07-21.md`.

## `POST /api/settings` payload shape (the silent 400 trap)

```bash
# WRONG — returns 400 "Invalid settings data"
curl -X POST http://127.0.0.1:8081/api/settings \
  -H "Content-Type: application/json" -H "X-Test-Bypass-Auth: true" \
  -d '{"settings": {"gemini_model": "gemini-3.8-flash"}}'

# RIGHT — payload is the raw settings dict, NOT wrapped
curl -X POST http://127.0.0.1:8081/api/settings \
  -H "Content-Type: application/json" -H "X-Test-Bypass-Auth: true" \
  -d '{"gemini_model": "gemini-3.8-flash", "llm_provider": "gemini"}'
```

**Trap diagnosis:** `$PROJECT_ROOT/main.py` line ~4740+ does
`data = request.get_json(force=True)` and passes it straight to
`world_logic.update_user_settings_unified({...})`. When you wrap in
`{"settings": ...}`, the downstream code reads `.settings` and gets
`None`, then validation rejects with the unhelpful 400 "Invalid
request data" or "Invalid settings data".

**Symptom → fix:** if you POST and get `400 Invalid settings data`,
peek `$PROJECT_ROOT/main.py` for that exact line — wrapping `{"settings":...}`
is the cause ~100% of the time.

**The reverse-direction guard:** many tests want to **read** settings,
in which case `GET /api/settings` returns the settings dict directly
(no wrapper). GET is the inverse: response = raw settings.

## Local server launch — the `local.sh` exit-0 trap

`./local.sh` from the repo root (or worktree) launches Flask + MCP in
the background and **exits with code 0 once the backgrounding is
done**. The wrapper script's exit code does NOT mean "Flask is alive."
Always verify with `lsof -ti:<port>` after launch:

```bash
$ ./local.sh --force-default-port --no-log-stream &
# exits 0 in ~25s even though Flask is still booting

$ sleep 10 && lsof -ti:8081 && echo "Flask is alive"
# If empty, Flask isn't up yet (or died). Read /tmp/.../server.log.
```

For settings-evidence work you usually **don't need the MCP server** —
the settings flow (`/settings`, `/api/settings`, `/api/constants/models`)
all routes through Flask, not MCP. To bypass `local.sh` entirely:

```bash
TESTING_AUTH_BYPASS=true PORT=8081 ./vpython -m mvp_site.main serve \
  > /tmp/server.log 2>&1 &
# Then verify:
sleep 15 && lsof -ti:8081 && curl -fsS http://127.0.0.1:8081/api/constants/models | jq .
```

The `PORT` env var is the **only** knob `main.py serve` reads for the
port — there's no `--port` CLI flag (verified by reading the argparse
block at `$PROJECT_ROOT/main.py:5583`).

`parse_port_robust()` (same file, ~5620+) tolerates messy `PORT` strings
(`"ℹ️ Port 8081 in use, trying 8082...\n8082"`) so collisions don't
crash the server.

## `/es` evidence shape — required for ANY `$PROJECT_ROOT/**` change

`your-project.com/AGENTS.md` says:

> Any non-test change under `$PROJECT_ROOT/**` requires `/es` evidence
> before the work is complete. ... A past bug report does not count
> at all as a red proof; a red proof must be a fresh, real failing
> test that runs locally against the codebase ... and fails before
> the fix is applied. ... If the changed behavior is user-visible
> or changes an interactive flow, include captioned video evidence
> (`.mp4`, `.gif`, or `.cast`) tied to the PR HEAD SHA.

For settings changes the required evidence bundle is:

1. **Local Flask server** boots clean (lsof 8081, no fatal errors).
2. **`/api/constants/models`** returns 200 with the expected `DEFAULT_GEMINI_MODEL` (or equivalent default for the field you touched).
3. **`/settings`** curl response contains the new `<option>` at the template level (Layer A in `web-page-screenshots` "selectable-option proof").
4. **`./vpython` constants probe** confirms the new id is in `ALLOWED_*_MODELS`, `*_MODEL_MAPPING`, `MODELS_WITH_CODE_EXECUTION` (if relevant), and has correct context/output limits (Layer C in `web-page-screenshots`).
5. **`POST /api/settings`** with the new id returns `{"message": "Settings saved", "success": true}`.
6. **`GET /api/settings`** round-trips the new id back.
7. **Headless Chromium capture** (Playwright record_video_dir): open `/settings?test_mode=true&test_user_id=...`, wait for the dropdown to hydrate to N+1 options, select each new option, screenshot. The .webm of the flow is the captioned video.
8. **Pytest regression guard** adding the new options to existing test classes (or new `TestXxxRegistration` class).

Units that don't qualify as `/es` proof (per AGENTS.md):
- Mocked unit tests alone
- CI green checks alone
- Past bug reports
- Agent claims ("the change looks right")

For settings changes, the **mandatory** layers are 3 (served HTML), 4
(constants), 5 (POST round-trip), 7 (browser video), 8 (regression
test). Layers 1, 2, 6 are diagnostic.

## Common omission patterns (verified regressions)

When a sibling model or option was added previously, it was often
missing from one of the columns above. The grep before you change:

```bash
# Find every place that names an existing sibling (e.g. gemini-3.5-flash):
rg -n "gemini-3\.5-flash" --type py --type js --type html \
   -g '!*test*' -g '!*node_modules*' $PROJECT_ROOT/
# Each hit is a candidate location for the new model. If a column of hits
# doesn't have a matching "gemini-3.8-flash" entry, you've missed a spot.
```

The classic omissions:
- **JS normalize map** forgotten → dropdown shows the value but server silently reverts to the legacy redirect target on save.
- **`MODEL_CONTEXT_WINDOW_TOKENS` / `MODEL_MAX_OUTPUT_TOKENS`** forgotten → prompt assembly falls back to defaults; either truncates or 400s.
- **Test regression-guard** forgotten → next person adding another model has no template.
- **Legacy redirect entries** forgotten (e.g. `"gemini-2.5-flash": "gemini-3-flash-preview"`) → old saved settings resume without the new id even though it's available.
- **`DEFAULT_*_MODEL`** constant update forgotten → fresh users see the old default text in the preview until they re-save.

## Pitfalls

- **Don't trust `local.sh` exit code.** Always verify port is listening AFTER the wrapper reports done. The wrapper exits 0 once backgrounding succeeds, not once Flask is healthy.

### The 401-vs-400 diagnostic flow (verified 2026-07-24, PR #8512)

When `/api/settings` is in play, **the response code tells you which knob is wrong**:

| Curl response | What it means | Fix |
|---|---|---|
| **401** | `check_token` rejected the request — auth bypass env var not set server-side | Set `TESTING_AUTH_BYPASS=true ALLOW_TEST_AUTH_BYPASS=true` in the parent shell that spawns `local.sh`, then **restart the server** (the constants are read at import time, not per-request) |
| **400 "Invalid settings data"** | Request payload was wrapped (`{"settings": {...}}`) — drop the wrapper, send the keys directly |
| **400 "Invalid pre-spicy model selection"** | New model id wasn't added to `ALLOWED_GEMINI_MODELS` in constants.py |
| **200 but `gemini_model` reverts to default on GET** | The JS-side `normalize()` map in `frontend_v1/js/settings.js` doesn't know the new id — the server silently applies the legacy redirect. Add the entry to the JS map too. |

The `local.sh` wrapper does **not** export `TESTING_AUTH_BYPASS=true` by default. Server boots fine, `/api/constants/models` returns 200, but every POST/GET to `/api/settings` returns **401** even with `X-Test-Bypass-Auth: true` header. The `check_token` decorator in `$PROJECT_ROOT/main.py:1930` requires `TESTING_AUTH_BYPASS_MODE` AND `ALLOW_TEST_AUTH_BYPASS` to be true at server boot. **Fix:**
```bash
TESTING_AUTH_BYPASS=true ALLOW_TEST_AUTH_BYPASS=true bash local.sh --no-log-stream --force-default-port
```
Diagnostic grep before assuming the fix worked:
```bash
ps -p $(lsof -ti:8081 | head -1) -ww -o command | grep -E "TESTING_AUTH_BYPASS|ALLOW_TEST_AUTH_BYPASS"
# If empty, the env var didn't propagate to the launched subprocess
```
The constants are read at module import time, so simply exporting the var in the same shell session AFTER the server is already running does NOT take effect — kill it and restart.
- **Worktree venv shortcut.** Fresh worktrees don't have `venv/`. Don't run `python3 -m venv venv` (takes 5+ min). Symlink to an existing repo's venv:
  ```bash
  ln -sfn $HOME/worldarchitect-main-origin/venv venv
  ```
  Both venvs share the same site-packages and the worktree's `$PROJECT_ROOT/` is what gets imported, so this is safe.
- **`POST /api/settings` is raw, not wrapped.** `{"settings": {...}}` returns 400 "Invalid settings data". The right shape is the keys-and-values directly.
- **`/api/settings` requires both `X-Test-Bypass-Auth: true` AND `X-Test-User-ID: <uid>` headers** (not just the bypass header). Without `X-Test-User-ID` the 401 returns even when bypass is honored. The bypass takes the value from the header, not from a query param — `?test_mode=true&test_user_id=...` is the v1 frontend's path, not the API path.
- **`main.py serve` has no `--port` flag.** Use `PORT=8081 ./vpython -m mvp_site.main serve`.
- **Setting `WORLDAI_DEFAULT_GEMINI_MODEL`** is read once at import time by `$PROJECT_ROOT/constants.py:62`. Restart the server if you change the env var mid-session; reload is on by default but the constants module caches at import time.
- **`/api/constants/models` returns only the *default* model name, not the allowed list.** The frontend doesn't query allowed models at runtime — it reads them from the inline JS `GEMINI_MODEL_MAPPING` map. So changing `ALLOWED_GEMINI_MODELS` on the backend has zero frontend effect until you also update `settings.js`.
- **No `--save-and-reload` test harness.** Save the model, GET to round-trip, then start a new campaign — that's the integration test. The 5-step pytest class in `test_centralized_model_selection.py` covers the unit side.

## Playwright + ffmpeg captioned-video pipeline (verified 2026-07-24, PR #8512)

The AGENTS.md `/es` mandate requires captioned video evidence for user-visible changes. The full pipeline:

### 1. Install the right Chromium for the venv's Playwright wheel

The pip-installed `playwright` (e.g. 1.60.0) and the homebrew `playwright` (1.58.0) have **different chromium revisions**. Don't mix them:
```bash
# Use the venv's own playwright to install the matching chromium
$HOME/worldarchitect-main-origin/venv/bin/playwright install chromium-headless-shell
# Then run capture via the venv's python:
$HOME/worldarchitect-main-origin/venv/bin/python /tmp/pr8512_proof/capture_settings_video.py
```
Symptom of mismatch: `Executable doesn't exist at $HOME/Library/Caches/ms-playwright/chromium_headless_shell-1223/...` — the venv wants rev 1223, not the 1208 the homebrew-clone would have downloaded.

### 2. Capture script (Playwright record_video_dir)

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir="/tmp/pr8512_proof",
        record_video_size={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    page.goto(f"{BASE}/settings?test_mode=true&test_user_id=test-user-8512", wait_until="networkidle")
    page.wait_for_selector("select#geminiModel")  # wait for hydration
    opts = page.evaluate("() => Array.from(document.querySelectorAll('select#geminiModel option')).map(o => ({value: o.value, text: o.textContent.trim()}))")
    assert {"gemini-3.8-flash", "gemini-3.5-flash-lite"} <= {o["value"] for o in opts}  # MANDATORY assertion
    page.select_option("select#geminiModel", "gemini-3.8-flash")
    # ...after each select, page.screenshot(path=...)
    ctx.close()
```
The `wait_for_selector("select#geminiModel")` is critical — the dropdown is hydrated by JS after page load; without it, `page.evaluate` may return zero options.

### 3. Optional in-page banner caption (during capture)

Inject a sticky top banner via `page.evaluate` so the raw `.webm` Playwright produces is self-describing in case the ffmpeg step fails:
```python
page.evaluate("""(t) => {
    const div = document.createElement('div');
    div.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;background:#000;color:#fff;padding:8px 14px;font:600 14px/1.2 system-ui;text-align:center;';
    div.textContent = t;
    document.body.appendChild(div);
}""", "Step 2/4: dropdown contains new models")
```

### 4. Caption + stitch pipeline (PIL + ffmpeg, NOT ffmpeg drawtext)

`ffmpeg -vf drawtext=text='...'` parses colons as filter option separators and breaks on URLs or PR numbers containing `:`. **Use PIL to burn captions onto PNGs, then ffmpeg concat:**
```python
# caption_and_stitch.py
from PIL import Image, ImageDraw, ImageFont
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
for fname, big, small in STEPS:
    img = Image.open(FRAMES / fname).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0,0), (W, 90)], fill=(0,0,0))  # top banner
    draw.text((centered_x, 12), big, fill=(255,255,255), font=font)
    draw.text((centered_x, 52), small, fill=(255,212,0), font=FONT_SMALL)
    img.save(CAPTIONED / fname)
```
Then concat:
```bash
# Each frame stays 3 seconds
cat > concat_list.txt <<EOF
file 'captioned/01.png'
duration 3
file 'captioned/02.png'
duration 3
... (and duplicate the last file so ffmpeg honors its duration)
file 'captioned/04.png'
EOF
ffmpeg -y -f concat -safe 0 -i concat_list.txt \
  -vf "scale=1280:1808,setsar=1,format=yuv420p" \
  -c:v libx264 -preset fast -crf 23 -r 30 -movflags +faststart \
  pr8512_proof.mp4
```
**Critical: the height must be divisible by 16** (libx264 macroblock). A full-page screenshot of a 1280×1809 page WILL fail with `Generic error in an external library` on encode. Use `scale=1280:1808` or `pad=1280:1824`. The `format=yuv420p` filter is also required for libx264 to accept RGB-converted PNGs.

If libx264 keeps failing, fallback to mpeg4 (`-c:v mpeg4 -q:v 5`) which is more permissive about dimensions — produces a larger file but always works.

### 5. The video is not yet uploaded — that step happens in the PR body

The video file lives at `/tmp/pr8512_proof/pr8512_proof.mp4` during the session. The PR body's evidence section must reference it via a **public GitHub gist** (per the env-preferences.mdc "Visual evidence → gist (mandatory gist-first)" rule), then embed in the PR description with `![caption](https://gist.githubusercontent.com/<user>/<id>/raw/<sha>/<​filename>)`. **Do NOT commit the .mp4 to the PR branch** — the repo diff must stay reviewable.

## Rebase-and-conflict recipe for settings PRs (verified 2026-07-24, PR #8512)

Settings PRs that touch a `$PROJECT_ROOT/schemas/prompt_tool_contracts.json` hash refresh commit conflict on rebase against current `origin/main` because the prompt bytes have changed. Resolution:

1. **Re-compute the actual sha256 of the prompt file at the REBASED HEAD** (not the pre-rebase hash from the conflict hunks):
   ```bash
   python3 -c "import hashlib; print(hashlib.sha256(open('$PROJECT_ROOT/prompts/game_state_instruction.md','rb').read()).hexdigest()[:12])"
   ```
2. **Replace both the `"version"` (first 12 chars of sha256) and `"sha256"` fields** in the conflict-resolved `prompt_tool_contracts.json`. The `git checkout --theirs` route will overwrite your hand-written fix — patch the hash AGAIN after `--theirs` if you take that shortcut.
3. **Validate JSON before committing**:
   ```bash
   python3 -c "import json; json.load(open('$PROJECT_ROOT/schemas/prompt_tool_contracts.json'))"
   ```
4. **Test the prompt invariant tests** before pushing the rebase:
   ```bash
   TESTING_AUTH_BYPASS=true ./vpython -m pytest $PROJECT_ROOT/tests/test_prompts.py -q -k "game_state"
   ```

The `$PROJECT_ROOT/tests/test_prompts.py` rebase conflict is simpler — keep both test methods (the rebase-head AND the rebased-in commit each add their own test). Just remove the conflict markers and keep both `def test_game_state_prompt_carries_*` bodies intact.

Re-runnable scripts (under `scripts/`):
- `capture_settings_video.py` — argparse CLI driving Playwright headless Chromium: opens `/settings`, asserts the new `<option>` values are present, selects each, captures per-step PNGs + raw `.webm`. Usage: `python scripts/capture_settings_video.py --new-models gemini-3.8-flash,gemini-3.5-flash-lite --out /tmp/pr8512_proof`.
- `caption_and_stitch.py` — burns captions onto frames via PIL (NOT ffmpeg drawtext, which breaks on colons in PR URLs), then stitches with `ffmpeg -f concat` into a captioned MP4. Height must be divisible by 16 (`scale=1280:1808`).

The pre-existing failure on `test_victory_ripple_protocol_present_in_narrative` (asserts `"VICTORY RIPPLE PROTOCOL"` section in `narrative_system_instruction.md`) is **unrelated** to settings PRs — it was red on `origin/main` before this worktree existed. Don't fix it in the settings PR; let it land via PR #8406 or follow-up.

## Reference recipes

- **PR `feat/gemini-3-5-flash-lite-3-6-flash` (2026-07-21):** The full evidence bundle — `web-page-screenshots` / `references/worldarchitect-ai-gemini-3-6-settings-evidence-2026-07-21.md`. Includes the 7-place registration map for both new models, the 5-test regression-guard class, and the verbatim curl/Playwright output that confirms each layer of proof.
- **PR #8455 (2026-07-19):** The earlier `web-page-screenshots` "BEFORE/AFTER proof" recipe that this skill inherits from for the Playwright capture half. See `web-page-screenshots` / `references/worldarchitect-ai-wizard-mobile-revert-pr-8455.md`.

## Anti-trigger

If the user wants to change a non-settings constant (e.g. a prompt
file, a default timeout, a BQ log retention) — NOT this skill, that
falls under `convergent-bug-triage` or `wa-prod-data-query` for
data-driven questions. Settings = user-facing preference surface.
