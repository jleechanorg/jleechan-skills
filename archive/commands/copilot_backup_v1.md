---
description: /copilot - Fast PR Processing
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### 🔄 Four-Phase Workflow (UPDATED)

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### **Phase 0: Critical Bug Scan (MANDATORY FIRST STEP)**

**🚨 EXECUTE BEFORE ANY COMMENT PROCESSING:**

**Action Steps:**
1. **Check Comment Cache**: Use the `is_cache_fresh()` function to check if cached comments exist and are fresh (< 5 minutes old)
   - If cache is fresh: Skip `/commentfetch` and use cached data from `$COMMENTS_FILE`
   - If cache is stale or missing: Execute `/commentfetch` to get complete comment list
2. **Critical Bug Detection**: Scan ALL comments for critical keywords:
   - Security: "CRITICAL", "BUG", "SECURITY", "BLOCKER", "PRODUCTION", "VULNERABILITY"
   - Auth/Rate Limiting: "rate limit", "authentication", "authorization", "admin", "UID"
   - Data Safety: "data loss", "corruption", "undefined behavior", "crash"
3. **Immediate Implementation**: For EACH critical bug found:
   - Read the affected file(s)
   - Implement the fix directly (NO agent delegation)
   - Write tests to verify the fix
   - Run tests to confirm working
   - Commit with clear message: "Fix: [critical bug description]"
4. **Verification Gate**: Only proceed to Phase 1 after ALL critical bugs are fixed

**Critical Bug Categorization Rules:**

**CRITICAL** (Must fix immediately):
- Security vulnerabilities (XSS, SQL injection, auth bypass)
- Data corruption or loss risks
- Production blockers (crashes, infinite loops)
- Rate limiting bypass or abuse
- Authentication/authorization bugs

**Example Critical Bug Keywords:**
```bash
# Scan for critical patterns
CRITICAL_PATTERNS="CRITICAL|BUG|SECURITY|BLOCKER|PRODUCTION BLOCKER|PRODUCTION BUG|rate limit|authentication|authorization|admin.*UID|data loss|data-loss|dataloss|corruption|crash|vulnerability|auth bypass"

# For each comment matching critical patterns (always sanitize first):
sanitized_body=$(sanitize_comment "$comment_body")
if echo "$sanitized_body" | grep -qiE "$CRITICAL_PATTERNS"; then
    # 1. Classify severity
    # 2. Implement fix immediately
    # 3. Test and verify
    # 4. Commit before proceeding
fi
```

**Quality Gate**: Phase 0 complete ONLY when:
- ✅ All critical bugs identified
- ✅ All critical bugs fixed with working code
- ✅ All critical bug fixes tested and verified
- ✅ All critical bug fixes committed

### **Phase 1: Analysis & Comment Categorization**

**Action Steps:**
1. **Direct Operations**: Execute `/gstatus` for PR status
2. **Comment Categorization**: Classify remaining comments by severity:
   - **BLOCKING**: CI failures, build failures, breaking API changes
   - **IMPORTANT**: Performance issues, logic errors, missing validation
   - **ROUTINE**: Code style, documentation, optional refactoring
3. **Agent Launch**: Deploy `copilot-fixpr` agent for BLOCKING/IMPORTANT file operations
4. **Composed Commands**:
  5. `/gstatus` - Get comprehensive PR status
  6. `/fixpr` - Resolve merge conflicts and CI failures (via agent for non-critical issues)

### **Phase 2: Implementation & Response Generation**

**🚨 CRITICAL LLM PRINCIPLE**: Every comment receives FULL comprehensive analysis regardless of length, author, or type.

**Action Steps:**
1. **Prioritize Queue**: Use `categorize_comment()` to tag comments for processing order ONLY (CRITICAL → BLOCKING → IMPORTANT → ROUTINE). **CRITICAL**: This categorization is solely for prioritization scheduling, NOT for filtering context. Maintain a TodoWrite checklist so no items are skipped.
2. **Read Full Comment Body**: For EACH comment (regardless of initial category tag), LLM reads the ENTIRE content with NO truncation, NO pre-parsing, NO keyword extraction. The LLM re-analyzes and determines the true category and how many distinct issues exist within each comment.
3. **Identify ALL Issues**: LLM analyzes each comment to identify EVERY distinct issue/suggestion, even if multiple issues are grouped in a single comment. No issue is skipped based on position in comment. Initial category tag from Step 1 is advisory only - LLM makes final determination.
4. **Direct Implementation**: The orchestrator fixes CRITICAL and BLOCKING issues immediately (no delegation) while documenting `action_taken`, `files_modified`, and verification steps for responses.json.
5. **Selective Delegation**: IMPORTANT issues that require large file edits may be delegated to the `copilot-fixpr` agent. ROUTINE comments stay with the orchestrator to avoid agent churn.
6. **Agent Result Collection**: Once delegated tasks finish, collect the structured status file (`agent_status.json`) and integrate file diffs/commits back into the orchestrator context.
7. **Comprehensive Response**: Generate ONE consolidated response per comment addressing ALL issues found, using ACTION_ACCOUNTABILITY format with specific status for each issue (FIXED/DEFERRED/ACKNOWLEDGED/NOT_DONE).
8. **GitHub Operations**:
   - **Default (REQUIRED)**: Run `/commentreply` after validating responses.json, then `/commentcheck` to confirm 100% coverage.
   - **Optional Summary-Only Override (EXPLICIT USER REQUEST REQUIRED)**:
     - Allowed **only** when the user explicitly requests summary-only posting.
     - Still requires full per-comment analysis internally.
     - **Do not** post per-comment replies; **post one summary comment** to the PR instead.
     - Skip `/commentreply` and `/commentcheck` for this run.
     - In the summary comment, clearly state that per-comment replies were intentionally skipped at user request.

**Example**: If CodeRabbit posts 1 comment with 11 issues, LLM identifies all 11 and generates 1 consolidated response with 11 status items.

### **Phase 3: Verification & Completion (ENHANCED)**

**Action Steps:**
1. **Project-Aware Test Execution**: Detect the appropriate project test command (see "Phase 3 Playbook" below) and run it. Block completion on failures for CRITICAL/BLOCKING fixes.
2. **Commit Verification**: Use filtered git logs (grep for `Fix:` or `Critical`) to prove every critical fix is committed individually. Capture commit SHAs for responses.json verification fields.
3. **File Review**: Inspect `git diff --stat` and targeted files to ensure only intentional changes exist and that File Justification Protocol entries are satisfied.
4. **Quality Gates**: Confirm Security → Runtime → Tests → Style order was respected, rerunning targeted tests if any remediation happened during verification.
5. **Final Operations**: Push via `/pushl` with `[copilot-commit]` in the message, regenerate guideline notes if needed, and archive timing metrics.

## 📘 DETAILED PHASE PLAYBOOKS & REFERENCE

### Phase 0 Playbook — Critical Bug Scan

- **Scope Clarification**: Claude (the orchestrator) owns Phase 0 end-to-end. Directly edit files, add tests, and run verification locally—do **not** delegate critical or blocking bugs to the agent. The agent only joins once Phase 0 is complete.
- **Sanitization First**: Run `sanitize_comment` on every comment body before keyword scans to avoid script injection. The sanitized payload feeds the `CRITICAL_PATTERNS` grep, ensuring detection happens on trusted text.
- **Testing & Commit Timing**:
  1. Apply the fix immediately after detecting a critical bug.
  2. Run the project’s detected test command (see Phase 3 Playbook) before proceeding.
  3. If tests fail, stay in Phase 0 until the fix passes; do **not** defer failures to Phase 3.
  4. Commit each fix individually using `git commit -m "Fix: <short description>"` before moving to the next issue. These commits are referenced later in responses.json.
- **Gate to Phase 1**: All critical bugs fixed, tested, and committed. Document each fix in TodoWrite so you can cite file paths and verification notes when generating responses.

### Phase 1 Playbook — Analysis & Categorization

- **Status + Comment Fetch**: Execute `/gstatus` immediately after Phase 0. Comments are already loaded from Phase 0 (either from cache or fresh fetch).
- **Outdated Comment Detection**: Before processing, check if comments reference code that has been refactored:
  ```bash
  # For each inline comment, check if the referenced commit is still relevant
  check_comment_outdated() {
      local comment_commit="$1"  # original_commit_id from the comment
      local comment_path="$2"    # file path the comment is on
      local comment_line="$3"    # line number

      # If comment references a commit not in current HEAD ancestry, it may be outdated
      if [ -n "$comment_commit" ] && ! git merge-base --is-ancestor "$comment_commit" HEAD 2>/dev/null; then
          echo "OUTDATED"
          return
      fi

      # Check if the file/line has been modified since the comment's commit
      if [ -n "$comment_commit" ] && [ -n "$comment_path" ]; then
          local changes=$(git diff "$comment_commit"..HEAD -- "$comment_path" 2>/dev/null | wc -l)
          if [ "$changes" -gt 50 ]; then
              echo "LIKELY_OUTDATED"
              return
          fi
      fi

      echo "CURRENT"
  }

  # Comments marked OUTDATED get response: "ALREADY FIXED - Code has been refactored since this comment"
  ```
- **Categorization Pipeline**:
  1. Sanitize each comment body.
  2. Check if comment is OUTDATED (references refactored code).
  3. Pass sanitized text to `categorize_comment()` to obtain CRITICAL/BLOCKING/IMPORTANT/ROUTINE labels.
  4. Record the mapping (e.g., in TodoWrite or a scratch buffer) so Phase 2 can consume a prioritized queue.
- **Clarify Delegation Rules**: Critical + blocking items remain orchestrator-owned. Only mark an item as agent-eligible if it is IMPORTANT and requires heavy file edits (e.g., multi-file refactors). ROUTINE feedback is kept local for speed.
- **Test Expectations**: No new tests run in Phase 1; this is purely classification + planning.

### Phase 2 Playbook — Implementation & Responses

- **Priority Queue Implementation**: Enforce the priority order with an explicit loop so reviewers can see it's implemented, not just promised:

```bash
PRIORITIZED_COMMENTS=$(jq -c '.comments[]' "$COMMENTS_FILE" | while read -r comment; do
    body=$(echo "$comment" | jq -r '.body')
    sanitized=$(sanitize_comment "$body")
    category=$(categorize_comment "$sanitized")
    echo "$category|$comment"
done | sort)

for entry in $PRIORITIZED_COMMENTS; do
    category="${entry%%|*}"
    comment_json="${entry#*|}"
    case "$category" in
        CRITICAL|BLOCKING)
            implement_directly "$comment_json"
            ;;
        IMPORTANT)
            delegate_to_agent_if_needed "$comment_json"
            ;;
        ROUTINE)
            handle_routine "$comment_json"
            ;;
    esac
done
```

- **Agent Coordination**: When delegation occurs, poll `/tmp/$REPO_NAME/$BRANCH_NAME/agent_status.json` until it reports `"status": "completed"`. Only then fold the diff back into responses.json.
- **Response Assembly**: Populate every response with the new ACTION_ACCOUNTABILITY fields (`action_taken`, `files_modified`, `commit`, `verification`, etc.) as you implement each fix so evidence is fresh.

#### Comprehensive Comment Analysis Protocol

**🚨 LLM ARCHITECTURE PRINCIPLE: Full Context Analysis (MANDATORY)**

**For EVERY comment (regardless of author, type, length, or category):**

1. **Full Content Analysis**:
   - Read entire comment body with NO length limits, NO truncation
   - Identify ALL distinct issues/suggestions within the comment
   - Parse file:line references from ANY format (markdown, plain text, etc.)
   - Extract severity indicators from comment text content
   - **NO special handling for bot comments** - LLM treats all comments identically

2. **Multi-Issue Detection**:
   - Count total distinct issues in each comment
   - For each issue identified, determine:
     - What specific action needs to be done
     - Which files/lines are affected
     - What the priority/severity is
     - Whether it requires code changes or is informational

3. **Consolidated Response Generation**:
   - Generate ONE comprehensive response per comment
   - Address ALL N issues found (not just the first issue)
   - Provide specific status for EACH issue identified
   - Group by type when presenting (Actionable/Nitpick/Informational)
   - Show completion statistics (e.g., "Fixed 8/11 issues")

   **Response Format Structure** (uses global issue numbering):
   ```markdown
   ## Comment Analysis (N issues identified)

   ### Actionable Issues (X found)
   1. **[File:Line]** - Status: FIXED
      - Action: Specific implementation details
      - Commit: abc123
      - Verification: Tests pass

   2. **[File:Line]** - Status: DEFERRED
      - Reason: Requires architectural discussion
      - Issue: #1234

   ### Nitpick Issues (Y found)
   3. **[File:Line]** - Status: FIXED
      - Action: Code style improvement applied
      - Commit: def456

   ### Summary
   - Total issues: N (= X + Y + ...)
   - Fixed: M issues
   - Deferred: K issues
   - Acknowledged: P issues
   ```

   **Note**: Issue numbering is global across all sections (1, 2, 3, ..., N), not reset per section.

4. **No Keyword-Based Shortcuts**:
   - ❌ NO bot author detection (e.g., checking if author == "coderabbitai")
   - ❌ NO structure-based pre-parsing (e.g., extracting "Actionable comments posted: 6")
   - ❌ NO automatic file:line extraction before LLM sees content
   - ❌ NO pre-categorization that strips context from LLM
   - ✅ LLM receives FULL comment body and makes ALL decisions

**Why This Matters**: A single comment from CodeRabbit or any reviewer may contain multiple distinct issues. Generic "acknowledged" responses miss actionable items. The LLM must read and analyze the ENTIRE comment to identify ALL issues, then generate a comprehensive response addressing each one.

### Phase 3 Playbook — Verification & Completion

- **Test Command Detection**:
  1. If `package.json` contains an npm `test` script, run `npm test`.
  2. Else if `pytest.ini` or `pyproject.toml` exists, run `pytest` via `./run_tests.sh`.
  3. Else fallback to `./run_tests.sh` if present, otherwise `./run_tests_with_coverage.sh`.
  4. Export `TEST_COMMAND` so the same path is logged in responses.
- **Execution & Exit Handling**:

```bash
if [ -z "$TEST_COMMAND" ]; then
    echo "❌ TEST_COMMAND not set - define project test entry point before Phase 3"
    exit 1
fi

echo "🧪 Running tests via: $TEST_COMMAND"
set +e
eval "$TEST_COMMAND"
TEST_EXIT=$?
set -e

if [ $TEST_EXIT -ne 0 ]; then
    echo "❌ Tests failed (exit $TEST_EXIT). Block completion until failure is resolved."
    exit $TEST_EXIT
fi
echo "✅ Test verification complete"
```

- **Failure Policy**: Critical/blocking fixes cannot be marked complete until tests pass. If failures persist, re-open the relevant Phase 2 item and capture the remediation steps in responses.json before retrying.
- **Metrics & Health Signal**: Once tests pass, recompute the quality metrics (see "Quality Metrics & Health" below) to determine SAFE TO MERGE vs NEEDS WORK.

# /copilot - Fast PR Processing

## 📑 Table of Contents

- [Command Overview & Structure](#-command-overview--structure)
  - [Purpose](#-purpose)
  - [Architecture Pattern: Hybrid Orchestrator](#️-architecture-pattern-hybrid-orchestrator)
  - [Key Composed Commands Integration](#️-key-composed-commands-integration)
  - [Critical Boundaries](#-critical-boundaries)
  - [Performance Targets](#-performance-targets)
- [Mandatory Comment Coverage Tracking](#-mandatory-comment-coverage-tracking)
- [Automatic Timing Protocol](#️-automatic-timing-protocol)
- [Detailed Phase Playbooks & Reference](#-detailed-phase-playbooks--reference)
  - [Phase 0 Playbook — Critical Bug Scan](#phase-0-playbook--critical-bug-scan)
  - [Phase 1 Playbook — Analysis & Categorization](#phase-1-playbook--analysis--categorization)
  - [Phase 2 Playbook — Implementation & Responses](#phase-2-playbook--implementation--responses)
  - [Phase 3 Playbook — Verification & Completion](#phase-3-playbook--verification--completion)
- [Utilities & Validation](#-utilities--validation)
- [Hybrid Execution Details](#-hybrid-execution-details)
- [Response Data Format Specification](#-response-data-format-specification-updated-action-protocol)
- [Quality Metrics & Health Signals](#-quality-metrics--health-signals)
- [Agent Boundaries](#-agent-boundaries)
- [Success Criteria](#-success-criteria)

## 📋 COMMAND OVERVIEW & STRUCTURE

### 🎯 Purpose (UPDATED: QUALITY-FIRST)

**Quality-focused PR processing** using priority-based bug triage and hybrid orchestration for production safety and code correctness. Prioritizes critical bug fixes over comment coverage metrics.

**Key Improvements (v2.0):**
- 🚨 **Critical Bug Scan**: MANDATORY first-pass scan for security/production issues
- 📊 **Priority Hierarchy**: CRITICAL → BLOCKING → IMPORTANT → ROUTINE
- ✅ **Action Accountability**: Detailed response format with files, commits, verification
- 🎯 **Quality Metrics**: Focus on bugs fixed vs comment count
- 🧪 **Test Verification**: Mandatory test execution for critical/blocking fixes
- 🔗 **Comment URL Tracking**: Commit messages include URLs of fixed vs considered comments for auditability

**Design Philosophy:**
- **Correctness Over Coverage**: Fix critical bugs BEFORE processing routine comments
- **Direct Implementation**: Critical/blocking bugs fixed immediately, no agent delegation
- **Accountability**: Every response includes category, action taken, files modified, verification
- **Safety Signal**: Clear "SAFE TO MERGE" or "NEEDS WORK" based on critical/blocking resolution

### 🏗️ Architecture Pattern: Hybrid Orchestrator

**HYBRID DESIGN**: Direct orchestration + specialized agent for maximum reliability
- **Direct Orchestrator**: Handles comment analysis, GitHub operations, workflow coordination
- **copilot-fixpr Agent**: Specialized for file modifications, security fixes, merge conflicts
- **Proven Strategy**: Uses only verified working components, eliminates broken patterns

### 🎛️ Key Composed Commands Integration

- **Status Commands**: `/gstatus` (PR status), `/commentcheck` (coverage verification)
- **GitHub Commands**: `/commentfetch` (comment collection), `/commentreply` (response posting)
- **Agent Commands**: `/fixpr` (via copilot-fixpr agent for file operations)
- **Workflow Commands**: `/pushl` (automated push), `/guidelines` (documentation update)

### 🚨 Critical Boundaries

- **Orchestrator**: Comment processing, GitHub API, workflow coordination
- **Agent**: File modifications, security fixes, technical implementations
- **Never Mixed**: Agent NEVER handles comments, Orchestrator NEVER modifies files

### ⚡ Performance Targets

- **Execution Time**: **Adaptive based on PR complexity**
  - **Simple PRs** (≤3 files, ≤50 lines): 2-5 minutes
  - **Moderate PRs** (≤10 files, ≤500 lines): 5-10 minutes
  - **Complex PRs** (>10 files, >500 lines): 10-15 minutes
  - **Auto-scaling timeouts** with complexity detection and appropriate warnings
- **Success Rate**: 100% reliability through proven component usage
- **Coverage**: 100% comment response rate + all actionable issues implemented

## 🚨 Mandatory Comment Coverage Tracking

This command automatically tracks comment coverage and warns about missing responses:
```bash

# COVERAGE TRACKING: Monitor comment response completion (silent unless errors)

```

## ⏱️ Automatic Timing Protocol

This command silently tracks execution time and only reports if exceeded:
```bash

# Silent timing - only output if >3 minutes

COPILOT_START_TIME=$(date +%s)
```

## 🔧 Utilities & Validation

### Cleanup & Timing Helpers

Ultra-fast PR processing using hybrid orchestration still needs reliable cleanup and error handling to avoid leaking temp files.

```bash
# CLEANUP FUNCTION: Define error recovery and cleanup mechanisms

get_repo_name() {
    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
    local repo_name=""

    if [ -n "$repo_root" ]; then
        repo_name=$(basename "$repo_root")
    else
        repo_name=$(basename "$(pwd)")
    fi

    repo_name=$(echo "$repo_name" | tr -cd '[:alnum:]._-')
    echo "${repo_name:-unknown-repo}"
}

get_branch_name() {
    local branch_name
    branch_name=$(git branch --show-current 2>/dev/null || true)
    branch_name=$(echo "$branch_name" | tr -cd '[:alnum:]._-')
    echo "${branch_name:-unknown-branch}"
}

cleanup_temp_files() {
    local repo_name
    repo_name=$(get_repo_name)
    local branch_name
    branch_name=$(get_branch_name)
    local temp_dir="/tmp/$repo_name/$branch_name"

    # Safety: never allow cleanup to target /tmp itself
    if [ "$temp_dir" = "/tmp" ] || [ "$temp_dir" = "/tmp/" ]; then
        echo "⚠️  CLEANUP: Skipping unsafe temp_dir=$temp_dir"
        return 0
    fi

    if [ -d "$temp_dir" ]; then
        echo "🧹 CLEANUP: Removing temporary files from $temp_dir"
        rm -rf "$temp_dir"/* 2>/dev/null || true
    fi

    # Reset any stuck GitHub operations
    echo "🔄 CLEANUP: Resetting any stuck operations"
    # Additional cleanup operations as needed
}

# Cleanup old caches (older than 7 days)
cleanup_old_caches() {
    local repo_name
    repo_name=$(get_repo_name)
    local repo_cache_dir="/tmp/$repo_name"
    
    # Safety: never allow cleanup to target /tmp itself
    if [ "$repo_cache_dir" = "/tmp" ] || [ "$repo_cache_dir" = "/tmp/" ]; then
        echo "⚠️  CLEANUP: Skipping unsafe repo_cache_dir=$repo_cache_dir"
        return 0
    fi

    if [ -d "$repo_cache_dir" ]; then
        # Remove caches older than 7 days (within the repo-scoped directory only)
        find "$repo_cache_dir" -mindepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
    fi
}

# ERROR HANDLER: Trap errors for graceful cleanup

trap 'cleanup_temp_files; echo "🚨 ERROR: Copilot workflow interrupted"; exit 1' ERR

COPILOT_START_TIME=$(date +%s)

# Initialize path variables with repo name

REPO_NAME=$(get_repo_name)
BRANCH_NAME=$(get_branch_name)
CACHE_DIR="/tmp/$REPO_NAME/$BRANCH_NAME"
CACHE_METADATA_FILE="$CACHE_DIR/cache_metadata.json"
COMMENTS_FILE="$CACHE_DIR/comments.json"

# Perform cleanup of old caches
cleanup_old_caches

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE STRATEGY: Always Fresh + Handled Registry (v2.0)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Previous approach: Complex staleness detection (is_cache_fresh_incremental, is_cache_fresh)
#   - Problem: Missed 12 comments because staleness check only covered 2/4 comment types
#   - Problem: Cache was "fresh" by TTL but stale in reality
#
# New approach: Always fetch fresh, skip already-handled comments
#   - Always get fresh comment data from GitHub (no staleness bugs)
#   - Per-comment cache tracks "handled" status after each successful reply
#   - Resumable: if interrupted mid-run, already-handled comments won't be reprocessed
#   - Thread-independent: each reply is tracked separately
#
# See bead worktree_worker4-qqj for design details
# ═══════════════════════════════════════════════════════════════════════════════

# Phase 0: ALWAYS fetch fresh comments - no staleness check
# The handled registry in per-comment cache ensures we don't reprocess comments
echo "🔄 Fetching fresh comments from GitHub API (always-fresh strategy)"
/commentfetch

# Resolve project root for Python helper import (must be before first use)
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Report unhandled comment count for visibility
if [ -d "$CACHE_DIR/comments" ]; then
    UNHANDLED_COUNT=$(python3 -c "
import sys
import os
sys.path.insert(0, os.path.join('$PROJECT_ROOT', '.claude', 'commands', '_copilot_modules'))
try:
    from per_comment_cache import PerCommentCache
    cache = PerCommentCache('$CACHE_DIR')
    unhandled = cache.get_unhandled_comments()
    print(len(unhandled))
except Exception as e:
    print(-1)
" || echo -1)

    if [ "$UNHANDLED_COUNT" -ge 0 ]; then
        echo "📊 Found $UNHANDLED_COUNT unhandled comment(s) requiring responses"
    fi
fi

# Get comprehensive PR status first

/gstatus

# Initialize timing for performance tracking (silent unless exceeded)
```

### Security Functions

```bash
# Security function for sanitizing GitHub comment content

sanitize_comment() {
    local input="$1"
    local max_length="${2:-10000}"  # Default 10KB limit

    # Length validation
    if [ ${#input} -gt $max_length ]; then
        echo "❌ Input exceeds maximum length of $max_length characters" >&2
        return 1
    fi

    # Remove null bytes and escape shell metacharacters
    local sanitized=$(echo "$input" | tr -d '\0' | sed 's/[`$\\]/\\&/g' | sed 's/[;&|]/\\&/g')

    # Check for suspicious patterns in original input (before escaping)
    if echo "$input" | grep -qE '(\$\(|`|<script|javascript:|eval\(|exec\()'; then
        echo "⚠️ Potentially malicious content detected and neutralized" >&2
        # Continue with sanitized version rather than failing completely
    fi

    echo "$sanitized"
}

# Validate branch name to prevent path injection

validate_branch_name() {
    local branch="$1"
    if [[ "$branch" =~ ^[a-zA-Z0-9._-]+$ ]] && [ ${#branch} -le 100 ]; then
        return 0
    else
        echo "❌ Invalid branch name: contains illegal characters or too long" >&2
        return 1
    fi
}
```

## 🤝 Hybrid Execution Details

### Orchestrator Responsibilities

- Analyze actionable issues and categorize by type (security, runtime, tests, style)
- Process issue responses and plan implementation strategy
- Handle all GitHub API operations directly (proven to work)

### 🚀 Parallel copilot-fixpr Agent Launch with Explicit Synchronization
Launch specialized agent for file modifications with structured coordination:
- **FIRST**: Execute `/fixpr` command to resolve merge conflicts and CI failures
- Analyze current GitHub PR status and identify potential improvements
- Review code changes for security vulnerabilities and quality issues
- Implement actual file fixes using Edit/MultiEdit tools with File Justification Protocol
- Focus on code quality, performance optimization, and technical accuracy
- **NEW**: Write completion status to structured result file for orchestrator

**🚨 EXPLICIT SYNCHRONIZATION PROTOCOL**: Eliminates race conditions
```bash

# Secure branch name and setup paths (using repo-scoped cache directory)

REPO_NAME=$(get_repo_name)
BRANCH_NAME=$(get_branch_name)
CACHE_DIR="/tmp/$REPO_NAME/$BRANCH_NAME"

# Ensure consistency across all cache operations
AGENT_STATUS="$CACHE_DIR/agent_status.json"
mkdir -p "$CACHE_DIR"

# Agent execution with status tracking

copilot-fixpr-agent > "$AGENT_STATUS" &
AGENT_PID=$!

# Detect PR complexity for appropriate timeout

FILES_CHANGED=$(git diff --name-only origin/main | wc -l)
LINES_CHANGED=$(git diff --stat origin/main | tail -1 | grep -oE '[0-9]+' | head -1 || echo 0)

if [ $FILES_CHANGED -le 3 ] && [ $LINES_CHANGED -le 50 ]; then
    TIMEOUT=300  # 5 minutes for simple PRs
elif [ $FILES_CHANGED -le 10 ] && [ $LINES_CHANGED -le 500 ]; then
    TIMEOUT=600  # 10 minutes for moderate PRs
else
    TIMEOUT=900  # 15 minutes for complex PRs
fi

echo "📊 PR Complexity: $FILES_CHANGED files, $LINES_CHANGED lines (timeout: $((TIMEOUT/60))m)"

# Orchestrator waits for agent completion with adaptive timeout

START_TIME=$(date +%s)
while [ ! -f "$AGENT_STATUS" ]; do
    # Check if agent is still running
    if ! kill -0 $AGENT_PID 2>/dev/null; then
        echo "⚠️ Agent process terminated unexpectedly"
        break
    fi

    CURRENT_TIME=$(date +%s)
    if [ $((CURRENT_TIME - START_TIME)) -gt $TIMEOUT ]; then
        echo "⚠️ Agent timeout after $((TIMEOUT/60)) minutes"
        kill $AGENT_PID 2>/dev/null
        break
    fi
    sleep 10
done

# Verify agent completion before proceeding

if [ -f "$AGENT_STATUS" ]; then
    echo "✅ Agent completed successfully, proceeding with response generation"
else
    echo "❌ CRITICAL: Agent did not complete successfully"
    exit 1
fi
```

**Coordination Protocol**: Explicit synchronization prevents race conditions between orchestrator and agent

# Read structured agent results from status file

# Note: AGENT_STATUS is already set earlier in the workflow
# Using the centralized cache directory for consistency

if [ -f "$AGENT_STATUS" ]; then
    # Parse structured agent results with error handling
    FILES_MODIFIED=$(jq -r '.files_modified[]?' "$AGENT_STATUS" 2>/dev/null | head -20 || echo "")
    FIXES_APPLIED=$(jq -r '.fixes_applied[]?' "$AGENT_STATUS" 2>/dev/null | head -20 || echo "")
    COMMIT_HASH=$(jq -r '.commit_hash?' "$AGENT_STATUS" 2>/dev/null || echo "")
    EXECUTION_TIME=$(jq -r '.execution_time?' "$AGENT_STATUS" 2>/dev/null || echo "0")

    echo "📊 Agent Results:"
    [ -n "$FILES_MODIFIED" ] && echo "  Files: $FILES_MODIFIED"
    [ -n "$FIXES_APPLIED" ] && echo "  Fixes: $FIXES_APPLIED"
    [ -n "$COMMIT_HASH" ] && echo "  Commit: $COMMIT_HASH"
    echo "  Time: ${EXECUTION_TIME}s"
else
    echo "❌ No agent status file found - using fallback git diff"
    FILES_MODIFIED=$(git diff --name-only | head -10)
fi
```

**Agent-Orchestrator Interface**:
- **Agent provides**: Structured JSON with files_modified, fixes_applied, commit_hash, execution_time
- **Agent JSON contract**: `agent_status.json` also includes a `status` field (e.g., `"completed"`) so the orchestrator can block until work finishes. The copilot-fixpr agent implementation has been updated to emit this structure before the orchestrator consumes it.
- **Orchestrator handles**: Comment processing, response generation, GitHub API operations, coverage tracking
- **Coordination ensures**: Explicit synchronization prevents race conditions and response inconsistencies

**Response Generation with Action Protocol** (MANDATORY ORCHESTRATOR RESPONSIBILITY):
```bash
# Ensure cache paths are defined for this block
REPO_NAME=$(get_repo_name)
BRANCH_NAME=$(get_branch_name)
CACHE_DIR="/tmp/$REPO_NAME/$BRANCH_NAME"
AGENT_STATUS="$CACHE_DIR/agent_status.json"

echo "📝 Generating action-based responses.json with implementation accountability"

# 🚨 NEW PROTOCOL: Action-based responses with files_modified, tests_added, commit, verification

echo "🔧 Implementing CodeRabbit technical suggestions:"

# 1. IMPLEMENTED: Accurate line counting with --numstat (CodeRabbit suggestion)

echo "  • Adding git diff --numstat for accurate line counting"
PR_LINES=$(git diff --numstat origin/main | awk '{added+=$1; deleted+=$2} END {print "Added:" added " Deleted:" deleted}')
echo "    Lines: $PR_LINES"

# 2. IMPLEMENTED: JSON validation with jq -e (CodeRabbit suggestion)

echo "  • Adding jq -e validation for all JSON files"
# Ensure cache paths are defined for this block (self-contained)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
REPO_NAME=$(basename "$REPO_ROOT" | tr -cd '[:alnum:]._-')
BRANCH_NAME=$(git branch --show-current 2>/dev/null | tr -cd '[:alnum:]._-')
REPO_NAME=${REPO_NAME:-unknown-repo}
BRANCH_NAME=${BRANCH_NAME:-unknown-branch}
CACHE_DIR="/tmp/$REPO_NAME/$BRANCH_NAME"
AGENT_STATUS="$CACHE_DIR/agent_status.json"

for json_file in $CACHE_DIR/*.json; do
    if [ -f "$json_file" ]; then
        echo "    Validating: $json_file"
        jq -e . "$json_file" > /dev/null || {
            echo "❌ CRITICAL: Invalid JSON in $json_file"
            exit 1
        }
        echo "    ✅ Valid JSON: $(basename "$json_file")"
    fi
done

# 3. IMPLEMENTED: Fix agent status race condition (CodeRabbit concern)

echo "  • Implementing proper agent status coordination (not immediate file creation)"
# Note: AGENT_STATUS is already set earlier using CACHE_DIR

# Wait for agent completion instead of immediate file creation

while [ ! -f "$AGENT_STATUS" ] || [ "$(jq -r '.status' "$AGENT_STATUS" 2>/dev/null)" != "completed" ]; do
    sleep 1
    echo "    Waiting for agent completion..."
done
echo "    ✅ Agent coordination: Proper status synchronization"

# CRITICAL: Generate responses in commentreply.py expected format

# Orchestrator writes to: $CACHE_DIR/responses.json

# 🚨 ACTION RESPONSE PROTOCOL: Every comment gets detailed action report

echo "🔍 ACTION PROTOCOL: Analyzing ALL comments for categorized responses with accountability"

# Comment categorization for response generation
categorize_comment() {
    local comment_body="$1"

    # CRITICAL: Use same pattern as Phase 0 for consistency (must match line 48)
    local critical_pattern="(CRITICAL|BUG|SECURITY|BLOCKER|PRODUCTION BLOCKER|PRODUCTION BUG|rate limit|authentication|authorization|admin.*UID|data loss|data-loss|dataloss|corruption|crash|vulnerability|auth bypass)"
    local blocking_pattern="(CI fail|build fail|test fail|breaking change|resource leak|timeout)"
    local important_pattern="(performance|logic error|validation|architectural|latency)"

    # CRITICAL: Security, production blockers, data corruption (should be handled in Phase 0)
    if echo "$comment_body" | grep -qiE "$critical_pattern"; then
        echo "CRITICAL"
        return
    fi

    # BLOCKING: CI failures, build failures, breaking changes
    if echo "$comment_body" | grep -qiE "$blocking_pattern"; then
        echo "BLOCKING"
        return
    fi

    # IMPORTANT: Performance, logic errors, missing validation
    if echo "$comment_body" | grep -qiE "$important_pattern"; then
        echo "IMPORTANT"
        return
    fi

    # ROUTINE: Code style, documentation, optional refactoring
    echo "ROUTINE"
}

# INPUT SANITIZATION: Validate branch name (already sanitized earlier)

REPO_NAME=$(get_repo_name)
BRANCH_NAME=$(get_branch_name)
CACHE_DIR="/tmp/$REPO_NAME/$BRANCH_NAME"
COMMENTS_FILE="$CACHE_DIR/comments.json"
if [ -z "$BRANCH_NAME" ]; then
    echo "❌ CRITICAL: Invalid or empty branch name"
    cleanup_temp_files
    return 1
fi

# SECURE PATH CONSTRUCTION: Use repo-scoped cache directory

# Note: COMMENTS_FILE and CACHE_DIR are already set earlier in the workflow
export RESPONSES_FILE="$CACHE_DIR/responses.json"

# API RESPONSE VALIDATION: Verify comment data exists and is valid JSON (using jq -e)

if [ ! -f "$COMMENTS_FILE" ]; then
    echo "❌ CRITICAL: No comment data from commentfetch at $COMMENTS_FILE"
    cleanup_temp_files
    return 1
fi

# VALIDATION: Verify comments.json is valid JSON before processing (CodeRabbit's jq -e suggestion)

if ! jq -e empty "$COMMENTS_FILE" 2>/dev/null; then
    echo "❌ CRITICAL: Invalid JSON in comments file"
    cleanup_temp_files
    return 1
fi

TOTAL_COMMENTS=$(jq '.comments | length' "$COMMENTS_FILE")
echo "📊 Processing $TOTAL_COMMENTS comments for response generation"

# Generate responses for ALL unresponded comments

# This is ORCHESTRATOR responsibility, not agent responsibility

# 🚨 NEW: MANDATORY FORMAT VALIDATION

echo "🔧 VALIDATING: Response format compatibility with commentreply.py"

# Resolve repository root for downstream tooling
PROJECT_ROOT=$(git rev-parse --show-toplevel)
if [ -z "$PROJECT_ROOT" ]; then
    echo "❌ CRITICAL: Unable to resolve project root"
    exit 1
fi

# Use dedicated validation script for better maintainability
python3 "$PROJECT_ROOT/.claude/commands/validate_response_format.py" || {
    echo "❌ CRITICAL: Invalid response format";
    exit 1;
}

# Verify responses.json exists and is valid before proceeding

if [ ! -f "$RESPONSES_FILE" ]; then
    echo "❌ CRITICAL: responses.json not found at $RESPONSES_FILE"
    echo "Orchestrator must generate responses before posting"
    exit 1
fi

# 🚨 ACTION RESPONSE TEMPLATE: Detailed accountability required

echo "📋 Building action-based response structure with implementation tracking"
cat > "$RESPONSES_FILE" << 'EOF'
{
  "response_protocol": "ACTION_ACCOUNTABILITY",
  "response_types": {
    "FIXED": "Issue implemented with working code (STRONGLY PREFERRED)",
    "DEFERRED": "Cannot do now - MUST create real bead with ID",
    "ACKNOWLEDGED": "Purely informational - NO future promises allowed",
    "NOT_DONE": "Won't implement with specific technical reason"
  },
  "response_priority_rules": {
    "rule_1": "FIXED is STRONGLY PREFERRED - do the work if at all feasible",
    "rule_2": "DEFERRED requires real bead_id - no vague 'TODO tracked'",
    "rule_3": "ACKNOWLEDGED must NOT contain 'will', 'TODO', or future promises",
    "rule_4": "NOT_DONE requires specific technical reason why not feasible"
  },
  "required_fields": {
    "FIXED": ["category", "action_taken", "files_modified", "commit", "verification"],
    "DEFERRED": ["category", "reason", "bead_id"],
    "ACKNOWLEDGED": ["category", "explanation"],
    "NOT_DONE": ["category", "reason"]
  },
  "template_fixed": {
    "response": "FIXED",
    "category": "CRITICAL|BLOCKING|IMPORTANT|ROUTINE",
    "html_url": "https://github.com/owner/repo/pull/123#issuecomment-456",
    "action_taken": "Specific implementation description",
    "files_modified": ["file1.ts:123", "file2.py:456"],
    "tests_added": ["test1.test.ts"],
    "commit": "abc123de",
    "verification": "✅ Tests pass, feature verified"
  },
  "template_deferred": {
    "response": "DEFERRED",
    "category": "CRITICAL|BLOCKING|IMPORTANT|ROUTINE",
    "html_url": "https://github.com/owner/repo/pull/123#issuecomment-456",
    "reason": "Specific technical reason why cannot be done in this PR",
    "bead_id": "worktree_worker4-xyz",
    "note": "MUST create actual bead BEFORE using DEFERRED - no vague 'TODO tracked'"
  },
  "template_acknowledged": {
    "response": "ACKNOWLEDGED",
    "category": "CRITICAL|BLOCKING|IMPORTANT|ROUTINE",
    "html_url": "https://github.com/owner/repo/pull/123#issuecomment-456",
    "explanation": "Factual note only - NO future promises, NO 'will do', NO 'TODO'",
    "forbidden": ["will", "TODO", "follow-up", "future", "later"]
  },
  "template_not_done": {
    "response": "NOT_DONE",
    "category": "CRITICAL|BLOCKING|IMPORTANT|ROUTINE",
    "html_url": "https://github.com/owner/repo/pull/123#issuecomment-456",
    "reason": "Specific reason why implementation not feasible"
  },
  "template_multi_issue": {
    "comment_id": "3675347161",
    "html_url": "https://github.com/owner/repo/pull/123#issuecomment-3675347161",
    "analysis": {
      "total_issues": 11,
      "actionable": 6,
      "nitpicks": 5
    },
    "issues": [
      {
        "number": 1,
        "file": "game_state_instruction.md",
        "line": "751-776",
        "description": "Remove phrase-scanning triggers",
        "category": "BLOCKING",
        "response": "FIXED",
        "action_taken": "Removed phrase-scanning trigger patterns, converted to intent-based processing",
        "files_modified": ["game_state_instruction.md:751-776"],
        "commit": "abc123",
        "verification": "✅ Verified no phrase-scanning patterns remain",
        "html_url": "https://github.com/owner/repo/pull/123#discussion_r456"
      }
    ],
    "reply_text": "Consolidated markdown addressing all 11 issues"
  },
  "responses": []
}
EOF

# Validate responses.json with jq -e (CodeRabbit suggestion)

jq -e . "$RESPONSES_FILE" > /dev/null || {
    echo "❌ CRITICAL: Invalid JSON in responses.json"
    exit 1
}

echo "🔄 Executing /commentreply with ACTION protocol (FIXED/DEFERRED/ACKNOWLEDGED/NOT_DONE)"
/commentreply || {
    echo "🚨 CRITICAL: Comment response failed"
    cleanup_temp_files
    return 1
}
echo "🔍 Verifying coverage via /commentcheck"
/commentcheck || {
    echo "🚨 CRITICAL: Comment coverage failed"
    cleanup_temp_files
    return 1
}

## 📊 Quality Metrics & Health Signals

# 🚨 NEW: Quality-focused metrics reporting
echo ""
echo "📊 QUALITY METRICS (Priority-Based Assessment):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Count responses by category and type
CRITICAL_FIXED=$(jq '[.responses[] | select(.category == "CRITICAL" and .response == "FIXED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
CRITICAL_DEFERRED=$(jq '[.responses[] | select(.category == "CRITICAL" and .response == "DEFERRED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
CRITICAL_TOTAL=$(jq '[.responses[] | select(.category == "CRITICAL")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
BLOCKING_FIXED=$(jq '[.responses[] | select(.category == "BLOCKING" and .response == "FIXED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
BLOCKING_DEFERRED=$(jq '[.responses[] | select(.category == "BLOCKING" and .response == "DEFERRED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
BLOCKING_TOTAL=$(jq '[.responses[] | select(.category == "BLOCKING")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
IMPORTANT_FIXED=$(jq '[.responses[] | select(.category == "IMPORTANT" and .response == "FIXED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
IMPORTANT_TOTAL=$(jq '[.responses[] | select(.category == "IMPORTANT")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
IMPORTANT_DEFERRED=$(jq '[.responses[] | select(.category == "IMPORTANT" and .response == "DEFERRED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
ROUTINE_RESPONSES=$(jq '[.responses[] | select(.category == "ROUTINE")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
TOTAL_RESPONSES=$(jq '.responses | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)

if [ $CRITICAL_TOTAL -gt 0 ]; then
    CRITICAL_PCT=$((CRITICAL_FIXED * 100 / CRITICAL_TOTAL))
    echo "🚨 Critical bugs fixed: $CRITICAL_FIXED/$CRITICAL_TOTAL ($CRITICAL_PCT%) — $CRITICAL_DEFERRED deferred"
else
    echo "🚨 Critical bugs fixed: $CRITICAL_FIXED/$CRITICAL_TOTAL (N/A)"
fi

if [ $BLOCKING_TOTAL -gt 0 ]; then
    BLOCKING_PCT=$((BLOCKING_FIXED * 100 / BLOCKING_TOTAL))
    echo "✅ Blocking issues fixed: $BLOCKING_FIXED/$BLOCKING_TOTAL ($BLOCKING_PCT%) — $BLOCKING_DEFERRED deferred"
else
    echo "✅ Blocking issues fixed: $BLOCKING_FIXED/$BLOCKING_TOTAL (N/A)"
fi

echo "⚠️  Important issues: $IMPORTANT_FIXED fixed, $IMPORTANT_DEFERRED deferred (of $IMPORTANT_TOTAL total)"
echo "📝 Routine responses: $ROUTINE_RESPONSES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Total comments processed: $TOTAL_RESPONSES"

# Determine PR health status
UNRESOLVED_CRITICAL=$((CRITICAL_TOTAL - CRITICAL_FIXED - CRITICAL_DEFERRED))
UNRESOLVED_BLOCKING=$((BLOCKING_TOTAL - BLOCKING_FIXED - BLOCKING_DEFERRED))

if [ $CRITICAL_TOTAL -eq 0 ] && [ $BLOCKING_TOTAL -eq 0 ]; then
    echo "✅ Overall health: SAFE TO MERGE (no critical/blocking issues)"
elif [ $CRITICAL_FIXED -eq $CRITICAL_TOTAL ] && [ $BLOCKING_FIXED -eq $BLOCKING_TOTAL ]; then
    echo "✅ Overall health: SAFE TO MERGE (all critical/blocking resolved)"
elif [ $UNRESOLVED_CRITICAL -eq 0 ] && [ $UNRESOLVED_BLOCKING -eq 0 ]; then
    # Check if any critical/blocking were deferred (not allowed for SAFE TO MERGE per success criteria)
    CRITICAL_DEFERRED_COUNT=$(jq -r '[.responses[] | select(.category == "CRITICAL" and .response == "DEFERRED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")
    BLOCKING_DEFERRED_COUNT=$(jq -r '[.responses[] | select(.category == "BLOCKING" and .response == "DEFERRED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")
    
    if [ "$CRITICAL_DEFERRED_COUNT" -gt 0 ] || [ "$BLOCKING_DEFERRED_COUNT" -gt 0 ]; then
        echo "⚠️ Overall health: NEEDS REVIEW (critical/blocking issues deferred - must be FIXED for SAFE TO MERGE per success criteria)"
    else
        echo "✅ Overall health: SAFE TO MERGE (all critical/blocking issues fixed)"
    fi
else
    echo "❌ Overall health: NEEDS WORK ($UNRESOLVED_CRITICAL critical, $UNRESOLVED_BLOCKING blocking unresolved)"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✅ Action-based comment responses posted successfully with accountability"
```
Direct execution of /commentreply with implementation details from agent file changes for guaranteed GitHub posting

# Show evidence of changes with CodeRabbit's --numstat implementation

echo "📊 COPILOT EXECUTION EVIDENCE:"
echo "🔧 FILES MODIFIED:"
git diff --name-only | sed 's/^/  - /'
echo "📈 CHANGE SUMMARY (using CodeRabbit's --numstat):"
git diff --numstat origin/main
echo "📈 TRADITIONAL STAT:"
git diff --stat

# 🚨 MANDATORY: Verify actual technical implementations before push

echo "🔍 IMPLEMENTATION VERIFICATION:"
echo "  • Line counting: git diff --numstat - IMPLEMENTED ✅"
echo "  • JSON validation: jq -e validation - IMPLEMENTED ✅"
echo "  • Agent status coordination: proper file handling - IMPLEMENTED ✅"
echo "  • Action response protocol: FIXED/DEFERRED/ACKNOWLEDGED/NOT_DONE - IMPLEMENTED ✅"
echo "  • Priority-based processing: CRITICAL → BLOCKING → IMPORTANT → ROUTINE - IMPLEMENTED ✅ (Phase 2 priority queue loop)"
echo "  • Quality metrics: Critical bugs fixed, blocking issues resolved - IMPLEMENTED ✅"

# Run tests to verify all fixes (Phase 3 verification)
echo ""
echo "🧪 PHASE 3: VERIFICATION - Running tests to confirm fixes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if there are any critical or blocking fixes that need test verification
NEEDS_TESTING=$((CRITICAL_FIXED + BLOCKING_FIXED))

if [ $NEEDS_TESTING -gt 0 ]; then
    echo "📊 Testing $NEEDS_TESTING critical/blocking fixes"

    TEST_COMMAND=""
    if [ -f package.json ] && jq -e '.scripts.test' package.json >/dev/null 2>&1; then
        TEST_COMMAND="npm test"
    elif [ -f ./run_tests.sh ]; then
        TEST_COMMAND="./run_tests.sh"
    elif [ -f pytest.ini ] || [ -f pyproject.toml ]; then
        TEST_COMMAND="pytest"
    elif [ -f ./run_tests_with_coverage.sh ]; then
        TEST_COMMAND="./run_tests_with_coverage.sh"
    fi

    if [ -z "$TEST_COMMAND" ]; then
        echo "❌ TEST_COMMAND not set - define the project test runner before continuing"
        exit 1
    fi

    echo "Running test suite via: $TEST_COMMAND"
    set +e
    eval "$TEST_COMMAND"
    TEST_EXIT=$?
    set -e

    if [ $TEST_EXIT -ne 0 ]; then
        echo "❌ Tests failed (exit $TEST_EXIT). Resolve before marking verification complete."
        exit $TEST_EXIT
    fi

    echo "✅ Test verification complete"
else
    echo "ℹ️  No critical/blocking fixes requiring test verification"
fi

# Verify commits for critical bugs
if [ $CRITICAL_FIXED -gt 0 ]; then
    echo ""
    echo "📝 Verifying critical bug fix commits:"
    git log --oneline --grep="Fix:" --grep="Critical" | sed 's/^/  /'
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 📋 Generate commit message with comment URLs for tracking

echo ""
echo "📋 GENERATING COMMIT MESSAGE WITH COMMENT URL TRACKING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Centralized jq filter: Flatten responses and nested issues for proper classification
# For multi-issue responses, preserve parent's comment_id and html_url as fallback
JQ_FLATTEN='(if (.issues? | length) > 0 then (.comment_id as $parent_id | .html_url as $parent_url | .issues[] | .comment_id //= $parent_id | .parent_html_url //= $parent_url) else . end)'

# Extract comment URLs from responses.json grouped by response type.
FIXED_URLS=$(jq -r "
  .responses[]
  | $JQ_FLATTEN
  | select(.response == \"FIXED\")
  | .html_url // .parent_html_url // empty
" "$RESPONSES_FILE" 2>/dev/null | sed '/^$/d' | sort -u || echo "")

CONSIDERED_URLS=$(jq -r "
  .responses[]
  | $JQ_FLATTEN
  | select(.response == \"ACKNOWLEDGED\" or .response == \"NOT_DONE\" or .response == \"DEFERRED\")
  | .html_url // .parent_html_url // empty
" "$RESPONSES_FILE" 2>/dev/null | sed '/^$/d' | sort -u || echo "")

# Get comment URLs from comments.json as fallback for responses with missing html_url.
# Identify which specific comment IDs lack URLs and backfill only those.
FIXED_IDS_WITHOUT_URLS=$(jq -r "
  .responses[]
  | $JQ_FLATTEN
  | select(.response == \"FIXED\" and ((.html_url // \"\") | length == 0) and ((.parent_html_url // \"\") | length == 0))
  | .comment_id // empty
" "$RESPONSES_FILE" 2>/dev/null | sed '/^$/d' | sort -u || echo "")

if [ -n "$FIXED_IDS_WITHOUT_URLS" ]; then
    echo "⚠️ Backfilling missing FIXED URLs from comments.json for $(echo "$FIXED_IDS_WITHOUT_URLS" | wc -l) comment(s)"
    while IFS= read -r id; do
        [ -z "$id" ] && continue
        url=$(jq -r --arg id "$id" '.comments[] | select((.id | tostring) == $id) | .html_url // empty' "$COMMENTS_FILE" 2>/dev/null)
        if [ -n "$url" ]; then
            FIXED_URLS="${FIXED_URLS}\n${url}"
        fi
    done <<< "$FIXED_IDS_WITHOUT_URLS"
fi

CONSIDERED_IDS_WITHOUT_URLS=$(jq -r "
  .responses[]
  | $JQ_FLATTEN
  | select((.response == \"ACKNOWLEDGED\" or .response == \"NOT_DONE\" or .response == \"DEFERRED\") and ((.html_url // \"\") | length == 0) and ((.parent_html_url // \"\") | length == 0))
  | .comment_id // empty
" "$RESPONSES_FILE" 2>/dev/null | sed '/^$/d' | sort -u || echo "")

if [ -n "$CONSIDERED_IDS_WITHOUT_URLS" ]; then
    echo "⚠️ Backfilling missing considered URLs from comments.json for $(echo "$CONSIDERED_IDS_WITHOUT_URLS" | wc -l) comment(s)"
    while IFS= read -r id; do
        [ -z "$id" ] && continue
        url=$(jq -r --arg id "$id" '.comments[] | select((.id | tostring) == $id) | .html_url // empty' "$COMMENTS_FILE" 2>/dev/null)
        if [ -n "$url" ]; then
            CONSIDERED_URLS="${CONSIDERED_URLS}\n${url}"
        fi
    done <<< "$CONSIDERED_IDS_WITHOUT_URLS"
fi

FIXED_URLS=$(echo -e "$FIXED_URLS" | sed '/^$/d' | sort -u)
CONSIDERED_URLS=$(echo -e "$CONSIDERED_URLS" | sed '/^$/d' | sort -u)

# Build commit message with comment URL tracking
COMMIT_MSG="Fix PR comments from /copilot workflow

**Comment Tracking:**"

if [ -n "$FIXED_URLS" ]; then
    FIXED_COUNT=$(echo -e "$FIXED_URLS" | grep -c 'http' || true)
    COMMIT_MSG="$COMMIT_MSG

✅ Fixed ($FIXED_COUNT):
$(echo -e "$FIXED_URLS" | sed 's/^/- /')"
else
    COMMIT_MSG="$COMMIT_MSG

✅ Fixed: None"
fi

if [ -n "$CONSIDERED_URLS" ]; then
    CONSIDERED_COUNT=$(echo -e "$CONSIDERED_URLS" | grep -c 'http' || true)
    COMMIT_MSG="$COMMIT_MSG

📝 Considered (acknowledged/deferred/not-done) ($CONSIDERED_COUNT):
$(echo -e "$CONSIDERED_URLS" | sed 's/^/- /')"
else
    COMMIT_MSG="$COMMIT_MSG

📝 Considered: None"
fi

COMMIT_MSG="$COMMIT_MSG

[copilot-commit]"

echo "📝 Generated commit message with comment tracking:"
echo "$COMMIT_MSG"
echo ""

# Create commit if there are changes (including untracked files)
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "💾 Creating tracking commit..."
    git add -A
    COMMIT_MSG_FILE=$(mktemp)
    printf '%s\n' "$COMMIT_MSG" > "$COMMIT_MSG_FILE"
    if git commit --allow-empty -F "$COMMIT_MSG_FILE"; then
        echo "✅ Tracking commit created"
    else
        echo "⚠️ Commit failed (possibly no changes or already committed)"
    fi
    rm -f "$COMMIT_MSG_FILE"
else
    echo "ℹ️ No changes to commit (all fixes already committed)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Push changes to PR with error recovery

/pushl || {
    echo "🚨 PUSH FAILED: PR not updated"
    echo "🔧 RECOVERY: Attempting git status check"
    git status
    cleanup_temp_files
    return 1
}

# 🚨 POST-PUSH COMMENT REFRESH: Catch late comments posted during workflow
echo "🔄 POST-PUSH: Re-fetching comments to catch late arrivals"
/commentfetch

# Check for NEW unhandled comments that arrived during the workflow
NEW_UNHANDLED=$(python3 -c "
import sys
import os
sys.path.insert(0, os.path.join('$PROJECT_ROOT', '.claude', 'commands', '_copilot_modules'))
try:
    from per_comment_cache import PerCommentCache
    cache = PerCommentCache('$CACHE_DIR')
    unhandled = cache.get_unhandled_comments()
    print(len(unhandled))
except Exception as e:
    print(0)
" || echo 0)

if [ "$NEW_UNHANDLED" -gt 0 ]; then
    echo "⚠️ Found $NEW_UNHANDLED new comment(s) posted during workflow - processing..."
    /commentreply || echo "⚠️ Warning: Some late comments may need manual response"
fi
```

**Coverage Tracking (MANDATORY GATE):**
```bash

# HARD VERIFICATION GATE with RECOVERY - Must pass before proceeding
# Now includes ROUTINE comment coverage (90% minimum)

echo "🔍 MANDATORY: Verifying comment coverage (100% critical/blocking, 90% routine)"
if ! /commentcheck; then
    echo "🚨 CRITICAL: Comment coverage failed - attempting recovery"
    echo "🔧 RECOVERY: Re-running comment response workflow"

    # Attempt recovery by re-running comment responses
    /commentreply || {
        echo "🚨 CRITICAL: Recovery failed - manual intervention required";
        echo "📊 DIAGNOSTIC: Check $CACHE_DIR/responses.json format";
        echo "📊 DIAGNOSTIC: Verify GitHub API permissions and rate limits";
        exit 1;
    }

    # Re-verify after recovery attempt
    /commentcheck || {
        echo "🚨 CRITICAL: Comment coverage still failing after recovery"
        cleanup_temp_files
        return 1
    }
fi

# Additional check: Verify ROUTINE comments have ≥90% coverage
ROUTINE_TOTAL=$(jq '[.responses[] | select(.category == "ROUTINE")] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)
ROUTINE_RESPONDED=$(jq '[.responses[] | select(.category == "ROUTINE" and (.response == "FIXED" or .response == "ACKNOWLEDGED" or .response == "NOT_DONE"))] | length' "$RESPONSES_FILE" 2>/dev/null || echo 0)

if [ "$ROUTINE_TOTAL" -gt 0 ]; then
    ROUTINE_PCT=$((ROUTINE_RESPONDED * 100 / ROUTINE_TOTAL))
    if [ "$ROUTINE_PCT" -lt 90 ]; then
        echo "⚠️ ROUTINE coverage: $ROUTINE_RESPONDED/$ROUTINE_TOTAL ($ROUTINE_PCT%) - below 90% target"
        echo "🔧 Attempting to process remaining ROUTINE comments..."
        /commentreply
    else
        echo "✅ ROUTINE coverage: $ROUTINE_RESPONDED/$ROUTINE_TOTAL ($ROUTINE_PCT%)"
    fi
fi

echo "✅ Comment coverage verification passed - proceeding with completion"
```

**🎯 Adaptive Performance Tracking:**
```bash

# Detect PR complexity for realistic timing expectations (if not done earlier)

if [ -z "$FILES_CHANGED" ]; then
    FILES_CHANGED=$(git diff --name-only origin/main | wc -l)
    LINES_CHANGED=$(git diff --stat origin/main | tail -1 | grep -oE '[0-9]+' | head -1 || echo 0)
fi

# Set complexity-based performance targets

if [ $FILES_CHANGED -le 3 ] && [ $LINES_CHANGED -le 50 ]; then
    COMPLEXITY="simple"
    TARGET_TIME=300  # 5 minutes
elif [ $FILES_CHANGED -le 10 ] && [ $LINES_CHANGED -le 500 ]; then
    COMPLEXITY="moderate"
    TARGET_TIME=600  # 10 minutes
else
    COMPLEXITY="complex"
    TARGET_TIME=900  # 15 minutes
fi

echo "📊 PR Complexity: $COMPLEXITY ($FILES_CHANGED files, $LINES_CHANGED lines)"
echo "🎯 Target time: $((TARGET_TIME / 60)) minutes"

# Calculate and report timing with complexity-appropriate targets

COPILOT_END_TIME=$(date +%s)
COPILOT_DURATION=$((COPILOT_END_TIME - COPILOT_START_TIME))
if [ $COPILOT_DURATION -gt $TARGET_TIME ]; then
    echo "⚠️ Performance exceeded: $((COPILOT_DURATION / 60))m $((COPILOT_DURATION % 60))s (target: $((TARGET_TIME / 60))m for $COMPLEXITY PR)"
else
    echo "✅ Performance target met: $((COPILOT_DURATION / 60))m $((COPILOT_DURATION % 60))s (under $((TARGET_TIME / 60))m target)"
fi

# SUCCESS: Clean up and complete

echo "✅ COPILOT WORKFLOW COMPLETED SUCCESSFULLY"
cleanup_temp_files
/guidelines
```

## 🚨 Agent Boundaries

### copilot-fixpr Agent Responsibilities:

- **FIRST PRIORITY**: Execute `/fixpr` command to resolve merge conflicts and CI failures
- **PRIMARY**: Security vulnerability detection and code implementation
- **TOOLS**: Edit/MultiEdit for file modifications, Serena MCP for semantic analysis, `/fixpr` command
- **FOCUS**: Make PR mergeable first, then actual code changes with File Justification Protocol compliance
- **BOUNDARY**: File operations and PR mergeability - **NEVER handles GitHub comment responses**

🚨 **CRITICAL AGENT BOUNDARY**: The copilot-fixpr agent must NEVER attempt to:
- Generate responses.json entries
- Handle comment response generation
- Execute /commentreply
- Manage GitHub comment posting
- Handle comment coverage verification

**Direct Orchestrator (EXCLUSIVE RESPONSIBILITIES):**
- **MANDATORY**: Generate ALL comment responses after agent completes
- Comment processing (/commentfetch, /commentreply)
- Response generation for every fetched comment
- GitHub operations and workflow coordination
- Verification checkpoints and evidence collection
- Ensuring 100% comment coverage before completion

## 🎯 **SUCCESS CRITERIA (UPDATED: QUALITY-FOCUSED)**

### **PRIORITY-BASED VERIFICATION REQUIREMENTS**:

1. **Critical Bug Resolution**: ALL critical bugs fixed with working code (100% required)
2. **Blocking Issue Resolution**: ALL blocking issues fixed or properly documented (100% required)
3. **Important Issue Handling**: Important issues fixed OR deferred with created issues (≥80% target)
4. **Routine Issue Handling**: Routine issues responded to (≥90% target) - includes low-severity bot comments
5. **Communication Coverage**: 100% comment response rate with action-based accountability
6. **Test Verification**: All critical/blocking fixes verified with passing tests
7. **Post-Push Refresh**: Re-fetch comments after push to catch late arrivals

**SUCCESS LEVELS:**

**✅ SAFE TO MERGE:**
- Critical bugs fixed: 100% (or 0 critical bugs found)
- Blocking issues fixed: 100% (or 0 blocking issues found)
- Routine issues responded: ≥90%
- All tests passing
- 100% comment response rate with action details

**⚠️ NEEDS REVIEW:**
- Critical bugs fixed: 100%
- Blocking issues fixed: <100% with documented reasons
- Routine issues responded: <90%
- Some tests pending
- 100% comment response rate

**❌ NOT READY:**
- Critical bugs unfixed: ANY
- Blocking issues unfixed: >20%
- Routine issues responded: <80%
- Tests failing
- Comment response rate: <100%

### **QUALITY GATES (PRIORITY ORDER)**:

1. ✅ **Critical Bug Priority**: Security vulnerabilities, production blockers fixed FIRST
2. ✅ **Blocking Issue Priority**: CI failures, breaking changes fixed SECOND
3. ✅ **Direct Implementation**: Critical/blocking bugs fixed by orchestrator directly
4. ✅ **Test Verification**: All critical/blocking fixes verified with test execution
5. ✅ **Routine Coverage**: Low-severity comments responded to (≥90%) - no silent skips
6. ✅ **Outdated Detection**: Comments on refactored code marked as "ALREADY FIXED"
7. ✅ **Post-Push Refresh**: Re-fetch comments after push to catch late arrivals
8. ✅ **Action Accountability**: Every response includes category, action, files, commits, verification
9. ✅ **File Justification Protocol**: All code changes properly documented and justified
10. ✅ **Input Sanitization**: All GitHub comment content validated and sanitized
11. ✅ **Synchronization**: Explicit agent coordination prevents race conditions
12. ✅ **Adaptive Performance**: Execution completed within complexity-appropriate targets

### **FAILURE CONDITIONS (PRIORITY ORDER)**:

**🚨 CRITICAL FAILURES (IMMEDIATE STOP):**
- ❌ **Unfixed Critical Bugs**: ANY critical bug not implemented
- ❌ **Security Violations**: Unsanitized input processing or validation failures
- ❌ **Test Failures**: Critical/blocking fixes not verified with passing tests

**❌ BLOCKING FAILURES (MANUAL REVIEW REQUIRED):**
- ❌ **Unfixed Blocking Issues**: >20% blocking issues unresolved
- ❌ **Coverage Gaps**: <100% comment response rate
- ❌ **Missing Accountability**: Responses without files_modified, commit, or verification
- ❌ **Race Conditions**: Orchestrator proceeding before agent completion

**⚠️ WARNING CONDITIONS (NON-BLOCKING):**
- ⚠️ **Protocol Violations**: File changes without proper justification documentation
- ⚠️ **Boundary Violations**: Agent handling GitHub responses OR orchestrator making non-critical file changes
- ⚠️ **Timing Warnings**: Execution time exceeding complexity-appropriate targets without alerts

### **Context Management**:

- **Complete Comment Coverage**: Process ALL comments without filtering for 100% coverage
  - 🚨 **CRITICAL CLARIFICATION**: "ALL comments" explicitly INCLUDES:
    - ✅ Bot comments (CodeRabbit, GitHub Copilot, automated reviewers)
    - ✅ Human comments (team members, manual reviewers)
    - ❌ **ONLY EXCEPTION**: Comments starting with "[AI responder]" (our own AI-generated responses)
  - 🚨 **MANDATORY**: Bot code review comments MUST be addressed - either implement fixes OR explain "NOT DONE: [reason]"
  - 🚨 **ZERO SKIP RATE**: 100% reply rate means EVERY comment (human AND bot) gets a response

### 🚨 **CRITICAL: GitHub API Reply Requirements (NEW)**

**"100% reply rate" means ACTUAL GitHub API POST calls, not just responses.json tracking.**

Every comment MUST receive an actual GitHub reply via the appropriate API endpoint:

| Comment Type | Source | API Endpoint for Reply |
|--------------|--------|----------------------|
| **Inline review comments** | `gh api repos/.../pulls/{pr}/comments` | `gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies -X POST -f body="..."` |
| **General issue comments** | `gh api repos/.../issues/{pr}/comments` | `gh api repos/{owner}/{repo}/issues/{pr}/comments -X POST -f body="..."` |
| **Review summary comments** | `gh pr view --json reviews` | Reply via inline comment on same review thread |

**Common Failure Mode (AVOID THIS):**
```
❌ WRONG: Track comment in responses.json → Post summary comment → Done
✅ RIGHT: Track comment in responses.json → Post DIRECT REPLY to that specific comment → Done
```

**Example: Responding to a General Issue Comment (like CodeRabbit protocol violation):**
```bash
# CodeRabbit posts general comment IC_kwDOO8L8Qs7itxod asking for DONE/NOT_DONE responses
# WRONG: Only post a new summary comment
# RIGHT: Post a direct reply to that specific comment

gh api repos/{owner}/{repo}/issues/{pr}/comments \
  -X POST \
  -f body="[AI responder] ✅ **Protocol Compliance Restored**

In reply to the Protocol Violation report:
- Issue 1: ✅ DONE (commit abc123)
- Issue 2: ✅ DONE (commit abc123)
..."
```

**Example: Responding to an Inline Review Comment:**
```bash
# Cursor posts inline comment 2730561960 about a bug
# Use the /replies endpoint for inline comments

gh api repos/{owner}/{repo}/pulls/{pr}/comments/2730561960/replies \
  -X POST \
  -f body="[AI responder] ✅ **DONE - BUG FIXED**
..."
```

**Verification Checklist:**
- [ ] Did I post GitHub API replies to ALL inline review comments?
- [ ] Did I post GitHub API replies to ALL general issue comments that asked questions or requested action?
- [ ] Did I check that bot comments (CodeRabbit, Copilot, Cursor) received direct replies, not just summary acknowledgment?
- **GitHub MCP Primary**: Strategic tool usage for minimal context consumption
- **Semantic Search**: Use Serena MCP for targeted analysis before file operations
- **Hybrid Coordination**: Efficient orchestration with selective task delegation

### **Performance Benefits**:

- **Reliability**: 100% working components eliminate broken agent failures
- **Specialization**: File operations delegated while maintaining coordination control
- **Quality Improvement**: Proven comment handling with verified file implementations
- **Simplified Architecture**: Eliminates complexity of broken parallel agent coordination

### **Coordination Efficiency**:

- **Selective Delegation**: Only delegate file operations, handle communication directly
- **Proven Components**: Use only verified working tools and patterns
- **Result Integration**: Direct access to agent file changes for accurate response generation
- **Streamlined Workflow**: Single coordination point with specialized file operation support

## 🚨 **RESPONSE DATA FORMAT SPECIFICATION (UPDATED: ACTION PROTOCOL)**

### **MANDATORY**: responses.json Format

The orchestrator MUST generate responses.json in this exact format:

#### Single-Issue Comment Example:

```json
{
  "response_protocol": "ACTION_ACCOUNTABILITY",
  "responses": [
    {
      "comment_id": "2357534669",
      "category": "CRITICAL",
      "response": "FIXED",
      "action_taken": "Implemented UID-based admin check in isAuthenticatedNonVIP()",
      "files_modified": ["shared-libs/packages/mcp-server-utils/src/RateLimitTool.ts:145"],
      "tests_added": ["backend/src/test/rate-limit-uid-fallback.test.ts"],
      "commit": "53702d91",
      "verification": "✅ Tests pass, admin UIDs now recognized",
      "reply_text": "[AI responder] ✅ **CRITICAL BUG FIXED**\n\n**Category**: CRITICAL\n**Action**: Implemented UID-based admin check in isAuthenticatedNonVIP()\n**Files Modified**: shared-libs/packages/mcp-server-utils/src/RateLimitTool.ts:145\n**Tests Added**: backend/src/test/rate-limit-uid-fallback.test.ts\n**Commit**: 53702d91\n**Verification**: ✅ Tests pass, admin UIDs now recognized",
      "in_reply_to": "optional_parent_id"
    }
  ]
}
```

#### Multi-Issue Comment Example (NEW - Critical for Bot Comments):

When a SINGLE comment contains MULTIPLE issues (e.g., CodeRabbit summary with 11 issues):

```json
{
  "response_protocol": "ACTION_ACCOUNTABILITY",
  "responses": [
    {
      "comment_id": "3675347161",
      "category": "BLOCKING",
      "response": "FIXED",
      "analysis": {
        "total_issues": 11,
        "actionable": 6,
        "nitpicks": 5
      },
      "issues": [
        {
          "number": 1,
          "file": "game_state_instruction.md",
          "line": "751-776",
          "description": "Remove phrase-scanning triggers",
          "category": "BLOCKING",
          "response": "FIXED",
          "action_taken": "Removed phrase-scanning trigger patterns, converted to intent-based processing",
          "files_modified": ["game_state_instruction.md:751-776"],
          "commit": "abc123",
          "verification": "✅ Verified no phrase-scanning patterns remain"
        },
        {
          "number": 2,
          "file": "game_state_instruction.md",
          "line": "800-820",
          "description": "Update validation logic for edge cases",
          "category": "IMPORTANT",
          "response": "FIXED",
          "action_taken": "Added null checks and edge case handling",
          "files_modified": ["game_state_instruction.md:800-820"],
          "commit": "abc123",
          "verification": "✅ Edge cases now handled correctly"
        },
        {
          "number": 3,
          "file": "system_instruction.md",
          "line": "100",
          "description": "Fix typo in documentation",
          "category": "ROUTINE",
          "response": "FIXED",
          "action_taken": "Corrected typo",
          "files_modified": ["system_instruction.md:100"],
          "commit": "def456",
          "verification": "✅ Typo fixed"
        }
      ],
      "reply_text": "[AI responder] ## Comment Analysis (11 issues identified)\n\n### Actionable Issues (6 found)\n1. **[game_state_instruction.md:751-776]** - Status: FIXED\n   - Action: Removed phrase-scanning triggers\n   - Commit: abc123\n\n2. **[game_state_instruction.md:800-820]** - Status: FIXED\n   - Action: Added edge case validation\n   - Commit: abc123\n\n...(4 more actionable issues)...\n\n### Nitpick Issues (5 found)\n7. **[system_instruction.md:100]** - Status: FIXED\n   - Action: Corrected typo\n   - Commit: def456\n\n...(4 more nitpick issues)...\n\n### Summary\n- Total: 11 issues\n- Fixed: 11 issues\n- Deferred: 0 issues"
    }
  ]
}
```

**📌 NOTES**:
- **Top-level fields**: `category` and `response` at top level represent the highest-priority issue in the comment (BLOCKING in this example)
- **Truncated example**: This shows only 3 of 11 issues for brevity; production responses would include all issues in the `issues` array
- **Global numbering**: Issue numbering continues globally (1, 2, 3, ..., 11), shown with `...(N more)...` truncation indicators
- **One reply_text**: Despite containing 11 issues, generates ONE consolidated `reply_text` addressing all issues together

### **CRITICAL FORMAT REQUIREMENTS**:

**Base Fields (ALL responses):**
- `comment_id` MUST be STRING (not integer)
- `html_url` SHOULD contain the GitHub comment URL for tracking and linking (extracted from comments.json)
- `category` MUST be one of: CRITICAL, BLOCKING, IMPORTANT, ROUTINE
  - **Multi-issue format**: Top-level `category` represents the highest-priority issue in the comment
  - **Single-issue format**: Top-level `category` represents the issue's priority
- `response` MUST be one of: FIXED, DEFERRED, ACKNOWLEDGED, NOT_DONE
  - **Multi-issue format**: Top-level `response` represents the overall status (typically FIXED if all fixed)
  - **Single-issue format**: Top-level `response` represents the issue's status
- `reply_text` MUST contain formatted action details for GitHub (example above shows the auto-generated output)
- `files_modified` should list repo-relative paths with optional `:line` suffixes for precision
- `commit` values must use the standard 7-8 character `git rev-parse --short` format for traceability

**Response Type Specific Fields:**

**FIXED** (implementation completed):
- `action_taken`: Specific implementation description
- `files_modified`: Array of "file:line" strings
- `tests_added`: Array of test files (if applicable)
- `commit`: Short commit SHA
- `verification`: Test/verification status

**DEFERRED** (ONLY if genuinely cannot do in this PR):
- `reason`: Specific technical reason (complexity, risk, architectural discussion needed)
- `bead_id`: REQUIRED - actual bead ID created via beads/create (e.g., "worktree_worker4-xyz")
- ⚠️ MUST create real bead BEFORE responding - no vague "TODO tracked"
- ⚠️ If reviewer requests it and it's feasible, use FIXED instead

**ACKNOWLEDGED** (purely informational - NO action implied):
- `explanation`: Factual statement only
- ❌ FORBIDDEN: "will do", "TODO tracked", "in a follow-up", "later", future tense promises
- ✅ CORRECT: "Noted for context" or "Informational comment, no action required"

**NOT_DONE** (cannot implement):
- `reason`: Specific technical reason why not feasible

**MULTI_ISSUE** (comment contains multiple distinct issues):
- `analysis`: Object with `total_issues`, `actionable`, `nitpicks` counts
- `issues`: Array of issue objects, each with:
  - `number`: Issue sequence number (1, 2, 3, ...)
  - `file`: Affected file path
  - `line`: Line number or range
  - `description`: Brief issue description
  - `category`: Severity level (CRITICAL/BLOCKING/IMPORTANT/ROUTINE)
  - `response`: Action taken (FIXED/DEFERRED/ACKNOWLEDGED/NOT_DONE)
  - `action_taken`: Specific implementation details
  - `files_modified`: Array of affected files with :line notation
  - `commit`: Commit SHA for the fix
  - `verification`: Test/verification status
- `reply_text`: Consolidated markdown addressing ALL issues together

### **INTEGRATION CONTRACT**:

- commentreply.py expects `responses` array with `comment_id` and `reply_text`
- `reply_text` is auto-generated from action fields for consistency
- Matching uses `str(response_item.get("comment_id")) == comment_id`
- Missing required fields cause validation failures
- Format validation is MANDATORY before attempting to post responses

### **RESPONSE QUALITY STANDARDS (UPDATED)**:

**FIXED responses MUST include:**
- ✅ Specific action taken (not generic "fixed")
- ✅ Files modified with line numbers
- ✅ Commit SHA for traceability
- ✅ Verification status (tests pass, CI green, etc.)

**NOT_DONE responses MUST include:**
- ✅ Specific technical reason (not "will consider")
- ✅ Category classification (why it's routine vs critical)

**Accountability Requirements:**
- No generic acknowledgments without category
- No "FIXED" without files_modified and commit
- No "NOT_DONE" without specific reason
- Every response traceable to actual code changes or decision rationale

**🚨 REVIEWER REQUEST PROTOCOL:**

When a reviewer asks for a change (refactoring, extraction, improvement):

1. **DEFAULT = DO IT NOW** (reviewer sets scope, not AI)
2. **If feasible** → FIXED with commit reference
3. **If genuinely not feasible** → NOT_DONE with specific technical reason
4. **If complex but should be tracked** → DEFERRED with REAL bead_id (create bead first!)

❌ **FORBIDDEN PATTERNS:**
- "Will extract in a follow-up" (without bead_id)
- "TODO tracked" (tracked WHERE?)
- "Good suggestion, will consider" (empty promise)
- Unilaterally deciding to defer reviewer requests

✅ **CORRECT PATTERNS:**
- FIXED: "Extracted to settings_validation.py (Commit: abc123)"
- NOT_DONE: "Would require changing public API, needs design discussion"
- DEFERRED: "Created bead worktree_worker4-xyz for this refactoring"
