#!/usr/bin/env python3
"""
commentfetch.py - Fetch all PR comments from GitHub

Extracts comments from all sources:
- Inline PR comments (code review comments)
- General PR comments (issue comments)
- Review comments
- Copilot suppressed comments

Based on copilot_comment_fetch.py from PR #796 but adapted for modular architecture.
"""

import sys
import argparse
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from .base import CopilotCommandBase
from .per_comment_cache import PerCommentCache
from .scratch_paths import copilot_cache_dir, copilot_cache_file


class CommentFetch(CopilotCommandBase):
    """Fetch all comments from a GitHub PR."""

    def __init__(self, pr_number: str, repo: str = None):
        """Initialize comment fetcher.

        Args:
            pr_number: GitHub PR number
            repo: Optional repository override (format: owner/repo). If not provided, uses current repo.
        """
        super().__init__(pr_number)
        # Override repo if provided (for cross-repo PR fetching)
        if repo:
            self.repo = repo
        self.comments = []

        # Get current branch for file path
        try:
            result = subprocess.run(['git', 'branch', '--show-current'],
                                  capture_output=True, text=True, check=True)
            branch_name = result.stdout.strip()
            # Sanitize branch name for filesystem safety - match shell's tr -cd '[:alnum:]._-'
            # Remove any character that is NOT alphanumeric, dot, underscore, or dash
            sanitized_branch = re.sub(r'[^a-zA-Z0-9._-]', '', branch_name) if branch_name else ""
            self.branch_name = sanitized_branch or "unknown-branch"
        except subprocess.CalledProcessError:
            # Use consistent fallback with base class
            self.branch_name = "unknown-branch"

        # Extract repo name from directory name to match shell scripts (basename of git root)
        try:
            git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).strip().decode('utf-8')
            repo_name = os.path.basename(git_root)
        except Exception:
            # Fallback to splitting repo string if git command fails
            repo_name = self.repo.split('/')[-1] if '/' in self.repo else self.repo

        # Sanitize repo name to match shell's tr -cd '[:alnum:]._-' (filesystem-safe)
        sanitized_repo = re.sub(r'[^a-zA-Z0-9._-]', '', repo_name) if repo_name else ""
        self.repo_name = sanitized_repo or "unknown-repo"

        # Set cache directory and initialize per-comment cache
        self.cache_dir = copilot_cache_dir(self.repo_name, self.branch_name)
        self.output_file = copilot_cache_file(
            self.repo_name, self.branch_name, "comments.json"
        )
        self.cache_metadata_file = self.cache_dir / "cache_metadata.json"
        self.per_comment_cache = PerCommentCache(self.cache_dir)

        # Fetch PR author for filtering out own coordination comments
        self.pr_author = self._get_pr_author()

    def _get_pr_author(self) -> str | None:
        """Fetch the PR author's username.

        Returns:
            PR author's username, or None if unable to fetch
        """
        try:
            cmd = ['gh', 'pr', 'view', self.pr_number, '--repo', self.repo, '--json', 'author', '--jq', '.author.login']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            return result.stdout.strip()
        except Exception as e:
            self.log(f"Warning: Could not fetch PR author: {e}")
            return None

    def _get_inline_comments(self, since: str = None) -> List[Dict[str, Any]]:
        """Fetch inline code review comments.

        Args:
            since: Optional ISO8601 timestamp to fetch only comments created/updated after this time
        """
        self.log("Fetching inline PR comments...")

        comments = []
        # Fetch all comments with pagination
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo}/pulls/{self.pr_number}/comments",
            "--paginate",
        ]

        # Add incremental fetch parameters if since timestamp provided
        if since:
            cmd.extend(["-F", f"since={since}"])
            cmd.extend(["-F", "sort=updated"])  # Sort by updated to catch edits
            cmd.extend(["-F", "direction=desc"])  # Newest first for early exit detection
            self.log(f"Incremental fetch: only comments since {since}")

        page_comments = self.run_gh_command(cmd)
        if isinstance(page_comments, list):
            comments.extend(page_comments)

        # Standardize format
        standardized = []
        for comment in comments:
            standardized.append(
                {
                    "id": comment.get("id"),
                    "type": "inline",
                    "body": comment.get("body", ""),
                    "author": (comment.get("user") or {}).get("login", "unknown"),
                    "created_at": comment.get("created_at", ""),
                    "html_url": comment.get("html_url", ""),
                    "file": comment.get("path"),
                    "line": comment.get("line") or comment.get("original_line"),
                    "position": comment.get("position"),
                    "in_reply_to_id": comment.get("in_reply_to_id"),
                    "requires_response": self._requires_response(comment),
                    "already_replied": self._check_already_replied(comment, comments),
                }
            )

        return standardized

    def _get_general_comments(self, since: str = None) -> List[Dict[str, Any]]:
        """Fetch general PR comments (issue comments).

        Args:
            since: Optional ISO8601 timestamp to fetch only comments created/updated after this time
        """
        self.log("Fetching general PR comments...")

        cmd = [
            "gh",
            "api",
            f"repos/{self.repo}/issues/{self.pr_number}/comments",
            "--paginate",
        ]

        # Add incremental fetch parameters if since timestamp provided
        if since:
            cmd.extend(["-F", f"since={since}"])
            cmd.extend(["-F", "sort=updated"])  # Sort by updated to catch edits
            cmd.extend(["-F", "direction=desc"])  # Newest first
            self.log(f"Incremental fetch: only comments since {since}")

        comments = self.run_gh_command(cmd)
        if not isinstance(comments, list):
            return []

        # Standardize format
        standardized = []
        for comment in comments:
            standardized.append(
                {
                    "id": comment.get("id"),
                    "type": "general",
                    "body": comment.get("body", ""),
                    "author": (comment.get("user") or {}).get("login", "unknown"),
                    "created_at": comment.get("created_at", ""),
                    "html_url": comment.get("html_url", ""),
                    "requires_response": self._requires_response(comment),
                    "already_replied": self._check_already_replied_general(comment, self.comments),
                }
            )

        return standardized

    def _get_review_comments(self, since: str = None) -> List[Dict[str, Any]]:
        """Fetch PR review comments.

        Args:
            since: Optional ISO8601 timestamp to fetch only reviews submitted after this time
        """
        self.log("Fetching PR reviews...")

        cmd = [
            "gh",
            "api",
            f"repos/{self.repo}/pulls/{self.pr_number}/reviews",
            "--paginate",
        ]

        # Note: GitHub reviews API doesn't support 'since' parameter directly
        # We'll filter after fetching
        # TODO: Consider using timestamps endpoint for more efficient filtering

        reviews = self.run_gh_command(cmd)
        if not isinstance(reviews, list):
            return []

        # If since timestamp provided, filter reviews client-side
        if since:
            # datetime is already imported at module level
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            filtered_reviews = []
            for review in reviews:
                submitted_at = review.get("submitted_at", "")
                if submitted_at:
                    try:
                        review_dt = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
                        if review_dt > since_dt:
                            filtered_reviews.append(review)
                    except (ValueError, AttributeError):
                        # Include review if we can't parse date (be conservative)
                        filtered_reviews.append(review)
                else:
                    # Include review if no timestamp (be conservative, e.g. pending/unknown)
                    filtered_reviews.append(review)
            reviews = filtered_reviews
            self.log(f"Filtered to {len(reviews)} reviews since {since}")

        # Extract review body comments
        standardized = []
        for review in reviews:
            if review.get("body"):
                standardized.append(
                    {
                        "id": review.get("id"),
                        "type": "review",
                        "body": review.get("body", ""),
                        "author": (review.get("user") or {}).get("login", "unknown"),
                        "created_at": review.get("submitted_at", ""),
                        "html_url": review.get("html_url", ""),
                        "state": review.get("state"),
                        "requires_response": self._requires_response(review),
                        "already_replied": self._check_already_replied_review(review, self.comments),
                    }
                )

        return standardized

    def _get_copilot_comments(self) -> List[Dict[str, Any]]:
        """Fetch Copilot suppressed comments if available."""
        self.log("Checking for Copilot comments...")

        # Try to get Copilot-specific comments using jq filtering with pagination
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo}/pulls/{self.pr_number}/comments",
            "--paginate",
            "--jq",
            '.[] | select(.user.login == "github-advanced-security[bot]" or .user.type == "Bot") | select((.body|ascii_downcase) | contains("copilot"))',
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if result.returncode == 0 and result.stdout.strip():
                # Parse JSONL output
                comments = []
                for line in result.stdout.strip().split("\n"):
                    try:
                        comments.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

                # Standardize format
                standardized = []
                for comment in comments:
                    standardized.append(
                        {
                            "id": comment.get("id"),
                            "type": "copilot",
                            "body": comment.get("body", ""),
                            "author": "copilot",
                            "created_at": comment.get("created_at", ""),
                            "html_url": comment.get("html_url", ""),
                            "file": comment.get("path"),
                            "line": comment.get("line"),
                            "suppressed": True,
                            "requires_response": True,  # Copilot comments usually need attention
                            "already_replied": False,  # Copilot comments are typically unresponded
                        }
                    )

                return standardized
        except subprocess.TimeoutExpired:
            self.log("Could not fetch Copilot comments: timed out")
        except Exception as e:
            self.log(f"Could not fetch Copilot comments: {e}")

        return []

    def _save_cache_metadata(self, comment_count: int, fetched_at: str) -> None:
        """Save cache metadata to track freshness.

        Args:
            comment_count: Number of comments in cache
            fetched_at: Timestamp when comments were fetched
        """
        # Get TTL from env var or default to 300 seconds (5 minutes)
        try:
            ttl = int(os.environ.get("COPILOT_CACHE_TTL_SECONDS", 300))
        except (TypeError, ValueError):
            ttl = 300
            self.log("Invalid COPILOT_CACHE_TTL_SECONDS value; using default 300s")
        
        # Get PR head SHA to invalidate cache on PR updates
        try:
            result = subprocess.run(
                ['gh', 'pr', 'view', self.pr_number, '--json', 'headRefOid', '--jq', '.headRefOid'],
                capture_output=True, text=True, check=True
            )
            pr_head_sha = result.stdout.strip()
        except Exception:
            pr_head_sha = "unknown"
        
        metadata = {
            "last_fetch_timestamp": fetched_at,
            "comment_count": comment_count,
            "pr_number": self.pr_number,
            "cache_ttl_seconds": ttl,
            "repo": self.repo,
            "pr_head_sha": pr_head_sha
        }

        try:
            with open(self.cache_metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            self.log(f"Cache metadata saved to {self.cache_metadata_file}")
        except Exception as e:
            self.log_error(f"Failed to save cache metadata: {e}")

    def _requires_response(self, comment: Dict[str, Any]) -> bool:
        """Filter out meta-comments to prevent recursive processing.

        Excludes "CLAUDE RESPONSE NEEDED" meta-comments while including actual
        technical review comments that need responses.

        Args:
            comment: Comment data

        Returns:
            False for meta-comments, True for actual technical comments
        """
        body = str(comment.get("body") or "")
        author = comment.get("author")
        if isinstance(author, dict):
            author = author.get("login") or ""
        elif author is None:
            author = ""
        if not author:
            author = (comment.get("user") or {}).get("login") or ""
        text = body.strip()

        # Skip empty comments
        if not text:
            return False

        # Skip PR author's coordination/command comments (like /smoke or @bot mentions)
        # but keep substantive review responses and code discussion questions.
        if self.pr_author and author and str(author) == self.pr_author:
            # Only filter if it matches command/coordination patterns
            text_lower = text.lower()
            # Check for slash commands (e.g., /smoke, /test, /deploy)
            if text_lower.startswith('/'):
                return False
            # Check for bot mention patterns (e.g., @coderabbitai, @coderabbit-ai, @bot)
            # Only check the first @-mention, not the entire comment body
            if text_lower.startswith('@'):
                # Extract first @-mention (first word starting with @)
                first_mention = text_lower.split()[0] if text_lower.split() else ''
                # Structural markers — unambiguous, safe for substring matching
                if '[bot]' in first_mention or '-bot' in first_mention:
                    return False
                # Known bot service names — use word-boundary regex to avoid
                # false positives (e.g. @precursor_dev matching 'cursor')
                bot_service_names = ['coderabbitai', 'coderabbit', 'copilot', 'codex', 'cursor', 'bugbot', 'greptile']
                bot_pattern = re.compile(
                    r'@(?:.*[\W_])?(' + '|'.join(bot_service_names) + r')(?:[\W_]|$)',
                    re.IGNORECASE,
                )
                if bot_pattern.match(first_mention):
                    return False
                # Also catch @user-bot, @user_bot patterns (separator required
                # to avoid @abbott, @robotnik false positives)
                if re.match(r'^@\w+[-_.]bot$', first_mention, re.IGNORECASE):
                    return False

        # Skip our own AI responder comments
        if self._is_ai_responder_comment(body, author):
            return False

        # Skip bot replies in existing threads (avoid double-counting threaded bot analyses)
        if comment.get("in_reply_to_id") and str(author).endswith("[bot]"):
            return False

        # Skip meta-comments created by previous commentreply runs
        if "CLAUDE RESPONSE NEEDED" in body and "No Claude-generated response found" in body:
            return False
        if text.startswith("[AI responder]"):
            return False

        # Skip comments that are just quotes of other comments
        lines = text.strip().split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        if (len(non_empty_lines) <= 5 and
            all(line.strip().startswith("> ") for line in non_empty_lines if line.strip())):
            return False

        # Include actual technical comments that need responses
        return True

    def _check_already_replied(self, comment: Dict[str, Any], all_comments: List[Dict[str, Any]]) -> bool:
        """Check if an inline comment has been replied to.

        Args:
            comment: The comment to check
            all_comments: All comments to search for replies

        Returns:
            True if comment has replies, False otherwise
        """
        comment_id = str(comment.get("id", ""))
        if not comment_id:
            return False

        # Check if any comment has this comment as in_reply_to
        for other_comment in all_comments:
            if str(other_comment.get("in_reply_to_id", "")) == comment_id:
                return True

        # Consolidated reply mode: treat a later [AI responder] summary comment that explicitly
        # references this comment ID (e.g. "Re: [Comment #<id>]") as a response. This avoids
        # requiring hundreds of per-inline threaded replies when commentreply runs in
        # anti-spam consolidated mode.
        created_at = comment.get("created_at", "")
        for other_comment in all_comments:
            other_body = str(other_comment.get("body", ""))
            other_author = other_comment.get("author", "")
            if (
                self._is_ai_responder_comment(other_body, other_author)
                and other_comment.get("created_at", "") > created_at
            ):
                # Check for comment ID references (case-insensitive)
                other_body_lower = other_body.lower()
                if f"comment #{comment_id}" in other_body_lower or f"#{comment_id}" in other_body_lower or f"discussion_r{comment_id}" in other_body_lower:
                    return True
                # Check for content similarity or reply patterns (consistent with general/review)
                if self._appears_to_be_reply_to(other_comment, comment):
                    return True

        return False

    def _check_already_replied_general(self, comment: Dict[str, Any], all_comments: List[Dict[str, Any]] = None) -> bool:
        """Check if a general comment has been replied to.

        Enhanced detection using cross-comment type checking and robust AI responder pattern matching.

        Args:
            comment: The comment to check
            all_comments: All comments from all sources to search for replies

        Returns:
            True if comment has replies, False otherwise
        """
        comment_id = str(comment.get("id", ""))
        if not comment_id:
            return False

        # Check if comment body indicates it's a response using robust pattern matching
        body = str(comment.get("body", ""))
        author = comment.get("author", "")

        # Enhanced AI responder detection with robust pattern matching
        if self._is_ai_responder_comment(body, author):
            return True

        # Cross-comment type threading detection
        if all_comments:
            for other_comment in all_comments:
                # Check direct threading via in_reply_to_id
                if str(other_comment.get("in_reply_to_id", "")) == comment_id:
                    return True

                # Check if other comment references this comment ID
                other_body = str(other_comment.get("body", ""))
                if f"#{comment_id}" in other_body or f"comment #{comment_id}" in other_body:
                    return True

                # Check if it's an AI responder reply to this comment's content
                if (self._is_ai_responder_comment(other_body, other_comment.get("author", "")) and
                    other_comment.get("created_at", "") > comment.get("created_at", "")):
                    # Look for content similarity or reply patterns
                    if self._appears_to_be_reply_to(other_comment, comment):
                        return True

        return False

    def _check_already_replied_review(self, review: Dict[str, Any], all_comments: List[Dict[str, Any]] = None) -> bool:
        """Check if a review comment has been replied to.

        Enhanced detection using cross-comment type checking and robust pattern matching.

        Args:
            review: The review to check
            all_comments: All comments from all sources to search for replies

        Returns:
            True if review has replies, False otherwise
        """
        review_id = str(review.get("id", ""))
        author = review.get("author", "")
        body = str(review.get("body", ""))

        # Enhanced AI responder detection
        if self._is_ai_responder_comment(body, author):
            return True

        # Cross-comment type threading detection
        if all_comments:
            for other_comment in all_comments:
                # Check direct threading
                if str(other_comment.get("in_reply_to_id", "")) == review_id:
                    return True

                # Check for AI responder replies
                other_body = str(other_comment.get("body", ""))
                if (self._is_ai_responder_comment(other_body, other_comment.get("author", "")) and
                    other_comment.get("created_at", "") > review.get("created_at", "")):
                    if self._appears_to_be_reply_to(other_comment, review):
                        return True

        return False

    def _is_ai_responder_comment(self, body: str, author: str) -> bool:
        """Enhanced AI responder detection with robust pattern matching.

        Args:
            body: Comment body text
            author: Comment author

        Returns:
            True if this appears to be an AI responder comment
        """
        if not body or not author:
            return False

        # Normalize text for pattern matching
        normalized_body = body.strip().lower()

        # Check for our specific author and AI responder patterns
        if author == "jleechan2015":
            # Multiple pattern variations to catch all AI responder formats
            ai_patterns = [
                "[ai responder]",
                "[ ai responder ]",
                "[ai responder] ✅",
                "✅ **",  # Common pattern in our responses
                "**analysis**:",  # Common technical response pattern
                "**fix applied**:",  # Common fix response pattern
                "**security analysis complete**",  # Security response pattern
                "**test infrastructure verified**"  # Test response pattern
            ]

            for pattern in ai_patterns:
                if pattern in normalized_body:
                    return True

        return False

    def _appears_to_be_reply_to(self, potential_reply: Dict[str, Any], original_comment: Dict[str, Any]) -> bool:
        """Check if a comment appears to be a reply to another comment.

        Args:
            potential_reply: Comment that might be a reply
            original_comment: Original comment being replied to

        Returns:
            True if potential_reply appears to be responding to original_comment
        """
        reply_body = str(potential_reply.get("body", "")).lower()
        original_body = str(original_comment.get("body", "")).lower()

        # Check for direct references to original comment
        original_id = str(original_comment.get("id", ""))
        if f"#{original_id}" in reply_body or f"comment #{original_id}" in reply_body:
            return True

        # Check for quoted content from original comment
        original_lines = original_body.split('\n')[:3]  # First few lines
        for line in original_lines:
            line = line.strip()
            if len(line) > 10 and line in reply_body:
                return True

        return False

    def _get_ci_status(self) -> Dict[str, Any]:
        """Fetch GitHub CI status using /fixpr methodology.

        Uses GitHub as authoritative source for CI status.
        Implements defensive programming patterns from /fixpr.

        Returns:
            Dict with CI status information
        """
        try:
            # Use /fixpr methodology: GitHub is authoritative source
            cmd = [
                'gh', 'pr', 'view', self.pr_number,
                '--repo', self.repo,
                '--json', 'statusCheckRollup,mergeable,mergeStateStatus'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
            pr_data = json.loads(result.stdout)

            # Defensive programming: statusCheckRollup is often a LIST
            status_checks = pr_data.get('statusCheckRollup', [])
            if not isinstance(status_checks, list):
                status_checks = [status_checks] if status_checks else []

            # Process checks with safe access patterns from /fixpr
            checks = []
            failing_checks = []
            pending_checks = []
            passing_checks = []

            for check in status_checks:
                if not isinstance(check, dict):
                    continue

                # Prefer conclusion (for completed check runs). Fall back to state (contexts), then UNKNOWN.
                status_value = (check.get('conclusion') or check.get('state') or 'UNKNOWN')
                check_info = {
                    'name': check.get('name', check.get('context', 'unknown')),
                    'status': status_value,
                    'description': check.get('description', ''),
                    'url': check.get('detailsUrl', ''),
                    'started_at': check.get('startedAt', ''),
                    'completed_at': check.get('completedAt', '')
                }
                checks.append(check_info)

                # Categorize for quick analysis with safe status normalization
                status_upper = (status_value or 'UNKNOWN').upper()
                # Treat failure-like outcomes as failing
                if status_upper in ['FAILURE', 'FAILED', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'ERROR', 'STALE']:
                    failing_checks.append(check_info)
                # Queue/progress states are pending
                elif status_upper in ['PENDING', 'IN_PROGRESS', 'QUEUED', 'REQUESTED', 'WAITING']:
                    pending_checks.append(check_info)
                # Only SUCCESS (and optionally NEUTRAL/SKIPPED) should count as passing
                elif status_upper in ['SUCCESS', 'NEUTRAL', 'SKIPPED']:
                    passing_checks.append(check_info)

            # Overall CI state assessment
            overall_state = 'UNKNOWN'
            if failing_checks:
                overall_state = 'FAILING'
            elif pending_checks:
                overall_state = 'PENDING'
            elif passing_checks and not failing_checks and not pending_checks:
                overall_state = 'PASSING'

            return {
                'overall_state': overall_state,
                'mergeable': pr_data.get('mergeable', None),
                'merge_state_status': pr_data.get('mergeStateStatus', 'unknown'),
                'checks': checks,
                'summary': {
                    'total': len(checks),
                    'passing': len(passing_checks),
                    'failing': len(failing_checks),
                    'pending': len(pending_checks)
                },
                'failing_checks': failing_checks,
                'pending_checks': pending_checks,
                'fetched_at': datetime.now(timezone.utc).isoformat()
            }

        except subprocess.TimeoutExpired:
            self.log("Error fetching CI status: timed out")
            return {
                'overall_state': 'ERROR',
                'error': "Failed to fetch CI status: timed out",
                'checks': [],
                'summary': {
                    'total': 0,
                    'passing': 0,
                    'failing': 0,
                    'pending': 0
                }
            }
        except subprocess.CalledProcessError as e:
            self.log(f"Error fetching CI status: {e}")
            return {
                'overall_state': 'ERROR',
                'error': f"Failed to fetch CI status: {e}",
                'checks': [],
                'summary': {'total': 0, 'passing': 0, 'failing': 0, 'pending': 0}
            }
        except json.JSONDecodeError as e:
            self.log(f"Error parsing CI status JSON: {e}")
            return {
                'overall_state': 'ERROR',
                'error': f"Failed to parse CI status: {e}",
                'checks': [],
                'summary': {'total': 0, 'passing': 0, 'failing': 0, 'pending': 0}
            }
        except Exception as e:
            self.log(f"Unexpected error fetching CI status: {e}")
            return {
                'overall_state': 'ERROR',
                'error': f"Unexpected error: {e}",
                'checks': [],
                'summary': {'total': 0, 'passing': 0, 'failing': 0, 'pending': 0}
            }

    def check_for_new_comments(self, since_timestamp: str) -> Dict[str, Any]:
        """Check if there are any new comments since the given timestamp.

        This is a lightweight operation that uses the 'since' parameter to fetch
        only comments created/updated after the cache timestamp. Returns immediately
        if no new comments found (early exit optimization).

        Args:
            since_timestamp: ISO8601 timestamp from cache_metadata.json

        Returns:
            Dict with 'has_new_comments' bool and 'new_count' int
        """
        self.log(f"🔍 Checking for new comments since {since_timestamp}")

        # Fetch comments from all sources with 'since' filter
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._get_inline_comments, since_timestamp): "inline",
                executor.submit(self._get_general_comments, since_timestamp): "general",
                executor.submit(self._get_review_comments, since_timestamp): "review",
            }

            new_comment_count = 0
            failed_checks = 0

            for future in as_completed(futures):
                data_type = futures[future]
                try:
                    result = future.result()
                    count = len(result)
                    if count > 0:
                        self.log(f"  Found {count} new {data_type} comment(s)")
                        new_comment_count += count
                except Exception as e:
                    self.log_error(f"Failed to check {data_type} comments: {e}")
                    failed_checks += 1

        # If API calls failed, we can't be sure about freshness
        if failed_checks > 0:
            self.log(f"⚠️  {failed_checks} API checks failed - assuming STALE for safety")
            return {
                "has_new_comments": True, # Force refresh
                "new_count": new_comment_count,
                "error": f"{failed_checks} API checks failed",
                "checked_at": datetime.now(timezone.utc).isoformat()
            }

        has_new = new_comment_count > 0

        if has_new:
            self.log(f"✅ Cache is STALE: {new_comment_count} new comment(s) found")
        else:
            self.log(f"✅ Cache is FRESH: No new comments since {since_timestamp}")

        return {
            "has_new_comments": has_new,
            "new_count": new_comment_count,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    def execute(self) -> Dict[str, Any]:
        """Execute comment fetching from all sources."""
        self.fetch_errors.clear()
        self.log(f"🔄 FETCHING FRESH COMMENTS for PR #{self.pr_number} from GitHub API")
        self.log("⚠️ NEVER reading from cache - always fresh API calls")
        self.log(f"📁 Will save to: {self.output_file}")

        # Fetch comments and CI status in parallel for speed
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._get_inline_comments): "inline",
                executor.submit(self._get_general_comments): "general",
                executor.submit(self._get_review_comments): "review",
                executor.submit(self._get_copilot_comments): "copilot",
                executor.submit(self._get_ci_status): "ci_status",
            }

            ci_status = None

            failed_sources = []
            for future in as_completed(futures):
                data_type = futures[future]
                try:
                    result = future.result()
                    if data_type == "ci_status":
                        ci_status = result
                        self.log(f"  Fetched CI status: {result.get('overall_state', 'unknown')}")
                    else:
                        # This is comment data
                        self.comments.extend(result)
                        self.log(f"  Found {len(result)} {data_type} comments")
                except Exception as e:
                    if data_type == "ci_status":
                        self.log_error(f"Failed to fetch CI status: {e}")
                        ci_status = {'overall_state': 'ERROR', 'error': str(e)}
                    else:
                        self.log_error(f"Failed to fetch {data_type} comments: {e}")
                        failed_sources.append(f"{data_type}: {e}")

        if failed_sources or self.fetch_errors:
            details = "; ".join(failed_sources + self.fetch_errors)
            raise RuntimeError(
                f"Fresh GitHub comment fetch failed; preserving existing cache: {details}"
            )

        # Sort by created_at (most recent first)
        self.comments.sort(key=lambda c: c.get("created_at", ""), reverse=True)

        # ENHANCED: Re-process already_replied status using cross-comment detection
        # This fixes the threading detection issue by checking all comment types together
        for comment in self.comments:
            if comment["type"] == "general":
                comment["already_replied"] = self._check_already_replied_general(comment, self.comments)
            elif comment["type"] == "review":
                comment["already_replied"] = self._check_already_replied_review(comment, self.comments)
            elif comment["type"] == "inline":
                comment["already_replied"] = self._check_already_replied(comment, self.comments)
            # copilot comments use the same logic as general comments
            elif comment["type"] == "copilot":
                comment["already_replied"] = self._check_already_replied_general(comment, self.comments)

        # Count comments needing responses that haven't been replied to yet
        unresponded_count = sum(
            1
            for c in self.comments
            if c.get("requires_response", True)
            and not c.get("already_replied", False)
        )

        # FIX REV-qcu3t-counting: Add standardized counts for single source of truth
        # Count unique comment IDs (deduplicated)
        unique_comment_ids = set(c.get("id") for c in self.comments if c.get("id"))
        unique_count = len(unique_comment_ids)

        # Count [AI responder] comments (these are skipped in requires_response)
        ai_responder_count = sum(
            1
            for c in self.comments
            if c.get("requires_response") == False
            and c.get("body", "").lstrip().startswith("[AI responder]")
        )

        # Count already replied (only comments that require response)
        already_replied_count = sum(1 for c in self.comments if c.get("already_replied", False) and c.get("requires_response", True))

        # Prepare data to save
        data = {
            "pr": self.pr_number,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "comments": self.comments,
            "ci_status": ci_status or {'overall_state': 'UNKNOWN', 'error': 'CI status not fetched'},
            "metadata": {
                # FIX REV-qcu3t-counting: Single source of truth for counts
                # All raw API comments from all sources
                "total": len(self.comments),
                # Unique comment IDs (deduplicated)
                "unique_count": unique_count,
                # Comments requiring response (excludes [AI responder] and meta-comments)
                "requires_response_count": sum(1 for c in self.comments if c.get("requires_response", True)),
                # Comments already replied to by current actor
                "already_replied_count": already_replied_count,
                # Comments still needing response
                "unresponded_count": unresponded_count,
                # [AI responder] comments count
                "ai_responder_count": ai_responder_count,
                "by_type": {
                    "inline": len(
                        [c for c in self.comments if c["type"] == "inline"]
                    ),
                    "general": len(
                        [c for c in self.comments if c["type"] == "general"]
                    ),
                    "review": len(
                        [c for c in self.comments if c["type"] == "review"]
                    ),
                    "copilot": len(
                        [c for c in self.comments if c["type"] == "copilot"]
                    ),
                },
                "repo": self.repo,
                # Documentation of count expectations
                "count_documentation": {
                    "total": "All raw API comments from inline + general + review + copilot sources",
                    "unique_count": "Deduplicated by comment ID - removes duplicate entries",
                    "requires_response_count": "Comments needing response - excludes [AI responder] and meta-comments",
                    "already_replied_count": "Comments that have replies from current actor",
                    "unresponded_count": "requires_response_count - already_replied_count",
                    "ai_responder_count": "Comments authored by current actor starting with [AI responder]",
                },
            },
        }

        # FIX REV-qcu3t-counting: Add validation that counts are consistent
        expected_unresponded = data["metadata"]["requires_response_count"] - already_replied_count
        if expected_unresponded != unresponded_count:
            self.log(f"⚠️  WARNING: Count mismatch detected!")
            self.log(f"   requires_response ({data['metadata']['requires_response_count']}) - already_replied ({already_replied_count}) = {expected_unresponded}")
            self.log(f"   But unresponded_count = {unresponded_count}")

        # Create directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Save using per-comment cache structure (new format)
        self.per_comment_cache.save_comments(
            self.comments,
            self.pr_number,
            data["fetched_at"],
            ci_status or {'overall_state': 'UNKNOWN', 'error': 'CI status not fetched'}
        )
        self.log(f"Comments saved to per-comment cache: {self.per_comment_cache.comments_dir}")

        # Also save legacy format for backward compatibility during migration
        with open(self.output_file, 'w') as f:
            json.dump(data, f, indent=2)
        self.log(f"Legacy format saved to {self.output_file}")

        # Save cache metadata
        self._save_cache_metadata(len(self.comments), data["fetched_at"])

        # Prepare result with CI status summary
        ci_summary = ""
        if ci_status:
            state = ci_status.get('overall_state', 'UNKNOWN')
            failing = len(ci_status.get('failing_checks', []))
            pending = len(ci_status.get('pending_checks', []))
            if failing > 0 and pending > 0:
                ci_summary = f", CI: {failing} failing, {pending} pending"
            elif failing > 0:
                ci_summary = f", CI: {failing} failing"
            elif pending > 0:
                ci_summary = f", CI: {pending} pending"
            else:
                ci_summary = f", CI: {state.lower()}"

        result = {
            "success": True,
            "message": f"Fetched {len(self.comments)} comments ({unresponded_count} unresponded){ci_summary} - saved to {self.output_file}",
            "data": data,
        }

        return result


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(description="Fetch all comments from a GitHub PR")
    parser.add_argument("pr_number", help="PR number to fetch comments from")
    parser.add_argument(
        "--output", "-o", default=None, help="No longer used - returns data directly"
    )

    args = parser.parse_args()

    fetcher = CommentFetch(args.pr_number)
    try:
        result = fetcher.execute()
        result["execution_time"] = fetcher.get_execution_time()

        # Output JSON data to stdout as documented
        print(json.dumps(result["data"], indent=2))

        # Log success to stderr so it doesn't interfere with JSON output
        print(f"[CommentFetch] ✅ Success: {result.get('message', 'Command completed')}", file=sys.stderr)

        return 0 if result.get("success") else 1
    except Exception as e:
        fetcher.log_error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
