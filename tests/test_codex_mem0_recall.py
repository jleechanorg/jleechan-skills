"""Input-shape regression tests for the Codex SessionStart hook."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HOOK = Path(__file__).resolve().parents[1] / ".codex/hooks/mem0_recall.py"
spec = importlib.util.spec_from_file_location("codex_mem0_recall", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class SessionStartInputTests(unittest.TestCase):
    def test_unsupported_and_short_inputs_continue_without_recall(self):
        inputs = [
            "", "{", "[]", "null", "{}",
            json.dumps({"prompt": ["short canary"]}),
            json.dumps({"prompt": {"text": "short canary"}}),
            json.dumps({"prompt": None}),
            json.dumps({"prompt": "short canary"}),
            json.dumps({"task": [], "prompt": " ", "message": "short canary"}),
        ]
        for payload in inputs:
            with self.subTest(payload=payload):
                output = io.StringIO()
                with patch("sys.stdin", io.StringIO(payload)), \
                     patch.object(hook, "_read_claude_memories") as recall, \
                     patch("builtins.__import__", side_effect=AssertionError("unexpected import")), \
                     contextlib.redirect_stdout(output):
                    with self.assertRaises(SystemExit) as stopped:
                        hook.main()
                self.assertEqual(stopped.exception.code, 0)
                self.assertEqual(json.loads(output.getvalue()), {"continue": True})
                recall.assert_not_called()


if __name__ == "__main__":
    unittest.main()
