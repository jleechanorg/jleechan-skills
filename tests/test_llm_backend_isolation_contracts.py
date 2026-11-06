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


def read_skill(name: str) -> str:
    path = SKILLS_DIR / name / "SKILL.md"
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

    def test_llm_first_agent_yaml_is_valid(self):
        agent_path = SKILLS_DIR / "llm-first" / "agents" / "openai.yaml"

        self.assertTrue(agent_path.is_file(), f"missing agent yaml: {agent_path}")
        agent_data = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
        self.assertEqual(agent_data["interface"]["display_name"], "LLM First")
        self.assertIn("$llm-first", agent_data["interface"]["default_prompt"])

    def test_isolate_llm_vs_backend_agent_yaml_is_valid(self):
        agent_path = SKILLS_DIR / "isolate-llm-vs-backend" / "agents" / "openai.yaml"

        self.assertTrue(agent_path.is_file(), f"missing agent yaml: {agent_path}")
        agent_data = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
        self.assertIn("Root Cause First", agent_data["interface"]["display_name"])
        self.assertIn(
            "$isolate-llm-vs-backend", agent_data["interface"]["default_prompt"]
        )


if __name__ == "__main__":
    unittest.main()
