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
            "~/.claude/skills/parallelize-to-ceiling/SKILL.md",
            parallel,
        )
        self.assertNotIn("## Coding and verification lane routing", parallel)
        self.assertNotIn("## Fallback precedence", parallel)
        self.assertNotIn("## Isolation contract", parallel)
        for required in (
            "## Coding and verification lane routing",
            "~/.claude/agents/agy-pair-coder.md",
            "~/.claude/agents/agy-pair-verifier.md",
            (
                "FALLBACK: if an AGY lane concretely fails, retry that lane with "
                "codexs, claudem, or an own cheap agent while preserving "
                "isolation and independent verification."
            ),
            "## Codex model routing",
            "## Fallback precedence",
            "`FALLBACK` template above is governed by this order:",
            "retry the same bounded lane with",
            "`codexs`, starting at Spark, then advance to Luna, Terra, Sol",
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

        expected_codex_routing = (
            "\nFor Codex parallel lanes, use this ordered fallback and advance "
            "only after a\n"
            "concrete per-lane failure:\n\n"
            "`gpt-5.3-codex-spark` → `gpt-5.6-luna` → "
            "`gpt-5.6-terra` → `gpt-5.6-sol`\n\n"
            "Record the rejection and retry the same bounded lane on the next "
            "model. Never\n"
            "skip directly from Spark to Sol.\n"
        )
        self.assertIn(expected_codex_routing, skill)


if __name__ == "__main__":
    unittest.main()
