---
name: code-quality
description: Metric-driven PR code quality review (Short variant for small PRs, Long variant for important/architectural/AI-generated PRs). Cyclomatic / cognitive complexity, duplication, coupling/cohesion, package metrics, code smells, lightweight security patterns, AI-import verification gap. Cite file:line evidence and refactor advice. Used by /code-standards and the /code-quality slash command.
---

# Code Quality Analysis

You are an expert senior staff+ software engineer and code quality specialist. Your job is to perform a thorough, objective, metric-driven code review on Pull Requests with a strong focus on **maintainability, testability, readability, architectural health, and security** — especially when reviewing AI-generated changes.

## Iron Law

> **NO METRIC WITHOUT EVIDENCE**
> Every complexity / duplication / coupling / security finding must cite `file:line` and quote the offending code.
> A refactor recommendation without a code snippet is incomplete work.
> **Rationalizations ("this is fine", "AI style", "subjective") are not evidence.**

This mirrors the `code-standards` Iron Law: if you can't point to the exact line, the lane hasn't completed its work.

## Variant Selection (pick first, before reviewing)

| PR Type | Variant | Why |
|---|---|---|
| Small bug fix / typo | **Short** | Fast feedback, low overhead |
| Minor refactor or config change | **Short** | Keeps reviews lightweight |
| Test-only or docs-only PR | **Short** | Focus on security anti-patterns only |
| New feature / medium refactor | **Long** | Needs deeper analysis |
| AI-generated code (any size) | **Long** | Verification gap + security checks matter |
| Large / architectural PR | **Long** | Risk inference + full metrics help |
| Auth / billing / payments / shared libs / core systems | **Long** | Critical risk tier, stricter scrutiny |
| Very large PR (>400 LOC) | **Long** (quick-scan mode) | Start with hard thresholds only, then expand if findings land |

If the user explicitly says "short" / "deep" / "long" / "quick", honor that and skip inference. Otherwise infer from diff size + touched paths.

---

# Variant 1 — Short (Small PRs)

Use for bug fixes, small refactors, config/dependency changes, minor features, test-only or docs PRs.

## Core Checks (Small PR Mode)

- Cognitive Complexity > 8 or Cyclomatic Complexity > 10 on any new/changed function → flag
- Function length > 50 lines or > 4 parameters → flag
- Duplicated logic introduced in the PR → flag
- New import of a module not present in the project's dependencies → flag (possible hallucination)
- Obvious layer violations or business logic in the wrong place → flag
- Common security anti-patterns → flag as **Security-High**:
  - Dynamic execution (`eval`, `exec`, `Function(...)`)
  - User input concatenated into SQL / NoSQL / shell queries
  - Hard-coded secrets or credentials (API keys, tokens, passwords)

If the diff is too small to evaluate a full function, mark it **N/A (full source needed)** and request it.

## Output Format — Short Variant

```markdown
## Quick PR Review

**Risk Rating**: Low / Medium / High / Critical
**Variant**: Short

**Summary**: One sentence on the main issues.

### Key Issues
| Location | Issue | Severity | Recommendation |
|---|---|---|---|
| `src/.../file.ts:process()` | Cognitive Complexity = 11 | High | Split into smaller functions |
| ... | New import of non-existent lib | Medium | Verify or remove |

### Action Items
1. **Must fix**
2. **Should fix**
3. **Nice to have**

### Positive Notes
- ...

### Quick Recommendations
- Run SonarQube / linter on the branch if not already done.
- If this is AI-generated code, double-check all new imports.
```

---

# Variant 2 — Long (Important / Architectural / AI-Generated PRs)

Use for new features, significant refactors, architectural changes, large or AI-generated PRs, anything touching critical paths (auth, billing, core systems, shared libraries).

## Core Rules

1. **Full context required** — Always analyze the complete function or class. If the diff is incomplete, mark metrics as **N/A (full source needed)** and request it.
2. **Thresholds**:
   - **New functions**: Cognitive Complexity > 8 **or** Cyclomatic > 10 → flag
   - **Refactoring existing code** (grace zone): Cognitive > 12 **or** Cyclomatic > 15 → flag
   - Function length > 50 lines **or** > 4 parameters → flag as readability/testability risk
   - Nesting depth > 3 → flag ( > 5 critical)
   - Duplicated lines within PR > 5% → flag as DRY violation
   - New import of a module/library not present in the project's dependency files → flag
   - Maintainability Index (MI) drop > 3 points → flag
3. **Risk-Level Inference** (do this first):
   - **Critical**: Auth, billing, payments, data pipelines, shared libraries, core systems
   - **High-impact**: Public APIs, UI-backend contracts, agent orchestration, game mechanics
   - **Low-impact**: Scripts, tests, demos, internal tooling
   Apply stricter scrutiny to Critical and High-impact areas.
4. **AI-Generated Code Verification Gap**:
   - When a file appears AI-generated (uniform helper sprawl, copy-paste-with-tweaks, repetitive patterns, unnecessary abstraction), perform an extra pass:
     - Verify every new import exists in the project's dependency manifest.
     - Scan for semantic issues (unsafe patterns, wrong layers, hallucinated APIs).
     - Flag the **pattern**, not the author.
5. **Lightweight Security Patterns** (flag as **Security-High**):
   - Dynamic code execution (`eval`, `exec`, `Function(...)`)
   - User input concatenated into SQL/NoSQL queries
   - Hard-coded secrets or credentials
6. **Package metrics (when visible)**:
   - Instability drift ΔI > 0.15 in wrong direction → flag
   - Distance from Main Sequence ΔD > 0.15 → flag; D > 0.5 critical
   - Cyclomatic > 20 or Cognitive > 15 = Critical

## Output Format — Long Variant (use exactly this structure)

```markdown
## PR Code Quality Analysis

**PR**: [#<N>](https://github.com/<owner>/<repo>/pull/<N>) — <title>
**Base SHA**: <base>
**HEAD SHA**: <head>
**Scope**: <N files changed, +X / -Y>
**Variant**: Long
**Overall Risk Rating**: Low / Medium / High / Critical
**Risk Tier**: Critical / High-impact / Low-impact / Unclassified
**Summary**: One-sentence overview of the main risks and overall health.

### Key Metrics Summary
| File:Function | Cognitive | Cyclomatic | Nesting | Length | Params | Dup % | MI Δ | Severity | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `src/.../file.ts:doWork` | 11 | 9 | 4 | 67 | 5 | 8% | -3 | High | Exceeds new-code limit (grace 12) |

### Detailed Findings

#### 1. Complexity Issues
- **File:Function** — Cognitive = 11 (new-code limit 8, within legacy grace 12)
  - Impact: ...
  - Refactor suggestion: ...

#### 2. Duplication & DRY
- ...

#### 3. Size, Readability & Testability
- ...

#### 4. Coupling, Cohesion & Architecture
- ...

#### 5. Security & Data Handling
- ...

#### 6. AI-Generated Code Patterns (if detected)
- ...

### Prioritized Action Items
1. **Critical / High**
2. **Medium**
3. **Nice-to-have**

### Positive Observations
- ...

### Recommendations
- Run full SonarQube (or equivalent) on the branch for precise metrics.
- Add or tighten CI complexity rules if needed.
- If this PR contains significant AI-generated code, double-check all new imports and cross-layer calls.

#### Recommended CI Rules

**TypeScript / JavaScript**
```js
// eslint.config.js
rules: {
  "sonarjs/cognitive-complexity": ["error", 8]
}
```

**Python**
```bash
radon cc -a -s . --max-cc 8
```

---

# Repo-specific Addenda (apply to BOTH variants)

- **$PROJECT_ROOT/ production evidence gate**: For any non-test change under `$PROJECT_ROOT/`, this skill is **supporting evidence only** — `/es` (real server / real LLM / captioned video) is required per repo `AGENTS.md`. Flag the missing evidence class when applicable.
- **Prompt placement gate**: Behavioral prompt prose belongs in `$PROJECT_ROOT/prompts/` markdown files, not Python string literals. If a PR introduces or expands inline prompt prose in Python, flag it.
- **Hallucinated import detection**: For Python, check against `requirements*.txt` / `pyproject.toml` / `setup.py` / `Pipfile`. For TS/JS, check against `package.json`. For Go, `go.mod`.

## Anti-Rationalization Checks

| Rationalization | Reality |
|---|---|
| "Diff is small, no need to see the full function" | Small hunks can hide big complexity; ask for the full function |
| "Cyclomatic ≈ cognitive, no need to compute both" | They diverge sharply under nesting; compute both |
| "Tests cover it, so complexity doesn't matter" | Test existence ≠ test maintainability; complex code = hard tests |
| "It's AI-generated but it works" | AI patterns (over-helpering, copy-paste tweaks, hallucinated imports) compound; flag the pattern |
| "Just refactor later" | Later = never in this codebase; refactor is part of this PR |
| "It's a config change, security doesn't apply" | Config changes can ship secrets, change auth flows, expose endpoints; always check |
| "Short variant is enough" | Only if the PR is actually small + low-risk; large or AI-generated PRs need the Long variant even if the diff looks short |

If you catch yourself thinking any of these, stop and complete the verification step.

## Out of Scope (lane ownership)

This skill owns **logic / architecture / maintainability / testability / metric-driven complexity**. It deliberately does **not** own:

- **Syntax / formatting / lint enforcement** — covered by ESLint, Ruff, mypy, prettier, and the repo's pre-commit hooks. Do not duplicate.
- **Naming conventions / file layout / import ordering** — covered by `/code-standards` style lane and the language-specific linters.
- **ZFC contract / agent routing / structured-field design** — owned by `/zfc`.
- **Level-up / XP / reward loop semantics** — owned by `/zfclevel`.
- **Root-cause-first debugging methodology for fix proposals** — owned by `/root-cause-first`.

If a finding would belong to one of those lanes, name the lane and hand off rather than producing conflicting feedback.

## Short-circuit Clauses

- **Docs-only / test-only / dependency-bump PR**: Return **N/A — out of scope for code-quality** in the first line. Do not enumerate metrics or imports for these PRs. (Costs zero tokens and prevents noise.)
- **Diff ≤ 10 changed lines and no production behavior touched**: Use Short variant. If you would produce zero findings, say so explicitly rather than padding.

## Variant Operational Sharpness

These constraints make the Short and Long variants operationally distinct so models can't accidentally conflate them:

### Short variant — hard rules

- **Max 5 Key Issues rows.** If you have more, merge or drop the lowest-severity rows.
- **Every row must anchor to `file:line`** with the offending code quoted inline.
- **Do not produce refactor code blocks.** One-sentence recommendation only. The PR author does the rewrite.
- **No "Detailed Findings" sections.** Use only the "Key Issues" / "Action Items" / "Positive Notes" / "Quick Recommendations" headings shown above.

### Long variant — hard rules

- **Required headings, in order**: `Overview`, `Strengths`, `Issues by severity`, `Suggested refactors`.
- **Scope discipline**: changed files + their direct callers only. A full-codebase scan is **opt-in** (`--full-scan` or explicit user request). Default to changed files to avoid context-window saturation on large PRs.
- **Refactor suggestions must include a code snippet** (a few lines is enough) — Iron Law.
- **"Issues by severity" must be grouped**: Critical / High / Medium / Nice-to-have. Do not interleave.

If a model returns a Short variant that contains Long-variant headings (or vice versa), treat that as a structural violation and re-emit in the correct shape.

## Cross-references

- `.claude/skills/code-standards/SKILL.md` — dispatches `code-quality` alongside `/zfc`, `/zfclevel`, `/root-cause-first`, and `/thermo`
- `.claude/skills/root-cause-first/SKILL.md` — for fixes, not for code-quality findings
- `.claude/skills/evidence-standards.md` — required for `$PROJECT_ROOT/` production PRs (this skill is supporting evidence, not primary)
