"""Focused rendering contracts; no publishing or external tools."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
