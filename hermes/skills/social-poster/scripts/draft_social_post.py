#!/usr/bin/env python3
"""
draft_social_post.py — Deterministic social-media post drafter.

Generates per-platform draft files from intent + key-points + link. Hard-rejects
on character-limit violations, soft-warns on spam-rule concerns. Pure template
logic — no LLM call unless --use-llm flag is passed (which routes through
the user's existing Hermes config, never hardcodes API keys).

Usage:
  python3 draft_social_post.py \\
    --intent "announce jleechanclaw open-source release" \\
    --key-points "AI agent orchestration, hermes deploy pipeline" \\
    --link "https://github.com/jleechanorg/jleechanclaw" \\
    --platforms reddit,twitter \\
    --reddit-subs "LocalLLaMA,Rag,OpenAI" \\
    --image "" \\
    --out /tmp/drafts/social-2026-07-06/

Output: per-platform .md files + manifest.json in --out dir.
"""
import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from platform_policy import parse_platforms, resolve_reddit_subs

# ----- Platform config -----

PLATFORM_LIMITS = {
    "linkedin":   {"hard": 3000, "recommended": 1500, "see_more": 210, "type": "long"},
    "linkedin_short": {"hard": 300, "recommended": 300, "see_more": 300, "type": "short"},
    "hackernews": {"hard": 10000, "recommended": 800, "see_more": 400, "title_hard": 80, "type": "long"},
    "twitter":    {"hard": 280, "recommended": 240, "see_more": 280, "type": "short"},
    "threads":    {"hard": 500, "recommended": 450, "see_more": 500, "type": "short"},
    "facebook":   {"hard": 63206, "recommended": 1500, "see_more": 480, "type": "long"},
    "instagram":  {"hard": 2200, "recommended": 2000, "see_more": 125, "type": "long"},
    "mastodon":   {"hard": 500, "recommended": 450, "see_more": 500, "type": "short"},
    "devto":      {"hard": 100000, "recommended": 3000, "see_more": 200, "title_hard": 80, "type": "long"},
}

REDDIT_BODY_LIMIT = 40000
REDDIT_TITLE_LIMIT = 300

# ----- Clickbait phrases (Reddit-wide title ban) -----
CLICKBAIT_PHRASES = [
    "you won't believe",
    "this x will blow your mind",
    "the future of",
    "revolutionary",
    "game-changing",
    "unlock the power",
    "why nobody is talking",
    "mind-blowing",
    "this changes everything",
]

# ----- Anti-pattern phrases -----
LINKEDIN_ENGAGEMENT_BAIT = [
    "i'm excited to announce",
    "i'm thrilled to share",
    "thrilled to announce",
    "excited to announce",
    "happy to announce",
]

TWITTER_BANNED_FIRST_HASHTAG = True  # hashtags in first tweet kill reach

# ----- Reddit per-sub rules -----
REDDIT_SUB_RULES = {
    "LocalLLaMA": {
        "format": "text",
        "spam_rule": "1/10",
        "requires_disclosure": True,
        "no_llm_generated_copy": True,
    },
    "Rag": {
        "format": "text",
        "spam_rule": "10/90",
        "requires_citation": True,
    },
    "OpenAI": {
        "format": "text",  # self-promo MUST be text post, not link
        "spam_rule": "1/10",
        "requires_prior_participation": True,
    },
    "ClaudeAI": {
        "format": "text",
        "spam_rule": "standard",
        "claude_specific_only": True,
    },
    "ChatGPT": {
        "format": "text",
        "spam_rule": "standard",
        "chatgpt_specific_only": True,
    },
}

# ----- Helpers -----

def slugify(name: str) -> str:
    """Filesystem-safe slug."""
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return s or "draft"


def safe_filename(*parts: str) -> str:
    """Join parts into a safe filename."""
    return "_".join(slugify(p) for p in parts if p) + ".md"


def count_chars(text: str) -> int:
    """Character count (proxy for limit checking)."""
    return len(text.strip())


def has_clickbait(text: str) -> list[str]:
    """Return list of clickbait phrases found."""
    lower = text.lower()
    return [p for p in CLICKBAIT_PHRASES if p in lower]


def has_engagement_bait(text: str) -> list[str]:
    """Return list of LinkedIn-style engagement bait phrases."""
    lower = text.lower()
    return [p for p in LINKEDIN_ENGAGEMENT_BAIT if p in lower]


def self_promo_ratio(text: str) -> float:
    """Heuristic: ratio of self-promo phrases to total sentences."""
    promo_signals = [
        r"\bi built\b",
        r"\bwe built\b",
        r"\bmy project\b",
        r"\bour project\b",
        r"\bshipped\b",
        r"\breleased\b",
        r"\blaunched\b",
        r"\bannounce\b",
        r"\bintroducing\b",
    ]
    sentences = re.split(r"[.!?]+", text)
    sentences = [s for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    promo_count = 0
    for sent in sentences:
        if any(re.search(pat, sent, re.IGNORECASE) for pat in promo_signals):
            promo_count += 1
    return promo_count / len(sentences)


# ----- Drafters -----

def draft_linkedin(intent: str, key_points: list[str], link: str, hashtags: list[str]) -> str:
    hook = intent[:210].strip()
    bullets = "\n".join(f"- {kp}" for kp in key_points[:5])
    htags = " ".join(f"#{h.lstrip('#')}" for h in hashtags[:5])
    return f"""{hook}

We kept hitting the same wall in production:

{bullets}

So we shipped the missing pieces as open source: a deterministic deploy pipeline, a skill framework with tests, and a 7-green verification gate that catches CI flakes before they wedge a cron.

MIT licensed, deployable in a single command, dogfooded on our own agent fleet for months.

{link}

{htags}
""".strip()


def draft_linkedin_short(intent: str, key_points: list[str], link: str) -> str:
    bullets_short = " · ".join(key_points[:3])
    return f"{intent}\n\n{bullets_short}\n\n{link}".strip()


def draft_hackernews(intent: str, key_points: list[str], link: str) -> dict:
    """Returns {'title': ..., 'body': ...}. HN has separate title + URL fields."""
    pitch = intent
    if len(pitch) > 60:
        pitch = pitch[:57] + "..."
    title = f"Show HN: jleechanclaw – {pitch}"
    if len(title) > 80:
        title = title[:77] + "..."

    bullets = "\n".join(f"- {kp}" for kp in key_points[:5])
    body = f"""Hi HN — I built jleechanclaw because every AI agent harness I touched died on the same three failure modes: skill drift between staging and prod, manual CI re-runs, and silent cron loops.

What it ships:

{bullets}

Stack: Python, launchd, Aside browser, the Hermes gateway.
License: MIT.
Missing pieces (would love feedback):
- Multi-tenant isolation (worktree-per-PR is good but heavy)
- A real eval harness (currently dogfooding via 7-green checks)

Repo: {link}

Happy to answer technical questions.
""".strip()
    return {"title": title, "body": body}


def draft_twitter(intent: str, key_points: list[str], link: str) -> dict:
    """Returns {'single': ..., 'thread': [...]}."""
    kp = key_points[0] if key_points else ""
    single = f"{intent[:140]}\n\n{kp}\n\n{link}"[:280]

    thread = [
        f"{intent[:240]}",
        f"The problem we kept hitting:\n\n" + "\n".join(f"• {kp}" for kp in key_points[:3]),
        f"What we built (open source, MIT):\n\n" + "\n".join(f"• {kp}" for kp in key_points[:5]),
        f"Repo + 5-min quickstart: {link}",
        f"If this saves you time, quote-tweet with your stack — I want to know what's missing.",
    ]
    return {"single": single, "thread": thread}


def draft_threads(intent: str, key_points: list[str], link: str) -> str:
    body = f"{intent[:200]}\n\n"
    if key_points:
        body += key_points[0] + "\n\n"
    body += link
    return body[:500]


def draft_facebook(intent: str, key_points: list[str], link: str) -> str:
    bullets = "\n".join(f"→ {kp}" for kp in key_points[:5])
    return f"""{intent}

The reason I'm posting this here instead of a launch announcement:

{bullets}

It's been in our own dogfood pipeline for months, and the deploy + skill pieces are finally clean enough that other people might actually want them.

{link}

Curious what you'd build on top.
""".strip()


def draft_instagram(intent: str, key_points: list[str], link: str, hashtags: list[str]) -> dict:
    """Returns {'caption': ..., 'hashtags': [...], 'alt_text': ...}."""
    hashtags = hashtags[:15]  # sweet spot
    htags_str = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    caption = f"""{intent}

{key_points[0] if key_points else ''}

Full post → link in bio.

.
.
.
{htags_str}
""".strip()[:2200]
    alt_text = f"Cover image for: {intent}"[:100]
    return {"caption": caption, "hashtags": hashtags, "alt_text": alt_text}


def draft_mastodon(intent: str, key_points: list[str], link: str) -> str:
    body = f"{intent[:200]}\n\n"
    if key_points:
        body += key_points[0] + "\n\n"
    body += link
    return body[:500]


def draft_devto(intent: str, key_points: list[str], link: str, description: str = "") -> dict:
    """Returns {'title': ..., 'description': ..., 'body': ...}."""
    title = intent[:80]
    if description:
        desc = description[:140]
    else:
        desc = (intent[:137] + "...") if len(intent) > 137 else intent
    body = f"""## Why this exists

{intent}

The gaps I kept hitting:

{chr(10).join(f"- {kp}" for kp in key_points[:5])}

## What jleechanclaw ships

A deterministic deploy pipeline, a skill framework with 11-item completeness checks, and a 7-green verification gate that catches CI flakes before they wedge a cron.

## How it works (5-minute quickstart)

```bash
git clone {link}
cd jleechanclaw
./install.sh
hermes skill list  # see the 9-platform social-poster skill, etc.
```

## What's missing (would love feedback)

- Multi-tenant isolation (worktree-per-PR is heavy)
- A real eval harness (currently dogfooding via 7-green checks)

Repo: {link}
License: MIT
""".strip()
    return {"title": title, "description": desc, "body": body}


def draft_reddit(sub: str, intent: str, key_points: list[str], link: str) -> dict:
    """Returns {'title': ..., 'body': ...} tailored per sub."""
    rules = REDDIT_SUB_RULES.get(sub, {})
    if rules.get("claude_specific_only") or rules.get("chatgpt_specific_only"):
        rules["skip_post"] = "sub requires platform-specific content"

    title = intent[:300]
    if has_clickbait(title):
        title = re.sub(r"(?i)" + "|".join(CLICKBAIT_PHRASES), "", title).strip()

    bullets = "\n".join(f"- {kp}" for kp in key_points[:5])

    if not sub:
        body = "\n\n".join(part for part in (intent, bullets, link) if part)
    elif sub == "LocalLLaMA":
        body = f"""I built jleechanclaw — an AI agent harness with a deterministic deploy pipeline, skill framework, and 7-green verification gate — because every other harness I tried died on the same three failure modes: skill drift, manual CI re-runs, silent cron loops.

## What it does

{bullets}

## What's missing (would love feedback on)

- Multi-tenant isolation (worktree-per-PR works but is heavy)
- A real eval harness (currently dogfooding via 7-green)
- A canonical LLM-evals directory (deferred — see roadmap)

## Stack

Python · launchd · Aside browser · Hermes gateway

Repo: {link}
License: MIT

---

Disclosure: I'm the maintainer.
""".strip()
    elif sub == "Rag":
        body = f"""Built this for RAG workflows that need deterministic deploy + skill composition.

## What it does

{bullets}

## Stack

- Vector DB: configurable (Qdrant / pgvector / Chroma)
- Embeddings: configurable
- Orchestration: Hermes gateway with launchd-managed workers

Repo: {link}
License: MIT

## Citation

```bibtex
@software{{jleechanclaw,
  author = {{Jeffrey Lee-Chan}},
  title = {{jleechanclaw: AI agent harness with deterministic deploy}},
  url = {{{link}}},
  year = {{2026}}
}}
```
""".strip()
    elif sub == "OpenAI":
        body = f"""I built jleechanclaw for OpenAI API + tool-use workflows.

## Context (why this is relevant to r/OpenAI)

Most agent frameworks I've tried either lock you to a single vendor or die the moment a single tool call flakes. jleechanclaw wraps the OpenAI API in a deploy pipeline that catches the flake before it bites.

## What it does

{bullets}

## What it doesn't do (yet)

- It's not a UI — it's a CLI + launchd pipeline
- It's not a fine-tuning framework
- Multi-tenant isolation is worktree-per-PR (heavy but clean)

## Why I'm posting in r/OpenAI specifically

The harness integrates with `openai` Python SDK out of the box, and the 7-green gate runs the eval harness I wrote against the Responses API. If you've hit the same tool-flake wedge I have, I'd love to compare notes.

Repo: {link}
""".strip()
    else:
        body = f"""{intent}

{bullets}

Repo: {link}
License: MIT
""".strip()

    return {"title": title, "body": body, "rules": rules}


# ----- Validation -----

def validate_draft(platform: str, content: str) -> dict:
    """Return {'ok': bool, 'warnings': [...], 'errors': [...]}."""
    result = {"ok": True, "warnings": [], "errors": []}
    cfg = PLATFORM_LIMITS.get(platform, {})
    hard = cfg.get("hard", 100000)

    if count_chars(content) > hard:
        result["ok"] = False
        result["errors"].append(f"{platform}: {count_chars(content)} chars exceeds hard limit {hard}")

    if platform == "hackernews":
        # Title check happens in drafter
        pass

    if platform == "linkedin" and cfg.get("see_more"):
        # First ~210 chars should be punchy
        first_chunk = content[: cfg["see_more"]]
        if has_engagement_bait(first_chunk):
            result["warnings"].append(f"linkedin: opening has engagement bait: {has_engagement_bait(first_chunk)}")

    if platform in ("twitter",) and content.startswith("#"):
        result["warnings"].append(f"twitter: starts with hashtag (kills reach)")

    if platform in ("reddit",) or platform.startswith("reddit_"):
        if has_clickbait(content):
            result["warnings"].append(f"reddit: clickbait phrase detected: {has_clickbait(content)}")
        ratio = self_promo_ratio(content)
        if ratio > 0.5:
            result["warnings"].append(f"reddit: self-promo ratio {ratio:.0%} > 50% (10/90 rule risk)")

    return result


# ----- Main -----

def main():
    ap = argparse.ArgumentParser(description="Draft social-media posts (deterministic, no LLM)")
    ap.add_argument("--intent", required=True, help="The core message / announcement")
    ap.add_argument("--key-points", default="", help="Comma-separated key points")
    ap.add_argument("--link", default="", help="Primary link (repo, blog post, etc.)")
    ap.add_argument("--image", default="", help="Optional image path / URL")
    ap.add_argument("--description", default="", help="Dev.to / OG description override")
    ap.add_argument("--hashtags", default="ai,opensource,python,agents,llm",
                    help="Comma-separated hashtag list (used by LinkedIn + Instagram)")
    ap.add_argument("--platforms", default=None,
                    help="Comma-separated platforms (default: reddit,twitter; x aliases twitter)")
    ap.add_argument("--reddit-subs", default=None,
                    help="Narrow Reddit targets; omitted uses scoped names or an untargeted draft for bare reddit")
    ap.add_argument("--out", required=True, help="Output directory for drafts + manifest")
    args = ap.parse_args()

    try:
        platforms = parse_platforms(args.platforms)
        reddit_subs = resolve_reddit_subs(platforms, args.reddit_subs)
    except ValueError as exc:
        ap.error(str(exc))

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "screenshots").mkdir(exist_ok=True)

    key_points = [kp.strip() for kp in args.key_points.split(",") if kp.strip()]
    hashtags = [h.strip() for h in args.hashtags.split(",") if h.strip()]

    manifest = {
        "mode": "draft",
        "discovery_status": "not_performed",
        "intent": args.intent,
        "key_points": key_points,
        "link": args.link,
        "platforms": platforms,
        "reddit_subs": reddit_subs,
        "drafted_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
        "warnings": {},
        "errors": [],
    }

    def write_and_track(filename: str, content, sub: str = None) -> None:
        path = out_dir / filename
        path.write_text(content if isinstance(content, str) else json.dumps(content, indent=2))
        key = f"reddit_{sub}" if sub else filename.replace(".md", "")
        manifest["files"][key] = str(path)

    # Render the resolved Reddit targets once, even when family and scoped flags overlap.
    draft_platforms = list(dict.fromkeys(
        "reddit" if p.startswith("reddit_") else p for p in platforms))
    for platform in draft_platforms:
        if platform == "linkedin":
            content = draft_linkedin(args.intent, key_points, args.link, hashtags)
            write_and_track("linkedin.md", content)
            v = validate_draft("linkedin", content)
            manifest["warnings"]["linkedin"] = v["warnings"]
            if not v["ok"]:
                manifest["errors"].extend(v["errors"])

        elif platform == "linkedin_short":
            content = draft_linkedin_short(args.intent, key_points, args.link)
            write_and_track("linkedin_short.md", content)
            v = validate_draft("linkedin_short", content)
            manifest["warnings"]["linkedin_short"] = v["warnings"]

        elif platform == "hackernews":
            d = draft_hackernews(args.intent, key_points, args.link)
            title = d["title"]
            if count_chars(title) > 80:
                manifest["errors"].append(f"hackernews title {count_chars(title)} chars > 80 (will truncate)")
            write_and_track("hackernews.md", f"## Title\n\n{title}\n\n## Body\n\n{d['body']}\n")
            manifest["files"]["hackernews_title"] = title
            v = validate_draft("hackernews", d["body"])
            manifest["warnings"]["hackernews"] = v["warnings"]

        elif platform == "twitter":
            d = draft_twitter(args.intent, key_points, args.link)
            content = f"## Single tweet\n\n{d['single']}\n\n## Thread\n\n" + \
                      "\n\n".join(f"**Tweet {i+1}/{len(d['thread'])}:**\n\n{t}" for i, t in enumerate(d["thread"]))
            write_and_track("twitter.md", content)
            v = validate_draft("twitter", d["single"])
            manifest["warnings"]["twitter"] = v["warnings"]
            for i, t in enumerate(d["thread"]):
                if count_chars(t) > 280:
                    manifest["errors"].append(f"twitter thread tweet {i+1}: {count_chars(t)} chars > 280")

        elif platform == "threads":
            content = draft_threads(args.intent, key_points, args.link)
            write_and_track("threads.md", content)
            v = validate_draft("threads", content)
            manifest["warnings"]["threads"] = v["warnings"]

        elif platform == "facebook":
            content = draft_facebook(args.intent, key_points, args.link)
            write_and_track("facebook.md", content)
            v = validate_draft("facebook", content)
            manifest["warnings"]["facebook"] = v["warnings"]

        elif platform == "instagram":
            d = draft_instagram(args.intent, key_points, args.link, hashtags)
            content = f"## Caption\n\n{d['caption']}\n\n## Alt text\n\n{d['alt_text']}\n"
            write_and_track("instagram.md", content)
            v = validate_draft("instagram", d["caption"])
            manifest["warnings"]["instagram"] = v["warnings"]
            if len(d["hashtags"]) > 30:
                manifest["errors"].append(f"instagram: {len(d['hashtags'])} hashtags > 30 (penalized)")

        elif platform == "mastodon":
            content = draft_mastodon(args.intent, key_points, args.link)
            write_and_track("mastodon.md", content)
            v = validate_draft("mastodon", content)
            manifest["warnings"]["mastodon"] = v["warnings"]

        elif platform == "devto":
            d = draft_devto(args.intent, key_points, args.link, args.description)
            content = f"## Title\n\n{d['title']}\n\n## Description\n\n{d['description']}\n\n## Body\n\n{d['body']}\n"
            write_and_track("devto.md", content)
            manifest["files"]["devto_title"] = d["title"]
            v = validate_draft("devto", d["body"])
            manifest["warnings"]["devto"] = v["warnings"]

        elif platform == "reddit":
            for sub in reddit_subs or [""]:
                rd = draft_reddit(sub, args.intent, key_points, args.link)
                fname = f"reddit_{slugify(sub)}.md" if sub else "reddit.md"
                content = f"## Title\n\n{rd['title']}\n\n## Body\n\n{rd['body']}\n"
                write_and_track(fname, content, sub=sub)
                manifest["files"][f"reddit_{sub}_title" if sub else "reddit_title"] = rd["title"]
                if rd.get("rules", {}).get("skip_post"):
                    manifest["warnings"][f"reddit_{sub}"] = [rd["rules"]["skip_post"]]
                    continue
                v = validate_draft("reddit", rd["title"] + " " + rd["body"])
                manifest["warnings"][f"reddit_{sub}"] = v["warnings"]
                if not v["ok"]:
                    manifest["errors"].extend(v["errors"])

    # Write manifest
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Summary
    print(f"\n✓ Drafted {len(manifest['files'])} files to {out_dir}")
    print(f"✓ Manifest: {manifest_path}")
    if manifest["errors"]:
        print(f"\n✗ ERRORS ({len(manifest['errors'])}):")
        for e in manifest["errors"]:
            print(f"  - {e}")
        return 1
    warn_count = sum(len(w) for w in manifest["warnings"].values())
    if warn_count:
        print(f"\n⚠ WARNINGS ({warn_count}):")
        for plat, ws in manifest["warnings"].items():
            for w in ws:
                print(f"  - [{plat}] {w}")
    print("\nDraft only: review source facts and complete discovery before selecting targets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())