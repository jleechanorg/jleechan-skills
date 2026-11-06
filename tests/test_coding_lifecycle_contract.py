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
        links = {}
        for path in SKILLS.rglob("SKILL.md"):
            for match in re.finditer(r"pr-lifecycle/([\w.-]+\.md)#([^)\s\"'>`]+)", path.read_text(encoding="utf-8")):
                links.setdefault((match.group(1), match.group(2)), set()).add(path.relative_to(SKILLS).as_posix())
        self.assertGreater(len(links), 0)
        missing = {}
        for (part, slug), src in links.items():
            target = SKILLS / "pr-lifecycle" / part
            if not target.is_file():
                missing[f"{part}#{slug}"] = sorted(src)
                continue
            if slug not in self._heading_anchors(target.read_text(encoding="utf-8")):
                missing[f"{part}#{slug}"] = sorted(src)
        self.assertEqual(missing, {}, f"unresolved pr-lifecycle anchors: {missing}")


class PrLifecycleSectionReferences(unittest.TestCase):
    """Every `§ Heading` reference to pr-lifecycle, in-file or from another skill, names a real heading.

    A reference resolves when a leading run of its words equals a heading, or the part of a heading
    before its parenthetical or em-dash subtitle, and the remaining words (if any) follow a comma or start with a
    sentence joiner or dash. Bare prefixes such as `§ Merge` do not resolve.
    """

    REF = re.compile(r"§\s*[\"`]?([A-Z][^§.;:()`\"\n]*)")
    JOINERS = {"or", "and", "in", "for", "takes", "to", "still", "governs", "instead", "before",
               "after", "including", "applies", "with", "that", "is", "are", "owns", "below", "above",
               "\u2014", "-"}

    @classmethod
    def _headings(cls):
        heads, fenced = [], False
        # SKILL.md plus its on-demand parts: a `§ Heading` reference resolves anywhere in the skill.
        for path in sorted((SKILLS / "pr-lifecycle").glob("*.md")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.lstrip().startswith("```"):
                    fenced = not fenced
                elif not fenced and line.startswith("#"):
                    heads.append(line.lstrip("#").strip())
        return heads

    @classmethod
    def _resolves(cls, ref, heads):
        words = ref.strip().split()
        for k in range(len(words), 0, -1):
            cand = " ".join(words[:k]).rstrip(",")
            rest = words[k:]
            ends_clause = words[k - 1].endswith(",")
            if rest and not ends_clause and rest[0].lower() not in cls.JOINERS:
                continue
            for h in heads:
                if cand == h or h.startswith(cand + " (") or h.startswith(cand + " \u2014"):
                    return True
        return False

    @classmethod
    def _references(cls):
        refs = []
        own = (SKILLS / "pr-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        for n, line in enumerate(own.splitlines(), 1):
            for m in cls.REF.finditer(line):
                before = line[: m.start()][-90:]
                if "SKILL.md" in before or "AGENTS.md" in before or "pr-green-definition" in before:
                    continue  # points into another file
                refs.append((f"pr-lifecycle:{n}", m.group(1)))
        for path in sorted(SKILLS.rglob("SKILL.md")):
            if path.parent.name == "pr-lifecycle":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for m in cls.REF.finditer(line):
                    before = line[: m.start()]
                    k = before.rfind("pr-lifecycle")
                    if k < 0:
                        continue
                    between = before[k + len("pr-lifecycle"):]
                    if len(between) > 60 or re.search(r"[a-z0-9]+-[a-z0-9-]+(/SKILL\.md)?`", between):
                        continue  # the reference belongs to a different skill named later
                    refs.append((f"{path.parent.name}:{n}", m.group(1)))
        return refs

    def test_section_references_resolve(self):
        heads = self._headings()
        refs = self._references()
        self.assertGreater(len(refs), 10)
        unresolved = [(where, ref.strip()) for where, ref in refs if not self._resolves(ref, heads)]
        self.assertEqual(unresolved, [], f"unresolved pr-lifecycle section references: {unresolved}")

    def test_bare_prefix_and_unknown_references_do_not_resolve(self):
        heads = self._headings()
        for bad in ("Merge", "Merge for details", "Review", "Coding", "Nonexistent section"):
            with self.subTest(bad=bad):
                self.assertFalse(self._resolves(bad, heads))


if __name__ == "__main__":
    unittest.main()

