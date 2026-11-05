import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "luna_audit_prs", ROOT / ".claude/skills/luna/scripts/audit_prs.py"
)
audit_prs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_prs
SPEC.loader.exec_module(audit_prs)


class LunaReportContainmentTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(dir="/var/tmp")
        root = Path(temp.name).resolve()
        scratch = root / "scratch"
        scratch.mkdir()
        return temp, root, scratch

    def item(self):
        return {
            "number": 7,
            "title": "fixture",
            "branch": "fixture",
            "age_hours": 9.0,
            "url": "https://example.invalid/7",
            "category": "CLEAN_GREEN",
        }

    def test_directory_escape_rejected_before_creation(self):
        temp, root, scratch = self.fixture()
        with temp:
            outside = root / "outside"
            outside.mkdir()
            (scratch / "worldarchitect.ai").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(audit_prs, "_scratch_root", return_value=str(scratch)):
                with self.assertRaisesRegex(RuntimeError, "outside Scratch"):
                    audit_prs.get_luna_review_dir()
            self.assertFalse((outside / "luna-reviews").exists())

    def test_dispatch_rejects_directory_escape_before_provider_dispatch(self):
        temp, root, scratch = self.fixture()
        with temp:
            outside = root / "outside"
            outside.mkdir()
            (scratch / "worldarchitect.ai").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(audit_prs, "_scratch_root", return_value=str(scratch)), \
                    mock.patch.object(audit_prs, "run_cmd") as run_cmd:
                with self.assertRaises(RuntimeError):
                    audit_prs.dispatch_review(7)
            run_cmd.assert_not_called()

    def test_review_rejects_leaf_symlink_before_provider_dispatch(self):
        temp, root, scratch = self.fixture()
        with temp:
            report_dir = scratch / "worldarchitect.ai/luna-reviews"
            report_dir.mkdir(parents=True)
            outside = root / "outside"
            outside.mkdir()
            target = outside / "escaped.md"
            target.write_text("sentinel")
            (report_dir / "PR_7_review.md").symlink_to(target)
            with mock.patch.object(audit_prs, "_scratch_root", return_value=str(scratch)), \
                    mock.patch.object(audit_prs, "run_cmd") as run_cmd, \
                    mock.patch.object(audit_prs.subprocess, "Popen") as popen:
                with self.assertRaises(RuntimeError):
                    audit_prs.review_single_pr(self.item(), report_dir=str(report_dir))
            run_cmd.assert_not_called()
            popen.assert_not_called()
            self.assertEqual(target.read_text(), "sentinel")

    def test_parallel_master_report_rejects_escape_before_provider_dispatch(self):
        temp, root, scratch = self.fixture()
        with temp:
            outside = root / "outside"
            outside.mkdir()
            with mock.patch.object(audit_prs, "get_stale_prs", return_value=[self.item()]), \
                    mock.patch.object(audit_prs, "inspect_pr_status", side_effect=lambda item, repo=None: item), \
                    mock.patch.object(audit_prs, "get_luna_review_dir", return_value=str(outside)), \
                    mock.patch.object(audit_prs, "review_single_pr") as review:
                with mock.patch.object(sys, "argv", ["audit_prs.py", "--parallel"]):
                    with self.assertRaises(RuntimeError):
                        audit_prs.main()
            review.assert_not_called()

    def test_inward_alias_is_canonicalized_inside_scratch(self):
        temp, root, scratch = self.fixture()
        with temp:
            real_dir = scratch / "worldarchitect.ai/luna-reviews"
            real_dir.mkdir(parents=True)
            alias = scratch / "alias"
            alias.symlink_to(scratch / "worldarchitect.ai", target_is_directory=True)
            with mock.patch.object(audit_prs, "_scratch_root", return_value=str(scratch)):
                report = audit_prs._safe_report_path(str(alias / "luna-reviews"), "PR_7_review.md")
                audit_prs._write_report_file(str(alias / "luna-reviews"), "PR_7_review.md", "inside\n")
            self.assertEqual(report.parent, real_dir.resolve())
            self.assertEqual((real_dir / "PR_7_review.md").read_text(), "inside\n")
