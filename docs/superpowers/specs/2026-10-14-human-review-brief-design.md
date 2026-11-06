# Human Review Brief (`human-review-brief`) Skill & Shared Policy Pointer — Design Specification

**Date:** 2026-10-14  
**Status:** Approved via `/superpowers-quick` (`Assumptions and Recommended Defaults`)  
**Scope:** Portable skill package (`.claude/skills/human-review-brief/SKILL.md`), thin slash-command dispatcher (`.claude/commands/what-to-review.md`), integration into `.claude/skills/pr-summary/SKILL.md`, and a compact shared instruction pointer in `~/.codex/AGENTS.md` (plus pointer adapter in `~/.gemini/GEMINI.md`).

---

## 1. Problem Statement & Empirical Motivation (30-Day Mac + Linux `/history` & PR Audit)

When autonomous coding agents finish a task, update a PR, or declare a branch ready for review/merge, they routinely output exhaustive lists of passing unit tests, green CI checks, or generic code summaries while omitting the exact **judgment calls, residual blind spots, and high-failure-rate surfaces** that only a human operator can evaluate.

An empirical audit of the last 30 days (`2026-09-14` to `2026-10-14`) across both macOS and Linux hosts (`6,472` Mac Codex threads + `1,257` Linux Codex threads, `8,429` Mac Claude JSONLs + `964` Linux Claude JSONLs, `1,468` Mac AGY conversations + `590` Linux AGY conversations, `1,161` Mac Hermes sessions + `172` Linux Hermes sessions, `979` `~/roadmap` documents, and `834` active PRs across four repositories) established that **agents rarely fail on syntax or basic unit tests**. Instead, 90%+ of post-agent human pushbacks, regressions, and review holds cluster into **10 recurring blind spots**:

1. **Unit / Mock / Static-Review Green Masking Broken Real-Path Runtime or Hidden UI State**:
   - Features pass 100% of unit tests, `jsdom` tests, mocked e2e suites, and static code reviews while leaving UI elements inside `display: none` containers, overlapping HUD elements on narrow viewports, or having new state fields silently stripped by downstream modal locks or fuzzy-match sanitizers.
2. **Main-Merge Smuggling, Stale Base Diffs & Silent Main Reverts on `MERGEABLE` PRs**:
   - GitHub reports `mergeable: MERGEABLE` and green CI, yet `git merge-tree --write-tree origin/main HEAD` reveals the branch would silently revert files updated on `origin/main` since the branch's merge-base, smuggle multi-file auto-formatter churn (`ruff --fix` stripping re-exported underscore imports), or introduce intra-stack conflicts across stacked PRs.
3. **Over-Claiming "Ready to Merge" When Gates Are Partial, Stale-SHA, or Substitute-Provider**:
   - Agents report "ready to merge" when evidence receipts attest an older SHA prior to a merge-from-main, when browser/UI runners used synthetic/mock fallbacks, or when only a subset of required gates ran.
4. **Undisclosed Product / Behavior / Constant Changes & Prompt Over-Compression**:
   - Under "cleanup" or docstring/prompt compression (`/ds`), agents alter gameplay/runtime constants (e.g., doubling cooldowns) or delete load-bearing domain rules from system instructions while structural contract tests stay green.
5. **Zero-Framework Cognition (ZFC) Violations & Scope-Blind Backend Guards / Clamps / Reducers**:
   - Agents add procedural backend Python/JS guards, clamps, or reducer normalizations that wipe valid nested state aliases, block legitimate empty-list clearing on sibling scopes, or add hundreds of lines of complexity when deletion/simplification (`/ponytail`) was warranted.
6. **Cross-PR / Multi-Agent Integration Contradictions**:
   - Individual PRs pass CI in isolation against `main`, but contradict sibling PRs in a stack or push shared system-instruction token budgets over hard ceilings when combined.
7. **Provider-Boundary & Schema Complexity Blind Spots**:
   - Schema changes pass local `jsonschema` validation and proxy providers that do not enforce structured-output state-machine caps, then fail with `400 INVALID_ARGUMENT` on the production model provider, or run against a stale pinned model in shared test settings.
8. **Cross-Host (`Mac <-> Linux`) Portability & Viewport Parity Gaps**:
   - Agents sync macOS-only tools/paths (`cmux`, `aside`, `vm_stat`, BSD `sed`) onto Linux (`tmux`, `/proc/meminfo`, GNU `sed`) or vice versa (Bash 4 `mapfile` breaking macOS `/bin/bash` 3.2 launchd jobs; missing `#[cfg(any(target_os = "linux", test))]` breaking macOS Clippy), or test only `1440px` and `390px` viewports while missing the `700–1024px` windowed-desktop band.
9. **Systemd / Cgroup Live State vs. On-Disk Config & Container Side Effects (Linux)**:
   - On Linux hosts, agents check only host free RAM (`free -h`) or unit `TasksMax` while missing ancestor cgroup caps (`automation.slice/pids.current` hitting `4096`, sibling `memory.pressure` PSI starving runner fleets) or lingering `/etc/systemd/system.control/` runtime drop-ins (`systemctl show`).
10. **Delivery != Execution, Subprocess/Hook Hygiene & Unnecessary Permission Stops**:
    - Agents equate typing into a shared composer or starting a timer with completed execution, omit `< /dev/null` on backgrounded `codex exec` calls (causing 25-minute stdin hangs), or stop to ask the human for permission on pre-authorized workflows (`/wa`, `/dot`).

---

## 2. Goals & Non-Goals

### Goals
1. **Standardize End-of-Turn Human Handoff**: Ensure every substantive agent turn that modifies code, updates a PR, completes a review, or reports merge readiness ends with two concise, scannable sections:
   - `## What Was Done`: Concrete outcome, full clickable PR/commit URLs, production vs non-production LOC delta (`prod +X/-Y, non-prod +A/-B`), `git merge-tree` cleanliness against `origin/main`, and SHA-bound gate status.
   - `## What to Review as a Human`: A tailored, high-signal checklist highlighting only the specific judgment calls, visual/UX frames, prompt/constant/ZFC changes, cross-host/systemd/schema hazards, and unproved boundaries relevant to the change.
2. **Keep Shared `AGENTS.md` Compact (`/up` Contract)**: Add only a brief pointer in `~/.codex/AGENTS.md` (and pointer adapter in `~/.gemini/GEMINI.md`) that delegates the full rubric and checklist to `.claude/skills/human-review-brief/SKILL.md`.
3. **Integrate Cleanly with `/pr-summary`**: Add a concise pointer in `.claude/skills/pr-summary/SKILL.md` so multi-PR and single-PR architectural summaries also surface the `What to Review as a Human` audit.
4. **Enforce Portability & Zero-PII**: Keep all exported files in `.claude/skills/` and `.claude/commands/` free of hardcoded personal usernames, emails, or machine-specific home paths (`/Users/<user>`, `/home/<user>`).

### Non-Goals
- Do not replace or duplicate `/es` (`evidence-standards`), `/er` (`evidence-review`), `/advice`, or `/green` (`pr-green-definition`).
- Do not require a 10-item wall of boilerplate on trivial read-only turns; scale the checklist strictly to the surfaces touched by the change.

---

## 3. Assumptions and Recommended Defaults (`/sq` Auto-Picked Decisions)

| # | Decision Question | Auto-Picked Default | Rationale |
|---:|---|---|---|
| 1 | Should the human-review rubric live inline in `~/.codex/AGENTS.md` or in a dedicated skill referenced by a brief pointer? | **Dedicated skill (`.claude/skills/human-review-brief/SKILL.md`) + 2-line pointer in `~/.codex/AGENTS.md`** | Matches the user's explicit request (*"use /sq /up to make a brief shared agents md instruction pointer to add/update a skill to tell me what to review as a human"*) and `~/.claude/skills/up/SKILL.md` pointer-first architecture. |
| 2 | Should we create a standalone skill (`human-review-brief`) or only modify `pr-summary`? | **Both: create `.claude/skills/human-review-brief/SKILL.md` (plus `.claude/commands/what-to-review.md`) AND add a section pointer in `.claude/skills/pr-summary/SKILL.md`** | `pr-summary` is invoked for deep roadmap PR summaries, whereas agents finish coding/PR/steering turns continuously outside `/pr-summary`. Having `human-review-brief` own the end-of-turn checklist and linking it from `pr-summary` covers both without duplication. |
| 3 | Should all 10 failure categories be printed on every turn, or filtered dynamically to the surfaces touched? | **Dynamic surface-matched filtering (3–6 bullets max per turn) + mandatory "What Evidence Does NOT Prove" bullet** | Printing irrelevant categories (e.g., Linux `systemd` cgroup checks on a CSS-only PR) causes reviewer fatigue. Requiring the agent to select the applicable risk categories from the 10-item taxonomy plus one explicit "What Evidence Does NOT Prove" bullet keeps signal high. |
| 4 | Where should the shared policy pointer be placed across runtimes? | **Canonical 2-line rule in `~/.codex/AGENTS.md` under `## Review, output, and scope discipline`, plus 1-line bullet in `~/.gemini/GEMINI.md` under `## Canonical Instruction Files & Authoritative Skills`; zero edits to `~/.claude/CLAUDE.md`** | Per `~/.claude/skills/up/SKILL.md`, `~/.claude/CLAUDE.md` imports `@~/.codex/AGENTS.md` natively and must never duplicate shared prose, while `~/.gemini/GEMINI.md` is a pointer adapter. |
| 5 | How should cross-host installation be handled? | **Install to `~/.claude/skills/human-review-brief` + symlink in `~/.agents/skills/human-review-brief` on Mac and Linux (`jeff-ubuntu`), and open a PR in the skills repository** | Follows `~/.claude/CLAUDE.md` § Default skill installation targets (`~/.claude/skills` canonical + `~/.agents/skills` symlink, never `~/.codex/skills`). |

---

## 4. Architectural Approaches Considered

### Approach A: Inline Checklist in `~/.codex/AGENTS.md` Only (Rejected)
- **Description**: Add a 40-line checklist of human-review items directly into `~/.codex/AGENTS.md`.
- **Pros**: Loaded into every session without opening a skill file.
- **Cons**: Violates `/up` pointer-first sizing discipline, bloats every prompt prefix across all runtimes, and cannot hold concrete examples from the 30-day Mac + Linux audit.

### Approach B: Expand `pr-summary` Only (Rejected)
- **Description**: Put the "What was done / What to review as a human" rubric solely inside `.claude/skills/pr-summary/SKILL.md`.
- **Pros**: No new skill directory.
- **Cons**: Agents only load `pr-summary` when explicitly asked to summarize PRs into `~/roadmap/pr-summary-*.md`; normal task completions, bug fixes, and PR redrives would miss the requirement.

### Approach C: Dedicated `human-review-brief` Skill + `pr-summary` Link + 2-Line Shared `AGENTS.md` Pointer (Selected / Recommended)
- **Description**:
  1. Create `.claude/skills/human-review-brief/SKILL.md` containing the concise end-of-turn template (`## What Was Done` and `## What to Review as a Human`) and the empirical 10-point Mac + Linux blind-spot decision matrix.
  2. Create `.claude/commands/what-to-review.md` as a thin slash-command dispatcher to `.claude/skills/human-review-brief/SKILL.md`.
  3. Add a compact `### 5. What to Review as a Human (Judgment Calls & Blind-Spot Audit)` section in `.claude/skills/pr-summary/SKILL.md` pointing to `human-review-brief`.
  4. Add a 2-line instruction + pointer in `~/.codex/AGENTS.md` (`## Review, output, and scope discipline`) and a 1-line pointer in `~/.gemini/GEMINI.md`.
- **Pros**: Minimal context overhead in `~/.codex/AGENTS.md`, single canonical owner for the human-review rubric, works for both normal turn completions and `/pr-summary` reports, and passes all repository portability contract tests.

---

## 5. Detailed Component Design

### 5.1 `.claude/skills/human-review-brief/SKILL.md`
Defines the mandatory closing structure when an agent finishes coding, updates or reviews a PR, or reports merge readiness:

1. **`## What Was Done` (Objective Facts & Provenance)**:
   - **Outcome & Links**: 1–2 sentences stating what actually changed, with full clickable GitHub PR (`[PR #NNNN](https://github.com/<owner>/<repo>/pull/NNNN)`) and commit URLs (`<40-char-sha>`).
   - **Line Deltas**: `Production: +X / -Y (M files) | Non-production: +A / -B (N files)` — flag whether net production LOC grew when deletion/simplification (`/ponytail`) was expected.
   - **Merge-Tree Cleanliness**: Result of `git merge-tree --write-tree origin/main HEAD` diffed against `origin/main` confirming zero conflicts, zero smuggled formatter files (`ruff --fix` / underscore re-export strips), and zero silent reverts of `origin/main`.
   - **Gate & Evidence Matrix at Exact Head `<short-sha>`**: Compact status of CI / local equivalents, `/es`, `/er`, `/advice`, `/cs`, and `/wa` with their exact attested SHAs and gist URLs.

2. **`## What to Review as a Human` (Empirical Agent Blind-Spot Checklist)**:
   Requires the agent to emit **3 to 6 concrete bullets** selected from the 10 empirical blind-spot categories that match the touched surfaces, plus **always** including `"What This Evidence Does NOT Prove"`:
   - **Visual / UX / Layout Frames (if UI/CSS/Frontend/Mobile touched)**: Direct links to before/after frames (`1440x900` desktop, `700–1024px` narrow/windowed desktop, `375x812` mobile, or native simulator) and walkthrough video timestamps to eyeball (checking for `display: none` containers, overlapped HUD/banners, theme contrast, or modal-lock traps).
   - **Product / Constant / Prompt Semantics (if prompts, configs, or gameplay rules touched)**: Exact constants, cooldowns, thresholds, or system-instruction clauses added, modified, or trimmed (`/ds`), highlighting any risk of dropped domain rules or competing prompt mandates.
   - **ZFC & Scope-Boundary Audit (if backend state, reducers, clamps, or sanitizers touched)**: Exact `file:line` of any guard, clamp, fallback, or reducer normalization and why it cannot clobber nested aliases, strip valid release flags, or block empty-list clearing on sibling state scopes.
   - **Cross-PR / Provider / Schema Boundary (if schemas, LLM calls, or stacked PRs touched)**: Whether structured-output schema changes were live-probed against the production model provider (`response_json_schema` complexity), whether shared token ratchets hold across stacked PRs, and which parent PRs must land first.
   - **Cross-Host (`Mac <-> Linux`) & Systemd / Runner State (if scripts, hooks, skills, daemons, or CI runners touched)**: Portability across macOS (Bash 3.2, BSD `sed`, `vm_stat`, `cmux`/`aside`, Clippy target guards) and Linux (`tmux`, `/proc/meminfo`, `systemctl show`, `/etc/systemd/system.control/` overrides, `automation.slice/pids.current` & `memory.pressure`, `< /dev/null` on backgrounded `codex exec`, isolated `git clone --no-local` for `/advice`).
   - **What Current Evidence Does NOT Prove (Mandatory on Every Brief)**: Explicit disclosure of any unexercised path, substitute provider, mocked boundary, or pending check.
   - **Exact Human Decision / Next Action**: Single line stating what the human needs to decide or approve (e.g., `MERGE APPROVED` for PR #NNNN, or direction on an unresolved product trade-off).

### 5.2 `.claude/commands/what-to-review.md`
Thin command dispatcher invoking `.claude/skills/human-review-brief/SKILL.md`.

### 5.3 `.claude/skills/pr-summary/SKILL.md` Update
Adds `#### ### What to Review as a Human (Blind-Spot & Judgment Audit)` under `### 2. Per-PR Structured Breakdown` referencing `.claude/skills/human-review-brief/SKILL.md`.

### 5.4 Shared Policy Pointer (`~/.codex/AGENTS.md` & `~/.gemini/GEMINI.md`)
- In `~/.codex/AGENTS.md` under `## Review, output, and scope discipline`:
  > When finishing coding, PR updates, or readiness reviews, end with concise `## What Was Done` (full PR/commit URLs, prod vs non-prod LOC delta, `git merge-tree` cleanliness vs `origin/main`, and SHA-bound gate matrix) and `## What to Review as a Human` (visual/UX frames, prompt/constant/ZFC judgment calls, cross-host/systemd/schema hazards, what current evidence does NOT prove, and exact human decision needed) per `~/.claude/skills/human-review-brief/SKILL.md`.
- In `~/.gemini/GEMINI.md` under `## Canonical Instruction Files & Authoritative Skills`:
  > - **Human Review Brief (`/what-to-review`)**: [`~/.claude/skills/human-review-brief/SKILL.md`]($HOME/.claude/skills/human-review-brief/SKILL.md)

---

## 6. Testing & Verification Strategy
1. Add a unit test file `tests/test_human_review_brief_skill.py` in the skills repository verifying:
   - `.claude/skills/human-review-brief/SKILL.md` exists, starts with valid YAML frontmatter (`name: human-review-brief`), and contains required sections (`## What Was Done`, `## What to Review as a Human`, the 10-category blind-spot matrix, and `What Current Evidence Does NOT Prove`).
   - `.claude/commands/what-to-review.md` exists and dispatches to `.claude/skills/human-review-brief/SKILL.md`.
   - `.claude/skills/pr-summary/SKILL.md` references `human-review-brief`.
   - Zero PII / non-portable paths exist in the new/modified files.
2. Run the full repository contract test suite (`python3 -m unittest discover -s tests -p "test_*.py" -v`).
3. Verify `shasum -a 256` parity across the skills repository worktree, local `~/.claude/skills/human-review-brief/SKILL.md`, and remote Linux `~/.claude/skills/human-review-brief/SKILL.md`, plus `~/.agents/skills/human-review-brief` symlinks.
