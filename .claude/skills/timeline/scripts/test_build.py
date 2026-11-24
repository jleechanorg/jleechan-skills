"""Focused rendering contracts; no publishing or external tools."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("timeline_build", Path(__file__).with_name("build.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class RenderingTests(unittest.TestCase):
    def render(self, **fields):
        data = {"title": "Example", "snapshot": "2026-10-12 12:00 PDT",
                "phases": [{"title": "Work", "rows": [
                    {"name": "Check", "owner": "main", "start": 0, "lo": 10, "hi": 20}]}]}
        data.update(fields)
        with tempfile.TemporaryDirectory(prefix="timeline-test-", dir="/tmp") as tmp:
            source, dest = Path(tmp) / "spec.json", Path(tmp) / "out.html"
            source.write_text(json.dumps(data))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                build.main(source, dest)
            return dest.read_text(), output.getvalue()

    def test_forecast_default(self):
        html, text = self.render()
        self.assertIn("estimate ≈ 10–20 min → finish ~12:10 PDT–12:20 PDT", text)
        self.assertIn("solid = low estimate, faded = up to high", html)
        self.assertEqual(build.axis_ticks(70), list(range(0, 71, 10)))

    def test_retrospective_is_not_a_finish_prediction(self):
        html, text = self.render(mode="retrospective", window_start="Yesterday <script>",
                                 window_end="Today", baseline="A & B", span=1440,
                                 phases=[{"title": "Actual", "rows": [
                                     {"name": "Check", "owner": "main", "start": 700,
                                      "lo": 5, "hi": 5}]}])
        self.assertIn("Observed window", text)
        self.assertNotIn("finish ~", text + html)
        self.assertIn("observed 5m", text)
        self.assertIn("Yesterday &lt;script&gt;", html)
        self.assertIn("Baseline: A &amp; B", html)
        self.assertIn("observed · 5m", html)
        self.assertIn('left:100.00%">1440 min', html)
        self.assertLessEqual(len(build.axis_ticks(1440)), 11)
        self.assertEqual(build.axis_ticks(1440)[-1], 1440)
        self.assertNotIn("13501440", text)
        ticks = build.axis_ticks(1440)
        self.assertGreaterEqual((ticks[-1] - ticks[-2]) * build.COLS / 1440,
                                len(str(ticks[-2])) + 1)

    def test_mixed_rows_preserve_independent_intervals(self):
        html, text = self.render(
            mode="retrospective", window_start="Yesterday", window_end="Today", span=1440,
            phases=[{"title": "Comparison", "rows": [
                {"name": "Actual", "owner": "main", "kind": "observed",
                 "start": 100, "lo": 80, "hi": 80},
                {"name": "Baseline", "owner": "main", "kind": "forecast",
                 "start": 100, "lo": 10, "hi": 20}]}])
        self.assertIn("observed 80m", text)
        self.assertIn("forecast 10–20m", text)
        self.assertIn("░", text)
        self.assertIn('width:5.56%', html)
        self.assertIn('width:0.69%', html)
        self.assertNotIn("finish ~", html + text)

    def test_observed_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "equal lo and hi"):
            self.render(mode="retrospective", window_start="Yesterday", window_end="Today")


class LegacySidecarMigrationTests(unittest.TestCase):
    SPEC = {
        "title": "Example",
        "snapshot": "2026-10-12 12:00 PDT",
        "branch": "feat/test",
        "pr": 42,
        "phases": [{"title": "Work", "rows": [
            {"name": "Check", "owner": "main", "start": 0, "lo": 10, "hi": 20},
        ]}],
    }

    def _stub_run(self, calls, db_path, repo="https://github.com/org/repo.git"):
        def fake_run(cmd, cwd=None, stdin=None):
            calls.append((list(cmd), stdin))
            if cmd[:3] == ["git", "remote", "get-url"]:
                return repo
            if cmd[:2] == ["git", "rev-parse"] and "--show-toplevel" in cmd:
                return str(db_path.parent.parent)
            if cmd[:2] == ["git", "rev-parse"] and "--git-common-dir" in cmd:
                return str(db_path.parent.parent / ".git")
            if cmd[:2] == ["br", "info"]:
                return json.dumps({"database_path": str(db_path)})
            if cmd[:4] == ["gh", "api", "-X", "PATCH"]:
                return "{}"
            if cmd[:4] == ["gh", "api", "-X", "POST"]:
                return json.dumps({"id": "new-gist-id"})
            if cmd[:2] == ["gh", "api"] and "--jq" in cmd:
                return "octocat"
            if len(cmd) >= 4 and cmd[0] == "br" and cmd[3] == "create":
                return json.dumps({"id": "new-bead-id"})
            if len(cmd) >= 4 and cmd[0] == "br" and cmd[3] == "update":
                return "{}"
            raise AssertionError(f"unexpected command: {cmd}")
        return fake_run

    def test_default_output_migrates_legacy_sidecars_and_reuses_ids(self):
        with tempfile.TemporaryDirectory(prefix="timeline-mig-", dir="/tmp") as tmp:
            root = Path(tmp)
            scratch = root / "scratch"
            scratch.mkdir()
            legacy = root / "legacy"
            legacy.mkdir()
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(self.SPEC))
            db_path = root / "repo" / ".beads" / "beads.db"
            db_path.parent.mkdir(parents=True)

            stem = "feat-test-pr42.html"
            owner = json.dumps({"repo": "https://github.com/org/repo.git", "branch": "feat/test", "pr": "42"})
            (legacy / f"{stem}.owner").write_text(owner + "\n")
            (legacy / f"{stem}.gist").write_text("old-gist-id\n")
            (legacy / f"{stem}.bead").write_text("old-bead-id\nstale-digest\n")

            calls = []
            with mock.patch.dict(os.environ, {"DISKM_SCRATCH": str(scratch)}), \
                    mock.patch.object(build, "LEGACY_TIMELINE_DIR", legacy), \
                    mock.patch.object(build, "run", side_effect=self._stub_run(calls, db_path)):
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main(spec_path, publish=True)

            dest = scratch / "timeline" / stem
            self.assertTrue(dest.is_file())
            self.assertEqual(Path(f"{dest}.owner").read_text().strip(), owner)
            self.assertEqual(Path(f"{dest}.gist").read_text().strip(), "old-gist-id")
            self.assertTrue(Path(f"{dest}.bead").read_text().startswith("old-bead-id\n"))
            cmds = [cmd for cmd, _ in calls]
            self.assertIn(["gh", "api", "-X", "PATCH", "gists/old-gist-id", "--input", "-"], cmds)
            self.assertFalse(any(cmd[:4] == ["gh", "api", "-X", "POST"] for cmd in cmds))
            self.assertTrue(any(
                cmd[:5] == ["br", "--db", str(db_path), "update", "old-bead-id"] for cmd in cmds
            ))
            self.assertFalse(any(len(cmd) >= 4 and cmd[0] == "br" and cmd[3] == "create" for cmd in cmds))

    def test_explicit_out_path_ignores_legacy_sidecars(self):
        with tempfile.TemporaryDirectory(prefix="timeline-explicit-", dir="/tmp") as tmp:
            root = Path(tmp)
            legacy = root / "legacy"
            legacy.mkdir()
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(self.SPEC))
            db_path = root / "repo" / ".beads" / "beads.db"
            db_path.parent.mkdir(parents=True)

            stem = "feat-test-pr42.html"
            (legacy / f"{stem}.owner").write_text(json.dumps(
                {"repo": "https://github.com/org/repo.git", "branch": "feat/test", "pr": "42"}
            ) + "\n")
            (legacy / f"{stem}.gist").write_text("old-gist-id\n")
            (legacy / f"{stem}.bead").write_text("old-bead-id\nstale-digest\n")

            custom_dest = root / "custom" / stem
            calls = []
            with mock.patch.object(build, "LEGACY_TIMELINE_DIR", legacy), \
                    mock.patch.object(build, "run", side_effect=self._stub_run(calls, db_path)):
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main(spec_path, out_path=str(custom_dest), publish=True)

            self.assertFalse(Path(f"{custom_dest}.owner").exists())
            self.assertEqual(Path(f"{custom_dest}.gist").read_text().strip(), "new-gist-id")
            self.assertTrue(Path(f"{custom_dest}.bead").read_text().startswith("new-bead-id\n"))
            cmds = [cmd for cmd, _ in calls]
            self.assertIn(["gh", "api", "-X", "POST", "gists", "--input", "-"], cmds)
            self.assertFalse(any("gists/old-gist-id" in cmd for cmd in cmds))
            self.assertTrue(any(len(cmd) >= 4 and cmd[0] == "br" and cmd[3] == "create" for cmd in cmds))

    def test_default_output_refuses_mismatched_legacy_owner(self):
        with tempfile.TemporaryDirectory(prefix="timeline-owner-", dir="/tmp") as tmp:
            root = Path(tmp)
            scratch = root / "scratch"
            scratch.mkdir()
            legacy = root / "legacy"
            legacy.mkdir()
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(self.SPEC))
            db_path = root / "repo" / ".beads" / "beads.db"

            stem = "feat-test-pr42.html"
            (legacy / f"{stem}.owner").write_text(json.dumps(
                {"repo": "https://github.com/other/repo.git", "branch": "feat/test", "pr": "42"}
            ) + "\n")
            (legacy / f"{stem}.gist").write_text("other-gist-id\n")

            with mock.patch.dict(os.environ, {"DISKM_SCRATCH": str(scratch)}), \
                    mock.patch.object(build, "LEGACY_TIMELINE_DIR", legacy), \
                    mock.patch.object(build, "run", side_effect=self._stub_run([], db_path)):
                with self.assertRaises(SystemExit):
                    build.main(spec_path, publish=False)

            self.assertFalse((scratch / "timeline" / f"{stem}.gist").exists())

    def test_default_output_skips_legacy_gist_when_scratch_owner_differs(self):
        with tempfile.TemporaryDirectory(prefix="timeline-conflict-", dir="/tmp") as tmp:
            root = Path(tmp)
            scratch = root / "scratch"
            (scratch / "timeline").mkdir(parents=True)
            legacy = root / "legacy"
            legacy.mkdir()
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(self.SPEC))
            db_path = root / "repo" / ".beads" / "beads.db"

            stem = "feat-test-pr42.html"
            (scratch / "timeline" / f"{stem}.owner").write_text(json.dumps(
                {"repo": "https://github.com/org/repo.git", "branch": "feat/test", "pr": "42"}
            ) + "\n")
            (legacy / f"{stem}.owner").write_text(json.dumps(
                {"repo": "https://github.com/other/repo.git", "branch": "feat/test", "pr": "42"}
            ) + "\n")
            (legacy / f"{stem}.gist").write_text("other-gist-id\n")

            with mock.patch.dict(os.environ, {"DISKM_SCRATCH": str(scratch)}), \
                    mock.patch.object(build, "LEGACY_TIMELINE_DIR", legacy), \
                    mock.patch.object(build, "run", side_effect=self._stub_run([], db_path)):
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main(spec_path, publish=False)

            self.assertFalse((scratch / "timeline" / f"{stem}.gist").exists())


if __name__ == "__main__":
    unittest.main()
