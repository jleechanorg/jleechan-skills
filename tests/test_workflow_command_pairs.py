"""Contracts for exported workflow command and skill pairs."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / ".claude" / "commands"
SKILLS = REPO_ROOT / ".claude" / "skills"


class WorkflowCommandPairTest(unittest.TestCase):
    def test_core_workflows_export_complete_packages(self):
        for name in ("nextsteps", "plan-micro", "ready"):
            with self.subTest(workflow=name):
                command = COMMANDS / f"{name}.md"
                skill = SKILLS / name / "SKILL.md"
                self.assertTrue(command.is_file(), command)
                self.assertTrue(skill.is_file(), skill)
                self.assertIn(
                    f"${{CLAUDE_HOME:-$HOME/.claude}}/skills/{name}/SKILL.md",
                    command.read_text(encoding="utf-8"),
                )

        self.assertTrue(
            (
                SKILLS
                / "plan-micro"
                / "references"
                / "history-baseline-2026-08-04-06.md"
            ).is_file()
        )

    def test_plan_micro_exports_its_required_command_dependencies(self):
        plan_micro = (SKILLS / "plan-micro" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for name in ("e", "ironclad", "p"):
            with self.subTest(command=name):
                self.assertIn(f"/{name}", plan_micro)
                self.assertTrue((COMMANDS / f"{name}.md").is_file())

        self.assertTrue((SKILLS / "ironclad" / "SKILL.md").is_file())
        self.assertTrue(
            (SKILLS / "parallelize-to-ceiling" / "SKILL.md").is_file()
        )

    def test_parallel_command_points_to_canonical_lane_routing_contract(self):
        parallel = (COMMANDS / "extended-library" / "parallel.md").read_text(
            encoding="utf-8"
        )
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md",
            parallel,
        )
        self.assertNotIn("## Coding and verification lane routing", parallel)
        self.assertNotIn("## Fallback precedence", parallel)
        self.assertNotIn("## Isolation contract", parallel)
        for required in (
            "## Coding and verification lane routing",
            "${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md",
            "${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md",
            (
                "FALLBACK: if an AGY lane concretely fails, retry that lane with "
                "codexs, claudem, or an own cheap agent while preserving "
                "isolation and independent verification."
            ),
            "## Codex model routing",
            "## Fallback precedence",
            "`FALLBACK` template above is governed by this order:",
            "retry the same bounded lane with",
            "invoke the Codex CLI explicitly with `-m gpt-5.6-luna`, then",
            "Use `claudem` or an own cheap agent only when the ordered Codex",
            "unavailable; preserve the same bounded scope",
            "## Isolation contract",
            "distinct lanes and contexts",
            "disjoint workspace/output",
            "verifier must",
            "independently rerun focused checks before signaling completion",
        ):
            with self.subTest(required=required):
                self.assertIn(required, skill)

        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "`codexs` as the Spark fallback; codexs is not a multi-model router",
            normalized_skill,
        )
        self.assertIn(
            "`gpt-5.3-codex-spark` → `gpt-5.6-luna` → "
            "`gpt-5.6-terra` → `gpt-5.6-sol`",
            skill,
        )
        self.assertIn(
            "retry the same bounded lane with the next explicit model",
            normalized_skill,
        )

    def test_retry_isolation_covers_every_attempt_and_prior_attempts(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "Every attempt, including initial execution and each retry, uses a "
            "fresh workspace and output disjoint from both coder and verifier "
            "lanes and from all previous attempts.",
            normalized_skill,
        )

    def test_parallel_contract_uses_configurable_claude_home(self):
        paths = (
            COMMANDS / "extended-library" / "parallel.md",
            COMMANDS / "p.md",
            SKILLS / "parallelize-to-ceiling" / "SKILL.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md",
        )
        for path in paths:
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("~/.claude/", content)
        for path in paths[:3]:
            self.assertIn(
                "${CLAUDE_HOME:-$HOME/.claude}",
                path.read_text(encoding="utf-8"),
            )

    def test_retry_contract_forbids_conversation_reuse(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        for name, content in (
            ("skill", skill),
            ("coder", coder),
            ("verifier", verifier),
        ):
            with self.subTest(document=name):
                self.assertNotIn("--continue", content)
                self.assertNotIn("--conversation", content)
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "Every retry uses a fresh worktree and unique output/log paths",
            normalized_skill,
        )
        self.assertIn("fresh `agy --new-project`", normalized_skill)

    def test_implementation_ready_carries_exact_revision_handoff(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        for name, content in (("skill", skill), ("coder", coder)):
            with self.subTest(document=name):
                self.assertIn("Revision: <exact git SHA>", content)
                self.assertIn("Worktree: <absolute path>", content)
        self.assertIn("git rev-parse HEAD", coder)

    def test_codexs_fallback_does_not_claim_multi_model_routing(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "`codexs` as the Spark fallback; codexs is not a multi-model router.",
            normalized_skill,
        )
        self.assertIn(
            "invoke the Codex CLI explicitly with `-m gpt-5.6-luna`, then "
            "`-m gpt-5.6-terra`, then `-m gpt-5.6-sol`",
            normalized_skill,
        )


if __name__ == "__main__":
    unittest.main()
