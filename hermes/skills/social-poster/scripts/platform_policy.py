"""Shared per-request destination selection; X threads are not Meta Threads."""
import re

DEFAULT_PLATFORMS = ("reddit", "twitter")
SUPPORTED_PLATFORMS = frozenset((*DEFAULT_PLATFORMS, "linkedin", "linkedin_short",
    "hackernews", "threads", "facebook", "instagram", "mastodon", "devto"))


def parse_platforms(value=None):
    if value is None:
        return list(DEFAULT_PLATFORMS)
    names = [p.strip().lower() for p in value.split(",") if p.strip()]
    names = ["twitter" if p == "x" else p for p in names]
    if not names or any(p not in SUPPORTED_PLATFORMS and not re.fullmatch(r"reddit_[a-z0-9_]+", p) for p in names):
        raise ValueError("Select supported platforms explicitly; empty allowlists are invalid")
    return list(dict.fromkeys(names))


def selected(key, allow):
    key = key.lower()
    return key in allow or (key.startswith("reddit_") and "reddit" in allow)


def intersect_platforms(left, right):
    """Intersect platform families and exact targets without expanding either side."""
    common = [p for p in dict.fromkeys([*left, *right])
              if selected(p, left) and selected(p, right)]
    if "reddit" in common:
        common = [p for p in common if not p.startswith("reddit_")]
    return common


def resolve_reddit_subs(platforms, value=None):
    """Resolve explicit targets, with --reddit-subs narrowing Reddit selections."""
    scoped = [p.removeprefix("reddit_") for p in platforms if p.startswith("reddit_")]
    if value is None:
        return scoped
    names = [s.strip() for s in value.split(",") if s.strip()]
    if not names or any(not re.fullmatch(r"[A-Za-z0-9_]+", s) for s in names):
        raise ValueError("Select nonempty subreddit names using letters, digits, or underscores")
    resolved = {s.lower(): s for s in names if selected("reddit_" + s, platforms)}
    if (scoped or "reddit" in platforms) and not resolved:
        raise ValueError("Platform and subreddit selections have no subreddit in common")
    return list(resolved.values())
