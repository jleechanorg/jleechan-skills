#!/usr/bin/env python3
"""
base.py - Base class for modular copilot commands

Provides:
- Strong I/O contracts with JSON schemas
- Standardized error handling
- Common utilities for all commands
- Verification patterns from PR #796
"""

import json
import os
import re
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class CopilotCommandBase(ABC):
    """Base class for all modular copilot commands."""

    def __init__(self, pr_number: Optional[str] = None):
        """Initialize base command.

        Args:
            pr_number: GitHub PR number (optional for some commands)
        """
        self.pr_number = pr_number
        self.start_time = datetime.now()
        self.repo = self._get_repo_info()
        self.current_branch = self._get_current_branch()
        # Producers that persist fetched data can fail closed on any API error;
        # a valid empty response remains distinguishable from a failed command.
        self.fetch_errors: List[str] = []

        # No caching - always fetch fresh data from GitHub API

    def _get_repo_info(self) -> str:
        """Get repository info from GitHub CLI or git remote."""
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner"],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            return data["nameWithOwner"]
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
            # Fallback to git remote parsing
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                url = result.stdout.strip()
                if "github.com" in url:
                    if url.endswith(".git"):
                        url = url[:-4]
                    if url.startswith("http"):
                        return "/".join(url.split("/")[-2:])
                    elif ":" in url:
                        return url.split(":")[-1]
                    else:
                        return "/".join(url.split("/")[-2:])
            except subprocess.CalledProcessError:
                pass
            # Default fallback - use your-project.com as default repo
            return os.environ.get(
                "DEFAULT_REPO", os.environ.get("GITHUB_REPOSITORY", "your-project.com")
            )

    def _get_current_branch(self) -> str:
        """Get current git branch for branch-specific file naming."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                cwd=os.getcwd(),
            )
            branch_name = result.stdout.strip()
            return self._sanitize_branch_name(branch_name)
        except Exception:
            return "unknown-branch"

    def _sanitize_branch_name(self, branch_name: str) -> str:
        """Sanitize branch name using PR #941 standard pattern for consistency."""
        # PR #941 standard: Replace any non-alphanumeric, non-dot, non-underscore, non-dash with underscore
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", branch_name)
        # Remove leading dots/dashes for filesystem safety
        sanitized = re.sub(r"^[.-]+", "", sanitized)
        return sanitized or "unknown-branch"

    def run_gh_command(self, command: List[str]) -> Any:
        """Run GitHub CLI command and return parsed JSON.

        Handles pagination by flattening results with --jq when --paginate is present.

        Args:
            command: Command list for subprocess

        Returns:
            Parsed JSON response (list for paginated, dict/object for single page)
        """
        # Check if --paginate is in command (before modification)
        is_paginated = '--paginate' in command
        original_has_jq = '--jq' in command

        try:
            if is_paginated and not original_has_jq:
                # Add --jq to flatten paginated results
                # Find where --paginate is and insert --jq after it
                paginate_idx = command.index('--paginate')
                # Use --jq '.[]' to flatten all pages into single array
                command = command[:paginate_idx+1] + ['--jq', '.[]'] + command[paginate_idx+1:]

            result = subprocess.run(command, capture_output=True, text=True, check=True)
            if not result.stdout.strip():
                return [] if is_paginated else {}

            # For paginated with INJECTED --jq, output is JSONL (one JSON object per line)
            # We only use special parsing if WE added the --jq flag
            if is_paginated and not original_has_jq:
                items = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            items.append(json.loads(line))
                        except json.JSONDecodeError:
                            message = f"JSON parsing error in paginated response: {line[:120]}"
                            self.log_error(message)
                            self.fetch_errors.append(message)
                return items

            # Single JSON object/array OR user-provided --jq output
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                # Fallback for user-provided --jq that produces JSONL (e.g. --jq '.[]')
                if is_paginated and original_has_jq:
                    items = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            try:
                                items.append(json.loads(line))
                            except json.JSONDecodeError:
                                message = f"JSON parsing error in paginated response: {line[:120]}"
                                self.log_error(message)
                                self.fetch_errors.append(message)
                    return items
                raise

        except subprocess.CalledProcessError as e:
            message = f"GitHub CLI error: {e.stderr or e}"
            self.log_error(message)
            self.fetch_errors.append(message)
            return [] if is_paginated else {}
        except json.JSONDecodeError as e:
            message = f"JSON parsing error: {e}"
            self.log_error(message)
            self.fetch_errors.append(message)
            return [] if is_paginated else {}

    # JSON file operations removed - using stateless approach

    def log(self, message: str):
        """Log informational message with timestamp in CI environments."""
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{self.__class__.__name__}] {message}", file=sys.stderr)
        else:
            print(f"[{self.__class__.__name__}] {message}", file=sys.stderr)

    def log_error(self, message: str):
        """Log error message to stderr with timestamp in CI environments."""
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"[{timestamp}] [{self.__class__.__name__}] ERROR: {message}",
                file=sys.stderr,
            )
        else:
            print(f"[{self.__class__.__name__}] ERROR: {message}", file=sys.stderr)

    def get_execution_time(self) -> float:
        """Get execution time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """Execute the command logic.

        Returns:
            Result dictionary with standard fields:
            - success: bool
            - message: str
            - data: dict (command-specific)
            - execution_time: float
        """
        pass

    def run(self) -> int:
        """Run the command and handle errors.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        try:
            result = self.execute()
            result["execution_time"] = self.get_execution_time()

            # No file saving - stateless operation

            # Print summary
            if result.get("success"):
                self.log(f"✅ Success: {result.get('message', 'Command completed')}")
            else:
                self.log_error(f"❌ Failed: {result.get('message', 'Command failed')}")

            return 0 if result.get("success") else 1

        except Exception as e:
            self.log_error(f"Unexpected error: {e}")
            {
                "success": False,
                "message": str(e),
                "execution_time": self.get_execution_time(),
            }
            # No file saving - error logged to stderr
            return 1

    def run_ci_replica(self, script_path: str = "run_ci_replica.sh") -> Dict[str, Any]:
        """Run local CI replica and capture results.

        Args:
            script_path: Path to CI replica script

        Returns:
            Dict with CI results and any errors
        """
        self.log(f"Running local CI replica: {script_path}")

        try:
            # Try different locations for the script
            # Use Path.home() for cross-platform home directory detection
            home_dir = Path.home()
            project_name = os.environ.get("PROJECT_NAME", "your-project.com")
            script_locations = [
                script_path,
                f"./{script_path}",
                f"../../{script_path}",
                f"../../../{script_path}",
                str(home_dir / "projects" / project_name / "worktree_human2" / script_path),
            ]

            result = None
            for location in script_locations:
                if os.path.exists(location):
                    result = subprocess.run(
                        [location],
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 minute timeout
                    )
                    break

            if result is None:
                raise FileNotFoundError(
                    f"CI replica script not found in any location: {script_path}"
                )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "executed_at": datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            self.log_error("CI replica timed out after 5 minutes")
            return {
                "success": False,
                "error": "Timeout after 5 minutes",
                "executed_at": datetime.now().isoformat(),
            }
        except FileNotFoundError:
            self.log_error(f"CI replica script not found: {script_path}")
            return {
                "success": False,
                "error": f"Script not found: {script_path}",
                "executed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            self.log_error(f"CI replica failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "executed_at": datetime.now().isoformat(),
            }

    def compare_ci_results(
        self, github_ci: Dict[str, Any], local_ci: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare GitHub CI results with local CI replica results.

        Args:
            github_ci: Results from GitHub CI checks
            local_ci: Results from local CI replica

        Returns:
            Comparison dict with discrepancies highlighted
        """
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "match": github_ci.get("success") == local_ci.get("success"),
            "github_ci": github_ci,
            "local_ci": local_ci,
            "discrepancies": [],
        }

        # Check basic success/failure match
        if github_ci.get("success") != local_ci.get("success"):
            comparison["discrepancies"].append(
                {
                    "type": "status_mismatch",
                    "github": "passing" if github_ci.get("success") else "failing",
                    "local": "passing" if local_ci.get("success") else "failing",
                }
            )

        # Extract test results if available
        github_tests = self._extract_test_results(github_ci.get("stdout", ""))
        local_tests = self._extract_test_results(local_ci.get("stdout", ""))

        if github_tests != local_tests:
            comparison["discrepancies"].append(
                {
                    "type": "test_count_mismatch",
                    "github_tests": github_tests,
                    "local_tests": local_tests,
                }
            )

        return comparison

    def _extract_test_results(self, output: str) -> Dict[str, int]:
        """Extract test counts from CI output.

        Args:
            output: CI output text

        Returns:
            Dict with test counts
        """
        # Common test result patterns
        patterns = {
            "passed": r"(\d+) passed",
            "failed": r"(\d+) failed",
            "skipped": r"(\d+) skipped",
            "errors": r"(\d+) error",
        }

        results = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                results[key] = int(match.group(1))
            else:
                results[key] = 0

        return results


class VerificationMixin:
    """Mixin providing verification patterns from PR #796."""

    def log(self, message: str):
        """Log method for mixin - should be provided by base class."""
        print(f"[Verification] {message}")

    def log_error(self, message: str):
        """Log error for mixin - should be provided by base class."""
        print(f"[Verification] ERROR: {message}", file=sys.stderr)

    def verify_with_retry(
        self, verify_func, expected_result, max_attempts: int = 3, backoff_base: int = 5
    ) -> bool:
        """Verify with exponential backoff retry.

        Args:
            verify_func: Function that returns current state
            expected_result: Expected result to compare against
            max_attempts: Maximum retry attempts
            backoff_base: Base seconds for exponential backoff

        Returns:
            True if verification succeeds, False otherwise
        """
        for attempt in range(1, max_attempts + 1):
            current = verify_func()
            if current == expected_result:
                self.log(f"✅ Verification passed (attempt {attempt})")
                return True

            if attempt < max_attempts:
                wait_time = backoff_base * attempt
                time.sleep(wait_time)

        self.log_error(f"❌ Verification failed after {max_attempts} attempts")
        return False
