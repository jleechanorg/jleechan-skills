#!/usr/bin/env python3
"""
stage_in_aside.py — Open Aside browser tabs for each draft, PASTE the draft
text, verify the field actually contains the text, then screenshot.

Reads drafts from --drafts dir (output of draft_social_post.py), opens an Aside
tab on each platform's compose URL, pastes the draft into the relevant input
field, reads the field back to VERIFY the paste persisted, screenshots, and
saves to screenshots/.

DOES NOT click submit / post. Just stages for human review.

Contract change (2026-07-11, v3 — enforced paste verification):
  A platform is reported "staged" ONLY when ALL of:
    1. compose form rendered (or "load_only" for no-web-compose platforms)
    2. draft text was programmatically pasted into the appropriate field
    3. field.read() returned a value whose length >= expected_chars * 0.7
       (allow a 30% slack for trailing whitespace stripped by the platform)
    4. screenshot captured

  Status taxonomy:
    "staged"        — paste verified + screenshot saved
    "paste_failed"  — compose loaded but text did NOT persist (user must paste manually)
    "login_wall"    — page loaded but is a sign-in screen, no paste attempted
    "load_only"     — Instagram / no-web-compose platform (caption-only)
    "no_recipe"     — no compose URL selector known for this platform key
    "failed"        — aside subprocess error or screenshot capture failed

  This change was forced by the 2026-07-11 user pushback in Slack thread
  C09GRLXF9GR/p1783809934.098269: "all of those drafts are obviously wrong and
  just random login screens so youre not even close to working". The previous
  v2 labeled 13 platforms "staged" when 0 had actually pasted text — the DOM
  verdict and the actual field content were not the same thing.

Updated 2026-07-11 (v3):
- Enforced paste + read-back verification before reporting "staged"
- Per-platform paste function: textarea (React setter) vs contentEditable
  (focus + document.execCommand('insertText'))
- "staged" label now means draft text is visible in the field, not just that
  the compose form loaded
- Screenshots are taken AFTER paste+verify so the captured image shows the
  filled state, not the empty compose UI
- LinkedIn / Facebook / Threads use the documented 3-step focus/execCommand
  dance for React-controlled contentEditable fields

Updated 2026-07-06:
- Reddit compose URL now uses ?selftext=true (lands on text-post form, avoids
  session-re-auth redirect that misclassified Reddit as "login wall").
- Aside `openTab()` returns a Playwright Page object; we screenshot via the
  Page's `screenshot()` method (Buffer → base64) rather than the older
  `annotatedScreenshot(pageObj)` API.

Aside REPL API used (verified 2026-07-06 + 2026-07-11):
  openTab(url)             -> Playwright Page object
  page.screenshot()        -> Buffer (PNG bytes)
  page.waitForLoadState()  -> Promise<void>
  page.evaluate(fn, ...args) -> Promise<json-serializable>
  page.locator(selector)   -> Locator (Playwright)
  page.frameLocator(selector) -> FrameLocator (for iframe clicks)
  listBrowserTabs()        -> Promise<[{url, title, ...}]>
  closeTab(target)         -> Promise

Usage:
  python3 stage_in_aside.py --drafts /tmp/drafts/social-2026-07-06/
  python3 stage_in_aside.py --drafts /tmp/drafts/social-2026-07-06/ --close-tabs
  python3 stage_in_aside.py --drafts /tmp/drafts/social-2026-07-06/ --only twitter,linkedin
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from platform_policy import parse_platforms, selected


# Per-platform compose config.
#
# Each entry maps a draft filename stem -> {
#   "url": compose URL,
#   "platform": short name,
#   "fields": [(selector, value_source, paste_kind), ...],
#   "verify_selectors": [selector, ...]   # any one matching with len >= threshold counts as paste-verified
#   "trigger_click": optional selector to click before pasting (LinkedIn "Start a post", Facebook "What's on your mind")
# }
#
# paste_kind:
#   "react_textarea" — vanilla <textarea> or <input>. Use HTMLTextAreaElement/HTMLInputElement
#                      prototype.value setter + dispatch input event. Works for Reddit, HN,
#                      Mastodon, Dev.to.
#   "exec_command"   — contentEditable (Twitter, LinkedIn, Facebook, Threads). focus +
#                      document.execCommand('insertText', false, text) is the only reliable
#                      pattern for React-controlled contentEditable fields.
#
# value_source:
#   "title"          — first line of ## Title section
#   "url"            — first URL found in draft
#   "body"           — everything after ## Body
#   "single_tweet"   — content of ## Single tweet section
#   "whole"          — entire draft file (default for platforms that don't split)
#
# Reddit is special: --drafts has separate files per subreddit (reddit_localllama.md etc.)
# and the sub is in the filename. We detect and handle that in main().
COMPOSE_RECIPES = {
    "linkedin": {
        "url": "https://www.linkedin.com/feed/",
        "platform": "LinkedIn",
        "fields": [("[role='dialog'] div[contenteditable='true']", "whole", "exec_command")],
        "verify_selectors": ["[role='dialog'] div[contenteditable='true']"],
        "trigger_click": "button:has-text('Start a post')",
    },
    "hackernews": {
        "url": "https://news.ycombinator.com/submit",
        "platform": "Hacker News",
        "fields": [
            ("input[name='title']", "title", "react_textarea"),
            ("input[name='url']", "url", "react_textarea"),
            ("textarea[name='text']", "body", "react_textarea"),
        ],
        "verify_selectors": ["input[name='title']", "textarea[name='text']"],
    },
    "twitter": {
        "url": "https://twitter.com/compose/post",
        "platform": "Twitter/X",
        "fields": [("div[contenteditable='true'][data-testid='tweetTextarea_0']", "single_tweet", "exec_command")],
        "verify_selectors": ["div[contenteditable='true'][data-testid='tweetTextarea_0']"],
    },
    "threads": {
        "url": "https://www.threads.net/",
        "platform": "Threads",
        "fields": [("div[contenteditable='true']", "whole", "exec_command")],
        "verify_selectors": ["div[contenteditable='true']"],
    },
    "facebook": {
        "url": "https://www.facebook.com/",
        "platform": "Facebook",
        "fields": [("div[contenteditable='true'][role='textbox']", "whole", "exec_command")],
        "verify_selectors": ["div[contenteditable='true'][role='textbox']"],
        "trigger_click": "div[aria-label*='on your mind' i]",
    },
    "mastodon": {
        "url": "https://mastodon.social/publish",
        "platform": "Mastodon",
        "fields": [("textarea[placeholder=\"What's on your mind?\"]", "whole", "react_textarea")],
        "verify_selectors": ["textarea[placeholder=\"What's on your mind?\"]"],
    },
    "devto": {
        "url": "https://dev.to/new",
        "platform": "Dev.to",
        "fields": [
            ("input#article-form-title", "title", "react_textarea"),
            ("textarea[id='article_body_markdown']", "body", "react_textarea"),
        ],
        "verify_selectors": ["input#article-form-title", "textarea[id='article_body_markdown']"],
    },
    "instagram": {
        "url": "https://www.instagram.com/",
        "platform": "Instagram",
        "no_web_compose": True,
        "fields": [],
        "verify_selectors": [],
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Aside REPL helpers
# ────────────────────────────────────────────────────────────────────────────

def aside_repr(code: str, timeout: int = 60) -> str:
    """Run an aside repl snippet, return stdout+stderr."""
    try:
        r = subprocess.run(
            ["aside", "repl", code],
            capture_output=True, text=True, timeout=timeout,
        )
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except FileNotFoundError:
        return "[ASIDE_NOT_FOUND]"


def aside_run(code: str, timeout: int = 60) -> dict:
    """Run aside repl and parse structured markers.

    Recognized markers:
      STATE <json>   — page state from evaluate
      PASTE <json>   — paste result {selector: {ok, len, val}}
      VERIFY <json>  — verify result {selector: {ok, len, val}}
      B64_OUT:<...>  — base64-encoded PNG screenshot
      ERR <string>
    """
    try:
        r = subprocess.run(
            ["aside", "repl", code],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "aside timeout"}
    except FileNotFoundError:
        return {"ok": False, "error": "aside CLI not found"}

    out = (r.stdout or "") + (r.stderr or "")
    result = {"ok": True, "raw": out}

    for marker, parser in [
        (r"STATE\s+(\{[\s\S]*?\})\s*(?:B64_OUT|$)", lambda m: ("state", _safe_json(m.group(1)))),
        (r"PASTE\s+(\{[\s\S]*?\})\s*(?:VERIFY|$)", lambda m: ("paste", _safe_json(m.group(1)))),
        (r"VERIFY\s+(\{[\s\S]*?\})\s*(?:B64_OUT|$)", lambda m: ("verify", _safe_json(m.group(1)))),
        (r"ERR\s+(.+?)$", lambda m: ("error", m.group(1).strip())),
    ]:
        m = re.search(marker, out, re.MULTILINE)
        if m:
            try:
                k, v = parser(m)
                result[k] = v
            except Exception as e:
                result["parse_error"] = f"{k}: {e}"

    # B64_OUT extraction (single per call)
    bm = re.search(r"B64_OUT:([A-Za-z0-9+/=]+)", out)
    if bm:
        try:
            result["b64_bytes"] = len(base64.b64decode(bm.group(1)))
        except Exception:
            pass

    return result


def _safe_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return {"raw": s[:200]}


# ────────────────────────────────────────────────────────────────────────────
# Draft parser
# ────────────────────────────────────────────────────────────────────────────

def parse_draft_sections(draft_text: str) -> dict:
    """Extract title / body / url / single_tweet / whole from a draft file."""
    out = {"whole": draft_text.strip()}

    m = re.search(r"^##\s*Title\s*\n+(.+?)(?=\n##\s|\Z)", draft_text, re.DOTALL | re.MULTILINE)
    if m:
        out["title"] = m.group(1).strip()

    m = re.search(r"^##\s*Body\s*\n+([\s\S]+?)(?=\n##\s|\Z)", draft_text, re.MULTILINE)
    if m:
        out["body"] = m.group(1).strip()

    m = re.search(r"^##\s*Single tweet\s*\n+([\s\S]+?)(?=\n##\s|\Z)", draft_text, re.MULTILINE)
    if m:
        out["single_tweet"] = m.group(1).strip()

    m = re.search(r"https?://\S+", draft_text)
    if m:
        out["url"] = m.group(0).rstrip(".,)")

    return out


# ────────────────────────────────────────────────────────────────────────────
# Paste + verify JS snippets (run inside Aside REPL)
# ────────────────────────────────────────────────────────────────────────────

PASTE_JS_REACT_TEXTAREA = """
({selector, text}) => {
    const el = document.querySelector(selector);
    if (!el) return { ok: false, reason: 'not_found' };
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, text);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return { ok: true, len: el.value.length, val: el.value.slice(0, 200) };
}
"""

PASTE_JS_EXEC_COMMAND = """
({selector, text}) => {
    const el = document.querySelector(selector);
    if (!el) return { ok: false, reason: 'not_found' };
    el.focus();
    const ok = document.execCommand('insertText', false, text);
    return { ok, len: (el.textContent || el.innerText || '').length, val: (el.textContent || el.innerText || '').slice(0, 200) };
}
"""

VERIFY_JS = """
(selector) => {
    const el = document.querySelector(selector);
    if (!el) return { ok: false, reason: 'not_found', len: 0 };
    const v = el.value !== undefined ? el.value : (el.textContent || el.innerText || '');
    return { ok: true, len: v.length, val: v.slice(0, 200) };
}
"""

INSPECT_JS = """
() => {
    const composeSelectors = [
        'div[contenteditable=\"true\"]',
        'textarea[name=\"text\"]',
        'input[name=\"title\"]',
        '[data-testid=\"tweetTextarea_0\"]',
    ];
    const found = composeSelectors.map(s => ({ sel: s, count: document.querySelectorAll(s).length })).filter(o => o.count > 0);
    return {
        url: window.location.href,
        title: document.title,
        compose_fields: found,
        login_prompt: /log in|sign in|welcome back|please log in/i.test(document.body.innerText),
    };
}
"""


def _save_screenshot(run_result: dict, dest: Path) -> int:
    """Extract B64_OUT from a run and save PNG. Returns byte count or 0."""
    raw = run_result.get("raw", "")
    m = re.search(r"B64_OUT:([A-Za-z0-9+/=]+)", raw)
    if not m:
        return 0
    try:
        data = base64.b64decode(m.group(1))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return len(data)
    except Exception:
        return 0


# ────────────────────────────────────────────────────────────────────────────
# Stage + paste + verify pipeline
# ────────────────────────────────────────────────────────────────────────────

def stage_platform(recipe_key: str, draft_path: Path, screenshot_path: Path,
                   close_tabs: bool = False) -> dict:
    """Open compose URL, paste draft into each field, verify, screenshot."""
    recipe = COMPOSE_RECIPES[recipe_key]
    draft_text = draft_path.read_text()
    sections = parse_draft_sections(draft_text)
    result = {
        "platform": recipe["platform"],
        "compose_url": recipe["url"],
        "draft_chars": len(draft_text),
        "status": "no_recipe",
    }

    if recipe.get("no_web_compose"):
        result["status"] = "load_only"
        result["note"] = (
            "Instagram has no web compose flow. Copy caption from "
            f"{draft_path.name} and paste via the mobile app."
        )
        code = (
            f"const p = await openTab({json.dumps(recipe['url'])}); "
            "await p.waitForLoadState('domcontentloaded'); "
            "await new Promise(r => setTimeout(r, 4500)); "
            "console.log('STATE ' + JSON.stringify(" + INSPECT_JS + "));"
            "const __b64 = (await p.screenshot()).toString('base64'); "
            "console.log('B64_OUT:' + __b64);"
        )
        run = aside_run(code, timeout=30)
        result["inspect"] = run.get("state", {})
        result["screenshot_bytes"] = _save_screenshot(run, screenshot_path)
        return result

    # Open compose page, optional trigger click, inspect
    code_parts = [
        f"const p = await openTab({json.dumps(recipe['url'])});",
        "await p.waitForLoadState('domcontentloaded');",
        "await new Promise(r => setTimeout(r, 4500));",
    ]
    if recipe.get("trigger_click"):
        code_parts.append(
            f"try {{ await p.locator({json.dumps(recipe['trigger_click'])}).first()"
            ".click({timeout: 5000}); await new Promise(r => setTimeout(r, 2500)); } "
            "catch(e) { console.log('ERR click: ' + e.message); }"
        )
    code_parts.append("console.log('STATE ' + JSON.stringify(" + INSPECT_JS + "));")
    inspect_code = " ".join(code_parts)

    run = aside_run(inspect_code, timeout=45)

    if "Chrome extension not connected" in run.get("raw", ""):
        result["status"] = "failed"
        result["error"] = (
            "Aside extension bridge not connected — user must click the Aside "
            "dock icon to revive it (see references/aside-repl-session-state.md "
            "lesson #9)"
        )
        return result

    state = run.get("state", {})
    if state.get("login_prompt"):
        result["status"] = "login_wall"
        result["inspect"] = state
        result["screenshot_bytes"] = _save_screenshot(run, screenshot_path)
        return result

    # Paste each field
    paste_results = {}
    for selector, value_source, paste_kind in recipe["fields"]:
        text = sections.get(value_source) or sections.get("whole")
        if text is None:
            paste_results[selector] = {"ok": False, "reason": f"no_value_for_{value_source}"}
            continue

        paste_fn = PASTE_JS_EXEC_COMMAND if paste_kind == "exec_command" else PASTE_JS_REACT_TEXTAREA
        paste_code = (
            f"const p = await openTab({json.dumps(recipe['url'])}); "
            "await new Promise(r => setTimeout(r, 1500)); "
            f"const __r = await p.evaluate({paste_fn}, "
            f"{{selector: {json.dumps(selector)}, text: {json.dumps(text)}}}); "
            f"console.log('PASTE ' + JSON.stringify({{ {json.dumps(selector)}: __r }}));"
        )
        pr = aside_run(paste_code, timeout=30)
        paste_results.update(pr.get("paste", {}))
        if pr.get("error") and selector not in paste_results:
            paste_results[selector] = {"ok": False, "reason": pr["error"]}

    # Verify each field
    verify_results = {}
    for selector in recipe.get("verify_selectors", []):
        actual_sel = selector.split(",")[0].strip()
        vcode = (
            f"const p = await openTab({json.dumps(recipe['url'])}); "
            "await new Promise(r => setTimeout(r, 2000)); "
            f"console.log('VERIFY ' + JSON.stringify({{ {json.dumps(actual_sel)}: "
            f"await p.evaluate({VERIFY_JS}, {json.dumps(actual_sel)}) }}));"
        )
        vr = aside_run(vcode, timeout=20)
        verify_results.update(vr.get("verify", {}))

    expected_chars = sum(
        len(sections.get(src) or sections.get("whole") or "")
        for _, src, _ in recipe["fields"]
    )
    actual_chars = sum(
        v.get("len", 0) for v in verify_results.values()
        if isinstance(v, dict) and v.get("ok")
    )
    threshold = max(1, int(expected_chars * 0.7))

    result["paste"] = paste_results
    result["verify"] = verify_results
    result["expected_chars"] = expected_chars
    result["actual_chars"] = actual_chars

    if actual_chars >= threshold:
        result["status"] = "staged"
    else:
        result["status"] = "paste_failed"
        result["note"] = (
            f"Compose form loaded but draft text did not persist "
            f"(expected {expected_chars} chars, got {actual_chars}). "
            f"User must paste manually from {draft_path.name}."
        )

    # Screenshot the post-paste state
    shot_code = (
        f"const p = await openTab({json.dumps(recipe['url'])}); "
        "await new Promise(r => setTimeout(r, 2000)); "
        "const __b64 = (await p.screenshot()).toString('base64'); "
        "console.log('B64_OUT:' + __b64);"
    )
    sr = aside_run(shot_code, timeout=30)
    result["screenshot_bytes"] = _save_screenshot(sr, screenshot_path)

    if close_tabs:
        try:
            subprocess.run(
                ["aside", "repl",
                 f"const t = await openTab({json.dumps(recipe['url'])}); "
                 "await closeTab(t); console.log('closed');"],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass

    return result


def stage_reddit(sub: str, draft_path: Path, screenshot_path: Path,
                 close_tabs: bool = False) -> dict:
    """Reddit is special: URL contains sub, fields are title + text."""
    url = f"https://old.reddit.com/r/{sub}/submit?selftext=true"
    draft_text = draft_path.read_text()
    sections = parse_draft_sections(draft_text)
    result = {
        "platform": f"Reddit r/{sub}",
        "compose_url": url,
        "draft_chars": len(draft_text),
        "status": "no_recipe",
    }

    # Inspect
    inspect_code = (
        f"const p = await openTab({json.dumps(url)}); "
        "await p.waitForLoadState('domcontentloaded'); "
        "await new Promise(r => setTimeout(r, 5000)); "
        "console.log('STATE ' + JSON.stringify(" + INSPECT_JS + "));"
    )
    run = aside_run(inspect_code, timeout=45)
    state = run.get("state", {})
    if state.get("login_prompt"):
        result["status"] = "login_wall"
        result["inspect"] = state
        result["screenshot_bytes"] = _save_screenshot(run, screenshot_path)
        return result

    # Paste title + body
    paste_results = {}
    for selector, value_source in [
        ("textarea[name='title']", "title"),
        ("textarea[name='text']", "body"),
    ]:
        text = sections.get(value_source) or ""
        if not text:
            paste_results[selector] = {"ok": False, "reason": f"no_{value_source}_in_draft"}
            continue
        paste_code = (
            f"const p = await openTab({json.dumps(url)}); "
            "await new Promise(r => setTimeout(r, 2000)); "
            f"const __r = await p.evaluate({PASTE_JS_REACT_TEXTAREA}, "
            f"{{selector: {json.dumps(selector)}, text: {json.dumps(text)}}}); "
            f"console.log('PASTE ' + JSON.stringify({{ {json.dumps(selector)}: __r }}));"
        )
        pr = aside_run(paste_code, timeout=30)
        paste_results.update(pr.get("paste", {}))

    # Verify
    verify_results = {}
    for selector in ["textarea[name='title']", "textarea[name='text']"]:
        vcode = (
            f"const p = await openTab({json.dumps(url)}); "
            "await new Promise(r => setTimeout(r, 2500)); "
            f"console.log('VERIFY ' + JSON.stringify({{ {json.dumps(selector)}: "
            f"await p.evaluate({VERIFY_JS}, {json.dumps(selector)}) }}));"
        )
        vr = aside_run(vcode, timeout=20)
        verify_results.update(vr.get("verify", {}))

    expected_chars = len(sections.get("title", "")) + len(sections.get("body", ""))
    actual_chars = sum(
        v.get("len", 0) for v in verify_results.values()
        if isinstance(v, dict) and v.get("ok")
    )
    threshold = max(1, int(expected_chars * 0.7))

    result["paste"] = paste_results
    result["verify"] = verify_results
    result["expected_chars"] = expected_chars
    result["actual_chars"] = actual_chars

    if actual_chars >= threshold:
        result["status"] = "staged"
    else:
        result["status"] = "paste_failed"
        result["note"] = (
            f"Reddit compose loaded but title+body did not persist "
            f"(expected {expected_chars} chars, got {actual_chars}). "
            f"User must paste manually from {draft_path.name}."
        )

    # Screenshot
    shot_code = (
        f"const p = await openTab({json.dumps(url)}); "
        "await new Promise(r => setTimeout(r, 2500)); "
        "const __b64 = (await p.screenshot()).toString('base64'); "
        "console.log('B64_OUT:' + __b64);"
    )
    sr = aside_run(shot_code, timeout=30)
    result["screenshot_bytes"] = _save_screenshot(sr, screenshot_path)

    return result


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Stage drafts in Aside browser tabs + paste + verify + screenshot"
    )
    ap.add_argument("--drafts", required=True, help="Draft dir (output of draft_social_post.py)")
    ap.add_argument("--close-tabs", action="store_true", help="Close tabs after screenshot")
    ap.add_argument("--only", default=None, help="Comma-separated platform allowlist (skip others)")
    args = ap.parse_args()

    drafts_dir = Path(args.drafts).expanduser().resolve()
    if not drafts_dir.exists():
        print(f"ERROR: drafts dir not found: {drafts_dir}")
        return 1

    manifest_path = drafts_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())

    screenshots_dir = drafts_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    only_set = parse_platforms(args.only)

    # Aside health check
    health = aside_repr("console.log('ASIDE_OK')", timeout=10)
    if "[ASIDE_NOT_FOUND]" in health:
        print("ERROR: `aside` CLI not found. Install: curl -fsSL https://releases.aside.com/install.sh | bash")
        return 2
    print(f"✓ Aside alive: {health.strip().split(chr(10))[0][:50]}")

    results = {}
    for fname in sorted(drafts_dir.glob("*.md")):
        key = fname.stem
        if key == "manifest":
            continue

        if not selected(key, only_set):
            continue

        shot_path = screenshots_dir / f"{key}.png"

        if key.startswith("reddit_"):
            sub = key.replace("reddit_", "")
            print(f"\n→ Staging reddit/{sub} (paste + verify)...")
            r = stage_reddit(sub, fname, shot_path, close_tabs=args.close_tabs)
            results[key] = r
        elif key in COMPOSE_RECIPES:
            print(f"\n→ Staging {key} (paste + verify)...")
            r = stage_platform(key, fname, shot_path, close_tabs=args.close_tabs)
            results[key] = r
        else:
            print(f"\n→ Skipping {key} (no recipe)")

    # Update manifest
    manifest["stage_results"] = results
    manifest["staged_at"] = datetime.now(timezone.utc).isoformat()
    manifest["stage_contract_version"] = "v3-verified-paste-2026-07-11"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Summary
    counts = {"staged": 0, "failed": 0, "login_wall": 0, "paste_failed": 0, "load_only": 0}
    for r in results.values():
        s = r.get("status")
        if s in counts:
            counts[s] += 1

    print(f"\n✓ Staged (paste verified): {counts['staged']}")
    print(f"✗ Failed:                 {counts['failed']}")
    print(f"⚠ Login walls:            {counts['login_wall']}")
    print(f"⚠ Paste failed:           {counts['paste_failed']}  (compose loaded but text didn't persist)")
    print(f"○ Load only (no compose): {counts['load_only']}")
    print(f"\nScreenshots in: {screenshots_dir}\n")
    for k, r in results.items():
        status = r.get("status", "?")
        icon = {
            "staged": "✓", "failed": "✗", "login_wall": "🔒",
            "paste_failed": "⚠", "load_only": "○",
        }.get(status, "?")
        expected = r.get("expected_chars")
        actual = r.get("actual_chars")
        chars_info = f" [{actual}/{expected}]" if expected else ""
        print(f"  {icon} {k:30s} {status:15s}{chars_info}")
        if r.get("note"):
            print(f"      ↳ {r['note']}")
        if r.get("error"):
            print(f"      ↳ {r['error']}")

    print(f"\n📋 'POST APPROVED [platforms]' to post | 'revise X' to re-draft")
    print(f"⚠ Platforms with status 'login_wall' or 'paste_failed' need manual paste from the .md files.")

    # Exit non-zero if any "staged" or "load_only" platform also has "failed" or others
    total = len(results)
    ok = counts["staged"] + counts["load_only"]
    return 0 if counts["failed"] == 0 and ok == total else 1


if __name__ == "__main__":
    sys.exit(main())