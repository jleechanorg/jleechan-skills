"""Structural guards for pr-lifecycle: frontmatter name, linked anchors and in-file section references."""

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"


def read(name: str) -> str:
    """Skill text with whitespace collapsed so assertions ignore line wrapping."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    return " ".join(text.split())


class CodingLifecycleContract(unittest.TestCase):
    def test_pr_lifecycle_frontmatter_name_matches_directory(self):
        self.assertIn("name: pr-lifecycle", read("pr-lifecycle"))


class PrLifecycleAnchorResolution(unittest.TestCase):
    """Every `pr-lifecycle/SKILL.md#<slug>` link in the skill catalog resolves to a heading.

    Compaction edits must not reword a heading that a sibling links to. Targets are
    discovered by scanning, not hard-coded, so new links are covered automatically.
    """

    @staticmethod
    def _github_slug(heading: str) -> str:
        text = heading.strip().lstrip("#").strip().lower()
        text = re.sub(r"[^\w\- ]", "", text)
        return text.replace(" ", "-")

    @classmethod
    def _heading_anchors(cls, markdown: str) -> set:
        """Anchors GitHub generates: skips fenced code, suffixes duplicates with -1, -2, ..."""
        anchors = set()
        seen = {}
        in_fence = False
        for line in markdown.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or not line.startswith("#"):
                continue
            slug = cls._github_slug(line)
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            anchors.add(slug if count == 0 else f"{slug}-{count}")
        return anchors

    def test_every_linked_anchor_resolves_to_a_heading(self):
        owner = (SKILLS / "pr-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        headings = self._heading_anchors(owner)
        links = {}
        for path in SKILLS.rglob("SKILL.md"):
            for match in re.finditer(r"pr-lifecycle/SKILL\.md#([^)\s\"'>`]+)", path.read_text(encoding="utf-8")):
                links.setdefault(match.group(1), set()).add(path.relative_to(SKILLS).as_posix())
        self.assertGreater(len(links), 0)
        missing = {slug: sorted(src) for slug, src in links.items() if slug not in headings}
        self.assertEqual(missing, {}, f"unresolved pr-lifecycle anchors: {missing}")


class PrLifecycleSectionReferences(unittest.TestCase):
    """Every in-file `§ Heading` reference in pr-lifecycle names a real heading."""

    def test_self_section_references_resolve(self):
        text = (SKILLS / "pr-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        headings = [line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#")]
        unresolved = []
        for match in re.finditer(r"§ ([A-Z][^.;:,()`\n]*)", text):
            line_prefix = text[: match.start()].rsplit("\n", 1)[-1][-90:]
            if "SKILL.md" in line_prefix or "AGENTS.md" in line_prefix:
                continue  # reference into another file
            ref = match.group(1).strip()
            if not any(ref == h or ref.startswith(h + " ") or h.startswith(ref + " (") for h in headings):
                unresolved.append(ref)
        self.assertEqual(unresolved, [], f"unresolved § references: {unresolved}")


if __name__ == "__main__":
    unittest.main()

