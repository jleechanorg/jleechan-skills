"""Regression contracts for portable approval and evidence-gate skills."""

import contextlib
import io
import json
import os
import re
import tempfile
from unittest import mock
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"
COMMANDS = REPO_ROOT / ".claude" / "commands"


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


def history_example(section: int) -> str:
    text = skill("conversation-history-sparse").split(f"### {section})", 1)[1]
    return re.search(r"```python\n(.*?)\n```", text, re.S).group(1)


def run_history_fixture(code: str, root: Path, *, denied=(), **env) -> str:
    """Run only the documented parser against synthetic files, never real homes."""
    captured = io.StringIO()
    real_open = open
    outside_attempts = []
    denied = {Path(path).resolve() for path in denied}

    def fixture_open(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(root.resolve()):
            outside_attempts.append(str(resolved))
            raise PermissionError("outside synthetic fixture")
        if resolved in denied:
            raise PermissionError("synthetic denied source")
        return real_open(path, *args, **kwargs)

    with mock.patch.dict(os.environ, {"HOME": str(root), "NO_COLOR": "1", **env}), \
         mock.patch("builtins.open", side_effect=fixture_open), \
         contextlib.redirect_stdout(captured):
        exec(compile(code, "<documented-history-example>", "exec"),
             {"ansify": lambda source, body, query="": f"[{source}] {body}"})
    if outside_attempts:
        raise AssertionError(f"Attempted non-fixture access: {outside_attempts}")
    return captured.getvalue()


def cursor_coverage(output: str) -> dict:
    return json.loads(output.split("source coverage: ", 1)[1].splitlines()[0])


class ApprovalContractsTest(unittest.TestCase):

    def test_commentcheck_fenced_code_blocks_are_not_nested(self) -> None:
        path = COMMANDS / "extended-library" / "commentcheck.md"
        in_fence = False
        fence_count = 0

        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.startswith("### Phase 5:") or line.startswith("### Phase 6:"):
                self.assertFalse(in_fence, f"phase heading fenced at {line_number}")
            if not line.startswith("```"):
                continue
            fence_count += 1
            if in_fence:
                self.assertEqual(
                    line.strip(),
                    "```",
                    f"unexpected nested fence at {line_number}",
                )
                in_fence = False
            else:
                in_fence = True

        self.assertGreater(fence_count, 0)
        self.assertFalse(in_fence, "commentcheck.md has an unclosed code fence")

    def test_superpowers_quick_dispatcher_resolves_portable_packages(self) -> None:
        command_path = COMMANDS / "superpowers-quick.md"
        self.assertTrue(command_path.is_file(), command_path)
        self.assertIn(
            "~/.claude/skills/superpowers-quick/SKILL.md",
            command_path.read_text(encoding="utf-8"),
        )

        package_names = (
            "superpowers-quick",
            "superpowers-brainstorming",
            "superpowers-writing-plans",
        )
        package_texts = {}
        for name in package_names:
            path = SKILLS / name / "SKILL.md"
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")
            metadata = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
            self.assertIsNotNone(metadata, path)
            self.assertRegex(
                metadata.group(1), rf"(?m)^name:\s*{re.escape(name)}$"
            )
            package_texts[name] = text

        self.assertRegex(
            package_texts["superpowers-quick"],
            r"(?m)^disable-model-invocation:\s*false$",
        )
        for name in package_names[1:]:
            with self.subTest(dependency=name):
                self.assertIn(
                    f"~/.claude/skills/{name}/SKILL.md",
                    package_texts["superpowers-quick"],
                )

    def test_history_claude_fixture_enforces_source_and_excerpt_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for index in range(3):
                path = root / f"session-{index}.jsonl"
                entries = [{"message": {"role": "assistant", "content": "SYNTHETIC_PRIVATE_PAYLOAD"}}]
                entries += [{"timestamp": "2026-10-04", "message": {"role": "user", "content": "question " + "x" * 600}} for _ in range(4)]
                path.write_text("\n".join(json.dumps(row) for row in entries) + "\n")
                paths.append(str(path))
            output = run_history_fixture(history_example(3), root,
                                         HISTORY_FILES_JSON=json.dumps(paths), HIST_QUERY="question")
            # A fourth candidate must remain outside the three-file sample even
            # when the first three files contain fewer than five total hits.
            for filename in paths:
                Path(filename).write_text(json.dumps({"message": {"role": "user", "content": "one bounded question"}}) + "\n")
            extra = root / "unselected.jsonl"
            extra.write_text(json.dumps({"message": {"role": "user", "content": "UNSELECTED_FOURTH_FILE"}}) + "\n")
            selected = run_history_fixture(history_example(3), root,
                                           HISTORY_FILES_JSON=json.dumps(paths + [str(extra)]), HIST_QUERY="")
            self.assertEqual(sum(line.startswith("[Claude]") for line in selected.splitlines()), 3)
            self.assertNotIn("UNSELECTED_FOURTH_FILE", selected)
        snippets = [line.split(" | ", 1)[1] for line in output.splitlines() if line.startswith("[Claude]")]
        self.assertEqual(len(snippets), 5)
        self.assertTrue(all(len(snippet) <= 200 for snippet in snippets))
        self.assertNotIn("SYNTHETIC_PRIVATE_PAYLOAD", output)
        self.assertNotIn('"message"', output)

    def test_cursor_fixture_preserves_missing_parse_and_permission_failures(self) -> None:
        cases = (("missing", None, "unavailable"), ("malformed", "{", "error"),
                 ("schema", "{}", "error"), ("denied", "[]", "error"))
        for name, content, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / ".cursor" / "prompt_history.json"
                if content is not None:
                    source.parent.mkdir(parents=True)
                    source.write_text(content)
                output = run_history_fixture(history_example(7), root,
                                             denied=[source] if name == "denied" else [], HIST_QUERY="needle")
                coverage = cursor_coverage(output)
                self.assertTrue(coverage["prompt_history"].startswith(expected), coverage)
                self.assertTrue(coverage["chats"].startswith("unavailable"), coverage)
                self.assertEqual(coverage["agent-transcripts"], "not searched")
                self.assertIn("zero returned hits", output)
                self.assertNotIn("no matches", output.lower())

    def test_cursor_fixture_searches_full_prefix_but_keeps_partial_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chats = root / ".cursor" / "chats"
            chats.mkdir(parents=True)
            for index in range(3):
                path = chats / f"chat-{index}.json"
                path.write_text("x" * 500 + "needle" + "y" * 2500 + "tail-only")
                os.utime(path, (index + 1, index + 1))
            output = run_history_fixture(history_example(7), root, HIST_QUERY="needle")
            hits = [line.split(" | ", 1)[1] for line in output.splitlines() if line.startswith("[cursor] chat ")]
            self.assertEqual(len(hits), 2)
            self.assertTrue(all("needle" in snippet and len(snippet) <= 200 for snippet in hits))
            self.assertTrue(cursor_coverage(output)["chats"].startswith("partial"))
            tail = run_history_fixture(history_example(7), root, HIST_QUERY="tail-only")
            self.assertIn("zero returned hits", tail)
            self.assertTrue(cursor_coverage(tail)["chats"].startswith("partial"))
            denied = run_history_fixture(history_example(7), root,
                                         denied=[chats / "chat-2.json"], HIST_QUERY="needle")
            self.assertIn("read errors in 1 selected files", cursor_coverage(denied)["chats"])

    def test_cursor_fixture_result_limits_and_unsupported_entries_stay_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / ".cursor" / "prompt_history.json"
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps([{"prompt": "needle " + "x" * 600}] * 5))
            output = run_history_fixture(history_example(7), root, HIST_QUERY="needle")
            snippets = [line.split(" | ", 1)[1] for line in output.splitlines() if line.startswith("[cursor] prompt_history ")]
            self.assertEqual(len(snippets), 3)
            self.assertTrue(all(len(snippet) <= 200 for snippet in snippets))
            coverage = cursor_coverage(output)
            self.assertTrue(coverage["prompt_history"].startswith("partial"))
            self.assertEqual(coverage["chats"], "not searched")
            source.write_text(json.dumps([{"content": ["nontext"]}]))
            partial = run_history_fixture(history_example(7), root, HIST_QUERY="needle")
            self.assertTrue(cursor_coverage(partial)["prompt_history"].startswith("partial"))
            self.assertIn("zero returned hits", partial)


class WorkspaceSpecificIdentifierTest(unittest.TestCase):
    def test_agento_report_has_no_workspace_specific_slack_channel(self):
        report = (SKILLS / "agento-report" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("#ai-slack-test", report)


if __name__ == "__main__":
    unittest.main()

