import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LUNA_PATH = ROOT / ".claude/skills/luna/scripts/audit_prs.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit_prs = load_module("audit_prs_contract", LUNA_PATH)
sys.path.insert(0, str(ROOT / ".claude/commands"))
from _copilot_modules import commentfetch, scratch_paths
import commentreply


class ScratchRoutingContracts(unittest.TestCase):
    def test_luna_uses_canonical_resolver_and_propagates_failure(self):
        failed = subprocess.CompletedProcess(
            [str(audit_prs.SCRATCH_RESOLVER)], 75, stdout="", stderr="Scratch unavailable"
        )
        with mock.patch.object(audit_prs.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "canonical Scratch resolver failed"):
                audit_prs._scratch_root()

    def test_luna_keeps_required_pending_checks_pending(self):
        payload = {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "BLOCKED",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "name": "required-ci",
                 "status": "IN_PROGRESS", "conclusion": None}
            ],
            "files": [],
        }
        with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
            result = audit_prs.inspect_pr_status({"number": 7})
        self.assertEqual(result["category"], "PENDING_OR_BLOCKED")
        self.assertEqual(result["pending_checks"], ["required-ci"])

    def test_luna_green_requires_completed_required_checks_and_clean_merge_state(self):
        payload = {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "name": "required-ci",
                 "status": "COMPLETED", "conclusion": "SUCCESS"}
            ],
            "files": [],
        }
        with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
            result = audit_prs.inspect_pr_status({"number": 8})
        self.assertEqual(result["category"], "CLEAN_GREEN")
        self.assertEqual(result["pending_checks"], [])

    def test_luna_rejects_unknown_or_incomplete_required_entries(self):
        entries = [
            {"name": "missing-type", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "UnknownUnion", "name": "unknown-type", "status": "IN_PROGRESS"},
            {"__typename": "StatusContext", "name": "missing-state"},
            {"__typename": "CheckRun", "name": "missing-status", "conclusion": "SUCCESS"},
            {"__typename": "CheckRun", "name": "unknown-conclusion",
             "status": "COMPLETED", "conclusion": ""},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                payload = {
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "statusCheckRollup": [entry],
                    "files": [],
                }
                with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
                    result = audit_prs.inspect_pr_status({"number": 9})
                self.assertEqual(result["category"], "PENDING_OR_BLOCKED")
                self.assertIn(entry["name"], result["pending_checks"])

    def test_luna_accepts_both_github_check_union_variants(self):
        entries = [
            {"__typename": "StatusContext", "name": "status-context",
             "state": "SUCCESS"},
            {"__typename": "CheckRun", "name": "check-run",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                payload = {
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "statusCheckRollup": [entry],
                    "files": [],
                }
                with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
                    result = audit_prs.inspect_pr_status({"number": 10})
                self.assertEqual(result["category"], "CLEAN_GREEN")
                self.assertEqual(result["pending_checks"], [])

    def test_luna_keeps_unknown_merge_states_pending(self):
        for merge_state in ("BLOCKED", "UNKNOWN"):
            with self.subTest(merge_state=merge_state):
                payload = {
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": merge_state,
                    "statusCheckRollup": [
                        {"__typename": "CheckRun", "name": "required-ci",
                         "status": "COMPLETED", "conclusion": "SUCCESS"}
                    ],
                    "files": [],
                }
                with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
                    result = audit_prs.inspect_pr_status({"number": 11})
                self.assertEqual(result["category"], "PENDING_OR_BLOCKED")

    def test_luna_admits_report_scratch_before_provider_dispatch(self):
        item = {
            "number": 12,
            "title": "fixture",
            "branch": "fixture",
            "age_hours": 9,
            "url": "https://example.invalid/12",
            "category": "CLEAN_GREEN",
        }
        with mock.patch.object(
            audit_prs,
            "get_luna_review_dir",
            side_effect=RuntimeError("configured Scratch unavailable"),
        ), mock.patch.object(
            audit_prs.subprocess,
            "Popen",
            side_effect=AssertionError("provider must not be called"),
        ) as provider:
            with self.assertRaisesRegex(RuntimeError, "configured Scratch unavailable"):
                audit_prs.review_single_pr(item)
        provider.assert_not_called()

    def test_comment_fetch_and_reply_roundtrip_uses_same_non_tmp_root(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = (Path(directory) / "canonical-scratch").resolve()
            root.mkdir()
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root),                  mock.patch.object(commentfetch.CommentFetch, "_get_pr_author", return_value=None),                  mock.patch.object(
                     commentfetch.subprocess,
                     "run",
                     return_value=subprocess.CompletedProcess(
                         ["git"], 0, stdout="feature/roundtrip\n", stderr=""
                     ),
                 ),                  mock.patch.object(
                     commentfetch.subprocess,
                     "check_output",
                     return_value=b"/repo/jleechan-skills\n",
                 ):
                fetcher = commentfetch.CommentFetch("42", "owner/repo")
            self.assertNotEqual(fetcher.cache_dir, Path("/tmp"))
            fetcher.cache_dir.mkdir(parents=True, exist_ok=True)
            responses = fetcher.cache_dir / "responses.json"
            responses.write_text(json.dumps({"responses": [{"comment_id": 1, "response": "fixed"}]}))
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root):
                loaded = commentreply.load_claude_responses("feature/roundtrip", "jleechan-skills")
            self.assertEqual(loaded["responses"][0]["comment_id"], 1)
            self.assertTrue(str(fetcher.cache_dir).startswith(str(root)))
            self.assertFalse(str(fetcher.cache_dir).startswith("/tmp/"))

    def test_comment_docs_use_the_producer_path_and_response_filename(self):
        docs = [
            ROOT / ".claude/skills/commentcheck/SKILL.md",
            ROOT / ".claude/skills/commentfetch/SKILL.md",
            ROOT / ".claude/skills/commentreply/SKILL.md",
        ]
        for doc in docs:
            content = doc.read_text()
            self.assertNotIn("scratch-dir.sh tmp", content)
            self.assertIn("scratch-dir.sh", content)
        reply_doc = (ROOT / ".claude/skills/commentreply/SKILL.md").read_text()
        self.assertIn("responses.json", reply_doc)
        self.assertNotIn("replies.json", reply_doc)

        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            fixture = Path(directory).resolve()
            home = fixture / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {fixture / 'scratch'}\n")
            resolver.chmod(0o755)
            repo_name = "jleechan-skills"
            branch_name = "feature-roundtrip"
            reader_line = next(
                line.strip()
                for line in (ROOT / ".claude/skills/commentfetch/SKILL.md").read_text().splitlines()
                if line.strip().startswith("COPILOT_DIR=")
            )
            result = subprocess.run(
                ["bash", "-c", f"REPO_NAME={repo_name} BRANCH_NAME={branch_name}\n{reader_line}\nprintf '%s' \"$COPILOT_DIR\""],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = fixture / "scratch" / repo_name / branch_name / "copilot"
            self.assertEqual(Path(result.stdout), expected)

    def test_comment_paths_fail_closed_for_resolver_and_symlink_escape(self):
        with mock.patch.object(
            scratch_paths,
            "resolve_scratch_root",
            side_effect=RuntimeError("configured Scratch unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "configured Scratch unavailable"):
                scratch_paths.copilot_cache_dir("repo", "branch")
            with self.assertRaisesRegex(RuntimeError, "configured Scratch unavailable"):
                commentfetch.CommentFetch("42", "owner/repo")

        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = (Path(directory) / "canonical-scratch").resolve()
            root.mkdir()
            outside = (Path(directory) / "outside").resolve()
            outside.mkdir()
            (root / "repo").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root):
                with self.assertRaisesRegex(RuntimeError, "escaped canonical Scratch root"):
                    scratch_paths.copilot_cache_dir("repo", "branch")

    def test_web_advice_smoke_stops_on_configured_resolver_failure(self):
        script = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            chrome = fake_bin / "google-chrome"
            chrome.write_text("#!/bin/sh\nexit 99\n")
            chrome.chmod(0o755)
            claude_home = root / "claude"
            resolver = claude_home / "skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text("#!/bin/sh\necho configured Scratch unavailable >&2\nexit 75\n")
            resolver.chmod(0o755)
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    **__import__("os").environ,
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "CLAUDE_HOME": str(claude_home),
                    "DISKM_SCRATCH": str(root / "missing"),
                },
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("configured Scratch unavailable", result.stderr)

    def test_web_advice_smoke_falls_back_from_aside_to_chrome(self):
        script = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            fake_bin = root / "bin"
            fake_bin.mkdir()
            aside = fake_bin / "aside"
            aside.write_text("#!/bin/sh\necho aside unavailable >&2\nexit 1\n")
            aside.chmod(0o755)
            chrome = fake_bin / "google-chrome"
            chrome.write_text("#!/bin/sh\nprintf '%s\\n' '<title>Example Domain</title>'\n")
            chrome.chmod(0o755)
            claude_home = root / "claude"
            resolver = claude_home / "skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {root / 'scratch'}\n")
            resolver.chmod(0o755)
            (root / "scratch").mkdir()
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "CLAUDE_HOME": str(claude_home),
                },
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Aside REPL browser: DOWN", result.stdout)
        self.assertIn("Chrome headless browser: UP", result.stdout)

    def test_web_advice_smoke_stops_when_profile_allocation_fails(self):
        script = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            fake_bin = root / "bin"
            fake_bin.mkdir()
            aside = fake_bin / "aside"
            aside.write_text("#!/bin/sh\nexit 1\n")
            aside.chmod(0o755)
            marker = root / "chrome-invoked"
            chrome = fake_bin / "google-chrome"
            chrome.write_text(
                "#!/bin/sh\nprintf '%s\\n' invoked > \"$CHROME_MARKER\"\n"
                "printf '%s\\n' '<title>Example Domain</title>'\n"
            )
            chrome.chmod(0o755)
            mktemp = fake_bin / "mktemp"
            mktemp.write_text("#!/bin/sh\nexit 77\n")
            mktemp.chmod(0o755)
            claude_home = root / "claude"
            resolver = claude_home / "skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {root / 'scratch'}\n")
            resolver.chmod(0o755)
            (root / "scratch").mkdir()
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "CLAUDE_HOME": str(claude_home),
                    "CHROME_MARKER": str(marker),
                },
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertIn("profile allocation failed", result.stderr)
        self.assertFalse(marker.exists(), "Chrome must not run after profile allocation failure")

if __name__ == "__main__":
    unittest.main()
