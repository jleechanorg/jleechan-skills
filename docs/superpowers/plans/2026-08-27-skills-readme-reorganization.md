# Skills Catalog Reorganization & Promotion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize the README skills catalog into a structured 5-tier functional taxonomy, promote essential engineering discipline skills, and maintain strict link integrity and test contract compatibility.

**Architecture:** Refactor `README.md` to introduce categorized sub-tables for each functional tier while retaining the top-level Left/Right Shift Executive Summary and command reference anchors. Add regression test assertions to ensure promoted skills, canonical paths, and external attributions remain intact across future updates.

**Tech Stack:** Markdown, Python 3.13 / pytest, Git

---

### Task 1: Add Unit Tests for Promoted Skills in Catalog

**Files:**
- Modify: `tests/test_readme_skill_counts.py`

**Step 1: Write the failing test**

Add assertions verifying that newly promoted skills (`root-cause-first`, `ponytail`, `draft-first-pr`, `zero-framework-cognition`) and third-party attribution are explicitly present in `README.md`.

```python
    def test_readme_contains_promoted_discipline_skills_and_attribution(self):
        text = README.read_text(encoding="utf-8")
        promoted = [
            "root-cause-first",
            "ponytail",
            "draft-first-pr",
            "zero-framework-cognition",
        ]
        for name in promoted:
            self.assertIn(
                f".claude/skills/{name}/SKILL.md",
                text,
                msg=f"README.md must link to promoted skill {name}",
            )
        self.assertIn("https://github.com/obra/superpowers", text)
        self.assertIn("Jesse Vincent", text)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_readme_skill_counts.py -k test_readme_contains_promoted_discipline_skills_and_attribution`
Expected: FAIL with missing links for promoted discipline skills.

**Step 3: Write minimal implementation**

Update `README.md` to include links to `.claude/skills/root-cause-first/SKILL.md`, `.claude/skills/ponytail/SKILL.md`, `.claude/skills/draft-first-pr/SKILL.md`, and `.claude/skills/zero-framework-cognition/SKILL.md` within the categorized catalog tables.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_readme_skill_counts.py -k test_readme_contains_promoted_discipline_skills_and_attribution`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_readme_skill_counts.py README.md
git commit -m "docs: add promoted discipline skills to catalog tests [gemini][gemini-3.7-flash]"
```

---

### Task 2: Restructure README Skills Catalog into 5 Functional Tiers

**Files:**
- Modify: `README.md:103-290`

**Step 1: Write the failing test**

Add verification in `tests/test_command_ranking_scope.py` that all catalog category headers exist in `README.md`.

```python
    def test_readme_contains_functional_category_headings(self):
        text = README.read_text(encoding="utf-8")
        categories = [
            "Shift-Left Ideation & Planning",
            "Shift-Right Debugging & Reproduction",
            "Evidence, Review & PR Lifecycle",
            "Discovery, Memory & Continuous Learning",
            "Autonomous Swarms & High-Scale Execution",
        ]
        for cat in categories:
            self.assertIn(cat, text, msg=f"README.md must contain category {cat}")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_command_ranking_scope.py -k test_readme_contains_functional_category_headings`
Expected: FAIL (category headings not yet in README).

**Step 3: Write minimal implementation**

Replace the monolithic `Skills at a Glance` table in `README.md` with 5 structured subsection tables matching the design specification:
1. `Shift-Left Ideation & Planning` (`/superpowers-quick`, `/advice`, `/web-advice`, `ponytail`, `root-cause-first`)
2. `Shift-Right Debugging & Reproduction` (`/4layer`, `/redgreen`, `/repro`)
3. `Evidence, Review & PR Lifecycle` (`/evidence-review`, `/es`, `draft-first-pr`, `pr-green-definition`)
4. `Discovery, Memory & Continuous Learning` (`/research`, `/memory-search`, `/history`, `/learn`)
5. `Autonomous Swarms & High-Scale Execution` (`/sidekick`, `/swarm`, `/parallel`, `/factory`, `/skillify`)

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_command_ranking_scope.py -k test_readme_contains_functional_category_headings`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md tests/test_command_ranking_scope.py
git commit -m "docs: reorganize skills catalog into 5 functional tiers [gemini][gemini-3.7-flash]"
```

---

### Task 3: Add Detailed Reference Sections for Promoted Skills

**Files:**
- Modify: `README.md:250-320`

**Step 1: Write the failing test**

Add test checking that each promoted skill has an anchor and descriptive paragraph in `README.md`.

```python
    def test_readme_detailed_sections_for_promoted_skills(self):
        text = README.read_text(encoding="utf-8")
        promoted_sections = [
            "### [`root-cause-first`]",
            "### [`ponytail`]",
            "### [`draft-first-pr`]",
            "### [`zero-framework-cognition`]",
        ]
        for sec in promoted_sections:
            self.assertIn(sec, text, msg=f"README.md must have section for {sec}")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_command_ranking_scope.py -k test_readme_detailed_sections_for_promoted_skills`
Expected: FAIL

**Step 3: Write minimal implementation**

Add concise reference descriptions and trigger examples for:
- `root-cause-first`: Fix prompt, schema, or instruction before adding backend clamps/retries.
- `ponytail`: Lazy senior dev mode — reuse or delete before writing new code.
- `draft-first-pr`: Complete draft-first lifecycle, evidence gates, and `/green` contract.
- `zero-framework-cognition`: Delegate cognitive decisions directly to LLM calls without brittle heuristic code.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_command_ranking_scope.py -k test_readme_detailed_sections_for_promoted_skills`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md tests/test_command_ranking_scope.py
git commit -m "docs: add detailed reference sections for promoted skills [gemini][gemini-3.7-flash]"
```

---

### Task 4: Full Suite Verification & Sync to User Home

**Files:**
- None (operational verification)

**Step 1: Run complete test suite**

Run: `pytest`
Expected: 57+ passed with 0 errors.

**Step 2: Merge-install to user configuration**

Run: `bash install-claude-commands.sh --merge`
Expected: Exit code 0 with manifest validation passed.

**Step 3: Verify git status is clean**

Run: `git status --porcelain`
Expected: Only intended modified files staged/committed.
