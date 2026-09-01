"""Contract tests for /nextsteps lean mode default and thin command dispatch."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEXTSTEPS_CMD = REPO_ROOT / ".claude" / "commands" / "nextsteps.md"
NEXTSTEPS_SKILL = REPO_ROOT / ".claude" / "skills" / "nextsteps" / "SKILL.md"

USER_REQUEST = (
    "Make /nextsteps only do beads and ~/roadmap and /nextsteps --full does everything"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_checklist_body(text: str, header_regex: str):
    """Find a `**...:**` checklist header and return the body of `- [x] ...`
    bullets that follow it, up to the next bold-header or `---` separator.
    Returns (body, end_index) or (None, -1) if the header is missing.
    """
    m = re.search(header_regex, text)
    if not m:
        return None, -1
    start = m.end()
    rest = text[start:]
    body_lines = []
    pos = 0
    seen_bullet = False
    for line in rest.split("\n"):
        if re.match(r"^-\s+`?\[[ xX]\]`?\s+", line):
            body_lines.append(line)
            seen_bullet = True
            pos += len(line) + 1
        elif (
            seen_bullet
            and line.strip().startswith("**")
            or seen_bullet
            and line.strip().startswith("---")
        ):
            break
        elif line.strip() == "":
            pos += len(line) + 1
            continue
        else:
            if seen_bullet:
                break
            pos += len(line) + 1
    return "\n".join(body_lines), start + pos


class NextstepsCommandContractTest(unittest.TestCase):
    """Contract for .claude/commands/nextsteps.md — thin argument-forwarding pointer."""

    def setUp(self):
        self.assertTrue(
            NEXTSTEPS_CMD.is_file(),
            f"nextsteps command file missing at {NEXTSTEPS_CMD}",
        )
        self.text = read(NEXTSTEPS_CMD)
        self.lines = self.text.splitlines()

    def test_has_yaml_frontmatter(self):
        self.assertTrue(
            self.text.startswith("---\n"),
            "nextsteps command file must start with YAML frontmatter",
        )
        end = self.text.find("\n---\n", 4)
        self.assertGreater(
            end,
            4,
            "nextsteps command YAML frontmatter must close with a second `---` line.",
        )

    def test_is_thin_argument_forwarding_pointer(self):
        self.assertLessEqual(
            len(self.lines),
            15,
            f"nextsteps command file must be <= 15 lines (got {len(self.lines)})",
        )
        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/nextsteps/SKILL.md",
            self.text,
        )
        self.assertIn("$ARGUMENTS", self.text)

    def test_command_is_not_thick(self):
        """Heavy tables, phase breakdowns, and side-effect logic must NOT live in the command file."""
        self.assertNotIn("| Phase |", self.text)
        self.assertNotIn("[x]", self.text)
        self.assertNotIn("Phase 4", self.text)
        self.assertNotIn("mem0_shared_client", self.text)


class NextstepsSkillContractTest(unittest.TestCase):
    """Contract for .claude/skills/nextsteps/SKILL.md — canonical skill handling lean mode."""

    def setUp(self):
        self.assertTrue(
            NEXTSTEPS_SKILL.is_file(),
            f"nextsteps skill missing at {NEXTSTEPS_SKILL}",
        )
        self.text = read(NEXTSTEPS_SKILL)

    def test_modes_section_exists(self):
        self.assertRegex(
            self.text,
            r"##\s+[Mm]odes(\b|\s|\()",
            "skill must have a `## Modes` section naming default and --full",
        )

    def test_default_mode_only_uses_beads_and_roadmap(self):
        sentence_patterns = [
            r"default.*only.*beads.*~/roadmap",
            r"only does? beads.*~/roadmap",
        ]
        table_pattern = r"\|.*default.*\|.*beads.*~/roadmap"
        combined = self.text
        ok = any(
            re.search(p, combined, re.IGNORECASE | re.DOTALL) for p in sentence_patterns
        ) or re.search(table_pattern, combined, re.IGNORECASE | re.DOTALL)
        self.assertTrue(
            ok,
            "default mode must be explicitly scoped to beads + ~/roadmap",
        )

    def test_full_mode_does_everything(self):
        sentence_patterns = [
            r"--full.*does everything",
            r"--full.*legacy all-source",
            r"--full.*preserves.*legacy",
        ]
        table_pattern = r"\|.*--full.*\|.*Claude.*memory.*mem0.*GH\s*Issues"
        combined = self.text
        ok = any(
            re.search(p, combined, re.IGNORECASE | re.DOTALL) for p in sentence_patterns
        ) or re.search(table_pattern, combined, re.IGNORECASE | re.DOTALL)
        self.assertTrue(
            ok,
            "--full mode must explicitly preserve legacy all-source behavior",
        )

    def test_side_effecting_phases_marked_full_only(self):
        for phase_num, phase_name in (
            ("Phase 4", "Claude auto-memory"),
            ("Phase 5", "mem0"),
            ("Phase 7b", "GitHub Issue"),
        ):
            pattern = rf"###+\s+{re.escape(phase_num)}[^#\n]*{phase_name}[^#\n]*`--full`\s*only"
            self.assertRegex(
                self.text,
                pattern,
                f"{phase_num} ({phase_name}) must be tagged as `--full` only in skill heading.",
            )

    def test_default_mode_checklist_present(self):
        body, _ = _extract_checklist_body(self.text, r"\*\*Default mode checklist:\*\*")
        self.assertIsNotNone(
            body,
            "skill must include a `Default mode checklist:` block under Phase 8",
        )
        done_bullets = "\n".join(
            line for line in body.split("\n") if re.search(r"\[x\]", line)
        )
        self.assertIn("Beads", done_bullets)
        self.assertIn("learnings-YYYY-MM.md", done_bullets)
        for forbidden in ("Claude memory", "mem0", "GH Issue"):
            self.assertNotIn(
                forbidden,
                done_bullets,
                f"default-mode checklist must not claim to write `{forbidden}`",
            )

    def test_full_mode_checklist_present(self):
        body, _ = _extract_checklist_body(
            self.text, r"\*\*`--full` mode checklist:\*\*"
        )
        self.assertIsNotNone(
            body,
            "skill must include a `--full` mode checklist: block under Phase 8",
        )
        for required in ("Beads", "Claude memory", "MEMORY.md", "mem0", "GH Issue"):
            self.assertIn(
                required,
                body,
                f"--full checklist must include `{required}`",
            )

    def test_preserves_user_request_verbatim(self):
        self.assertIn(
            USER_REQUEST,
            self.text,
            f"user's verbatim request must be preserved in skill. Request: {USER_REQUEST!r}",
        )


class NextstepsModeParsingTest(unittest.TestCase):
    """Sanity checks for documented flag parsing rules."""

    def test_skill_documents_flag_parsing_rules(self):
        for needle in (
            "first non-whitespace token",
            "exactly `--full`",
            "strip it from the brief",
        ):
            self.assertIn(
                needle,
                self.text,
                f"skill must document the flag-parsing rule: `{needle}`",
            )

    def setUp(self):
        self.text = read(NEXTSTEPS_SKILL)

    def test_mode_report_examples_present(self):
        self.assertIn("Mode: default", self.text)
        self.assertIn("Mode: --full", self.text)


if __name__ == "__main__":
    unittest.main()
