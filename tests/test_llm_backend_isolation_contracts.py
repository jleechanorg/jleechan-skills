"""Contracts for generalized LLM vs backend isolation skills (bd-u1c).

Covers root-cause-first (3-lane diagnostic router), llm-first (model contract compliance),
backend-first (deterministic execution proof), isolate-llm-vs-backend (alias), and
end2end-testing (telemetry fixture provenance).
"""

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


def read_skill(name: str) -> str:
    path = SKILLS_DIR / name / "SKILL.md"
    return path.read_text(encoding="utf-8")


def read_command(name: str) -> str:
    path = COMMANDS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def read_frontmatter(text: str) -> dict:
    _, frontmatter, _ = text.split("---", 2)
    return yaml.safe_load(frontmatter)


class LLMBackendIsolationContractsTest(unittest.TestCase):
    def test_all_affected_skills_have_portable_frontmatter(self):
        allowed_keys = {
            "name",
            "description",
            "license",
            "compatibility",
            "allowed-tools",
            "metadata",
        }
        for name in (
            "root-cause-first",
            "llm-first",
            "backend-first",
            "isolate-llm-vs-backend",
            "end2end-testing",
        ):
            with self.subTest(skill=name):
                frontmatter = read_frontmatter(read_skill(name))
                self.assertEqual(frontmatter["name"], name)
                self.assertTrue(frontmatter["description"].startswith("Use when"))
                self.assertLessEqual(set(frontmatter), allowed_keys)

    def test_root_cause_first_implements_three_lane_router(self):
        skill_text = read_skill("root-cause-first")
        command_text = read_command("root-cause-first")

        self.assertIn("ROOT CAUSE ROUTE: LLM", skill_text)
        self.assertIn("ROOT CAUSE ROUTE: BACKEND", skill_text)
        self.assertIn("ROOT CAUSE ROUTE: UNDER-INSTRUMENTED", skill_text)

        self.assertNotIn("`.claude/skills/", skill_text)
        self.assertIn("/llm-first", skill_text)
        self.assertIn("/backend-first", skill_text)

        self.assertIn("server-owned invariant", skill_text)
        self.assertIn("backend-transformation fix", skill_text)
        self.assertIn("prompt/schema-insufficient with raw-path proof", skill_text)
        self.assertIn("unproven fallback", skill_text)
        self.assertIn("model-ownership violation candidate", skill_text)
        self.assertIn("ZFC violation candidate", skill_text)

        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/root-cause-first/SKILL.md",
            command_text,
        )

    def test_root_cause_first_review_consumers_are_fail_closed(self):
        root_skill = read_skill("root-cause-first")
        command_text = read_command("root-cause-first")
        review_consumers = (
            SKILLS_DIR / "code-standards" / "SKILL.md",
            SKILLS_DIR / "zero-framework-cognition" / "SKILL.md",
            COMMANDS_DIR / "extended-library" / "zfc.md",
        )

        self.assertIn("Direct diagnostic mode", root_skill)
        self.assertIn("Review-only mode", root_skill)
        self.assertIn("loaded by another review", root_skill)
        self.assertIn("stop before executing `/llm-first` or `/backend-first`", root_skill)
        self.assertIn("/skills/root-cause-first/SKILL.md", command_text)

        for consumer_path in review_consumers:
            with self.subTest(consumer=consumer_path.relative_to(REPO_ROOT)):
                consumer_text = consumer_path.read_text(encoding="utf-8")
                self.assertIn("review-only mode", consumer_text)

    def test_all_isolation_skills_exclude_project_specific_contracts(self):
        for name in (
            "root-cause-first",
            "llm-first",
            "backend-first",
            "isolate-llm-vs-backend",
            "end2end-testing",
        ):
            skill_text = read_skill(name)
            with self.subTest(skill=name):
                for project_specific_token in (
                    "mvp_site",
                    "WORLDAI_",
                    "test_god_mode",
                    "worldarchitect.ai",
                ):
                    self.assertNotIn(project_specific_token, skill_text)

    def test_llm_first_enforces_frozen_backend_and_attributable_ablation(self):
        skill_text = read_skill("llm-first")
        command_text = read_command("llm-first")
        agent_path = SKILLS_DIR / "llm-first" / "agents" / "openai.yaml"

        self.assertIn("freeze parser, reducer, persistence", skill_text)
        self.assertIn("One-variable discipline", skill_text)
        self.assertIn("Ablation and removal first", skill_text)
        self.assertIn("LLM CONTRACT GREEN", skill_text)
        self.assertIn("LLM CONTRACT RED", skill_text)
        self.assertIn("Backend behavior: FROZEN / NOT PROVEN", skill_text)
        self.assertIn("deliberate bundle", skill_text)
        self.assertIn("loaded every prompt file", skill_text)
        self.assertIn("numeric PII", skill_text)
        self.assertNotIn("`.claude/skills/", skill_text)

        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/llm-first/SKILL.md", command_text
        )

        self.assertTrue(agent_path.is_file(), f"missing agent yaml: {agent_path}")
        agent_data = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
        self.assertEqual(agent_data["interface"]["display_name"], "LLM First")
        self.assertIn("$llm-first", agent_data["interface"]["default_prompt"])

    def test_backend_first_enforces_frozen_model_and_telemetry_fixtures(self):
        skill_text = read_skill("backend-first")
        command_text = read_command("backend-first")

        self.assertIn("Freeze prompts, routing, provider configuration", skill_text)
        self.assertIn("BACKEND READY", skill_text)
        self.assertIn("SYNTHETIC CONTRACT FIXTURE", skill_text)
        self.assertIn("Live LLM compliance: NOT TESTED / PROVEN SEPARATELY", skill_text)
        self.assertNotIn("`.claude/skills/", skill_text)

        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/backend-first/SKILL.md",
            command_text,
        )

    def test_isolate_llm_vs_backend_is_compatibility_alias(self):
        skill_text = read_skill("isolate-llm-vs-backend")
        agent_path = SKILLS_DIR / "isolate-llm-vs-backend" / "agents" / "openai.yaml"

        self.assertIn("Compatibility alias only", skill_text)
        self.assertNotIn("`.claude/skills/", skill_text)
        self.assertIn("/root-cause-first", skill_text)

        self.assertTrue(agent_path.is_file(), f"missing agent yaml: {agent_path}")
        agent_data = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
        self.assertIn("Root Cause First", agent_data["interface"]["display_name"])
        self.assertIn(
            "$isolate-llm-vs-backend", agent_data["interface"]["default_prompt"]
        )

    def test_end2end_testing_includes_telemetry_source_preference(self):
        skill_text = read_skill("end2end-testing")
        command_text = read_command("end2end-testing")

        self.assertIn("Source preference and fallback labels", skill_text)
        self.assertIn("SYNTHETIC CONTRACT FIXTURE", skill_text)
        self.assertIn("`occurred_at`, `request_id`, `event_type`", skill_text)
        self.assertIn("numeric PII", skill_text)
        self.assertLess(
            skill_text.index("production or staging"),
            skill_text.index("local raw provider transport capture"),
        )
        self.assertLess(
            skill_text.index("local raw provider transport capture"),
            skill_text.index("SYNTHETIC CONTRACT FIXTURE"),
        )
        for project_specific_token in (
            "mvp_site",
            "WORLDAI_",
            "test_god_mode",
            "worldarchitect.ai",
        ):
            self.assertNotIn(project_specific_token, skill_text)
        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/end2end-testing/SKILL.md",
            command_text,
        )
        self.assertIn("$ARGUMENTS", command_text)


if __name__ == "__main__":
    unittest.main()
