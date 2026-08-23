---
description: Split PR Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Step 1: Commit Domain Classification

**Action Steps:**
Analyze each commit for logical domains:
1. **Security**: auth, permissions, vulnerability fixes, validation
2. **Infrastructure**: deployment, scripts, configuration, tooling
3. **Frontend**: UI components, styling, client-side logic
4. **Backend**: API endpoints, business logic, database operations
5. **Testing**: test files, test utilities, CI/CD improvements
6. **Documentation**: README, docs, comments
7. **Foundation**: type definitions, core utilities, architectural changes

### Phase 2: Step 2: File Dependency Analysis

**Action Steps:**
Analyze file dependencies to determine coupling:
1. Identify which files depend on each other
2. Group tightly coupled files together
3. Assess if splits would break logical units
4. Consider test coverage and verification needs

### Phase 3: Step 3: Splitting Decision Matrix

**Action Steps:**
**DON'T SPLIT if**:
1. < 5 commits total
2. All commits in same domain
3. Heavy file overlap (>50% files shared)
4. Changes are tightly coupled
5. Time pressure (splitting adds review overhead)

**CONSIDER SPLITTING if**:
6. Multiple distinct domains represented
7. Security fixes mixed with other changes
8. Foundation changes that others depend on
9. Independent features that can be reviewed separately
10. Large PR (>15 files) with logical boundaries

**ALWAYS SPLIT if**:
11. Security vulnerabilities mixed with non-critical changes
12. Breaking changes mixed with safe improvements
13. Emergency fixes bundled with feature work

### Phase 4: Implementation Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 4A: Analysis

**Action Steps:**
1. Ensure working tree is clean (commit or stash local changes)
2. Check if current branch has upstream PR
3. Analyze commit history and file changes
4. Detect file overlaps and dependencies
5. Classify commits by domain and risk
6. Recommend splitting strategy or suggest keeping combined

### Phase 4B: Planning

**Action Steps:**
1. Create scratchpad file in `roadmap/scratchpad_[branch].md`
2. Document file count verification (splits must sum to original)
3. Provide implementation commands for chosen strategy
4. Include dependency order and merge sequence

### Phase 4C: Execution (Optional)

**Action Steps:**
1. Prompt user if they want to execute the split
2. Create branches according to strategy
3. Cherry-pick appropriate commits to each branch (use `git cherry-pick -x` to preserve provenance)
4. Push branches and create PRs with proper base branches

## 📋 REFERENCE DOCUMENTATION

# Split PR Command

**Purpose**: Intelligently analyze a PR for potential splitting opportunities using file dependency analysis, commit grouping, and risk assessment.

**Usage**: `/split [branch]` or `/split` (uses current branch)

## Smart Splitting Methodology

### Pre-Analysis Checks

1. **Size Threshold**: PRs < 5 commits or < 10 files rarely benefit from splitting
2. **Coherence Check**: Single-domain changes (all frontend, all docs) usually shouldn't split
3. **Risk Assessment**: Critical security fixes might need isolation from other changes

### Analysis Framework

# Get all files changed in the last N commits of the current branch

# Replace N with the number of commits you want to analyze (e.g., for 5 commits, use HEAD~5..HEAD)

git show --name-only --format="" HEAD~N..HEAD | sort -u

# For each commit, map files changed (example for the last 5 commits)

git show --name-only --format="=== %h %s ===" HEAD~5..HEAD

# Identify overlapping files between commits (files touched by 2+ commits in the range)

git log --name-only --format="" HEAD~N..HEAD | sort | uniq -d
```

**Critical Check**: Files appearing in multiple commits create dependencies that affect splitting strategy.

### Splitting Strategies

#### Strategy A: Foundation-First (for dependent files)

```markdown
When files overlap between commits:
1. **Foundation PR**: Base changes that others depend on
2. **Dependent PRs**: Built on foundation, cherry-picked incrementally
```

#### Strategy B: Domain Separation (for independent changes)

```markdown
When commits have distinct file sets:
1. **Critical Domain**: Security, breaking changes (highest priority)
2. **Feature Domain**: New functionality, improvements
3. **Infrastructure Domain**: Tooling, deployment, non-user-facing
```

#### Strategy C: Risk-Based Separation

```markdown
When mixing high and low risk changes:
1. **High Risk**: Security, breaking changes, database migrations
2. **Medium Risk**: API changes, significant refactoring
3. **Low Risk**: Documentation, tests, minor improvements
```

### File Count Verification

**MANDATORY**: All split PRs must account for every file in original PR
```bash

# Original PR files

# Replace N with the number of commits in your PR (e.g., for 8 commits, use HEAD~8..HEAD)

ORIGINAL_COUNT=$(git show --name-only --format="" HEAD~N..HEAD | sort -u | wc -l)

# Sum of split PR files (accounting for overlaps)

# Example: count unique files across all split branches relative to the base branch

# Set your base branch (defaults to origin/main)

: "${PR_BASE:=origin/main}"

# List your split branches

SPLIT_BRANCHES=(split-foundation split-security split-infra)
SPLIT_COUNT=$(
  (for b in "${SPLIT_BRANCHES[@]}"; do
     git diff --name-only "${PR_BASE}...${b}"
   done) | sort -u | wc -l
)

# Must equal: ORIGINAL_COUNT == SPLIT_COUNT

```

## Smart Recommendations

### When NOT to Split

- "Single feature across multiple commits" - keep together for atomic review
- "Refactoring + tests for same component" - logical pairing
- "Bug fix + test for the bug" - should be reviewed together
- "Documentation updates for new feature" - context helps review

### When TO Split

- "Security fix + unrelated feature work" - security needs fast track
- "Breaking API change + backward compatibility layer" - separate for gradual rollout
- "Foundation types + features using those types" - foundation first
- "Emergency hotfix + planned improvements" - different urgency levels

### Special Cases

- **Hotfix Extraction**: Pull critical fixes from feature branches
- **Foundation Dependency**: When new utilities are used by other changes
- **Security Isolation**: Separate security fixes for faster security review
- **Review Complexity**: Split large PRs to reduce cognitive load on reviewers

## Example Output

```markdown

## Split Analysis: feature-complex-pr

### File Analysis

- **Total Files**: 12
- **Commits**: 8 commits across 3 domains

### Overlapping Files Detected

- `api.service.ts` (commits: security, foundation)
- `main.py` (commits: foundation, infrastructure)

### Recommended Strategy: Foundation-First

1. **Foundation PR**: 6 files (types, core utilities)
2. **Security PR**: 4 files (1 shared with foundation)
3. **Infrastructure PR**: 5 files (1 shared with foundation)

**File Count**: 6 + 3 + 3 = 12 unique files ✅

### Implementation Plan

[Detailed commands for creating each PR with proper dependencies]
```

**Implementation**: Analyze current PR state, generate intelligent recommendations, create scratchpad with verified file counts and dependency-aware splitting strategy.
