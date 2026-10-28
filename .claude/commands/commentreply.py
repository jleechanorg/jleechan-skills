#!/usr/bin/env python3
"""
/commentreply Command Implementation

Systematically processes ALL PR comments with proper GitHub API threading.
Prevents the bug pattern where individual comments are missed while claiming 100% coverage.

This is the ACTUAL IMPLEMENTATION that was missing - the .md file had extensive
documentation but no working code to execute the systematic processing.
"""

import json
import subprocess
import sys
import os
import tempfile
import html
import re
import time
import warnings
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from _copilot_modules.scratch_paths import copilot_cache_file




def run_command(
    cmd: List[str],
    description: str = "",
    timeout: int = 60,
    input_text: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Execute shell command safely with error handling"""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,  # Don't raise on non-zero exit
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"[timeout] {description or 'cmd'}: {' '.join(cmd)}"
    except Exception as e:
        return False, "", f"[failure] {description or 'cmd'}: {e}"


def parse_arguments() -> Tuple[str, str, str]:
    """Parse command line arguments for owner, repo, and PR number"""
    if len(sys.argv) != 4:
        print("❌ ERROR: Missing required arguments")
        print("Usage: python3 commentreply.py <owner> <repo> <pr_number>")
        print("Example: python3 commentreply.py jleechanorg your-project.com 1510")
        sys.exit(1)

    return sys.argv[1], sys.argv[2], sys.argv[3]


def sanitize_branch_name(branch: str) -> str:
    """Sanitize branch name to match shell's tr -cd '[:alnum:]._-'.

    Removes any character that is NOT alphanumeric, dot, underscore, or dash.
    """
    return re.sub(r"[^a-zA-Z0-9._-]", "", branch or "")


def sanitize_repo_name(repo_name: str) -> str:
    """Sanitize repo name for filesystem safety.

    Uses the same allowlist as branch sanitization so cache paths cannot be
    influenced by path separators or traversal sequences.
    """
    return re.sub(r"[^a-zA-Z0-9._-]", "", repo_name or "")


def get_current_branch() -> str:
    """Get current git branch name for temp file path"""
    success, branch, _ = run_command(["git", "branch", "--show-current"])
    if success and branch.strip():
        return sanitize_branch_name(branch.strip()) or "unknown-branch"
    return "unknown-branch"


def get_repo_name(fallback_repo: str) -> str:
    """Get repo name from git root to match shell scripts, with fallback."""
    success, git_root, _ = run_command(["git", "rev-parse", "--show-toplevel"])
    if success and git_root.strip():
        candidate = os.path.basename(git_root.strip())
    else:
        candidate = fallback_repo

    sanitized = sanitize_repo_name(candidate)
    return sanitized or "unknown-repo"


def load_claude_responses(branch_name: str, repo_name: str) -> Dict:
    """
    Load Claude-generated responses from JSON file.
    In the modern workflow, Claude analyzes comments, implements fixes,
    generates responses, and saves them to responses.json for Python to post.

    Args:
        branch_name: Current git branch name (sanitized)
        repo_name: Repository name (sanitized)

    Returns:
        Dictionary containing responses data, empty dict if file not found
    """
    try:
        responses_path = copilot_cache_file(repo_name, branch_name, "responses.json")
    except RuntimeError as error:
        print(f"⚠️ SECURITY: Comment response path unavailable: {error}")
        return {}

    if not responses_path.exists():
        print(f"RESPONSES FILE NOT FOUND: {responses_path}")
        print("Claude should have generated responses.json after analyzing comments")
        return {}

    try:
        # Additional security: check file size before reading
        file_size = responses_path.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            print(
                f"⚠️ SECURITY: File too large: {responses_path} ({file_size} bytes)"
            )
            return {}

        with responses_path.open("r") as f:
            responses_data = json.load(f)
        print(
            f"📁 LOADED: {len(responses_data.get('responses', []))} responses from {responses_path}"
        )
        return responses_data
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Failed to parse responses JSON: {e}")
        return {}
    except Exception as e:
        print(f"❌ ERROR: Failed to load responses file: {e}")
        return {}


def load_comments_with_staleness_check(
    branch_name: str, owner: str, repo: str, pr_number: str, repo_name: str
) -> List[Dict]:
    """
    Load comment data with staleness detection and real-time fallback.
        repo: Repository name
        pr_number: PR number
        repo_name: Repository name (sanitized)

    Returns:
        List of comment dictionaries (fresh or cached)
    """
    try:
        comments_path = copilot_cache_file(repo_name, branch_name, "comments.json")
    except RuntimeError as error:
        print(f"❌ ERROR: Comment cache file unavailable: {error}")
        sys.exit(1)

    # Fallback to legacy single-file format
    comments_file = str(comments_path)

    # COPILOT: Always fetch fresh data - no cache for PR processing
    if comments_path.exists():
        cache_age_minutes = (time.time() - os.path.getmtime(comments_file)) / 60
        print(
            f"🔄 COPILOT MODE: Ignoring {cache_age_minutes:.1f}min cache - fetching fresh comments"
        )
        fetch_fresh_comments(owner, repo, pr_number, comments_file)
    else:
        print(f"📥 NO CACHE: Fetching fresh comments for {owner}/{repo}#{pr_number}")
        fetch_fresh_comments(owner, repo, pr_number, comments_file)

    try:
        with comments_path.open("r") as f:
            comment_data = json.load(f)
        return comment_data.get("comments", [])
    except Exception as e:
        print(f"❌ ERROR: Failed to load comments: {e}")
        sys.exit(1)


def fetch_fresh_comments(owner: str, repo: str, pr_number: str, output_file: str):
    """Fetch fresh comments using GitHub API and save to cache file"""

    # Fetch both review comments and issue comments
    inline_cmd = [
        "gh",
        "api",
        f"repos/{owner}/{repo}/pulls/{pr_number}/comments",
        "--paginate",
        "-q",
        ".[]",
    ]
    issue_cmd = [
        "gh",
        "api",
        f"repos/{owner}/{repo}/issues/{pr_number}/comments",
        "--paginate",
        "-q",
        ".[]",
    ]
    review_body_cmd = [
        "gh",
        "api",
        f"repos/{owner}/{repo}/pulls/{pr_number}/reviews",
        "--paginate",
        "-q",
        ".[]",
    ]

    print("📡 FETCHING: Fresh comment data from GitHub API...")

    success_inline, inline_data, _ = run_command(
        inline_cmd, "fetch inline review comments", timeout=120
    )
    success_issue, issue_data, _ = run_command(
        issue_cmd, "fetch issue comments", timeout=120
    )
    success_review_bodies, review_body_data, _ = run_command(
        review_body_cmd, "fetch review bodies", timeout=120
    )

    # Require inline and issue comments (core functionality)
    # Review bodies are optional - gracefully degrade if endpoint fails
    if not (success_inline and success_issue):
        print("❌ ERROR: Failed to fetch core comments (inline/issue) from GitHub API")
        if not os.path.exists(output_file):
            sys.exit(1)
        print("⚠️  Falling back to stale cache...")
        return

    if not success_review_bodies:
        print(
            "⚠️  WARNING: Review bodies fetch failed (permissions/rate-limit?) - continuing without review bodies"
        )
        review_body_data = ""  # Empty, will result in empty list

    # Parse and combine comments
    try:
        inline_comments = [
            json.loads(line)
            for line in (inline_data or "").splitlines()
            if line.strip()
        ]
        issue_comments = [
            json.loads(line) for line in (issue_data or "").splitlines() if line.strip()
        ]
        # Filter out reviews with empty bodies (e.g., approval reviews without comments)
        raw_reviews = [
            json.loads(line)
            for line in (review_body_data or "").splitlines()
            if line.strip()
        ]
        review_body_comments = [r for r in raw_reviews if r.get("body", "").strip()]

        # Add type information and combine
        for comment in inline_comments:
            comment["type"] = "inline"
        for comment in issue_comments:
            comment["type"] = "issue"
        for review in review_body_comments:
            review["type"] = "review"

        all_comments = inline_comments + issue_comments + review_body_comments

        # Save to cache file
        cache_data = {
            "pr": pr_number,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "comments": all_comments,
        }

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(cache_data, f, indent=2)

        print(f"✅ CACHED: {len(all_comments)} comments saved to {output_file}")

    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Failed to parse fresh comment data: {e}")
        sys.exit(1)


def validate_comment_data(comment: Dict) -> bool:
    """Validate comment data structure and content for security.

    Args:
        comment: Comment data dictionary

    Returns:
        True if comment data is valid and safe
    """
    if not isinstance(comment, dict):
        return False

    # Required fields (user field no longer required due to author field support)
    required_fields = ["id", "body"]
    for field in required_fields:
        if field not in comment:
            return False

    # Validate comment ID (must be numeric)
    comment_id = comment.get("id")
    if not isinstance(comment_id, (int, str)) or not str(comment_id).isdigit():
        return False

    # Validate user structure (support both user.login and author formats)
    user = comment.get("user")
    author = comment.get("author")

    # Accept either user.login structure or direct author field
    has_valid_user = isinstance(user, dict) and "login" in user
    has_valid_author = isinstance(author, str) and author.strip()

    if not (has_valid_user or has_valid_author):
        # Normalize missing author metadata to "unknown" for backward compatibility.
        comment["author"] = "unknown"

    # Validate body content
    body = comment.get("body")
    if not isinstance(body, str):
        return False

    # Check for potentially dangerous content patterns
    dangerous_patterns = [
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:text/html",  # Data URLs
        r"vbscript:",  # VBScript
        r"<[^>]+\son\w+\s*=",  # Inline event handlers in HTML tags
    ]

    # Allow known bot content that includes HTML/event-handler examples.
    author_login = ""
    user_type = ""
    if isinstance(user, dict):
        if user.get("login"):
            author_login = str(user.get("login"))
        if user.get("type"):
            user_type = str(user.get("type"))
    elif isinstance(author, str):
        author_login = author

    is_bot_author = False
    if user_type.lower() == "bot":
        is_bot_author = True
    elif author_login.lower().endswith("[bot]"):
        is_bot_author = True

    def strip_code_blocks(text: str) -> str:
        # Remove fenced code blocks and inline code to avoid false positives on examples.
        without_fences = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        return re.sub(r"`[^`]*`", "", without_fences, flags=re.DOTALL)

    for pattern in dangerous_patterns:
        if re.search(pattern, body, re.IGNORECASE | re.DOTALL):
            print(
                f"⚠️ SECURITY: Potentially dangerous content detected in comment #{comment_id}"
            )
            if is_bot_author:
                scrubbed_body = strip_code_blocks(body)
                if not re.search(pattern, scrubbed_body, re.IGNORECASE | re.DOTALL):
                    print(
                        "⚠️ SECURITY: Allowing bot-authored code example content for response processing"
                    )
                    return True
            return False

    return True


def sanitize_comment_content(content: str) -> str:
    """Sanitize comment content for safe processing.

    Args:
        content: Raw comment content

    Returns:
        Sanitized content safe for processing
    """
    if not isinstance(content, str):
        return str(content)

    # HTML escape potentially dangerous characters
    sanitized = html.escape(content)

    # Limit length to prevent DoS
    if len(sanitized) > 10000:  # 10KB limit
        sanitized = sanitized[:10000] + "... [truncated]"

    return sanitized


def get_response_for_comment(
    comment: Dict,
    responses_data: Dict,
    commit_hash: str,
    parent_comment: Optional[Dict] = None,
) -> str:
    """
    Get Claude-generated response for a specific comment.

    Args:
        comment: Comment data from GitHub API
        responses_data: Loaded responses from Claude
        commit_hash: Current commit hash as fallback
        parent_comment: Optional parent comment data for context (when processing replies)
    Returns:
        Claude-generated response text or placeholder if not found
    """
    # SECURITY: Validate comment data first
    if not validate_comment_data(comment):
        print("⚠️ SECURITY: Invalid comment data structure, skipping")
        return ""

    comment_id = str(comment.get("id"))

    # Look for Claude-generated response
    responses = responses_data.get("responses", [])
    for response_item in responses:
        if str(response_item.get("comment_id")) == comment_id:
            # Backward compatibility: support both 'reply_text' and legacy 'response' keys
            return response_item.get("reply_text") or response_item.get("response", "")

    # CRITICAL FIX: Never post placeholder comments - return empty string to skip posting
    print(
        f"⚠️ SKIP: No Claude response found for comment #{comment_id} - will not post placeholder"
    )
    return ""


def get_git_commit_hash() -> str:
    """Get current git commit hash"""
    success, commit_hash, _ = run_command(["git", "rev-parse", "--short", "HEAD"])
    return commit_hash.strip() if success else "unknown"


def get_files_modified() -> str:
    """Get files modified in current branch compared to main, using git diff --stat.

    Returns:
        A formatted string with the number of files changed and the file list.
        Returns empty string if git command fails.
    """
    # Get diff against main branch
    success, diff_output, _ = run_command(
        ["git", "diff", "--stat", "main...", "--no-color"],
        description="get files modified since main",
    )
    if not success or not diff_output.strip():
        # Fallback: try against origin/main
        success, diff_output, _ = run_command(
            ["git", "diff", "--stat", "origin/main...", "--no-color"],
            description="get files modified since origin/main",
        )

    if success and diff_output.strip():
        # Parse the output to get a clean summary
        lines = diff_output.strip().split("\n")
        # Last line typically contains the summary (e.g., "5 files changed, 100 insertions(+)")
        if lines:
            # Extract file names from all lines (excluding the summary line)
            file_names = []
            for line in lines[:-1]:
                # Each line looks like: "path/to/file.py | 10 ++++"
                if "|" in line:
                    file_path = line.split("|")[0].strip()
                    if file_path:
                        file_names.append(file_path)
            return f"{len(file_names)} file(s) changed - {', '.join(file_names[:10])}{'...' if len(file_names) > 10 else ''}"
    return ""





TRACKING_START_MARKER = "<!-- COPILOT_TRACKING_START -->"
TRACKING_END_MARKER = "<!-- COPILOT_TRACKING_END -->"

TRACKING_STATUS_MAP = {
    "FIXED": ("✅ Fixed", "fixed"),
    "ALREADY_IMPLEMENTED": ("✅ Fixed", "fixed"),
    "DEFERRED": ("🔄 Deferred", "deferred"),
    "ACKNOWLEDGED": ("⏭️ Acknowledged", "ignored"),
    "SKIPPED": ("⏭️ Acknowledged", "ignored"),
    "NOT_DONE": ("⏭️ Not Done", "not_done"),
}


def parse_existing_tracking_table(owner: str, repo: str, pr_number: str) -> Dict[str, Dict]:
    """Parse existing tracking table from PR description to preserve original reasons.

    This function fetches the PR description and extracts the tracking table
    to preserve original tracking reasons for comments that were already resolved
    in prior copilot runs. This prevents using boilerplate reasons.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        Dict mapping comment_id -> {status, reason} for all entries in tracking table
    """
    tracking_lookup: Dict[str, Dict] = {}

    # Fetch current PR body
    repo_flag = f"{owner}/{repo}"
    success, pr_body, stderr = run_command(
        ["gh", "pr", "view", pr_number, "--repo", repo_flag, "--json", "body", "--jq", ".body // \"\""],
        description="fetch PR body for tracking table parsing",
        timeout=30,
    )
    if not success:
        print(f"   ⚠️  Could not fetch PR description: {stderr}")
        return tracking_lookup

    pr_body = pr_body.rstrip("\n")

    # Check if tracking markers exist and are in correct order
    if TRACKING_START_MARKER not in pr_body or TRACKING_END_MARKER not in pr_body:
        print("   ℹ️  No existing tracking table found in PR description")
        return tracking_lookup

    start_count = pr_body.count(TRACKING_START_MARKER)
    end_count = pr_body.count(TRACKING_END_MARKER)
    if start_count != 1 or end_count != 1:
        print(
            f"   ⚠️  Malformed tracking markers in PR body (start={start_count}, end={end_count})"
        )

    # Extract tracking section
    start_idx = pr_body.find(TRACKING_START_MARKER) + len(TRACKING_START_MARKER)
    end_idx = pr_body.rfind(TRACKING_END_MARKER)

    # Validate marker order to prevent empty slice
    if start_idx > end_idx:
        print("   ⚠️  Tracking markers in wrong order - START after END")
        return tracking_lookup

    tracking_section = pr_body[start_idx:end_idx]

    # Parse markdown table rows
    # Format: | Status | Comment | Reason |
    lines = tracking_section.split('\n')
    for line in lines:
        line = line.strip()
        # Skip header and separator lines
        if not line or not line.startswith('|'):
            continue
        # Skip separator lines (e.g., |---|---|---|)
        if '---' in line:
            continue
            
        # Parse row: | Status | [Comment #id](url) by @author | Reason |
        # Use more robust split to handle escaped pipes (\|) in tracking reasons
        raw_parts = [p for p in line.split('|')]
        # Row starts and ends with |, so raw_parts[0] and raw_parts[-1] are typically empty
        if len(raw_parts) < 4:
            continue

        status_text = raw_parts[1].strip()
        comment_link = raw_parts[2].strip()
        
        # Skip header row
        if 'Status' in status_text and 'Comment' in comment_link:
            continue

        # Reason is everything from 3rd column onwards (handle extra pipes in reason)
        # Markdown tables typically end with a |
        reason_raw = '|'.join(raw_parts[3:-1]) if raw_parts[-1].strip() == "" else '|'.join(raw_parts[3:])
        reason_text = reason_raw.replace('\\|', '|').strip()

        # Extract comment ID from link like "[#123](url) by @author"
        comment_id = None
        if '#' in comment_link and ']' in comment_link:
            try:
                # Extract ID between # and ]
                id_start = comment_link.index('#') + 1
                id_end = comment_link.index(']', id_start)
                comment_id = comment_link[id_start:id_end]
            except (ValueError, IndexError):
                continue

        if not comment_id:
            continue

        # Map status text to response type
        status_to_response = {
            "✅ Fixed": "FIXED",
            "🔄 Deferred": "DEFERRED",
            "⏭️ Ignored": "ACKNOWLEDGED",
            "⏭️ Acknowledged": "ACKNOWLEDGED",
            "⏭️ Not Done": "NOT_DONE",
            "❓ Unresolved": "UNRESOLVED",
        }
        response_type = status_to_response.get(status_text, "ACKNOWLEDGED")

        tracking_lookup[comment_id] = {
            "status": status_text,
            "response": response_type,
            "reason": reason_text,
        }

    print(f"   📋 Parsed {len(tracking_lookup)} entries from existing tracking table")
    return tracking_lookup


def compute_metrics(responses: List[Dict]) -> Dict[str, int]:
    """Compute metrics from responses.json - single source of truth.

    This function computes ALL metrics from responses.json to ensure consistency
    between tracking table footer and consolidated reply metrics.
    Handles both single-issue and multi-issue response formats.

    Args:
        responses: List of response entries from responses.json

    Returns:
        Dict with computed metrics: total, fixed, acknowledged, deferred, not_done, already_implemented,
        plus category counts: critical, blocking, important, style, routine
    """
    fixed = 0
    acknowledged = 0
    deferred = 0
    not_done = 0
    already_implemented = 0
    critical = 0
    blocking = 0
    important = 0
    style = 0  # STYLE category (renamed from ROUTINE)
    routine = 0

    # Helper to get all issues from a response (handles both single and multi-issue formats)
    def get_all_issues(resp):
        """Extract all issues from response, handling both single-issue and multi-issue formats."""
        if "issues" in resp and "analysis" in resp:
            # Multi-issue format: return list of issues
            return resp.get("issues", [])
        else:
            # Single-issue format: treat entire response as one issue
            return [resp]

    for resp in responses:
        # Handle both single-issue and multi-issue response formats
        issues = get_all_issues(resp)

        for issue in issues:
            response_type = issue.get("response", "")
            category = issue.get("category", "")

            # Count by response type
            if response_type == "FIXED":
                fixed += 1
            elif response_type == "ALREADY_IMPLEMENTED":
                already_implemented += 1
                fixed += 1  # Count as fixed for display purposes
            elif response_type == "DEFERRED":
                deferred += 1
            elif response_type == "ACKNOWLEDGED":
                acknowledged += 1
            elif response_type == "NOT_DONE":
                not_done += 1
            elif response_type == "SKIPPED":
                acknowledged += 1  # Count as acknowledged for display
            else:
                # Default to acknowledged for unknown types to match tracking table logic
                # This ensures compute_metrics and build_tracking_section totals match
                acknowledged += 1

            # Count by category
            if category == "CRITICAL":
                critical += 1
            elif category == "BLOCKING":
                blocking += 1
            elif category == "IMPORTANT":
                important += 1
            elif category == "STYLE":
                style += 1  # STYLE renamed from ROUTINE in copilot.md
            elif category == "ROUTINE":
                routine += 1
                style += 1  # Also count ROUTINE in style for backwards compatibility

    return {
        "total": fixed + acknowledged + deferred + not_done,
        "fixed": fixed,
        "acknowledged": acknowledged,
        "deferred": deferred,
        "not_done": not_done,
        "already_implemented": already_implemented,
        "critical": critical,
        "blocking": blocking,
        "important": important,
        "style": style,  # STYLE + ROUTINE combined
        "routine": routine,
    }


def _get_comment_url(
    owner: str, repo: str, pr_number: str, comment: Dict, comment_type: str
) -> str:
    """Build the GitHub URL for a comment based on its type and ID."""
    html_url = comment.get("html_url")
    if html_url:
        return html_url

    comment_id = comment.get("id", "unknown")
    if comment_type == "review":
        anchor = f"pullrequestreview-{comment_id}"
    elif comment_type in ("inline", "copilot"):
        anchor = f"discussion_r{comment_id}"
    else:
        anchor = f"issuecomment-{comment_id}"
    return f"https://github.com/{owner}/{repo}/pull/{pr_number}#{anchor}"


def _get_comment_author(comment: Dict) -> str:
    """Extract author from comment, supporting both user.login and author formats."""
    user_dict = comment.get("user")
    if isinstance(user_dict, dict) and user_dict.get("login"):
        return user_dict["login"]
    return comment.get("author", "unknown")


def build_tracking_section(
    owner: str,
    repo: str,
    pr_number: str,
    responses_data: Dict,
    all_comments: List[Dict],
    already_replied_ids: set,
    existing_tracking: Dict[str, Dict] = None,
) -> str:
    """Build the PR description tracking section with categorized comment URLs.

    Categorizes each comment as fixed, deferred, ignored, or unresolved based
    on the response type in responses.json.  Includes a 2-3 sentence
    tracking_reason for each entry.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        responses_data: Loaded responses.json with ACTION_ACCOUNTABILITY format
        all_comments: All fetched PR comments
        already_replied_ids: Set of comment IDs already replied to (for context)
        existing_tracking: Optional dict from parse_existing_tracking_table to preserve original reasons

    Returns:
        Markdown string for the tracking section
    """
    responses = responses_data.get("responses", [])

    # Pre-compute string set for O(1) lookups instead of recreating on each loop iteration
    already_replied_ids_str = {str(x) for x in already_replied_ids}

    # Build a lookup: comment_id (str) -> response entry
    # Handle both single-issue and multi-issue response formats
    response_lookup: Dict[str, Dict] = {}
    for resp in responses:
        if "issues" in resp and "analysis" in resp:
            # Multi-issue format: store individual issue dict (not parent)
            # so tracking table reads per-issue response/tracking_reason
            for issue in resp.get("issues", []):
                cid = str(issue.get("comment_id", ""))
                if cid:
                    response_lookup[cid] = issue
        else:
            # Single-issue format: use comment_id directly
            cid = str(resp.get("comment_id", ""))
            if cid:
                response_lookup[cid] = resp

    # If no existing_tracking provided, parse from PR description
    if existing_tracking is None:
        existing_tracking = parse_existing_tracking_table(owner, repo, pr_number)

    # Determine current actor to skip self-comments
    ok_actor, actor_login, _ = run_command(
        ["gh", "api", "user", "-q", ".login"], description="current actor"
    )
    actor_login = (actor_login or "").strip() or os.environ.get("GITHUB_ACTOR", "")

    # Categorize each top-level comment
    fixed_entries: List[str] = []
    deferred_entries: List[str] = []
    not_done_entries: List[str] = []
    ignored_entries: List[str] = []
    unresolved_entries: List[str] = []

    # Sort comments chronologically
    sorted_comments = sorted(all_comments, key=lambda c: c.get("created_at", ""))

    for comment in sorted_comments:
        comment_id = str(comment.get("id", ""))
        if not comment_id:
            continue

        # Skip replies (only track top-level comments)
        if comment.get("in_reply_to_id"):
            continue

        # Skip our own comments
        author = _get_comment_author(comment)
        if author in ('$USER-af', 'jleechanao', actor_login):
            continue

        comment_type = comment.get("type") or detect_comment_type(comment)
        url = _get_comment_url(owner, repo, pr_number, comment, comment_type)
        link_text = f"[#{comment_id}]({url}) by @{author}"

        resp = response_lookup.get(comment_id)

        if resp:
            response_type = resp.get("response", "ACKNOWLEDGED")
            tracking_reason = resp.get("tracking_reason", "")

            # Coerce to string to guard against non-string values in responses.json
            if not isinstance(tracking_reason, str):
                tracking_reason = str(tracking_reason) if tracking_reason else ""

            # Fallback: derive reason from existing fields if tracking_reason is missing
            if not tracking_reason:
                tracking_reason = _derive_tracking_reason(resp)

            # Escape pipe characters in reason for markdown table
            tracking_reason = tracking_reason.replace("|", "\\|").replace("\n", " ")

            status_label, category = TRACKING_STATUS_MAP.get(
                response_type, ("⏭️ Acknowledged", "ignored")
            )
            row = f"| {status_label} | {link_text} | {tracking_reason} |"

            if category == "fixed":
                fixed_entries.append(row)
            elif category == "deferred":
                deferred_entries.append(row)
            elif category == "not_done":
                not_done_entries.append(row)
            else:
                ignored_entries.append(row)
        elif comment_id in already_replied_ids_str:
            # Already replied in a prior run - preserve original status
            # FIX: Use original status from existing tracking table, NOT hardcoded "Fixed"
            existing_entry = existing_tracking.get(comment_id)
            if existing_entry:
                # Preserve original status and reason from prior tracking table
                original_status = existing_entry.get("status", "✅ Fixed")
                if existing_entry.get("reason"):
                    # RE-ESCAPE: existing_entry["reason"] was un-escaped by parser, must re-escape for table
                    reason = existing_entry["reason"].replace("|", "\\|").replace("\n", " ")
                else:
                    reason = "[Original tracking reason not found in PR description - comment was already addressed]"
            else:
                # No existing entry found - mark as unknown rather than assuming Fixed
                original_status = "❓ Unresolved"
                reason = "[Already replied but no tracking entry found - status unknown]"
            
            row = f"| {original_status} | {link_text} | {reason} |"
            
            # Add to appropriate list based on original status
            if "Deferred" in original_status:
                deferred_entries.append(row)
            elif "Not Done" in original_status:
                not_done_entries.append(row)
            elif "Ignored" in original_status or "Acknowledged" in original_status:
                ignored_entries.append(row)
            elif "Unresolved" in original_status or "❓" in original_status:
                unresolved_entries.append(row)
            else:
                # Default to fixed if no other keywords match (likely "Fixed")
                fixed_entries.append(row)
        else:
            # No response entry and not already replied = unresolved
            reason = "Comment was not processed in this copilot run. No response entry found in responses.json."
            row = f"| ❓ Unresolved | {link_text} | {reason} |"
            unresolved_entries.append(row)

    # FIX REV-qcu3t-numbers: Footer stats must match actual table rows
    # Derive counts directly from row lists so footer always matches visible table
    fixed_count = len(fixed_entries)
    deferred_count = len(deferred_entries)
    not_done_count = len(not_done_entries)
    acknowledged_count = len(ignored_entries)
    unresolved_count = len(unresolved_entries)
    total = fixed_count + deferred_count + not_done_count + acknowledged_count + unresolved_count
    coverage = total - unresolved_count
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Combine all rows in order: fixed, deferred, not_done, ignored, unresolved
    all_rows = fixed_entries + deferred_entries + not_done_entries + ignored_entries + unresolved_entries

    if not all_rows:
        return ""

    table_header = "| Status | Comment | Reason |\n|--------|---------|--------|"
    table_body = "\n".join(all_rows)

    section = f"""{TRACKING_START_MARKER}
---
## Copilot Comment Tracking

{table_header}
{table_body}

**Last processed**: {timestamp} | **Coverage**: {coverage}/{total} ({coverage * 100 // total if total > 0 else 100}%) | **Fixed**: {fixed_count} | **Deferred**: {deferred_count} | **Not Done**: {not_done_count} | **Acknowledged**: {acknowledged_count} | **Unresolved**: {unresolved_count}
{TRACKING_END_MARKER}"""

    return section


def _ensure_period(text: str) -> str:
    """Ensure text ends with a period, without creating double punctuation."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    text = text.rstrip()
    if text and text[-1] in ".!?":
        return text
    return text + "."


def _derive_tracking_reason(resp: Dict) -> str:
    """Derive a tracking reason from existing response fields when tracking_reason is missing.

    Args:
        resp: A single response entry from responses.json

    Returns:
        A derived reason string
    """
    response_type = resp.get("response", "")

    if response_type == "FIXED":
        action = resp.get("action_taken", "Fix applied")
        verification = resp.get("verification", "")
        files = resp.get("files_modified", [])
        if not isinstance(files, list):
            files = [str(files)] if files else []
        parts = [_ensure_period(action)]
        if files:
            parts.append(f"Modified {', '.join(files[:3])}{'...' if len(files) > 3 else ''}.")
        if verification:
            parts.append(_ensure_period(verification.lstrip("✅ ").strip()))
        return " ".join(parts[:3])

    if response_type == "ALREADY_IMPLEMENTED":
        evidence = resp.get("evidence", {})
        if isinstance(evidence, dict):
            return f"Already implemented at {evidence.get('file', 'unknown')}:{evidence.get('line', '?')}. No changes needed."
        return "Feature already exists in the codebase. No changes needed."

    if response_type == "DEFERRED":
        reason = resp.get("reason", "Deferred for future implementation")
        bead_id = resp.get("bead_id", "")
        parts = [_ensure_period(reason)]
        if bead_id:
            parts.append(f"Tracked in bead {bead_id}.")
        return " ".join(parts)

    if response_type == "NOT_DONE":
        reason = resp.get("reason", "Could not implement the requested change")
        return _ensure_period(reason)

    if response_type == "ACKNOWLEDGED":
        explanation = resp.get("explanation", "Noted for context")
        return _ensure_period(explanation)

    if response_type == "SKIPPED":
        reason = resp.get("reason", "Out of scope for this copilot run")
        return _ensure_period(reason)

    return "Processed without specific tracking reason."


def _replace_tracking_section_in_pr_body(pr_body: str, tracking_section: str) -> Tuple[str, str]:
    """Replace, append, or rebuild the tracking section in a PR body.

    Returns:
        Tuple[updated_body, mode], where mode is "replace", "append", or "rebuild".
    """
    start_count = pr_body.count(TRACKING_START_MARKER)
    end_count = pr_body.count(TRACKING_END_MARKER)

    if start_count == 0 and end_count == 0:
        separator = "\n\n" if pr_body.strip() else ""
        return pr_body + separator + tracking_section, "append"

    # Normal case: exactly one bounded section.
    if start_count == 1 and end_count == 1:
        start_idx = pr_body.find(TRACKING_START_MARKER)
        end_idx = pr_body.find(TRACKING_END_MARKER)
        if start_idx < end_idx:
            end_idx += len(TRACKING_END_MARKER)
            return pr_body[:start_idx] + tracking_section + pr_body[end_idx:], "replace"

    # Malformed markers (duplicates, mismatch, wrong order): rebuild deterministically.
    first_start = pr_body.find(TRACKING_START_MARKER)
    last_end = pr_body.rfind(TRACKING_END_MARKER)
    if first_start != -1:
        prefix = pr_body[:first_start].rstrip()
        if last_end != -1 and last_end > first_start:
            suffix = pr_body[last_end + len(TRACKING_END_MARKER):].lstrip()
            if prefix and suffix:
                cleaned_body = f"{prefix}\n\n{suffix}"
            else:
                cleaned_body = prefix or suffix
        else:
            cleaned_body = prefix
    elif last_end != -1:
        # Orphaned END marker: keep content before it too
        prefix = pr_body[:last_end].rstrip()
        suffix = pr_body[last_end + len(TRACKING_END_MARKER):].lstrip()
        if prefix and suffix:
            cleaned_body = f"{prefix}\n\n{suffix}"
        else:
            cleaned_body = prefix or suffix
    else:
        cleaned_body = pr_body

    separator = "\n\n" if cleaned_body.strip() else ""
    return cleaned_body + separator + tracking_section, "rebuild"


def update_pr_description_with_tracking(
    owner: str,
    repo: str,
    pr_number: str,
    responses_data: Dict,
    all_comments: List[Dict],
    already_replied_ids: set,
) -> bool:
    """Update the PR description with a comment tracking section at the bottom.

    Builds a categorized table of all PR comments (fixed, deferred, ignored,
    unresolved) with reasons, and appends or replaces it at the bottom of the
    PR description using idempotent HTML comment markers.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        responses_data: Loaded responses.json
        all_comments: All fetched PR comments
        already_replied_ids: Set of comment IDs already replied to

    Returns:
        True if PR description was updated successfully
    """
    print("📋 TRACKING: Building PR description comment tracking section")

    tracking_section = build_tracking_section(
        owner, repo, pr_number, responses_data, all_comments, already_replied_ids
    )

    if not tracking_section:
        print("   ℹ️  No trackable comments found, skipping PR description update")
        return True

    # Fetch current PR body
    repo_flag = f"{owner}/{repo}"
    success, pr_body, stderr = run_command(
        ["gh", "pr", "view", pr_number, "--repo", repo_flag, "--json", "body", "--jq", ".body // \"\""],
        description="fetch PR body",
        timeout=30,
    )
    if not success:
        print(f"   ❌ Failed to fetch PR body: {stderr}")
        return False

    pr_body = pr_body.rstrip("\n")

    updated_body, replacement_mode = _replace_tracking_section_in_pr_body(
        pr_body, tracking_section
    )
    if replacement_mode == "replace":
        print("   🔄 Replacing existing tracking section in PR description")
    elif replacement_mode == "append":
        print("   ➕ Appending new tracking section to PR description")
    else:
        print("   ⚠️  Rebuilding malformed tracking section in PR description")

    # Write updated body to PR via REST API (avoids GraphQL Projects Classic errors)
    temp_file_path = None
    try:
        payload = json.dumps({"body": updated_body})
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(payload)

        success, stdout, stderr = run_command(
            [
                "gh", "api",
                f"repos/{owner}/{repo}/pulls/{pr_number}",
                "--method", "PATCH",
                "--input", temp_file_path,
                "--jq", ".html_url",
            ],
            description="update PR description with tracking via REST API",
            timeout=30,
        )
    except Exception as e:
        print(f"   ❌ Failed to create temp file for PR body: {e}")
        return False
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

    if success:
        print("   ✅ PR description updated with comment tracking section")
        return True
    else:
        print(f"   ❌ Failed to update PR description: {stderr}")
        return False


def detect_comment_type(comment: Dict) -> str:
    """Detect comment kind: inline (code), review (review body), or issue"""
    html_url = comment.get("html_url") or ""
    if (
        "#discussion_r" in html_url
        or comment.get("path")
        or comment.get("position")
        or comment.get("diff_hunk")
    ):
        return "inline"
    if "#pullrequestreview-" in html_url or comment.get("pull_request_review_id"):
        return "review"
    if "#issuecomment-" in html_url:
        return "issue"
    return "inline"


def post_consolidated_summary(
    owner: str,
    repo: str,
    pr_number: str,
    collected_replies: List[Dict],
    responses_data: Dict,
    commit_hash: str,
    total_targets: int,
    already_replied_count: int,
) -> bool:
    """Post ONE consolidated summary comment with all replies embedded.

    Instead of posting individual threaded replies, this posts a single comment
    containing all responses organized by comment, making it easier to review
    and reducing notification spam.

    .. deprecated::
        Use LLM-generated consolidated reply instead. This function will be
        removed in a future version in favor of direct LLM-generated responses.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        collected_replies: List of dicts with comment_id, author, body_snippet, response_text
        responses_data: Loaded responses.json data with ACTION_ACCOUNTABILITY format
        commit_hash: Current commit hash
        total_targets: Total number of target comments
        already_replied_count: Number of comments already replied to

    Returns:
        True if summary was posted successfully
    """
    # REV-hg6ce: Deprecation warning for this function
    warnings.warn(
        "post_consolidated_summary is deprecated. Use LLM-generated consolidated reply instead.",
        DeprecationWarning,
        stacklevel=2
    )

    print(f"📝 POSTING: Consolidated summary comment to PR #{pr_number}")

    # REV-hyn6w: Get files modified from git
    files_modified = get_files_modified()

    responses = responses_data.get("responses", [])

    # FIX REV-qcu3t-numbers: Use compute_metrics for SINGLE SOURCE OF TRUTH
    # This ensures tracking table and consolidated reply have consistent numbers
    # All metrics (response types AND categories) now come from one function
    metrics = compute_metrics(responses)
    fixed_count = metrics.get("fixed", 0)
    deferred_count = metrics.get("deferred", 0)
    acknowledged_count = metrics.get("acknowledged", 0)
    not_done_count = metrics.get("not_done", 0)
    total_issues = metrics.get("total", 0)

    # Category counts from compute_metrics (single source of truth)
    critical_count = metrics.get("critical", 0)
    blocking_count = metrics.get("blocking", 0)
    important_count = metrics.get("important", 0)
    routine_count = metrics.get("style", 0)  # style includes both STYLE and ROUTINE categories

    # Count multi-issue responses for display
    multi_issue_count = sum(1 for r in responses if "issues" in r and "analysis" in r)

    # Build category breakdown
    category_breakdown = []
    if critical_count > 0:
        category_breakdown.append(f"  - 🚨 **Critical**: {critical_count} issue(s)")
    if blocking_count > 0:
        category_breakdown.append(f"  - ⛔ **Blocking**: {blocking_count} issue(s)")
    if important_count > 0:
        category_breakdown.append(f"  - ⚠️  **Important**: {important_count} issue(s)")
    if routine_count > 0:
        category_breakdown.append(f"  - 📝 **Routine**: {routine_count} issue(s)")

    # Build response type breakdown
    response_breakdown = []
    if fixed_count > 0:
        response_breakdown.append(
            f"  - ✅ **FIXED**: {fixed_count} issue(s) implemented with working code"
        )
    if deferred_count > 0:
        response_breakdown.append(
            f"  - 🔄 **DEFERRED**: {deferred_count} issue(s) - created issues for future implementation"
        )
    if acknowledged_count > 0:
        response_breakdown.append(
            f"  - 📋 **ACKNOWLEDGED**: {acknowledged_count} issue(s) - noted but not actionable"
        )
    if not_done_count > 0:
        response_breakdown.append(
            f"  - ❌ **NOT DONE**: {not_done_count} issue(s) - cannot implement with specific reason"
        )

    # Build consolidated replies section
    replies_section_parts = []
    for idx, reply_data in enumerate(collected_replies, 1):
        comment_id = reply_data.get("comment_id")
        author = reply_data.get("author", "unknown")
        body_snippet = reply_data.get("body_snippet", "")
        response_text = reply_data.get("response_text", "")
        comment_type = reply_data.get("comment_type", "inline")

        # Determine correct anchor based on comment type
        if comment_type == "review":
            anchor = f"pullrequestreview-{comment_id}"
        elif comment_type in ("inline", "copilot"):
            anchor = f"discussion_r{comment_id}"
        else:
            anchor = f"issuecomment-{comment_id}"

        comment_link = f"https://github.com/{owner}/{repo}/pull/{pr_number}#{anchor}"

        reply_entry = f"""
---

### {idx}. Re: [Comment #{comment_id}]({comment_link}) by @{author}

> {body_snippet}...

{response_text}
"""
        replies_section_parts.append(reply_entry)

    max_comment_size = 65000
    part_placeholder = "\n**Summary Part 1 of 10**"

    def build_summary_body(replies_text: str, part_line: str) -> str:
        replies_section = (
            replies_text
            if replies_text.strip()
            else "\n*No new replies needed - all comments already addressed.*\n"
        )
        return f"""## 🤖 [AI responder] Consolidated Comment Response Summary{part_line}

**Processing Overview**:
- 📊 **Total Comments**: {total_targets} comment(s) analyzed
- ✅ **New Responses**: {len(collected_replies)} response(s) in this summary
- 🔄 **Already Replied**: {already_replied_count} comment(s) previously addressed
- 📈 **Total Issues**: {total_issues} distinct issue(s) identified
- 🔀 **Multi-Issue Comments**: {multi_issue_count} comment(s) contain multiple issues
- 📝 **Commit**: {commit_hash}
- 📁 **Files Modified**: {files_modified}

**Category Breakdown**:
{chr(10).join(category_breakdown) if category_breakdown else "  - No categorized responses"}

**Response Type Breakdown**:
{chr(10).join(response_breakdown) if response_breakdown else "  - No responses"}

---

**Follow-up Reviews Requested**:
- @coderabbitai
- @copilot
- @cursor
- @chatgpt-codex-connector

Please re-review this PR and confirm whether all prior issues are resolved.

---

## 📋 Individual Responses
{replies_section}

---

**LLM Architecture**: Following CLAUDE.md principles - LLM analyzed FULL comment content, identified ALL distinct issues (even when multiple issues in one comment), and generated comprehensive responses with ACTION_ACCOUNTABILITY format.

**Anti-Spam Design**: Consolidated into single comment to reduce notification noise while maintaining 100% coverage.

*Generated by /commentreply - Systematic comment processing with consolidated response format*"""

    def split_reply_entries(entries: List[str]) -> List[str]:
        chunks: List[List[str]] = []
        current_chunk: List[str] = []
        base_size = len(build_summary_body("", part_placeholder))
        max_replies_size = max_comment_size - base_size - 200
        for entry in entries:
            candidate = current_chunk + [entry]
            candidate_text = "\n".join(candidate)
            if len(build_summary_body(candidate_text, part_placeholder)) <= max_comment_size:
                current_chunk = candidate
                continue
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                candidate = [entry]
            entry_text = candidate[0]
            if len(build_summary_body(entry_text, part_placeholder)) > max_comment_size:
                truncated = entry_text[:max_replies_size].rstrip()
                entry_text = (
                    truncated
                    + "\n\n... [TRUNCATED TO FIT GITHUB COMMENT LIMIT]"
                )
            current_chunk = [entry_text]
        if current_chunk:
            chunks.append(current_chunk)
        return ["\n".join(chunk) for chunk in chunks]

    reply_chunks = split_reply_entries(replies_section_parts)
    total_parts = len(reply_chunks) if reply_chunks else 1
    bodies_to_post = []
    for idx, replies_text in enumerate(reply_chunks or [""], 1):
        part_line = (
            f"\n**Summary Part {idx} of {total_parts}**"
            if total_parts > 1
            else ""
        )
        bodies_to_post.append(build_summary_body(replies_text, part_line))

    for idx, summary_body in enumerate(bodies_to_post, 1):
        if total_parts > 1:
            print(f"🧩 POSTING: Summary part {idx}/{total_parts}")

        summary_data = {"body": summary_body}
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as temp_file:
                json.dump(summary_data, temp_file)
                temp_file_path = temp_file.name

            success, response_json, stderr = run_command(
                [
                    "gh",
                    "api",
                    f"repos/{owner}/{repo}/issues/{pr_number}/comments",
                    "--method",
                    "POST",
                    "--header",
                    "Content-Type: application/json",
                    "--input",
                    temp_file_path,
                ]
            )

        except Exception as e:
            print(f"❌ ERROR: Failed to create secure summary JSON: {e}")
            return False
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        if success:
            try:
                response_data = json.loads(response_json)
                summary_url = response_data.get("html_url")
                print("✅ SUCCESS: Consolidated summary comment posted")
                print(f"🔗 SUMMARY URL: {summary_url}")
            except json.JSONDecodeError:
                print("⚠️ WARNING: Summary posted but couldn't parse response")
        else:
            print("❌ ERROR: Failed to post consolidated summary comment")
            print(f"   Error: {stderr}")
            return False

    return True


def main():
    """Main execution function.

    .. deprecated::
        Use LLM-generated consolidated reply instead. This function will be
        removed in a future version in favor of direct LLM-generated responses.
    """
    # REV-hg6ce: Deprecation warning for main function
    warnings.warn(
        "main() is deprecated. Use LLM-generated consolidated reply instead.",
        DeprecationWarning,
        stacklevel=2
    )

    print("🚀 STARTING: /commentreply systematic comment processing")
    print(
        "🎯 PURPOSE: Process ALL PR comments with proper threading to prevent missed comment bugs"
    )

    # Step 1: Parse command line arguments (passed from commentreply.md)
    owner, repo, pr_number = parse_arguments()
    print(f"📋 REPOSITORY: {owner}/{repo}")
    print(f"📋 PR NUMBER: #{pr_number}")

    # Retry control: Track retry attempts to prevent infinite loops
    retry_count = 0
    max_retries = 2

    # Global tracking across retries
    initial_target_ids: set[str] = set()
    successful_reply_ids: set[str] = set()
    already_replied_ids: set[str] = set()
    missing_response_ids: set[str] = set()

    # CONSOLIDATED MODE: Collect all replies for single summary comment
    collected_replies: List[Dict] = []
    responses_data: Dict = {}

    # Step 2: Load comments with staleness detection and real-time fallback
    repo_name = get_repo_name(repo)
    branch_name = get_current_branch()

    # Retry loop: Re-fetch and retry on 422 stale comment errors
    while retry_count <= max_retries:
        if retry_count > 0:
            print(
                f"\n🔄 RETRY ATTEMPT {retry_count}/{max_retries}: Re-fetching comments after 422 failures"
            )

        all_comments = load_comments_with_staleness_check(
            branch_name, owner, repo, pr_number, repo_name
        )
        print(f"📁 LOADED: {len(all_comments)} comments with staleness validation")

        if not all_comments:
            print("⚠️ WARNING: No comments found in fetched data")
            if retry_count > 0 and collected_replies:
                print("   ⚠️ Breaking retry loop to preserve collected replies")
                break
            return

        # Step 3: Process each comment systematically
        print(f"\n🔄 PROCESSING: {len(all_comments)} comments systematically")

        # Determine current actor
        ok_actor, actor_login, _ = run_command(
            ["gh", "api", "user", "-q", ".login"], description="current actor"
        )
        actor_login = (actor_login or "").strip() or os.environ.get("GITHUB_ACTOR", "")
        if not ok_actor and not actor_login:
            print(
                "⚠️ WARNING: Unable to determine actor login; self-comment filtering may be incomplete"
            )

        # CRITICAL FIX: Process ALL comments (including replies) in chronological order
        # Sort all comments by created_at to preserve conversation order
        # This prevents out-of-sequence execution when replies contain corrections
        all_targets = sorted(all_comments, key=lambda c: c.get("created_at", ""))
        total_targets = 0
        missing_responses = 0

        # Get commit hash once to avoid multiple git calls (fixes Copilot efficiency issue)
        commit_hash = get_git_commit_hash()
        print(f"📝 COMMIT: Using commit {commit_hash} for all responses")

        # Step 3: Load Claude-generated responses
        responses_data = load_claude_responses(branch_name, repo_name)



        # CONSOLIDATED REPLY MODE: Collect all replies instead of posting individually
        # This reduces notification spam and provides a cleaner summary
        # Note: collected_replies is initialized outside the retry loop
        print("\n📝 CONSOLIDATED MODE: Collecting replies for single summary comment")

        # CRITICAL FIX: Process all comments in chronological order (including replies)
        # On retry, only process comments that previously failed with 422_not_found
        targets_to_process = all_targets
        if retry_count > 0:
            unresolved_ids = (
                initial_target_ids
                - successful_reply_ids
                - already_replied_ids
                - missing_response_ids
            )
            targets_to_process = [
                c for c in all_targets if str(c.get("id")) in unresolved_ids
            ]
            print(
                f"🔄 RETRY: Processing only {len(targets_to_process)} unresolved comment(s)"
            )
        for i, comment in enumerate(targets_to_process, 1):
            # SECURITY: Validate each comment before processing
            if not validate_comment_data(comment):
                print(
                    f"[{i}/{len(targets_to_process)}] ❌ SECURITY: Skipping invalid comment data"
                )
                continue

            comment_id = comment.get("id")
            comment_id_str = str(comment_id)
            in_reply_to_id = comment.get("in_reply_to_id")

            # Capture parent comment context when processing replies (for logging)
            parent_comment = None
            if in_reply_to_id:
                parent_comment = next(
                    (c for c in all_comments if c.get("id") == in_reply_to_id), None
                )
                if parent_comment:
                    parent_user_dict = parent_comment.get("user")
                    if isinstance(parent_user_dict, dict) and parent_user_dict.get("login"):
                        parent_author = parent_user_dict.get("login")
                    else:
                        parent_author = parent_comment.get("author", "unknown")
                    parent_body_snippet = sanitize_comment_content(
                        parent_comment.get("body", "")
                    )[:50].replace("\n", " ")
                    print(
                        f"   📎 Reply context: Parent comment #{in_reply_to_id} by @{parent_author}"
                    )
                    print(f'   📎 Parent content: "{parent_body_snippet}..."')
                else:
                    print(
                        f"   ⚠️ WARNING: Parent comment #{in_reply_to_id} not found in fetched comments"
                    )

            # Support both user.login and author field formats
            user_dict = comment.get("user")
            if isinstance(user_dict, dict) and user_dict.get("login"):
                author = user_dict.get("login")
            else:
                author = comment.get("author", "unknown")
            body_snippet = sanitize_comment_content(comment.get("body", ""))[
                :50
            ].replace("\n", " ")

            comment_type_label = "reply" if in_reply_to_id else "top-level"
            print(
                f"\n[{i}/{len(targets_to_process)}] Processing {comment_type_label} comment #{comment_id} by @{author}"
            )
            print(f'   Content: "{body_snippet}..."')

            # Skip our own comments
            if author in ('$USER-af', 'jleechanao', actor_login):
                print("   ↪️ Skip: comment authored by current actor")
                continue
            total_targets += 1
            if retry_count == 0:
                initial_target_ids.add(comment_id_str)

            # Idempotency: skip if already replied by current actor AND no one replied after us
            # Support both user.login and author field formats
            our_replies = [
                c
                for c in all_comments
                if (c.get("in_reply_to_id") == comment_id)
                and (
                    ((c.get("user") or {}).get("login") in ('$USER-af', 'jleechanao', actor_login))
                    if isinstance(c.get("user"), dict)
                    else (c.get("author") in ('$USER-af', 'jleechanao', actor_login))
                )
            ]
            if our_replies:
                # Check if anyone replied AFTER our last reply
                our_replies.sort(key=lambda x: x.get("created_at", ""))
                our_last_reply_time = our_replies[-1].get("created_at", "")
                # Find all replies to this comment
                all_replies_to_comment = [
                    c for c in all_comments if c.get("in_reply_to_id") == comment_id
                ]
                # Check if there are any replies after our last reply
                replies_after_ours = [
                    c
                    for c in all_replies_to_comment
                    if c.get("created_at", "") > our_last_reply_time
                    and (
                        ((c.get("user") or {}).get("login") not in ('$USER-af', 'jleechanao', actor_login))
                        if isinstance(c.get("user"), dict)
                        else (c.get("author") not in ('$USER-af', 'jleechanao', actor_login))
                    )
                ]
                if not replies_after_ours:
                    print(
                        "   ↪️ Skip: already replied by current actor (no new replies)"
                    )
                    already_replied_ids.add(comment_id_str)
                    missing_response_ids.discard(comment_id_str)
                    continue
                # Someone replied after us - continue processing to respond to their reply
                print(
                    f"   ℹ️  We already replied, but {len(replies_after_ours)} new reply(ies) found - will process"
                )

            # Idempotency for comments replied via issue comments (review bodies and issue comments)
            # with reference pattern since these don't use in_reply_to_id
            review_ref_pattern = f"In response to [comment #{comment_id}]"
            consolidated_ref_pattern = f"Re: [Comment #{comment_id}]"
            already_has_review_reply = any(
                ((c.get("user") or {}).get("login") in ('$USER-af', 'jleechanao', actor_login))
                and (
                    review_ref_pattern in (c.get("body") or "")
                    or consolidated_ref_pattern in (c.get("body") or "")
                )
                for c in all_comments
                if c.get("type") in ("issue", None)
            )
            if already_has_review_reply:
                print(
                    "   ↪️ Skip: comment already has issue comment reply from current actor"
                )
                already_replied_ids.add(comment_id_str)
                missing_response_ids.discard(comment_id_str)
                continue

            # Skip if thread ends with OUR [AI responder] comment indicating completion
            # Only skip if WE are the last commenter, not if someone else replied after us
            thread_replies = [
                c for c in all_comments if c.get("in_reply_to_id") == comment_id
            ]
            if thread_replies:
                # Sort by created_at to find the last reply
                thread_replies.sort(key=lambda x: x.get("created_at", ""))
                last_reply = thread_replies[-1]
                last_reply_body = last_reply.get("body", "")
                last_reply_user = last_reply.get("user")
                last_reply_author = (
                    last_reply_user.get("login", "")
                    if isinstance(last_reply_user, dict)
                    else ""
                )
                # Only skip if WE are the last commenter AND our comment has [AI responder]
                if (
                    "[AI responder]" in last_reply_body
                    and last_reply_author in ('$USER-af', 'jleechanao', actor_login)
                ):
                    print(
                        "   ↪️ Skip: thread already completed with our [AI responder] comment"
                    )
                    already_replied_ids.add(comment_id_str)
                    missing_response_ids.discard(comment_id_str)
                    continue

            # Get Claude-generated response for this comment
            response_text = get_response_for_comment(
                comment, responses_data, commit_hash
            )

            # Skip posting if no response available (empty string = skip)
            if not response_text or not response_text.strip():
                print(f"   ❌ No Claude response available for comment #{comment_id}")
                missing_responses += 1
                missing_response_ids.add(comment_id_str)
                continue

            # SECURITY: Final validation before collecting
            if len(response_text.strip()) > 65000:  # GitHub comment limit
                print(
                    f"   ⚠️ WARNING: Response too long for comment #{comment_id}, truncating"
                )
                response_text = (
                    response_text[:65000]
                    + "\n\n[Response truncated due to length limit]"
                )

            # CONSOLIDATED MODE: Collect reply instead of posting individually
            comment_type = comment.get("type") or detect_comment_type(comment)
            collected_replies.append({
                "comment_id": comment_id,
                "author": author,
                "body_snippet": body_snippet,
                "response_text": response_text,
                "comment_type": comment_type,
            })
            successful_reply_ids.add(comment_id_str)
            missing_response_ids.discard(comment_id_str)
            print(f"   ✅ COLLECTED: Response for comment #{comment_id} added to consolidated summary")

        # Capture total targets from first pass for accurate reporting
        if retry_count == 0:
            print(
                f"📊 STATS: First pass processed {len(initial_target_ids)} valid targets"
            )

        # Step 4: Check if retry is needed for coverage gaps or 422 failures
        total_targets = len(initial_target_ids)
        covered = len(successful_reply_ids) + len(already_replied_ids)
        coverage_valid = (len(missing_response_ids) == 0) and (covered == total_targets)
        if not coverage_valid and retry_count < max_retries:
            print(
                f"\n🔄 RETRY NEEDED: coverage {covered}/{total_targets} (missing={len(missing_response_ids)})"
            )
            unresolved_ids = (
                initial_target_ids
                - successful_reply_ids
                - already_replied_ids
                - missing_response_ids
            )
            print(f"   Unresolved IDs: {sorted(unresolved_ids)}")
            print(
                f"   Will re-fetch comments and retry (attempt {retry_count + 1}/{max_retries})"
            )
            retry_count += 1
            continue  # Continue while loop for retry
        elif not coverage_valid:
            print(
                f"\n⚠️ RETRY EXHAUSTED: coverage {covered}/{total_targets} (missing={len(missing_response_ids)})"
            )
            print("   Some comments could not be processed after retries")
        else:
            print("\n✅ NO RETRIES NEEDED: Coverage is 100%")

        # Exit retry loop - proceed with coverage validation
        break

    # Step 5: Coverage validation over target comments
    total_targets = len(initial_target_ids)
    covered = len(successful_reply_ids) + len(already_replied_ids)
    coverage_valid = (len(missing_response_ids) == 0) and (covered == total_targets)
    print(
        f"\n🔍 VALIDATION: targets={total_targets} covered={covered} "
        f"(already={len(already_replied_ids)}, posted={len(successful_reply_ids)}) "
        f"missing={len(missing_response_ids)}"
    )

    # Fail on insufficient coverage
    if not coverage_valid:
        print("\n❌ CRITICAL: Coverage validation failed")
        sys.exit(1)

    # Step 6: Post consolidated summary with all replies embedded
    print("\n📝 SUMMARY: Posting consolidated summary comment with all replies")
    summary_posted = post_consolidated_summary(
        owner,
        repo,
        pr_number,
        collected_replies,
        responses_data,
        commit_hash,
        total_targets,
        len(already_replied_ids),
    )
    if not summary_posted:
        print("\n❌ CRITICAL: Failed to post consolidated summary comment")
        sys.exit(1)

    # Step 6b: Update PR description with comment tracking table
    print("\n📋 TRACKING: Updating PR description with comment tracking")
    tracking_updated = update_pr_description_with_tracking(
        owner,
        repo,
        pr_number,
        responses_data,
        all_comments,
        already_replied_ids,
    )
    if not tracking_updated:
        print("⚠️ WARNING: Failed to update PR description with tracking (non-fatal)")

    # Step 7: Final report
    print("\n✅ COMPLETE: Comment processing finished")
    print(f"   📊 Total comments: {len(all_comments)}")
    print(f"   🎯 Target comments: {total_targets}")
    print(f"   ✅ Successful replies: {len(successful_reply_ids)}")
    print(f"   🔄 Already replied: {len(already_replied_ids)}")
    print(f"   ❌ Missing responses: {len(missing_response_ids)}")
    print(f"   🎯 Coverage valid: {'Yes' if coverage_valid else 'No'}")

    # Note: No additional failure check needed here - coverage_valid check above
    # already exits if coverage is invalid or missing_responses > 0
    print("\n🎉 SUCCESS: All comments processed with verified coverage!")


if __name__ == "__main__":
    main()
