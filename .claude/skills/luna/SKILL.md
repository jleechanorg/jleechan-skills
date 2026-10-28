---
name: luna
description: "Audit and review open, non-draft PRs unmodified for >8 hours using codexl (GPT-6 Luna) and pil (DeepSeek-4.1-flash). Diagnoses CI failures, merge conflicts, missing evidence, and outputs actionable fix plans."
---

# /luna: Automated Stale PR Review & Remediation Skill

The `/luna` skill orchestrates automated reviews of open, non-draft pull requests that have stalled or remained unmodified for 8 or more hours. It uses a tri-engine architecture:
- **`codexl`** (`codex-luna`, OpenAI native `gpt-6-luna` with high reasoning effort): For deep architectural analysis, test-harness failures, game-state logic, and complex multi-file reviews where 80%+ prompt caching hit rates and deep reasoning are essential.
- **`pil`** (`pi --provider lunaroute --model deepseek-4.1-flash`): For rapid diagnostic passes, diff scanning, lint verification, and fast triage using DeepSeek V4 Flash with zero CLI initialization overhead.
- **`pig`** (`pi --provider lunaroute --model glm-5.3`): For long-horizon agentic task planning, tool recovery, and GLM-5.3 semantic evaluations.

---

## When to Use

- When auditing stale open PRs to determine what fixes, rebases, or evidence updates are required.
- When unblocking CI failures on PRs that haven't been touched in over 8 hours.
- When checking merge readiness, conflicts with `origin/main`, and evidence compliance (`/es`, `/er`).

---

## Workflow

### Step 1: Scan and Categorize Stale Open Non-Draft PRs

Run the `/luna` automated audit script:

```bash
~/.claude/skills/luna/scripts/audit_prs.py
```

This immediately parses all open non-draft PRs older than 8 hours, evaluates their CI status via GitHub check rollups and mergeability in parallel, and categorizes them into:
1. **CI Failed**: Dispatches `codexl` for test failure diagnosis.
2. **Conflicting / Dirty**: Flags for rebase onto `origin/main` via `/fixpr`.
3. **Clean & Green**: Lists PRs awaiting final evidence signoff or operator `MERGE APPROVED`.

To review a specific PR immediately with ultra-fast triage:
```bash
~/.claude/skills/luna/scripts/audit_prs.py --review <PR_NUMBER>
```

### Step 2: Tri-Engine Specialized Reviews

#### A. Fast Diagnostic Pass (`pil`) with `-nc`
For checking diff size, syntax, and basic rule conformance with zero context bloat (<2s latency):
```bash
gh pr diff <PR_NUMBER> | pil -nc -p "Review this diff against main. Identify any obvious syntax errors, unreceipted deltas, or missing test coverage."
```

#### B. Agentic Tool & Planning Review (`pig`)
For complex tool chains, multi-step migration plans, or SWE-bench level task execution:
```bash
pig -p "Analyze the planned migration in PR #<PR_NUMBER>. Verify whether all required tool definitions and error-recovery paths are addressed."
```

#### C. Deep Architectural / Harness Review (`codexl`)
For investigating broken CI tests, complex state machine bugs, or prompt/schema coupling where 80%+ cache hit rate and deep reasoning are essential:
```bash
codexl "Review PR #<PR_NUMBER> on branch <BRANCH>. Inspect the failing CI tests from GitHub checks. Diagnose the root cause and propose the exact minimal patch to resolve it."
```

### Step 4: Generate Actionable Fix Roadmap

For every audited PR, output a structured summary table:

| PR # | Title | Stale Age | CI Status | Mergeable | Primary Blocker | Recommended Action | Engine |
|---|---|---|---|---|---|---|---|
| #10312 | fix(streaming): map Gemini 429... | 28h | ❌ Failed | CONFLICT | CI test failure & rebase needed | Rebase on main, fix exception mapping | `codexl` |

Each item must specify:
1. **Root Cause**: Why the PR stalled or failed.
2. **Immediate Next Step**: Exact shell commands to checkout, reproduce, fix, and verify.
3. **Verification Command**: Exact test or check required to confirm green.

---

## Tooling Invariants

1. **`codexl` Resolution**: Always maps to `codex-luna` (`codex --yolo --search -m gpt-6-luna --config model_reasoning_effort=high`).
2. **`pil` Resolution**: Uses LunaRoute gateway `deepseek-4.1-flash` (`pi --provider lunaroute --model deepseek-4.1-flash`).
3. **Evidence Hygiene**: All review artifacts and logs must be stored under the canonical scratch directory via `"$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh "worldarchitect.ai/luna-reviews")"` (referencing `~/.claude/skills/scratch-space/SKILL.md`). Never litter repository workspaces.
4. **Absolute Paths**: Always cite full absolute paths for modified or inspected files.
