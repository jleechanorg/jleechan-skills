#!/usr/bin/env python3
"""
post_approved.py — Gated publisher. ONLY runs after POST APPROVED token is present.

Without --approval-token, exits code 2 with "BLOCKED — no POST APPROVED token".
With --approval-token "POST APPROVED", opens the staged Aside tabs and clicks
submit on each. Writes posted.json with results.

Per-platform allowlist supported: --platforms linkedin,hackernews posts only those.

Usage:
  # Dry-run (safe — no clicks)
  python3 post_approved.py --drafts /tmp/drafts/social-2026-07-06/

  # Actually post
  python3 post_approved.py --drafts /tmp/drafts/social-2026-07-06/ \\
      --approval-token "POST APPROVED" \\
      --publish-request --platforms reddit,twitter
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from platform_policy import intersect_platforms, parse_platforms, selected


def check_approval(token: str | None) -> None:
    """
    Hard gate. Token must be the literal string 'POST APPROVED' (case-insensitive).
    Raises SystemExit(2) if missing or wrong.
    """
    if not token:
        print("=" * 60)
        print("BLOCKED — no POST APPROVED token.")
        print("This script requires verified user authorization and an internal approval token.")
        print("Add --approval-token 'POST APPROVED' to actually post.")
        print("Without it, publishing is blocked.")
        print("=" * 60)
        raise SystemExit(2)
    if token.strip().lower() != "post approved":
        print(f"BLOCKED — approval token '{token}' != 'POST APPROVED' (case-insensitive).")
        raise SystemExit(2)


def parse_approval_platforms(token: str) -> tuple[str, list[str] | None]:
    """
    Parse 'POST APPROVED' or 'POST APPROVED linkedin,hackernews' form.
    Returns ('POST APPROVED', platforms_list_or_None).
    """
    parts = token.strip().split(maxsplit=2)
    if len(parts) >= 2 and parts[0].lower() == "post" and parts[1].lower() == "approved":
        # 3rd field is comma-separated platforms
        if len(parts) == 3:
            plats = [p.strip() for p in parts[2].split(",") if p.strip()]
            return ("POST APPROVED", plats)
        return ("POST APPROVED", None)
    return ("INVALID", None)


def click_submit_via_aside(platform_key: str, compose_url: str) -> dict:
    """
    Open the staged tab and click submit.
    This is the most platform-fragile part — different sites have different
    submit-button selectors. We use a heuristic: find any button with text
    matching {Post, Submit, Publish, Tweet, Share, Submit link}.
    """
    code = f"""
const p = await openTab({json.dumps(compose_url)});
await new Promise(r=>setTimeout(r,2500));
const s = await snapshot(p, {{interactive: true}});
// Find submit button by label
const submitLabels = ['Post', 'Submit', 'Publish', 'Tweet', 'Share', 'Submit link', 'Post thread'];
let submitRef = null;
for (const el of (s.refs || [])) {{
  const t = (el.text || el.name || '').trim();
  if (submitLabels.some(l => t.includes(l))) {{ submitRef = el.ref; break; }}
}}
if (submitRef) {{
  await click(submitRef);
  await new Promise(r=>setTimeout(r,3000));
  const finalUrl = (await snapshot(p)).url || (await pageInfo(p)).url;
  console.log('POSTED:' + p + ':' + finalUrl);
}} else {{
  console.log('NO_SUBMIT_BUTTON:' + p);
}}
"""
    try:
        r = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + (r.stderr or "")
        if "POSTED:" in out:
            url = out.split("POSTED:")[1].split("\n")[0]
            return {"status": "posted", "url": url, "platform": platform_key}
        elif "NO_SUBMIT_BUTTON" in out:
            return {"status": "no_submit_button_found", "platform": platform_key,
                    "note": "Aside couldn't find the submit button — manual click required"}
        return {"status": "unknown", "platform": platform_key, "aside_output": out}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "platform": platform_key}
    except FileNotFoundError:
        return {"status": "aside_not_found", "platform": platform_key}


def main():
    ap = argparse.ArgumentParser(description="Gated publisher — requires POST APPROVED token")
    ap.add_argument("--drafts", required=True, help="Draft directory")
    ap.add_argument("--approval-token", default="", help="Must be 'POST APPROVED' or 'POST APPROVED platform1,platform2'")
    ap.add_argument("--publish-request", action="store_true",
                    help="Operator attests latest user request explicitly authorizes publishing reviewed content")
    ap.add_argument("--platforms", default=None, help="Comma-separated platform allowlist (narrows token allowlist; default reddit,twitter)")
    args = ap.parse_args()

    # Hard gate
    normalized, token_plats = parse_approval_platforms(args.approval_token)
    check_approval(normalized if args.approval_token else "")

    # Intersect both directions: reddit ∩ reddit_example is reddit_example.
    # An explicitly empty token scope must not fall back to default permission.
    try:
        allow = parse_platforms(args.platforms if args.platforms is not None
                                else (",".join(token_plats) if token_plats is not None else None))
        if token_plats is not None:
            allow = intersect_platforms(allow, parse_platforms(",".join(token_plats)))
        if not allow:
            raise ValueError("Token and flag platform selections have no destinations in common")
    except ValueError as exc:
        ap.error(str(exc))

    drafts_dir = Path(args.drafts).expanduser().resolve()
    manifest_path = drafts_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest.json not found in {drafts_dir}")
        return 1

    if not args.publish_request:
        print("BLOCKED — latest request must explicitly authorize publishing; draft/stage is not approval")
        return 2

    manifest = json.loads(manifest_path.read_text())
    posted_path = drafts_dir / "posted.json"

    # Compose URLs (mirror of stage_in_aside.py)
    compose_urls = {
        "linkedin": "https://www.linkedin.com/feed/?shareActive=true",
        "linkedin_short": "https://www.linkedin.com/feed/?shareActive=true",
        "hackernews": "https://news.ycombinator.com/submit",
        "twitter": "https://twitter.com/compose/post",
        "threads": "https://www.threads.net/@$USER",
        "facebook": "https://www.facebook.com/",
        "mastodon": "https://mastodon.social/publish",
        "devto": "https://dev.to/new",
        "instagram": "https://www.instagram.com/",  # no compose
    }

    posted = {"posted_at": datetime.now(timezone.utc).isoformat(),
              "approval_token": args.approval_token, "platforms": [], "results": {}}

    previous = json.loads(posted_path.read_text()) if posted_path.exists() else {}
    posted["results"].update(previous.get("results", {}))
    files = manifest.get("files", {})
    for key, path in files.items():
        # Reddit keys are "reddit_<sub>", not "reddit"
        if key.startswith("reddit_") and not key.endswith("_title"):
            sub = key.replace("reddit_", "")
            platform_key = f"reddit_{sub}"
            compose_url = f"https://old.reddit.com/r/{sub}/submit"
        elif key.endswith("_title"):
            continue
        else:
            platform_key = key
            compose_url = compose_urls.get(key)
            if not compose_url:
                continue

        if not selected(platform_key, allow):
            posted["results"].setdefault(platform_key, {"status": "skipped", "reason": "not in allowlist"})
            continue

        prior = posted["results"].get(platform_key, {})
        if prior.get("status") in {"posted", "existing", "unknown", "timeout", "submitting"}:
            print(f"Skipping {platform_key}: existing or uncertain submission; inspect history before retry")
            continue

        if platform_key == "instagram":
            posted["results"][platform_key] = {
                "status": "manual_required",
                "note": "Instagram has no web compose — copy caption from drafts/instagram.md and paste via mobile app",
            }
            continue

        print(f"\n→ Posting {platform_key} ({compose_url})...")
        posted["results"][platform_key] = {"status": "submitting"}
        posted_path.write_text(json.dumps(posted, indent=2))
        result = click_submit_via_aside(platform_key, compose_url)
        posted["results"][platform_key] = result
        posted["platforms"].append(platform_key)

    posted_path.write_text(json.dumps(posted, indent=2))

    ok = sum(1 for r in posted["results"].values() if r.get("status") == "posted")
    fail = sum(1 for r in posted["results"].values() if r.get("status") in ("failed", "no_submit_button_found", "timeout"))
    manual = sum(1 for r in posted["results"].values() if r.get("status") == "manual_required")
    print(f"\n\n✓ Posted: {ok}  ✗ Failed: {fail}  ⚠ Manual required: {manual}")
    print(f"✓ Log: {posted_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())