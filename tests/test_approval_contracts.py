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
    def test_superpowers_quick_delegates_recommended_choices_and_finishes_documents(self) -> None:
        command = (COMMANDS / "superpowers-quick.md").read_text()
        quick = skill("superpowers-quick")

        self.assertIn("~/.claude/skills/superpowers-quick/SKILL.md", command)
        self.assertNotIn("superpowers:brainstorming", command)
        self.assertNotIn("superpowers:writing-plans", command)
        self.assertIn("superpowers:brainstorming", quick)
        self.assertIn("superpowers:writing-plans", quick)
        self.assertIn("disable-model-invocation: false", quick)
        self.assertIn("recommended", quick.lower())
        self.assertIn("invocation is the user's explicit authorization", quick.lower())
        self.assertIn("do not ask the user", quick.lower())
        self.assertIn("docs/superpowers/specs/", quick)
        self.assertIn("docs/superpowers/plans/", quick)
        self.assertIn("terminal condition", quick.lower())

    def test_superpowers_quick_resolves_portable_dependencies_and_overrides_child_pauses(self) -> None:
        quick = skill("superpowers-quick")

        for dependency in ("superpowers-brainstorming", "superpowers-writing-plans"):
            dependency_path = SKILLS / dependency / "SKILL.md"
            self.assertTrue(dependency_path.is_file(), dependency_path)
            self.assertIn(f"~/.claude/skills/{dependency}/SKILL.md", quick)

        self.assertIn("Do not offer the visual companion", quick)
        self.assertIn("Do not pause for user review", quick)
        self.assertIn("Do not commit or push", quick)
        self.assertIn("Skip its execution handoff", quick)
        self.assertIn("Terminate immediately after", quick)
        self.assertIn("takes precedence over every child instruction", quick)
        self.assertIn("write either artifact to a different path", quick)
        self.assertIn("still write and self-review both documents", quick)
        self.assertNotIn("stop with the exact blocker", quick)

    def test_superpowers_quick_reports_autopicks_and_advice_without_unapproved_disclosure(self) -> None:
        quick = skill("superpowers-quick")

        self.assertIn(
            "question, the auto-picked answer, and the underlying rationale",
            quick,
        )
        self.assertIn("both the design specification and implementation plan", quick)
        self.assertIn(
            "A bare `/superpowers-quick` invocation does not authorize external browser review",
            quick,
        )
        self.assertIn("Run at most one standalone `/web-advice`", quick)
        self.assertIn("Do not pause or ask the user to log in", quick)
        self.assertIn(
            "`/web-advice is disabled; do not invoke it or any external browser transport.`",
            quick,
        )
        self.assertIn(
            "Verify the synthesis records no browser submission",
            quick,
        )
        self.assertIn(
            "Treat an attempted browser submission as an incomplete `/advice` run and record it as `FAILED`",
            quick,
        )
        self.assertIn(
            "Retry `/advice` once only for a transient transport or reviewer-launch failure",
            quick,
        )
        self.assertIn(
            "permits the terminal report but prohibits claiming that advice passed or approved the documents",
            quick,
        )
        self.assertIn(
            "record `/web-advice` as `FAILED` with the attempted-submission reason",
            quick,
        )
        self.assertIn(
            "When no external attempt occurred and explicit authorization is absent",
            quick,
        )
        self.assertIn(
            "Retry the whole `/advice` invocation only when it failed before any reviewer launched",
            quick,
        )
        self.assertIn(
            "Any browser submission made during `/advice` consumes the single `/web-advice` run",
            quick,
        )
        self.assertIn(
            "only when `/advice` made no browser submission",
            quick,
        )
        self.assertIn("`/advice`: `RAN | FAILED`", quick)
        self.assertIn(
            "`/web-advice`: `RAN | SKIPPED | UNAVAILABLE | FAILED`",
            quick,
        )
        self.assertIn("<repo-root>/docs/superpowers/specs/", quick)
        self.assertIn("<repo-root>/docs/superpowers/plans/", quick)
        self.assertIn("advice attempts and required status records are complete", quick)

    def test_advice_reviews_repository_before_approving(self) -> None:
        advice = skill("advice")
        command = (COMMANDS / "advice.md").read_text()
        readme = (REPO_ROOT / "README.md").read_text()
        self.assertIn("**Pointer**", advice)
        self.assertIn("Send the pointer, not a transcription.", advice)
        self.assertIn("A verdict built on a truncated inline artifact may not be `APPROVED`.", advice)
        self.assertIn("VERDICT: WITHHELD at <SHA>", advice)
        self.assertIn("COVERAGE", advice)
        self.assertIn("research-only output are not approval reviewers", advice)
        self.assertIn("combined scope covers the whole declared change", advice)
        self.assertIn("`COVERAGE: <files/diff scope actually read>`", advice)
        self.assertIn("Each original\nindependent approving reviewer must inspect", advice)
        self.assertIn("explicitly reaffirm", advice)
        self.assertIn("never by directory or", advice)
        self.assertIn("Codex + Opus CLI", command)
        self.assertIn("/research", command)
        self.assertIn("/extended-library:secondo", command)
        self.assertNotIn("/web-advice", command)
        self.assertNotIn("/web-advice", advice)
        self.assertNotIn("Reviewer D", advice)
        self.assertIn("up to four reviewers concurrently", readme)
        self.assertIn("`/extended-library:secondo`", readme)
        self.assertNotIn("up to four reviewers concurrently: an Opus subagent", readme)

    def test_ready_requires_advice_without_web_advice_fanout(self) -> None:
        ready = skill("ready")
        draft_first = skill("draft-first-pr")
        advice = skill("advice")
        web_advice_command = (COMMANDS / "web-advice.md").read_text()

        self.assertIn("/er and /advice\nwhere `draft-first-pr` (including repo-defined exemptions) requires them", (COMMANDS / "ready.md").read_text())
        self.assertIn("**/advice**", ready)
        self.assertIn("→ /advice APPROVED @ SHA", draft_first)
        self.assertNotIn("/web-advice", advice)
        self.assertNotIn("Reviewer D", advice)
        self.assertIn("canonical skill", web_advice_command)

    def test_web_advice_requires_real_browser_transport(self) -> None:
        web_adv = skill("web-advice")
        self.assertIn(
            "COVERAGE: exact filenames from the attached packet actually read",
            web_adv,
        )
        self.assertIn("Zero Aside Inference Invariant", web_adv)
        self.assertIn("NEVER use Aside inference", web_adv)
        self.assertIn("chrome_headless_cookies", web_adv)
        self.assertIn("playwright_mcp", web_adv)
        self.assertNotIn("fall back to a subagent", web_adv.lower())
        self.assertNotIn("fall back to subagent", web_adv.lower())

        workflow = (
            REPO_ROOT
            / "hermes"
            / "skills"
            / "workflow"
            / "apply-supplied-patch-and-open-pr"
            / "SKILL.md"
        ).read_text()
        self.assertNotIn("recorded CLI review via `codex exec`", workflow)
        self.assertNotIn("/web-advice (Codex)", workflow)

        evals = (
            SKILLS / "web-advice" / "evals" / "web_advice_evals.md"
        ).read_text()
        self.assertIn("authenticated Playwright fallback", evals)
        self.assertIn("Chrome cookie headless", evals)
        self.assertNotIn("the four ladder rungs", evals)

    def test_evidence_review_separates_integrity_from_provenance(self) -> None:
        review = skill("evidence-review")
        self.assertIn("Checksums establish integrity, not provenance", review)
        self.assertIn("does not make a claim STRONG", review)

    def test_evidence_staleness_is_about_production_behavior(self) -> None:
        standards = skill("evidence-standards")
        self.assertIn("the delta and the claim decide, not the path", standards)
        self.assertIn("A moving HEAD does NOT invalidate evidence by itself.", standards)

    def test_draft_gate_requires_sha_bound_approval_not_withheld(self) -> None:
        draft_first = skill("draft-first-pr")
        self.assertIn("`WITHHELD at <SHA>`", draft_first)
        self.assertIn("does not satisfy the draft gate", draft_first)
        self.assertIn("SHA-binding rule", draft_first)

    def test_documentation_only_draft_gate_skips_evidence_review(self) -> None:
        draft_first = skill("draft-first-pr")
        evidence_review = skill("evidence-review")
        green = skill("pr-green-definition")
        readme = (REPO_ROOT / "README.md").read_text()

        self.assertIn("Documentation-only `/er` exception", draft_first)
        self.assertIn("do not run `/er`", draft_first)
        self.assertIn("`README.md`", draft_first)
        self.assertIn("`docs/**`", draft_first)
        self.assertIn("`.claude/**`", draft_first)
        self.assertRegex(
            draft_first,
            r"still require `/es`\s+and, unless a repo-exempted class applies,"
            r"\s+`/advice`",
        )
        allowlist = re.search(
            r"For this `/er` exemption, every changed path must be one of:\n\n"
            r"(?P<paths>(?:- `[^`]+`\n)+)",
            draft_first,
        )
        self.assertIsNotNone(allowlist)
        self.assertEqual(
            re.findall(r"- `([^`]+)`", allowlist.group("paths")),
            ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "docs/**"],
        )
        self.assertIn("Documentation-only exception", evidence_review)
        self.assertIn("`/er` is not run", evidence_review)
        receipt = "`/er: NOT REQUIRED — documentation-only (<changed paths>)`"
        self.assertIn(receipt, draft_first)
        self.assertIn(receipt, evidence_review)
        self.assertRegex(
            draft_first,
            r"Any\s+mixed diff uses the normal `/er` gate",
        )
        self.assertRegex(
            evidence_review,
            r"Mixed diffs and every path outside that allowlist follow the normal gate",
        )
        self.assertIn("requires `/er` = **PASS** at the current SHA", evidence_review)
        self.assertIn("outside any low-risk class the repo's own\ninstructions exempt per `draft-first-pr`", evidence_review)
        self.assertNotIn("Acceptable for `/green` on NON_PRODUCTION", evidence_review)
        self.assertIn("when `/er` is required by that lifecycle", green)
        self.assertNotIn("DRAFT → `/es` → `/er` → `/advice`", green)
        self.assertIn("draft-phase gate", readme)
        self.assertIn("Documentation-only PRs skip `/er`", readme)
        self.assertNotIn("production-tier `/green` requires PASS", readme)

    def test_portable_and_orchestration_contracts_disclose_actual_behavior(self) -> None:
        history = skill("conversation-history-sparse")
        factory = skill("dark-factory")
        swarm = skill("swarm")

        discovery = history.split("### 2)", 1)[1].split("### 3)", 1)[0]
        self.assertIn("Return filenames only", discovery)
        self.assertIn("at most three", discovery)
        self.assertIn("--files-with-matches", discovery)
        self.assertNotIn("xargs -0 rg -n", discovery)
        self.assertIn("HISTORY_FILES_JSON", history)
        self.assertIn("Always tell the user the **actual command** you ran", factory)
        self.assertIn("The top-level session owns named visible lanes", swarm)

    def test_github_cli_reference_fallback_and_merge_authority(self) -> None:
        ref = skill("github-cli-reference")
        norm = " ".join(ref.split())
        self.assertIn("read-only or idempotent", ref)
        self.assertIn("must read back", ref)
        self.assertIn("Human merge authority", ref)
        self.assertIn(
            "When an uncertain response occurs on a non-idempotent mutation (such as creating a comment, creating a release, or modifying state), the client must read back the current state or check idempotency before any retry attempt; never retry a mutation blindly to avoid creating duplicate comments, releases, or side effects.",
            norm,
        )
        self.assertIn(
            "Human merge authority and approval gates remain strictly preserved; automated fallbacks must never merge pull requests without explicit authorization.",
            norm,
        )



    def test_history_source_admission_and_empty_results_fail_closed(self) -> None:
        history = " ".join(skill("conversation-history-sparse").split())
        for rule in (
            "Before any filesystem probe, glob, helper invocation, or connector search",
            "Never probe denied roots, credentials, backups, or unrelated profiles",
            "do not request access to a policy-denied corpus or try another tool to bypass denial",
            "If a source includes an excluded subtree and the helper cannot exclude it",
            "skip that helper/source",
            "Never describe dot-room search as all-account history",
            "An empty helper result does not prove no matches",
            "successful parsing/search, and completion of the declared search scope",
            "do not label a source `no-match` solely from an empty result or exit code zero",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, history)

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


if __name__ == "__main__":
    unittest.main()
