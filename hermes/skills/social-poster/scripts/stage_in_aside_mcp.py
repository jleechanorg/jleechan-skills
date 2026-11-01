#!/usr/bin/env python3
"""
stage_in_aside_mcp.py — Stage drafts in the user's real Chrome via the Aside
HTTP MCP at 127.0.0.1:8013/mcp (the most reliable automation path when the
Aside extension bridge is alive — verified 2026-07-17).

Differs from stage_in_aside.py (which uses `aside repl` CLI — known to silently
no-op on programmatic paste per lesson #11):

  * One MCP call per platform bundles (open + locate + click [if trigger] + fill
    + verify + screenshot) into a single IIFE on the persistent MCP REPL.
    CRITICAL: every step must run on the same `page` object — split across calls
    reopens a fresh tab and resets the form, losing the pasted text.

  * Screenshots emit on a separate `SHOT_<var>:` console.log line so the
    companion `RESULT_<var>=<json>` stays small and JSON.parseable.

  * Subprocess uses Popen+communicate() — `subprocess.run(timeout=...)`
    silently drops output if the curl process writes after Python's timeout
    fires but before the process exits.

  * Auto-retries once on empty MCP response after a 2s sleep (MCP server
    degrades after ~6-8 bundled calls; recovery: `pkill -9 -f aside` or wait
    10s, restart Aside GUI, `aside account use u0`).

Verified selectors per platform (Chrome profile u0 = $USER@gmail.com,
2026-07-17):
  - HN submit (NO LOGIN): input[name='title'] + textarea[name='text']
  - Twitter compose (signed in): div[contenteditable='true'][data-testid='tweetTextarea_0']
  - Mastodon publish (signed in): first <textarea> (placeholder "What's on your mind?")
  - Reddit /r/X/submit?selftext=true (NO LOGIN): textarea[name='title'] + textarea[name='text']
  - Dev.to /new (REQUIRES LOGIN, often login_wall): input#article-form-title + textarea#article_body_markdown
  - LinkedIn /feed (REQUIRES LOGIN): div[contenteditable='true'] after "Start a post" click
  - Facebook / (REQUIRES LOGIN): div[contenteditable='true'] after "What's on your mind" click
  - Threads / (REQUIRES LOGIN): div[contenteditable='true']

CLI:
  python3 stage_in_aside_mcp.py --drafts /tmp/drafts/social-<date>/
  python3 stage_in_aside_mcp.py --drafts /tmp/drafts/social-<date>/ --only hackernews,twitter
"""
import argparse
import base64
import json
import re
import subprocess
import time
from pathlib import Path
from platform_policy import parse_platforms, selected

MCP_URL = "http://127.0.0.1:8013/mcp"


def mcp_init():
    r = subprocess.run(
        ["curl", "-sS", "-i", "-X", "POST", MCP_URL,
         "-H", "Content-Type: application/json",
         "-H", "Accept: application/json, text/event-stream",
         "-d", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {"protocolVersion": "2024-11-05",
                                       "capabilities": {},
                                       "clientInfo": {"name": "stage-mcp",
                                                      "version": "1.0"}}})],
        capture_output=True, text=True, timeout=60)
    for line in r.stdout.split("\n"):
        if line.lower().startswith("mcp-session-id"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("MCP init failed (server reachable?)")


def mcp_call(session, code, title="stage", timeout=180):
    """Drive Aside via HTTP MCP. Popen+communicate (not subprocess.run) so we
    capture output written before the process exits even on timeout."""
    body = json.dumps({"jsonrpc": "2.0", "id": int(time.time() * 1000) % 100000,
                       "method": "tools/call",
                       "params": {"name": "repl",
                                   "arguments": {"title": title, "code": code}}})
    proc = subprocess.Popen(
        ["curl", "-sS", "-X", "POST", MCP_URL,
         "-H", "Content-Type: application/json",
         "-H", "Accept: application/json, text/event-stream",
         "-H", f"mcp-session-id: {session}",
         "-d", body],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return f"TIMEOUT after {timeout}s, partial: {(out or '')[:500]}"
    output = ""
    for line in out.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if "result" in data and "content" in data.get("result", {}):
                    for c in data["result"]["content"]:
                        if c.get("type") == "text":
                            output += c.get("text", "") + "\n"
                elif "error" in data:
                    output += f"ERROR: {json.dumps(data['error'])}\n"
            except json.JSONDecodeError:
                pass
    return output


PLATFORMS = {
    "hackernews": {
        "url": "https://news.ycombinator.com/submit",
        "fields": [("input[name='title']", "title"),
                   ("textarea[name='text']", "body")],
    },
    "twitter": {
        "url": "https://x.com/compose/post",
        "fields": [("div[contenteditable='true'][data-testid='tweetTextarea_0']", "body")],
    },
    "linkedin": {
        "url": "https://www.linkedin.com/feed/",
        "fields": [("div[contenteditable='true']", "body")],
        "triggers": ["Start a post"],
    },
    "facebook": {
        "url": "https://www.facebook.com/",
        "fields": [("div[contenteditable='true']", "body")],
        "triggers": ["on your mind"],
    },
    "threads": {
        "url": "https://www.threads.net/",
        "fields": [("div[contenteditable='true']", "body")],
    },
    "mastodon": {
        "url": "https://mastodon.social/publish",
        "fields": [("textarea", "body")],
    },
    "devto": {
        "url": "https://dev.to/new",
        "fields": [("input#article-form-title", "title"),
                   ("textarea#article_body_markdown", "body")],
    },
}

REDDIT_URL = "https://old.reddit.com/r/{sub}/submit?selftext=true"


def parse_draft(text):
    """`## Title` / `## Body` section headers → (title, body) tuple."""
    m_title = re.search(r"^##\s*Title\s*\n+(.+?)(?=\n##\s|\Z)", text,
                        re.DOTALL | re.MULTILINE)
    m_body = re.search(r"^##\s*Body\s*\n+([\s\S]+?)(?=\n##\s|\Z)", text,
                       re.MULTILINE)
    title = m_title.group(1).strip() if m_title else ""
    body = m_body.group(1).strip() if m_body else text.strip()
    if not title:
        title = "Draft post"
    if not body:
        body = text.strip()
    return title, body


def stage_one(session, platform, url, fields, title_text, body_text,
              screenshot_path, triggers=None):
    """One MCP call bundles open + paste + verify + screenshot on a single
    `page` object (see lesson: split calls = lost paste)."""
    var = f"v{int(time.time() * 1000000) % 1000000}"

    triggers_js = ""
    if triggers:
        for trig in triggers:
            triggers_js += f"""
    try {{
        const {var}_trighandle = await {var}_pg.evaluateHandle((txt) => {{
            const all = Array.from(document.querySelectorAll('button, [role=button], div[contenteditable=true]'));
            for (const el of all) {{
                const t = (el.textContent || '').trim();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (t.toLowerCase().includes(txt.toLowerCase()) || aria.includes(txt.toLowerCase())) {{
                    return el;
                }}
            }}
            return null;
        }}, {json.dumps(trig)});
        if ({var}_trighandle && {var}_trighandle.asElement()) {{
            await {var}_trighandle.asElement().click();
            await sleep(2500);
        }}
    }} catch (e) {{ /* trigger click failed, continue */ }}
"""

    paste_fields_js = ""
    verify_js = ""
    for sel, kind in fields:
        text = title_text if kind == "title" else body_text
        h = abs(hash(sel)) % 10000
        paste_fields_js += f"""
    try {{
        const {var}_loc{h} = {var}_pg.locator({json.dumps(sel)}).first();
        await {var}_loc{h}.waitFor({{state:'visible', timeout:10000}});
        await {var}_loc{h}.click();
        await sleep(300);
        await {var}_loc{h}.fill({json.dumps(text)});
        await sleep(1500);
        const {var}_v{h} = await {var}_pg.evaluate((s) => {{
            const el = document.querySelector(s);
            if (!el) return 0;
            return (el.value !== undefined ? el.value.length
                    : (el.textContent || el.innerText || '').length);
        }}, {json.dumps(sel)});
        {var}_paste[{json.dumps(sel)}] = {{ ok: true, len: {var}_v{h} }};
    }} catch (e) {{
        {var}_paste[{json.dumps(sel)}] = {{ ok: false, err: e.message.slice(0, 150) }};
    }}
"""
        verify_js += f"""
    {var}_verify[{json.dumps(sel)}] = await {var}_pg.evaluate((s) => {{
        const el = document.querySelector(s);
        if (!el) return {{ ok: false, len: 0, val: '' }};
        const v = el.value !== undefined ? el.value
                  : (el.textContent || el.innerText || '');
        return {{ ok: true, len: v.length, val: v.slice(0, 80) }};
    }}, {json.dumps(sel)});
"""

    code = f"""
await (async () => {{
    const {var}_result = {{}};
    const {var}_pg = await openTab({json.dumps(url)});
    await {var}_pg.waitForLoadState('domcontentloaded');
    await sleep(4500);
    {var}_result.open = await {var}_pg.evaluate(() => ({{
        url: location.href,
        title: document.title,
        login_prompt: /log in|sign in|welcome back|please log in/i.test(document.body.innerText),
    }}));
    if ({var}_result.open.login_prompt) {{
        console.log('RESULT_{var}=' + JSON.stringify({{status:'login_wall', open: {var}_result.open}}));
        return;
    }}
    {triggers_js}
    const {var}_paste = {{}};
    {paste_fields_js}
    const {var}_verify = {{}};
    {verify_js}
    {var}_result.paste = {var}_paste;
    {var}_result.verify = {var}_verify;
    const {var}_ss = await {var}_pg.screenshot();
    console.log('SHOT_{var}:' + {var}_ss.toString('base64'));
    console.log('RESULT_{var}=' + JSON.stringify({var}_result));
}})();
"""
    out = mcp_call(session, code, title=f"stage {platform}", timeout=180)

    # Retry once on empty response (MCP server occasionally blanks)
    if not out.strip():
        time.sleep(2)
        print(f"   (retrying {platform} after empty response)", flush=True)
        out = mcp_call(session, code, title=f"stage {platform} (retry)",
                       timeout=180)

    # Save screenshot from SHOT_<var>: (base64 is too large to live inside JSON)
    shot_m = re.search(rf"SHOT_{var}:([A-Za-z0-9+/=]+)", out)
    if shot_m:
        try:
            data = base64.b64decode(shot_m.group(1))
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(data)
        except Exception:
            pass

    m = re.search(rf"RESULT_{var}=(.+)$", out, re.MULTILINE | re.DOTALL)
    if not m:
        return {"platform": platform, "status": "no_result", "raw": out[:1000],
                "raw_len": len(out)}
    raw = m.group(1)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        try:
            result = json.loads(raw[:raw.rindex("}") + 1])
        except Exception:
            return {"platform": platform, "status": "parse_failed",
                    "raw": raw[:500]}

    open_info = result.get("open", {})
    if open_info.get("login_prompt"):
        result["status"] = "login_wall"
    else:
        verify = result.get("verify", {})
        actual = sum(v.get("len", 0)
                     for v in verify.values()
                     if isinstance(v, dict) and v.get("ok"))
        expected = sum(len(title_text if kind == "title" else body_text)
                       for _, kind in fields)
        threshold = max(1, int(expected * 0.7))
        result["actual_chars"] = actual
        result["expected_chars"] = expected
        if actual >= threshold:
            result["status"] = "staged"
        else:
            result["status"] = "paste_failed"
            result["note"] = (f"expected {expected}, got {actual} "
                              f"(paste: {json.dumps(result.get('paste', {}))[:200]})")
    result["platform"] = platform
    result["compose_url"] = url
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drafts", required=True,
                        help="dir with one .md per platform")
    parser.add_argument("--only", help="comma-separated platform allowlist")
    args = parser.parse_args()

    drafts_dir = Path(args.drafts)
    shot_dir = drafts_dir / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    allow = parse_platforms(args.only)

    print("→ Init MCP session...", flush=True)
    session = mcp_init()
    print(f"   session-id: {session[:8]}\n", flush=True)

    targets = []
    for name, recipe in PLATFORMS.items():
        if not selected(name, allow):
            continue
        targets.append(("platform", name, recipe))
    for md in sorted(drafts_dir.glob("reddit_*.md")):
        key = md.stem
        sub = key.removeprefix("reddit_")
        if not selected(key, allow):
            continue
        targets.append(("reddit", sub, {"sub": sub}))

    results = []
    for i, (kind, key, recipe) in enumerate(targets):
        if kind == "platform":
            name = key
            md = drafts_dir / f"{name}.md"
            if not md.exists():
                continue
            title, body = parse_draft(md.read_text())
            print(f"→ {name}", flush=True)
            r = stage_one(session, name, recipe["url"], recipe["fields"],
                          title, body, shot_dir / f"{name}.png",
                          triggers=recipe.get("triggers"))
        else:
            sub = key
            name = f"reddit_{sub.lower()}"
            md = drafts_dir / f"{name}.md"
            if not md.exists():
                continue
            title, body = parse_draft(md.read_text())
            url = REDDIT_URL.format(sub=sub)
            fields = [("textarea[name='title']", "title"),
                      ("textarea[name='text']", "body")]
            print(f"→ {name}", flush=True)
            r = stage_one(session, name, url, fields, title, body,
                          shot_dir / f"{name}.png")
        results.append(r)
        print(f"   {r['status']} "
              f"({r.get('actual_chars', 0)}/{r.get('expected_chars', 0)} chars)",
              flush=True)
        # Throttle between calls to avoid MCP degradation
        if i < len(targets) - 1:
            time.sleep(3)

    out_path = drafts_dir / "staged_mcp.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n→ Results: {out_path}")

    counts = {}
    for r in results:
        s = r.get("status", "failed")
        counts[s] = counts.get(s, 0) + 1
    print(f"\n✓ staged: {counts.get('staged', 0)} "
          f"| ⚠ paste_failed: {counts.get('paste_failed', 0)} "
          f"| ⚠ login_wall: {counts.get('login_wall', 0)} "
          f"| ✗ failed: "
          f"{counts.get('failed', 0) + counts.get('no_result', 0) + counts.get('parse_failed', 0)}")


if __name__ == "__main__":
    main()
