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
    def test_wiki_bfs_forwards_the_selected_wiki_to_child_commands(self) -> None:
        workflow = skill("wiki-bfs")
        self.assertIn(
            "`/wiki-ingest <candidate-source> --wiki \"$WIKI\"`",
            workflow,
        )
        self.assertIn("`/wiki-assess --wiki \"$WIKI\"`", workflow)

    def test_wiki_evolve_forwards_the_selected_wiki_to_ingest(self) -> None:
        workflow = (COMMANDS / "extended-library" / "wiki-evolve.md").read_text()
        self.assertIn(
            'Pass `--wiki "$WIKI_DIR"` to every `/wiki-ingest` call',
            workflow,
        )
        self.assertIn(
            '`/wiki-ingest <candidate-source> --wiki "$WIKI_DIR"`',
            workflow,
        )

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

    def test_lifecycle_entrypoints_reference_the_canonical_owner(self) -> None:
        for name in (
            "agento-report", "auton", "factory-evolve", "ironclad", "pr-report",
            "superpowers-quick", "testing-layers", "write-goal", "zero-touch",
        ):
            with self.subTest(skill=name):
                text = skill(name)
                self.assertIn("pr-lifecycle", text)
                self.assertNotIn("draft-first-pr", text)
        template = (SKILLS / "write-goal" / "templates" / "goal-spec.md").read_text()
        self.assertIn("canonical `pr-lifecycle` skill", template)
        self.assertNotIn("draft-first-pr", template)

    def test_readiness_reports_delegate_applicability_not_exact_sha_or_green_alone(self) -> None:
        agento = skill("agento-report")
        self.assertIn("applicable draft gate lacks coverage for the candidate", agento)
        self.assertNotIn("is missing at current head", agento)
        report = skill("pr-report")
        self.assertIn('`gate1 == 0` AND `gate2 == "MERGEABLE"` → `GREEN`', report)
        self.assertNotIn("→ `MERGE_READY`", report)
        self.assertIn("green alone does not establish READY", report)

    def test_autonomy_metrics_follow_applicable_gates_and_reasoned_sha_reuse(self) -> None:
        zero = skill("zero-touch")
        self.assertNotIn("completed `/es`, `/er`, and `/advice`", zero)
        self.assertIn("completed the applicable draft gates per `pr-lifecycle`", zero)
        auton = skill("auton")
        self.assertNotIn("draft through /es, /er, and /advice", auton)
        self.assertNotIn("current-head /es, /er, /advice artifacts", auton)
        self.assertNotIn("Verify current-head `/es`, `/er`, `/advice`", auton)
        self.assertIn("applicable draft gates per pr-lifecycle", auton)
        self.assertIn("current-candidate applicability", auton)
        self.assertIn("reasoned SHA-binding assessment", auton)
        self.assertIn("original tested/reviewed SHAs and timestamps", auton)
        self.assertIn("affected or uncertain coverage requires independent review", auton)

    def test_agento_summary_does_not_equate_green_with_merge_authority(self) -> None:
        report = skill("agento-report")
        self.assertNotIn("GREEN (ready to merge)", report)
        self.assertIn("GREEN (draft readiness + /green only)", report)
        self.assertIn("green alone does not establish READY", report)
        self.assertIn("merge authorization remains separate", report)

    def test_agento_zero_touch_requires_evidence_not_title_tags(self) -> None:
        report = skill("agento-report")
        self.assertIn("~/.claude/skills/zero-touch/SKILL.md", report)
        self.assertIn("discovery hint only", report)
        self.assertIn("spawn provenance, quality-gate receipts and pre-merge intervention history", report)
        self.assertIn("UNKNOWN", report)
        self.assertIn("Incomplete coverage makes the overall zero-touch rate unknown", report)
        self.assertIn("total_merged > 0", report)
        self.assertIn("N/A (no merged PRs)", report)
        self.assertIn("Do not count merge authorization or the merge action itself", report)
        for obsolete in ("prefix means AO produced", "tagged** (zero-touch)",
                         "**Non-[agento]** (operator-assisted)",
                         "agento_count / total_merged", "[agento] YES / NO",
                         "worker didn't add [agento] prefix", "~/.openclaw/SOUL.md"):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, report)

    def test_factory_draft_and_readiness_use_applicable_canonical_gates(self) -> None:
        factory = " ".join(skill("factory-evolve").split())
        self.assertIn("gh pr create --repo jleechanorg/<repo> --draft", factory)
        self.assertIn("applicable draft gates cover the candidate", factory)
        self.assertNotIn("`/es`, `/er`, and `/advice` pass at the current head", factory)
        self.assertNotIn("CR approved", factory)
        self.assertIn("**STOP. Do not merge.**", factory)

    def test_evidence_consumers_point_directly_to_lifecycle_policy(self) -> None:
        for name in ("evidence-review", "evidence-standards"):
            with self.subTest(skill=name):
                section = skill(name).split(
                    "## Claim-proportionate evidence and publication", 1
                )[1].split("\n## ", 1)[0]
                self.assertIn("../pr-lifecycle/SKILL.md#proportional-exceptions-and-fast-paths", section)
                self.assertIn("../pr-lifecycle/SKILL.md#evidence-attached-to-every-stage-exit", section)
                self.assertNotIn("#claim-proportionate-evidence-and-publication", section)
        self.assertIn("../evidence-standards/SKILL.md", skill("evidence-review"))
        standards = skill("evidence-standards")
        self.assertIn("mark irrelevant server/PID/provider fields N/A with reasons", standards)
        self.assertIn("Source hashes alone do not prove execution", standards)

    def test_agento_report_uses_an_authorized_portable_slack_destination(self) -> None:
        report = skill("agento-report")
        self.assertIn("user-authorized Slack summary destination", report)
        self.assertIn('channel_id="<slack-channel>"', report)
        self.assertNotIn("#ai-slack-test", report)

    def test_shared_policy_delegates_lifecycle_without_relaxing_merge_scope(self) -> None:
        shared = (REPO_ROOT / "md_files" / "AGENTS.shared.md").read_text()
        self.assertIn("~/.claude/skills/pr-lifecycle/SKILL.md", shared)
        self.assertNotIn("~/.claude/skills/draft-first-pr/SKILL.md", shared)
        self.assertNotIn("The original approving reviewers must reaffirm", shared)
        self.assertNotIn("rerun only on a material production change", shared)
        self.assertIn("generic lifecycle and evidence-reuse rules", shared)
        self.assertIn("Gate depth, including small low-risk changes, follows its § Coding lifecycle", shared)
        self.assertIn("~/.claude/skills/evidence-standards/SKILL.md` § Evidence Sequencing", shared)
        self.assertIn("## Coding lifecycle — scale layers to risk", skill("pr-lifecycle"))
        self.assertIn("## Evidence Sequencing — expensive evidence runs LAST, once", skill("evidence-standards"))
        for safeguard in (
            "Authorization persists for the same action, target, and requested outcome",
            "User merge approval",
            "MERGE APPROVED",
            "150 or fewer production delta lines",
            "More than 150 production delta lines",
            "wait for human review or the user's `MERGE APPROVED`",
            "merge with `--match-head-commit`",
        ):
            with self.subTest(safeguard=safeguard):
                self.assertIn(safeguard, shared)

    def test_shared_provenance_tags_precede_the_trailing_lifecycle_stage(self) -> None:
        shared = (REPO_ROOT / "md_files" / "AGENTS.shared.md").read_text()
        self.assertIn("provenance tags immediately before the trailing lifecycle stage suffix", shared)
        self.assertIn("`[<cli>][<model>]`", shared)
        self.assertIn("otherwise the provenance tags go last", shared)
        self.assertNotIn("PR titles must end with `[<cli>][<model>]`", shared)
        self.assertIn("the stage suffix goes last", skill("pr-lifecycle"))
        self.assertIn("PRs must include GitHub labels for both CLI and model", shared)
        self.assertIn("never a bare `gpt-6`", shared)

    def test_claude_adapter_points_to_canonical_lifecycle(self) -> None:
        adapter = (REPO_ROOT / "md_files" / "CLAUDE.adapter.md").read_text()
        self.assertIn("~/.claude/skills/pr-lifecycle/SKILL.md", adapter)
        self.assertNotIn("~/.claude/skills/draft-first-pr/SKILL.md", adapter)
        self.assertIn("~/.claude/skills/pr-green-definition/SKILL.md", adapter)
        self.assertIn("~/.claude/skills/pr-quantity-control/SKILL.md", adapter)

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

    def test_static_reviewer_owns_cold_verbatim_input(self) -> None:
        static = " ".join(skill("static-reviewer").split())
        for phrase in (
            "starts cold and blank",
            "Static review prompt (skill-owned, verbatim):",
            "Document-only review prompt (skill-owned, verbatim):",
            "Document-only preamble for CLI alternates and static reviewers",
            "COVERAGE: line",
            "VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA>",
            "`prompt` and `prompt_sha256`",
            "Advice vote requested.",
            "the exact prompt sent",
            "no reviewer process survives",
            "replaces only the runner exit field",
            "differ by both subagent type and harness",
            "Any deviation, including added context, summary or framing, voids that vote",
        ):
            self.assertIn(phrase, static)
        command = (COMMANDS / "static-reviewer.md").read_text()
        self.assertIn("skills/static-reviewer/SKILL.md", command)

    def test_advice_static_reviewer_fallback_contract(self) -> None:
        advice = " ".join(skill("advice").split())
        for phrase in (
            "[static-reviewer](../static-reviewer/SKILL.md)",
            "owner-authorized exception",
            "every alternate CLI attempt",
            "one outside vote pairs with one static reviewer",
            "that case requires a real outside vote",
            "attempted|skipped",
            "tell the user which reviewers were unavailable",
            "does not make the same CLI unavailable on another host",
        ):
            self.assertIn(phrase, advice)
        for gone in ("third distinct", "subagent seat", "Reviewer preamble (skill-owned"):
            self.assertNotIn(gone, advice)

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
        self.assertIn("Preserve the original reviewers and reviewed SHAs", advice)
        self.assertIn("inspect the complete actual delta, claims, evidence and phase", advice)
        self.assertIn("not a new independent vote", advice)
        self.assertIn("require affected independent review", advice)
        self.assertIn("two independent full-coverage approvals", advice)
        self.assertIn("never by directory or", advice)
        self.assertIn("Codex + Opus CLI", command)
        self.assertIn("/research", command)
        self.assertNotIn("secondo", command)
        self.assertNotIn("Reviewer C", command)
        self.assertNotIn("secondo", advice)
        self.assertNotIn("Reviewer C", advice)
        self.assertNotIn("/web-advice", command)
        self.assertNotIn("/web-advice", advice)
        self.assertNotIn("Reviewer D", advice)
        advice_readme = readme[readme.index("Use this when you need independent reasoning"):][:1500]
        self.assertIn("`/research` is nonvoting", advice_readme)
        self.assertNotIn("up to three reviewers", advice_readme)
        self.assertNotIn("secondo", advice_readme)
        self.assertNotIn("Reviewer C", advice_readme)

    def test_ready_requires_advice_without_web_advice_fanout(self) -> None:
        ready = skill("ready")
        draft_first = skill("pr-lifecycle")
        advice = skill("advice")
        web_advice_command = (COMMANDS / "web-advice.md").read_text()

        self.assertIn("Use `draft-first-pr` for applicability", (COMMANDS / "ready.md").read_text())
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
        draft_first = skill("pr-lifecycle")
        self.assertIn("`WITHHELD at <SHA>`", draft_first)
        self.assertIn("does not satisfy the draft gate", draft_first)
        self.assertIn("SHA-binding rule", draft_first)

    def test_documentation_only_draft_gate_skips_evidence_review(self) -> None:
        draft_first = skill("pr-lifecycle")
        evidence_review = skill("evidence-review")
        green = skill("pr-green-definition")
        readme = (REPO_ROOT / "README.md").read_text()

        self.assertIn("Documentation-only `/er` exception", draft_first)
        self.assertIn("do not run `/er`", draft_first)
        self.assertIn("`README.md`", draft_first)
        self.assertIn("`docs/**`", draft_first)
        self.assertIn("`.claude/**`", draft_first)
        self.assertIn("Advice applicability requires it", draft_first)
        self.assertIn("PRs still require applicable `/es`", draft_first)
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
        self.assertIn("unless the entire diff qualifies for the explicit trivial-change exception", evidence_review)
        self.assertIn("requires `/er` = **PASS** applicable to the candidate", evidence_review)
        self.assertIn("retaining the original reviewed SHA and documented delta assessment", evidence_review)
        self.assertIn("explicitly requested reviews remain required", draft_first)
        self.assertIn("this workflow policy cannot exempt its own review", draft_first)
        self.assertIn("A one-line change can be high risk", draft_first)
        self.assertIn("outside any low-risk class the repo's own\ninstructions exempt per `pr-lifecycle`", evidence_review)
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

