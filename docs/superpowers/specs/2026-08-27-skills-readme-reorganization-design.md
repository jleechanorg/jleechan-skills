# Skills Catalog Reorganization & Promotion Design Specification

## Overview

This specification establishes a structured, tiered taxonomy for the agent skills in `jleechan-skills` and redesigns the `README.md` catalog to highlight core workflows, promote essential discipline skills, and clearly delineate universal portable skills from specialized or infrastructure-specific skills.

---

## Problem Statement & Current State Analysis

The repository currently exports dozens of portable skills and thin slash commands. However, the documentation presents several organizational challenges:

1. **Flat Catalog Structure:** The "Skills at a Glance" table lists 19 skills in a single unranked table without clear functional groupings (e.g., planning, debugging, PR lifecycle, memory, multi-agent orchestration).
2. **Under-Promoted Core Disciplines:** Critical operational skills defined in canonical policies (such as `ponytail`, `root-cause-first`, `zero-framework-cognition`, and `draft-first-pr`/`pr-green-definition`) are referenced in user baselines but missing or obscured in the primary README catalog.
3. **Ambiguity in Dependency Tiers:** Readers and automated agents inspecting the catalog cannot immediately distinguish between zero-dependency portable prompts (e.g., `/advice`, `/redgreen`, `/superpowers-quick`), tool-dependent skills (e.g., `/browser` requiring Aside/Playwright, `/factory` requiring Dark Factory), and private/domain packages (`worldai-*`, `ao-*`).
4. **Shift Strategy Alignment:** While the Executive Summary introduces the 7-skill Left/Right Shift loop (`/superpowers-quick`, `/advice`, `/web-advice`, `/redgreen`, `/4layer`, `/evidence-review`, `/harness`), the subsequent catalog does not reinforce this workflow grouping.

---

## Assumptions and Recommended Defaults

To ensure autonomous decision-making without ambiguous placeholders, the following defaults are selected:

1. **Taxonomy Structure (Recommended):** Group the catalog into 5 functional tiers:
   - **Tier 1: Shift Left / Shift Right Quality Loop** (Core 7 skills: `/superpowers-quick`, `/advice`, `/web-advice`, `/redgreen`, `/4layer`, `/evidence-review`, `/harness`).
   - **Tier 2: Engineering Discipline & Ground Truth** (`root-cause-first`, `ponytail`, `zero-framework-cognition`, `readonly-scope`, `draft-first-pr`, `pr-green-definition`).
   - **Tier 3: Discovery, Memory & Research** (`/research`, `/memory-search`, `/history`, `/learn`).
   - **Tier 4: Multimodal, Browser & Evidence Gathering** (`/browser`, `/repro`, `/ui-video-evidence`, `/design-fidelity-diff`, `/runtime-activation-claim`).
   - **Tier 5: Orchestration, Parallelism & Metaprogramming** (`/sidekick`, `/swarm`, `/parallel`, `/factory`, `/skillify`).

2. **Skill Promotion Candidates:**
   - Promote `root-cause-first` (`/rcf`): Enforces prompt/schema fixes before backend retries.
   - Promote `ponytail`: Enforces reuse and deletion before new code is written.
   - Promote `draft-first-pr` / `pr-green-definition` (`/green`): Enforces the PR lifecycle and green gates.
   - Promote `zero-framework-cognition`: Replaces heuristic routing with model-delegated judgment.

3. **Attribution & Provenance Invariant:** Maintain explicit attribution to Jesse Vincent for Superpowers, linking directly to `https://github.com/obra/superpowers` in both table summaries and detailed skill entries.

4. **Test & Contract Compatibility:** Preserve all existing anchor links, command pointer formats, and test assertions in `tests/test_approval_contracts.py`, `tests/test_readme_skill_counts.py`, and `tests/test_command_ranking_scope.py`.

---

## Approaches Considered & Trade-off Analysis

### Approach A: Flat Alphabetical List with Badges
- *Description:* Keep a single table but add tags/badges for tier, portable vs tool-dependent.
- *Pros:* Minimal diff, simple table.
- *Cons:* Fails to provide immediate visual hierarchy; difficult for users to grasp workflow lifecycles.

### Approach B: Functional Tiered Grouping (Selected)
- *Description:* Retain the Left/Right Shift Executive Summary, followed by structured functional sections for each operational phase (Ideation/Design, Test-Driven Verification, Evidence & Gates, Multi-Agent Orchestration, Memory/Learning), accompanied by a consolidated quick-reference matrix.
- *Pros:* Guides developers and agents through the natural engineering lifecycle; highlights high-value skills while maintaining clean organization.
- *Cons:* Slightly longer README, requires precise heading hierarchy to maintain test compatibility.

### Approach C: Separate README per Subsystem
- *Description:* Break the README into multiple sub-documents (`docs/catalog/ideation.md`, etc.).
- *Pros:* Modular files.
- *Cons:* Degrades the single-file self-setup experience for agents reading `README.md` in one context window.

---

## Detailed Reorganization Design

### 1. Header & Executive Summary
- Maintain top-level package metadata and the left/right shift strategy table.
- Pair `/superpowers-quick` (Shift Left ideation & architectural design) against `/4layer` (Shift Right minimal repro escalation).

### 2. Functional Catalog Categorization
The `Skills at a Glance` catalog will be organized into the following clear subsections:

| Category | Skills Included | Purpose |
|---|---|---|
| **Shift-Left Ideation & Planning** | `/superpowers-quick`, `/advice`, `/web-advice`, `ponytail`, `root-cause-first` | Clarify intent, explore alternatives, select designs, and simplify before coding. |
| **Shift-Right Debugging & Reproduction** | `/4layer`, `/redgreen`, `/repro` | Isolate failures, prove defects test-first, and establish verifiable RED states. |
| **Evidence, Review & PR Lifecycle** | `/evidence-review`, `/es`, `draft-first-pr`, `pr-green-definition` | Audit claim provenance, enforce real-path evidence, and manage PR gates. |
| **Discovery, Memory & Continuous Learning** | `/research`, `/memory-search`, `/history`, `/learn` | Query primary sources, search multi-tier memories, and record durable lessons. |
| **Autonomous Swarms & High-Scale Execution** | `/sidekick`, `/swarm`, `/parallel`, `/factory`, `/skillify` | Scale concurrency safely, manage durable teammates, and package repeatable workflows. |

### 3. Detailed Skill Reference Enhancements
- Add structured entries for newly promoted skills (`root-cause-first`, `ponytail`, `draft-first-pr`/`pr-green-definition`, `zero-framework-cognition`).
- Standardize all entry blocks:
  - Command invocation syntax.
  - Canonical `SKILL.md` path.
  - Trigger conditions & inputs.
  - Deliverables & terminal outcomes.

---

## Validation & Regression Safeguards

1. **Automated Test Suite:** Run `pytest tests/` ensuring all 57 tests pass without regression.
2. **Link Integrity:** Verify all relative markdown links (`.claude/skills/...`) point to existing files on disk.
3. **Installer Verification:** Run `tests/test_installer.py` to confirm directory packaging is unaffected.

---

## Implementation Preconditions

- Primary working directory must remain `/Users/jleechan/projects_other/claude-commands`.
- Git commits and branch workflows must follow standard repository conventions.
