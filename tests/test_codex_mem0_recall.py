"""Input-shape regression tests for the Codex SessionStart hook."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HOOK = Path(__file__).resolve().parents[1] / ".codex/hooks/mem0_recall.py"
spec = importlib.util.spec_from_file_location("codex_mem0_recall", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class SessionStartInputTests(unittest.TestCase):
    def run_recall(self, payload):
        output = io.StringIO()
        memory = SimpleNamespace(
            search=lambda query, **kwargs: {
                "results": [{"score": 0.9, "memory": f"matched {query}"}]
            }
        )
        memory_type = SimpleNamespace(from_config=lambda config: memory)
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             patch.object(hook, "_read_claude_memories", return_value=""), \
             patch.dict("sys.modules", {"mem0": SimpleNamespace(Memory=memory_type)}), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as stopped:
                hook.main()
        self.assertEqual(stopped.exception.code, 0)
        return json.loads(output.getvalue())

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

    def test_positive_query_returns_matching_memory(self):
        result = self.run_recall({
            "task": "A sufficiently long task query",
            "prompt": "A lower priority prompt query",
            "message": "A lower priority message query",
            "userMessage": "A lower priority user query",
        })

        self.assertEqual(
            result,
            {"context": "## Relevant memories (from past sessions)\n"
             "- [0.90] matched A sufficiently long task query"},
        )

    def test_query_fields_use_priority_and_skip_blank_values(self):
        result = self.run_recall({
            "task": "   ",
            "prompt": "The selected prompt query has enough characters",
            "message": "A later message query also has enough characters",
            "userMessage": "A final query that should not take precedence",
        })

        self.assertIn(
            "matched The selected prompt query has enough characters",
            result["context"],
        )


if __name__ == "__main__":
    unittest.main()
