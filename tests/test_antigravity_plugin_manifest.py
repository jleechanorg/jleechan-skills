"""RED contract test for the Antigravity plugin manifest (bead bd-11g.23)."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / ".agents" / "plugins" / "plugin.json"
MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"


def test_marketplace_json_parses():
    data = json.load(open(MARKETPLACE))
    assert isinstance(data, dict)


def test_plugin_json_declares_name_and_skills_path():
    data = json.load(open(PLUGIN))
    assert data["name"].strip()
    assert Path(data["skills"]).parts[-2:] == (".claude", "skills")
