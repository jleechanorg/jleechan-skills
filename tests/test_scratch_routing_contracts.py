import importlib.util
import json
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

    def test_comment_fetch_and_reply_roundtrip_uses_same_non_tmp_root(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory) / "canonical-scratch"
            root.mkdir()
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root),                  mock.patch.object(commentreply, "resolve_scratch_root", return_value=root),                  mock.patch.object(commentfetch.CommentFetch, "_get_pr_author", return_value=None),                  mock.patch.object(
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
            with mock.patch.object(commentreply, "resolve_scratch_root", return_value=root):
                loaded = commentreply.load_claude_responses("feature/roundtrip", "jleechan-skills")
            self.assertEqual(loaded["responses"][0]["comment_id"], 1)
            self.assertTrue(str(fetcher.cache_dir).startswith(str(root)))
            self.assertFalse(str(fetcher.cache_dir).startswith("/tmp/"))

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


if __name__ == "__main__":
    unittest.main()
