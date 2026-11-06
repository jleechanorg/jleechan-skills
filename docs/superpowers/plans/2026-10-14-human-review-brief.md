# Human Review Brief (`human-review-brief`) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the `human-review-brief` skill (`.claude/skills/human-review-brief/SKILL.md`), thin `/what-to-review` command dispatcher (`.claude/commands/what-to-review.md`), `pr-summary` integration, and brief shared `~/.codex/AGENTS.md` pointer so agents end finished work with concise `## What Was Done` and `## What to Review as a Human` sections grounded in 30-day Mac + Linux empirical failure modes.

**Architecture:** Author the portable skill package and contract test in the skills repository (`.claude/skills/human-review-brief/SKILL.md`, `.claude/commands/what-to-review.md`, `.claude/skills/pr-summary/SKILL.md`, `tests/test_human_review_brief_skill.py`), sync the canonical skill and `.agents/skills` discovery symlink to macOS and Linux (`jeff-ubuntu`), and add a 2-line shared policy pointer in `~/.codex/AGENTS.md` (plus 1-line pointer in `~/.gemini/GEMINI.md`) with a `/up` changelog receipt in `~/roadmap/`.

**Tech Stack:** Markdown skill specifications, YAML frontmatter, Python `unittest` contract suite, Git/GitHub CLI (`gh`), SSH/SCP cross-host sync.

---

## TDD Plan Check

| Task | Behavior Change? | TDD Sequence / Verification Check |
|---|---|---|
| **Task 1: Add `.claude/skills/human-review-brief/SKILL.md`, `.claude/commands/what-to-review.md`, and `.claude/skills/pr-summary/SKILL.md` integration** | Yes (adds new skill contract and command dispatcher) | **Full TDD**: Step 1 write failing test `tests/test_human_review_brief_skill.py` -> Step 2 run `python3 -m unittest tests/test_human_review_brief_skill.py -v` and confirm RED (`FileNotFoundError` / missing skill) -> Step 3 write `.claude/skills/human-review-brief/SKILL.md`, `.claude/commands/what-to-review.md`, and update `.claude/skills/pr-summary/SKILL.md` -> Step 4 run `python3 -m unittest discover -s tests -p "test_*.py" -v` and confirm GREEN -> Step 5 commit. |
| **Task 2: Install skill to local Mac (`~/.claude/skills`) and remote Linux (`jeff-ubuntu`), and open skills repo PR** | No (deployment/sync of tested package) | **TDD: N/A (deployment & cross-host file sync)** — Verified by `shasum -a 256` digest equality across repo worktree, Mac `~/.claude/skills/human-review-brief/SKILL.md`, and Linux `~/.claude/skills/human-review-brief/SKILL.md`, plus `readlink` check on `~/.agents/skills/human-review-brief` and `gh pr create` receipt. |
| **Task 3: Apply `/up` pointer to `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md` across Mac & Linux and write `~/roadmap/up-changelog-*.md` receipt** | No (global instruction pointer configuration + changelog receipt) | **TDD: N/A (policy pointer & `/up` receipt)** — Verified by backing up target files to `/tmp/`, grepping `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md` to confirm exactly one canonical pointer and zero prose duplication in `~/.claude/CLAUDE.md`, syncing `~/.codex/AGENTS.md` to Linux, and committing/pushing `~/roadmap/up-changelog-20261014-*.md`. |

---

### Task 1: Author `human-review-brief` Skill, `/what-to-review` Command, and `pr-summary` Integration (TDD)

**Files:**
- Test: `tests/test_human_review_brief_skill.py`
- Create: `.claude/skills/human-review-brief/SKILL.md`
- Create: `.claude/commands/what-to-review.md`
- Modify: `.claude/skills/pr-summary/SKILL.md:50-65`

**Step 1: Write the failing test**

Create `tests/test_human_review_brief_skill.py`:

```python
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "human-review-brief" / "SKILL.md"
COMMAND_PATH = REPO_ROOT / ".claude" / "commands" / "what-to-review.md"
PR_SUMMARY_PATH = REPO_ROOT / ".claude" / "skills" / "pr-summary" / "SKILL.md"


class HumanReviewBriefSkillTests(unittest.TestCase):
    def test_skill_exists_with_valid_frontmatter_and_core_sections(self) -> None:
        self.assertTrue(SKILL_PATH.is_file(), f"Missing skill file: {SKILL_PATH}")
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "Skill must start with YAML frontmatter")
        self.assertIn("name: human-review-brief", text)
        self.assertIn("## What Was Done", text)
        self.assertIn("## What to Review as a Human", text)
        self.assertIn("What Current Evidence Does NOT Prove", text)
        self.assertIn("git merge-tree --write-tree", text)

    def test_skill_covers_mac_and_linux_empirical_blind_spots(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        for required_phrase in (
            "Visual / UX / Hidden-State Verification",
            "Main-Merge Smuggling, Stale Base Diffs & Silent Reverts",
            "Partial, Stale-SHA, or Substitute-Provider Gates",
            "Product Constants, Cooldowns & Prompt Compression",
            "Zero-Framework Cognition (ZFC) & Scope-Blind Backend Guards",
            "Cross-PR Stack & Shared Token/Budget Ratchets",
            "Provider-Boundary & Structured-Output Schema Complexity",
            "Cross-Host (macOS vs Linux) & Viewport Parity",
            "Linux Systemd / Cgroup Live State & Runner Side Effects",
            "Delivery vs Execution, Subprocess Stdin & Hook Hygiene",
        ):
            self.assertIn(required_phrase, text)

    def test_command_dispatcher_points_to_skill(self) -> None:
        self.assertTrue(COMMAND_PATH.is_file(), f"Missing command file: {COMMAND_PATH}")
        cmd_text = COMMAND_PATH.read_text(encoding="utf-8")
        self.assertIn("human-review-brief/SKILL.md", cmd_text)

    def test_pr_summary_links_to_human_review_brief(self) -> None:
        pr_summary_text = PR_SUMMARY_PATH.read_text(encoding="utf-8")
        self.assertIn("What to Review as a Human", pr_summary_text)
        self.assertIn("human-review-brief/SKILL.md", pr_summary_text)

    def test_portability_no_hardcoded_personal_paths(self) -> None:
        for path in (SKILL_PATH, COMMAND_PATH, PR_SUMMARY_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"/(Users|home)/[A-Za-z0-9_.-]+/", text),
                f"Non-portable user path found in {path}",
            )


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:
```bash
python3 -m unittest tests/test_human_review_brief_skill.py -v
```
Expected: `FAIL` with `AssertionError: False is not true : Missing skill file: .../.claude/skills/human-review-brief/SKILL.md`.

**Step 3: Write minimal implementation**

1. Create `.claude/skills/human-review-brief/SKILL.md` defining:
   - Frontmatter (`name: human-review-brief`, `description: ...`).
   - When to apply: at the end of any substantive coding, PR-driving, review, or readiness-reporting turn, and inside `/pr-summary` reports.
   - Section 1 (`## What Was Done`): Deliverable + full GitHub PR/commit URLs, Production vs Non-Production LOC delta (`prod +X/-Y, non-prod +A/-B` with `/ponytail` bloat check), `git merge-tree --write-tree origin/main HEAD` cleanliness check against silent main reverts or formatter smuggling, and SHA-bound gate matrix.
   - Section 2 (`## What to Review as a Human`): Dynamic 3–6 bullet selection from the 10 empirical Mac + Linux blind-spot categories, plus mandatory `What Current Evidence Does NOT Prove` and `Exact Human Decision Needed`.
2. Create `.claude/commands/what-to-review.md` dispatching to `~/.claude/skills/human-review-brief/SKILL.md`.
3. Update `.claude/skills/pr-summary/SKILL.md` to add `#### ### What to Review as a Human (Judgment Calls & Blind-Spot Audit)` referencing `~/.claude/skills/human-review-brief/SKILL.md` (and replace any hardcoded `/Users/<user>` examples in `.claude/skills/pr-summary/SKILL.md` with portable `~/...` or `$HOME/...` paths).

**Step 4: Run tests to verify they pass**

Run:
```bash
python3 -m unittest tests/test_human_review_brief_skill.py -v
python3 -m unittest discover -s tests -p "test_*.py" -v
```
Expected: `OK` (all unit and repository contract tests pass).

**Step 5: Commit**

```bash
git add tests/test_human_review_brief_skill.py .claude/skills/human-review-brief/SKILL.md .claude/commands/what-to-review.md .claude/skills/pr-summary/SKILL.md docs/superpowers/specs/2026-10-14-human-review-brief-design.md docs/superpowers/plans/2026-10-14-human-review-brief.md
git commit -m "gemini/gemini-4-argon: feat(skills): add human-review-brief skill and pr-summary human review checklist [gemini][gemini-4-argon]"
```

---

### Task 2: Sync Skill Package Across Mac, Linux (`jeff-ubuntu`), and Skills Repo PR

**Files:**
- Sync target (Mac): `~/.claude/skills/human-review-brief/SKILL.md`, `~/.agents/skills/human-review-brief`, `~/.claude/commands/what-to-review.md`, `~/.claude/skills/pr-summary/SKILL.md`
- Sync target (Linux `jeff-ubuntu`): `~/.claude/skills/human-review-brief/SKILL.md`, `~/.agents/skills/human-review-brief`, `~/.claude/commands/what-to-review.md`, `~/.claude/skills/pr-summary/SKILL.md`

**Step 1: Copy files to local Mac canonical skill/command roots and create `.agents/skills` symlink**

```bash
mkdir -p "$HOME/.claude/skills/human-review-brief"
cp .claude/skills/human-review-brief/SKILL.md "$HOME/.claude/skills/human-review-brief/SKILL.md"
cp .claude/commands/what-to-review.md "$HOME/.claude/commands/what-to-review.md"
cp .claude/skills/pr-summary/SKILL.md "$HOME/.claude/skills/pr-summary/SKILL.md"
ln -sfn "$HOME/.claude/skills/human-review-brief" "$HOME/.agents/skills/human-review-brief"
```

**Step 2: Sync files to Linux (`jeff-ubuntu`) and create `.agents/skills` symlink**

```bash
ssh jeff-ubuntu 'mkdir -p ~/.claude/skills/human-review-brief ~/.claude/commands ~/.agents/skills'
scp .claude/skills/human-review-brief/SKILL.md jeff-ubuntu:~/.claude/skills/human-review-brief/SKILL.md
scp .claude/commands/what-to-review.md jeff-ubuntu:~/.claude/commands/what-to-review.md
scp .claude/skills/pr-summary/SKILL.md jeff-ubuntu:~/.claude/skills/pr-summary/SKILL.md
ssh jeff-ubuntu 'ln -sfn ~/.claude/skills/human-review-brief ~/.agents/skills/human-review-brief'
```

**Step 3: Verify SHA-256 digests across all three targets and push PR**

```bash
shasum -a 256 .claude/skills/human-review-brief/SKILL.md "$HOME/.claude/skills/human-review-brief/SKILL.md"
ssh jeff-ubuntu 'sha256sum ~/.claude/skills/human-review-brief/SKILL.md'
git push -u origin feat/human-review-brief-skill
```

---

### Task 3: Add Shared Policy Pointer via `/up` (`~/.codex/AGENTS.md` & `~/.gemini/GEMINI.md`) and Write Receipt

**Files:**
- Modify (Mac & Linux): `~/.codex/AGENTS.md` (`## Review, output, and scope discipline`)
- Modify (Mac): `~/.gemini/GEMINI.md` (`## Canonical Instruction Files & Authoritative Skills`)
- Create: `~/roadmap/up-changelog-20261014-0235.md`

**Step 1: Back up `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md` to `/tmp/`**

```bash
BACKUP_DIR="$(mktemp -d /tmp/up_backup.XXXXXX)"
cp "$HOME/.codex/AGENTS.md" "$BACKUP_DIR/AGENTS.md.bak"
cp "$HOME/.gemini/GEMINI.md" "$BACKUP_DIR/GEMINI.md.bak"
```

**Step 2: Add the 2-line pointer to `~/.codex/AGENTS.md` and 1-line pointer to `~/.gemini/GEMINI.md`**

- In `~/.codex/AGENTS.md` under `## Review, output, and scope discipline`, append:
  `When finishing coding, PR updates, or readiness reviews, end with concise ## What Was Done (full PR/commit URLs, prod vs non-prod LOC delta, git merge-tree cleanliness vs origin/main, and SHA-bound gate matrix) and ## What to Review as a Human (visual/UX frames, prompt/constant/ZFC judgment calls, cross-host/systemd/schema hazards, what current evidence does NOT prove, and exact human decision needed) per ~/.claude/skills/human-review-brief/SKILL.md.`
- In `~/.gemini/GEMINI.md` under `## Canonical Instruction Files & Authoritative Skills`, append:
  `- **Human Review Brief (/what-to-review)**: [~/.claude/skills/human-review-brief/SKILL.md]($HOME/.claude/skills/human-review-brief/SKILL.md)`

**Step 3: Verify single canonical copy and write `/up` brief report receipt**

```bash
grep -n "human-review-brief/SKILL.md" "$HOME/.codex/AGENTS.md" "$HOME/.gemini/GEMINI.md" "$HOME/.claude/CLAUDE.md" || true
```
Expected: matches in `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md`; 0 duplicate lines in `~/.claude/CLAUDE.md` (which loads `@~/.codex/AGENTS.md`). Write the 3-column `/up` receipt table to `~/roadmap/up-changelog-20261014-0235.md`.
