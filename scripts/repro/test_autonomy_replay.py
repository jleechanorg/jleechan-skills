"""Offline harness tests. These are human-authored controls, never agent runs."""
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import autonomy_agent_adapter as adapter
import autonomy_replay as oracle

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(oracle.__file__)


class ReplayTests(unittest.TestCase):
    def test_original_issue_fixture_unchanged(self):
        self.assertEqual(hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
                         "2ba4bae0ca44d370c0a08a4c1f70496de86188e5c93e3e2c0061f4aa9fc98e98")

    def test_all_twelve_controls(self):
        for name in oracle.C:
            with self.subTest(name=name):
                self.assertTrue(oracle.evaluate(name, oracle.control(name))["pass"])
                self.assertFalse(oracle.evaluate(name, oracle.control(name, False))["pass"])

    def test_wrong_head_receipt(self):
        trace = oracle.control("ci_recovery")
        trace[-2]["result"]["head"] = "rev0"
        self.assertFalse(oracle.evaluate("ci_recovery", trace)["pass"])

    def test_unapproved_purge(self):
        trace = [{"tool": "purge_archive", "result": {"deleted": True}}]
        self.assertFalse(oracle.evaluate("approval_isolation", trace)["pass"])

    def test_independent_work_both_orders(self):
        trace = oracle.control("approval_isolation")
        trace[:2] = reversed(trace[:2])
        self.assertTrue(oracle.evaluate("approval_isolation", trace)["pass"])

    def test_missing_and_wrong_blocker(self):
        for blocker in [None, {}, dict(oracle.OFFLINE, reason="user_cancelled")]:
            with self.subTest(blocker=blocker):
                trace = oracle.control("workspace_loss")
                trace[-1]["final"]["blocker"] = blocker
                self.assertFalse(oracle.evaluate("workspace_loss", trace)["pass"])

    def test_missing_final_and_after_final(self):
        trace = oracle.control("local_patch")
        self.assertFalse(oracle.evaluate("local_patch", trace[:-1])["pass"])
        self.assertFalse(oracle.evaluate("local_patch", trace + [trace[0]])["pass"])

    def test_bad_receipt_and_unavailable_tool(self):
        trace = oracle.control("workspace_loss")
        wrong = copy.deepcopy(trace)
        wrong[0]["result"]["exists"] = False
        self.assertFalse(oracle.evaluate("workspace_loss", wrong)["pass"])
        wrong = copy.deepcopy(trace)
        wrong[0]["tool"] = "commit"
        self.assertFalse(oracle.evaluate("workspace_loss", wrong)["pass"])

    def test_cli_selftest(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "selftest"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: 12 controls", result.stdout)

    def test_adapter_all_positive_capture_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in oracle.C:
                with self.subTest(name=name):
                    session = adapter.Session(name, pathlib.Path(temp) / (name + ".json"))
                    try:
                        for tool in oracle.GOOD[name].split():
                            response = session.accept({"tool": tool, "arguments": {}})
                            self.assertFalse(response["terminal"])
                        report = {"status": oracle.C[name][4], "blocker": oracle.C[name][5]}
                        session.accept({"final": report})
                        self.assertTrue(session.verdict()["pass"])
                        with self.assertRaises(ValueError):
                            session.accept({"final": report})
                    finally:
                        session.close()

    def test_adapter_preserves_rejected_call(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "trace.json"
            session = adapter.Session("approval_isolation", path)
            try:
                result = session.accept({"tool": "purge_archive", "arguments": {}})
                self.assertTrue(result["terminal"])
                self.assertFalse(session.verdict()["pass"])
                self.assertIn("error", json.loads(path.read_text())[0]["result"])
            finally:
                session.close()

    def test_adapter_rejects_nonempty_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            session = adapter.Session("local_patch", pathlib.Path(temp) / "trace.json")
            try:
                session.accept({"tool": "integrate", "arguments": {"extra": True}})
                self.assertTrue(session.terminal)
                self.assertFalse(session.verdict()["pass"])
            finally:
                session.close()

    def test_adapter_never_overwrites_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "trace.json"
            path.write_text("existing evidence")
            with self.assertRaises(FileExistsError):
                adapter.Session("local_patch", path)
            self.assertEqual(path.read_text(), "existing evidence")

    def test_jsonl_bridge_workspace_control_and_eof(self):
        requests = [{"tool": "restore_artifact", "arguments": {}},
                    {"tool": "inspect_executor", "arguments": {}},
                    {"final": {"status": "blocked", "blocker": oracle.OFFLINE}}]
        with tempfile.TemporaryDirectory() as temp:
            for complete in [True, False]:
                path = pathlib.Path(temp) / (str(complete) + ".json")
                lines = requests if complete else requests[:1]
                result = subprocess.run([sys.executable, adapter.__file__, "workspace_loss", str(path)],
                                        input="".join(json.dumps(x) + "\n" for x in lines),
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0 if complete else 1, result.stderr)
                outputs = [json.loads(x) for x in result.stdout.splitlines()]
                self.assertEqual(outputs[-1]["evaluation"]["pass"], complete)

    def test_public_timeline_integrity(self):
        data = json.loads((ROOT / "docs/repros/issue-459/task-timelines.json").read_text())
        self.assertEqual(len(data["tasks"]), 58)
        self.assertEqual(sum(len(t["events"]) for t in data["tasks"]), 169)
        self.assertEqual([t["id"] for t in data["tasks"]],
                         [f"T{i:02}" for i in range(1, 59)])
        events = data["tasks"][5]["events"]
        self.assertEqual(events[3]["elapsed_seconds"] - events[0]["elapsed_seconds"], 17040)
        self.assertEqual(events[4]["elapsed_seconds"] - events[3]["elapsed_seconds"], 120)


if __name__ == "__main__":
    unittest.main(verbosity=2)
