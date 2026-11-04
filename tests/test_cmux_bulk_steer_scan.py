import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCAN_PY = ROOT / ".claude" / "skills" / "cmux-bulk-steer" / "scripts" / "scan.py"


def load_scan_module():
    spec = importlib.util.spec_from_file_location("cmux_bulk_steer_scan", SCAN_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CmuxBulkSteerZfcScanTests(unittest.TestCase):
    def test_scan_script_has_zero_regex_classifiers(self):
        source = SCAN_PY.read_text(encoding="utf-8")
        banned_tokens = (
            "import re",
            "re.compile",
            "CHURN_RE",
            "IDLE_OVERRIDE_RE",
            "DEAD_RE",
            "SHELL_RE",
            "FOOTER_RE",
            "QUESTION_RE",
            "PARK_RE",
            "WARN_LIMIT_RE",
            "def classify(",
        )
        for token in banned_tokens:
            self.assertNotIn(
                token,
                source,
                f"ZFC violation: banned regex/classifier token {token!r} found in scan.py",
            )

    def test_truncate_to_last_n_words_preserves_lines_and_caps_words(self):
        scan = load_scan_module()
        lines = [f"line_{idx} " + " ".join(f"w{idx}_{j}" for j in range(9)) for idx in range(20)]
        raw_text = "\n".join(lines)
        truncated, total_words, captured_words = scan.truncate_to_last_n_words(raw_text, max_words=50)
        self.assertEqual(total_words, 200)
        self.assertLessEqual(captured_words, 50)
        self.assertGreaterEqual(captured_words, 40)
        self.assertTrue(truncated.endswith("line_19 " + " ".join(f"w19_{j}" for j in range(9))))
        self.assertIn("\n", truncated)

    def test_capture_fleet_writes_10k_files_and_manifest_without_semantic_state(self):
        scan = load_scan_module()
        fake_tree = {
            "windows": [
                {
                    "ref": "window:1",
                    "workspaces": [
                        {
                            "ref": "workspace:10",
                            "title": "lvl up",
                            "panes": [
                                {
                                    "ref": "pane:1",
                                    "surfaces": [
                                        {
                                            "ref": "surface:21",
                                            "title": "codex-worker",
                                            "type": "terminal",
                                        },
                                        {
                                            "ref": "surface:22",
                                            "title": "PR #10379",
                                            "type": "browser",
                                        },
                                        {
                                            "ref": "surface:23",
                                            "title": "non-terminal-fallback",
                                            "type": "terminal",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        fake_top = (
            "12.5\t1000\t10\ttotal\ttotal\t\t\n"
            "4.2\t500\t3\tsurface\tsurface:21\tpane:1\tcodex-worker\n"
        )
        # Per-workspace fallback shape: "  <CPU>%  <MEM>  <procs>  surface surface:<id> ..."
        fake_procs_top = "  4.2%   500.0 MB   3   surface surface:21 [terminal] codex-worker\n"
        fake_pane_text = "\n".join(f"step {i}: working on PR #10379" for i in range(15))

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["cmux", "tree", "--all"]:
                return mock.Mock(returncode=0, stdout=json.dumps(fake_tree), stderr="")
            if cmd[:3] == ["cmux", "top", "--all"]:
                return mock.Mock(returncode=0, stdout=fake_top, stderr="")
            if cmd[:2] == ["cmux", "top"] and cmd[-1] == "--processes":
                # Per-workspace CPU fallback, used when --flat reports 0.0 everywhere.
                return mock.Mock(returncode=0, stdout=fake_procs_top, stderr="")
            if cmd[:2] == ["cmux", "capture-pane"]:
                sf = cmd[cmd.index("--surface") + 1]
                if sf == "surface:23":
                    return mock.Mock(
                        returncode=1,
                        stdout="",
                        stderr="Error: Surface is not a terminal",
                    )
                return mock.Mock(returncode=0, stdout=fake_pane_text, stderr="")
            raise AssertionError(f"Unexpected command: {cmd}")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "cmux_fleet"
            with mock.patch("subprocess.run", side_effect=fake_run):
                manifest = scan.capture_fleet(out_dir=out_dir, max_words=100)

            self.assertTrue((out_dir / "manifest.json").is_file())
            self.assertEqual(len(manifest["surfaces"]), 1)
            entry = manifest["surfaces"][0]
            for required_key in (
                "workspace",
                "workspace_ref",
                "surface",
                "surface_ref",
                "surface_title",
                "file_10k",
                "total_words",
                "captured_words",
                "lines_read",
                "tail_lines",
            ):
                self.assertIn(required_key, entry)
            self.assertNotIn("state", entry)
            self.assertEqual(entry["workspace"], "lvl up")
            self.assertEqual(entry["workspace_ref"], "workspace:10")
            self.assertEqual(entry["surface_ref"], "surface:21")
            self.assertEqual(len(entry["tail_lines"]), 10)
            captured_file = Path(entry["file_10k"])
            self.assertTrue(captured_file.is_file())
            self.assertIn("step 14: working on PR #10379", captured_file.read_text(encoding="utf-8"))

    def test_capture_fleet_enriches_alternate_screen_pi_surface_from_session_jsonl(self):
        scan = load_scan_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_home = Path(tmpdir) / "home"
            worktree_dir = tmp_home / "projects" / "worktree_demo"
            worktree_dir.mkdir(parents=True)
            session_dir = tmp_home / ".pi" / "agent" / "sessions" / "--projects-worktree_demo--"
            session_dir.mkdir(parents=True)
            session_jsonl = session_dir / "2026-10-14T18-00-00-000Z_demo.jsonl"
            session_rows = [
                {"type": "session", "id": "demo", "cwd": str(worktree_dir)},
                {
                    "type": "message",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Fix PR #10999 level up bug"}],
                    },
                },
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "Checking game_state_merge.py"},
                            {
                                "type": "toolCall",
                                "name": "bash",
                                "arguments": {"command": "./run_tests.sh tests/unit/test_demo.py"},
                            },
                            {
                                "type": "text",
                                "text": " ".join(f"transcript_word_{i}" for i in range(80)),
                            },
                        ],
                    },
                },
            ]
            session_jsonl.write_text(
                "\n".join(json.dumps(r) for r in session_rows) + "\n",
                encoding="utf-8",
            )

            fake_tree = {
                "windows": [
                    {
                        "ref": "window:1",
                        "workspaces": [
                            {
                                "ref": "workspace:44",
                                "title": "pi-lane",
                                "panes": [
                                    {
                                        "ref": "pane:1",
                                        "surfaces": [
                                            {
                                                "ref": "surface:99",
                                                "title": "π - worktree_demo",
                                                "type": "terminal",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
            fake_pane = (
                "── ⠋ Working ──────────────────────────────────────────\n"
                "~/projects/worktree_demo (feat/demo-branch)\n"
                "↑216k ↓41k R5.7M (lunaroute) deepseek-4.1-flash • medium\n"
            )

            def fake_run(cmd, *args, **kwargs):
                if cmd[:3] == ["cmux", "tree", "--all"]:
                    return mock.Mock(returncode=0, stdout=json.dumps(fake_tree), stderr="")
                if cmd[:3] == ["cmux", "top", "--all"]:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if cmd[:2] == ["cmux", "top"] and cmd[-1] == "--processes":
                    return mock.Mock(
                        returncode=0,
                        stdout="  4.2%   500.0 MB   3   surface surface:44 [terminal] pi\n",
                        stderr="",
                    )
                if cmd[:2] == ["cmux", "capture-pane"]:
                    return mock.Mock(returncode=0, stdout=fake_pane, stderr="")
                raise AssertionError(f"Unexpected command: {cmd}")

            out_dir = Path(tmpdir) / "out"
            with mock.patch("subprocess.run", side_effect=fake_run):
                manifest = scan.capture_fleet(
                    out_dir=out_dir, max_words=60, home_dir=tmp_home
                )

            entry = manifest["surfaces"][0]
            self.assertEqual(entry["pi_session_jsonl"], str(session_jsonl.resolve()))
            self.assertLessEqual(entry["captured_words"], 65)
            self.assertGreaterEqual(entry["captured_words"], 40)
            captured_text = Path(entry["file_10k"]).read_text(encoding="utf-8")
            self.assertIn("=== PI SESSION TRANSCRIPT", captured_text)
            self.assertIn("=== LIVE TERMINAL PANE ===", captured_text)
            self.assertIn("transcript_word_79", captured_text)
            self.assertIn("~/projects/worktree_demo (feat/demo-branch)", captured_text)
