"""Structural invariants for opt-in plugin folders under plugins/."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS = ROOT / "plugins"
EXPECTED = {"worldarchitect", "ai-universe", "self-hosted-runners"}


def frontmatter_name(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return None


LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PLUGIN_ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}/"


def markdown_link_targets(text):
    """Relative link targets outside fenced code blocks (no URLs, no bare anchors)."""
    targets = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for raw in LINK.findall(line):
            target = raw.strip("<>").split("#", 1)[0]
            if not target or "://" in raw or raw.startswith(("mailto:", "#")):
                continue
            targets.append(target)
    return targets


def plugin_dirs():
    return sorted(p for p in PLUGINS.iterdir() if p.is_dir())


def skill_dirs(plugin):
    skills = plugin / "skills"
    if not skills.is_dir():
        return []
    return sorted(p for p in skills.iterdir() if p.is_dir())


class PluginFoldersTest(unittest.TestCase):
    def test_marketplace_sources_exist(self):
        for p in json.loads(MARKET.read_text())["plugins"]:
            src = p["source"]
            if isinstance(src, str):
                self.assertTrue((ROOT / src).is_dir(), src)

    def test_expected_plugins_registered(self):
        names = {p["name"] for p in json.loads(MARKET.read_text())["plugins"]}
        self.assertTrue(EXPECTED <= names, EXPECTED - names)

    def test_plugin_manifests_and_skills(self):
        self.assertTrue(PLUGINS.is_dir(), "plugins/ missing")
        for d in plugin_dirs():
            manifest = json.loads((d / ".claude-plugin" / "plugin.json").read_text())
            self.assertEqual(manifest["name"], d.name)
            self.assertTrue(skill_dirs(d), f"{d.name}: plugin has no skills/<name>/ directory")
            for skill in skill_dirs(d):
                with self.subTest(skill=str(skill.relative_to(ROOT))):
                    self.assertEqual(
                        frontmatter_name((skill / "SKILL.md").read_text()), skill.name
                    )

    def test_plugin_markdown_links_stay_inside_plugin(self):
        """An installed plugin is copied out of the repo, so links must not escape it."""
        self.assertTrue(PLUGINS.is_dir(), "plugins/ missing")
        for d in plugin_dirs():
            plugin_root = d.resolve()
            for md in sorted(d.rglob("*.md")):
                for target in markdown_link_targets(md.read_text(encoding="utf-8")):
                    with self.subTest(file=str(md.relative_to(ROOT)), link=target):
                        if target.startswith(PLUGIN_ROOT_VAR):
                            resolved = (plugin_root / target[len(PLUGIN_ROOT_VAR):]).resolve()
                        else:
                            resolved = (md.parent / target).resolve()
                        self.assertTrue(
                            resolved == plugin_root or plugin_root in resolved.parents,
                            f"link escapes plugin {d.name}",
                        )
                        self.assertTrue(resolved.exists(), "link target missing")

    def test_no_name_in_both_export_and_plugin(self):
        self.assertTrue(PLUGINS.is_dir(), "plugins/ missing")
        export = {p.name for p in (ROOT / ".claude" / "skills").iterdir() if p.is_dir()}
        for d in plugin_dirs():
            overlap = export & {p.name for p in skill_dirs(d)}
            self.assertFalse(overlap, f"{d.name}: {sorted(overlap)}")

    def test_moved_skills_are_not_referenced_at_the_export_path(self):
        """A moved skill lives in its plugin; `.claude/skills/<name>/` is a dead path."""
        self.assertTrue(PLUGINS.is_dir(), "plugins/ missing")
        moved = {s.name for d in plugin_dirs() for s in skill_dirs(d)}
        # `${CLAUDE_HOME:-$HOME/.claude}/skills/x/`, `~/.claude/skills/x/`,
        # `.claude/skills/x/` and `$CLAUDE_HOME/skills/x/` all resolve through the
        # generic export; a plugin-relative `skills/x/` has no leading path prefix.
        export_ref = re.compile(r"([^\s`\"'()]*)/skills/([A-Za-z0-9._-]+)/")
        offenders = []
        for d in plugin_dirs():
            for path in sorted(d.rglob("*")):
                if not path.is_file() or path.suffix not in {".md", ".sh", ".py", ".json", ".mjs"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for prefix, name in export_ref.findall(text):
                    if name in moved and any(
                        marker in prefix.lower() for marker in ("claude", "codex", "hermes")
                    ):
                        offenders.append(f"{path.relative_to(ROOT)} -> {prefix}/skills/{name}/")
        self.assertEqual(
            offenders,
            [],
            "A plugin must resolve its own skills inside the plugin, not at the "
            "generic export path that no longer holds them. Offenders:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
