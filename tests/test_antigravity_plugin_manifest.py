"""RED contract test for the Antigravity plugin manifest (bead bd-11g.23)."""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / ".agents" / "plugins" / "plugin.json"
MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"


class AntigravityPluginManifestTest(unittest.TestCase):
    def test_marketplace_json_parses(self):
        data = json.load(open(MARKETPLACE))
        self.assertIsInstance(data, dict)

    def test_plugin_json_declares_name_and_skills_path(self):
        data = json.load(open(PLUGIN))
        self.assertTrue(data["name"].strip())
        self.assertEqual(Path(data["skills"]).parts[-2:], (".claude", "skills"))


if __name__ == "__main__":
    unittest.main()
