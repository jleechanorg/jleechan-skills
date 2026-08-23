---
description: /copilot-lite - Streamlined PR Processing
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🎯 MISSION

Atomic single-pass PR comment processor with ground truth verification.

**SCOPE**: ONLY fixes GitHub PR comments. Does NOT:
- ❌ Fix merge conflicts (use `/fixpr` separately)
- ❌ Fix failing tests (handle separately)
- ❌ Handle CI failures (not in scope)

**Key Principle**: Ground truth over inference - try the fix, report what actually happened.

**Architecture**:
- **Claude (LLM)**: Analyzes comments, attempts fixes, generates truthful responses
- **Python**: ONLY manages state and API calls (NO hardcoded responses)
- **Threading**: Proper GitHub threading via `in_reply_to` parameter

## 🚨 EXECUTION WORKFLOW

### Phase 1: Environment Setup

**Action Steps:**
```bash
# Get PR context
BRANCH_NAME=$(git branch --show-current)
export BRANCH_NAME  # Export for Python subprocess
SAFE_BRANCH=$(python3 - <<'PY'
import os, re
branch = os.environ.get("BRANCH_NAME", "")
safe = re.sub(r"[^a-zA-Z0-9._-]", "_", branch)
safe = re.sub(r"^[.-]+", "", safe)
print(safe or "unknown-branch")
PY
)
WORK_DIR="/tmp/$SAFE_BRANCH"
mkdir -p "$WORK_DIR"

# Detect PR number
PR_NUMBER=$(gh pr view --json number -q '.number' 2>/dev/null || echo "")
if [ -z "$PR_NUMBER" ]; then
    echo "❌ ERROR: No PR found for current branch"
    exit 1
fi

REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner')
echo "🎯 Processing PR #$PR_NUMBER on $REPO (branch: $BRANCH_NAME)"
```

### Phase 2: Fetch ALL Comments

**Action Steps:**
Execute `/commentfetch` OR run directly:
```bash
# Fetch all comments from all sources (human + bot)
# Set pipefail so pipeline fails if commentfetch.py fails (not just tee)
set -o pipefail
python3 .claude/commands/_copilot_modules/commentfetch.py "$PR_NUMBER" 2>/dev/null | tee "$WORK_DIR/comments.json" >/dev/null || {
    # Fallback: fetch and combine comments manually, adding .type field to match commentfetch.py output
    gh api "repos/$REPO/pulls/$PR_NUMBER/comments" --paginate | jq '[.[] | . + {type: "inline"}]' > "$WORK_DIR/inline_comments.json"
    gh api "repos/$REPO/issues/$PR_NUMBER/comments" --paginate | jq '[.[] | . + {type: "issue"}]' > "$WORK_DIR/issue_comments.json"
    # Combine into single comments.json file with {comments: [...]} structure to match commentfetch.py output
    jq -s '{comments: (.[0] + .[1])}' "$WORK_DIR/inline_comments.json" "$WORK_DIR/issue_comments.json" > "$WORK_DIR/comments.json"
}

# Verify comments.json was created (either by commentfetch.py or fallback)
if [ ! -f "$WORK_DIR/comments.json" ]; then
    echo "❌ ERROR: Comments fetch failed. $WORK_DIR/comments.json not created." && exit 1
fi

echo "📥 Comments fetched to $WORK_DIR/comments.json"
```

**Important**: This fetches ALL comments including:
- Human reviewer comments
- Bot comments (Codex, GitHub bots, etc.)
- Inline review comments
- General PR conversation comments

### Phase 3: Atomic Comment Processing (CORE - LLM RESPONSIBILITY)

**🚨 CRITICAL: Claude (LLM) MUST process each top-level comment atomically:**

For EACH **top-level (non-reply)** comment in `/tmp/{branch}/comments.json` (including bot comments):

1. **READ** the comment body and understand what is being requested
   - **Bot comments** requesting code changes should be treated like human comments
   - **Bot status updates** (e.g., "CI passed", "Merge conflict detected") should be SKIPPED

2. **CATEGORIZE** the comment request:
   - `CRITICAL`: Security vulnerabilities, production blockers, data corruption in PR code
   - `IMPORTANT`: Performance issues, logic errors, missing validation in PR code
   - `ROUTINE`: Code style, documentation, optional refactoring suggestions
   - **SKIP**: Bot status updates, merge conflicts, test failures, or CI issues (not in scope)
     - Examples to SKIP: "Merge conflict detected", "Tests failed", "CI check pending"
     - Examples to PROCESS: "@codex please fix this bug", "Bot: This function has a security issue"
   - **Replies**: If a comment has `in_reply_to_id` (i.e., it is a reply), SKIP generating a response entry for it in `responses.json`; only top-level comments require responses for coverage accounting

3. **ATTEMPT** the fix (if applicable):
   - Read the affected file(s)
   - Make the code change using Edit/MultiEdit tools
   - Verify syntax is correct
   - Commit the change with descriptive message
   - **NOTE**: Do NOT fix tests or merge conflicts - only address the specific comment request
     - If the comment is about merge conflicts, failing tests, or CI status, categorize it as **SKIP** in Step 2 and respond with a `SKIPPED` entry (no ATTEMPT changes)

4. **GENERATE** a truthful response based on ACTUAL outcome:

**Response Types**:
- **FIXED**: Successfully implemented the change
  - MUST include: commit hash, files modified, verification status
- **NOT DONE**: Could not implement (with REAL reason from actual attempt)
  - MUST include: specific error or constraint that prevented implementation
- **ACKNOWLEDGED**: Style suggestion noted for future consideration
- **ALREADY IMPLEMENTED**: Code already does this (MUST show evidence)
  - MUST include: file path, line number, code snippet proving implementation
- **SKIPPED**: Comment is about merge conflicts, test failures, CI issues, or bot status updates (out of scope)
  - MUST include: brief note directing to appropriate command (/fixpr for merge conflicts)
  - Examples: Bot status updates like "Merge conflict detected", "CI pending"
  - **NOTE**: Bot comments requesting actual code changes should NOT be skipped - treat them like human comments

**MANDATORY for ALL response types**: Include `tracking_reason` field - a 2-3 sentence justification explaining WHY this response type was chosen and WHAT was done/decided. This appears in the PR description's comment tracking table.

### Phase 4: Build responses.json

**🚨 Claude MUST write responses to `/tmp/{branch}/responses.json`:**

```json
{
  "response_protocol": "ACTION_ACCOUNTABILITY",
  "responses": [
    {
      "comment_id": "2357534669",
      "category": "CRITICAL",
      "response": "FIXED",
      "action_taken": "Removed strict=True from zip() for Python 3.8 compatibility",
      "files_modified": ["testing_integration/test_file.py:171"],
      "commit": "946958873",
      "verification": "✅ Tests pass, Python 3.8+ compatible",
      "tracking_reason": "Removed strict=True parameter from zip() call to restore Python 3.8 compatibility. The strict parameter was added in Python 3.10 and breaks CI on older runtimes. Tests pass on both 3.8 and 3.11.",
      "reply_text": "[AI responder] ✅ **FIXED**\n\n**Category**: CRITICAL\n**Action**: Removed strict=True from zip() for Python 3.8 compatibility\n**Files**: testing_integration/test_file.py:171\n**Commit**: 946958873\n**Verification**: ✅ Tests pass",
      "in_reply_to": null
    },
    {
      "comment_id": "2357534670",
      "category": "BLOCKING",
      "response": "NOT_DONE",
      "reason": "cast() is required for mypy type inference - removing it causes 'object has no attribute append' error",
      "tracking_reason": "Attempted to remove cast() as requested but mypy type inference fails without it. The cast() call is necessary because mypy cannot infer the append attribute on the base object type. Needs upstream type stub fix first.",
      "reply_text": "[AI responder] ❌ **NOT DONE**\n\n**Category**: BLOCKING\n**Reason**: cast() is required for mypy type inference. Attempted removal, but mypy fails with: 'object has no attribute append'\n**Evidence**: Ran `mypy src/file.py` - exit code 1",
      "in_reply_to": null
    },
    {
      "comment_id": "2357534671",
      "category": "ROUTINE",
      "response": "ACKNOWLEDGED",
      "explanation": "Good suggestion for code clarity, will apply in next refactoring cycle",
      "tracking_reason": "Style suggestion for improving variable naming clarity. Current naming follows existing codebase convention and changing it would require a broader refactoring effort beyond this PR's scope.",
      "reply_text": "[AI responder] 📝 **ACKNOWLEDGED**\n\n**Category**: ROUTINE\n**Note**: Good suggestion for code clarity. Noting for future refactoring.",
      "in_reply_to": null
    },
    {
      "comment_id": "2357534672",
      "category": "IMPORTANT",
      "response": "ALREADY_IMPLEMENTED",
      "evidence": {
        "file": "src/utils.py",
        "line": 45,
        "code": "branch_name = branch_name.replace('/', '_').replace('\\\\', '_')"
      },
      "tracking_reason": "Branch sanitization already exists at src/utils.py:45 using replace() for path separators. The existing implementation covers the requested functionality with both forward and backslash handling.",
      "reply_text": "[AI responder] ✅ **ALREADY IMPLEMENTED**\n\n**Category**: IMPORTANT\n**Evidence**: Branch sanitization exists at src/utils.py:45\n```python\nbranch_name = branch_name.replace('/', '_').replace('\\\\', '_')\n```\n**Verified**: Actual code shows path-safe character replacement",
      "in_reply_to": null
    },
    {
      "comment_id": "2357534673",
      "comment_author": "codex-bot",
      "category": "IMPORTANT",
      "response": "FIXED",
      "action_taken": "Added null check before accessing user.name property",
      "files_modified": ["src/auth.py:45"],
      "commit": "abc123def",
      "verification": "✅ Syntax valid, null pointer exception prevented",
      "tracking_reason": "Added null check before accessing user.name property as flagged by codex-bot. The missing guard caused NullPointerException when unauthenticated users hit the endpoint. Fix verified with syntax check.",
      "reply_text": "[AI responder] ✅ **FIXED**\n\n**Category**: IMPORTANT\n**Action**: Added null check before accessing user.name property (from @codex-bot comment)\n**Files**: src/auth.py:45\n**Commit**: abc123def\n**Verification**: ✅ Syntax valid, null pointer exception prevented",
      "in_reply_to": null
    },
    {
      "comment_id": "2357534674",
      "comment_author": "github-actions[bot]",
      "category": "SKIP",
      "response": "SKIPPED",
      "reason": "Bot status update about merge conflicts - use /fixpr command",
      "tracking_reason": "Automated bot notification about merge conflict status. Not actionable by /copilot-lite - merge conflicts should be resolved using /fixpr command separately.",
      "reply_text": "[AI responder] ⏭️ **SKIPPED**\n\n**Reason**: This is a bot status update about merge conflicts, which is out of scope for /copilot-lite.\n**Action**: Please run `/fixpr` to resolve merge conflicts separately.",
      "in_reply_to": null
    }
  ]
}
```

#### Phase 4.5: MANDATORY VERIFICATION GATE (HARD REQUIREMENT)

**🚨 CRITICAL: You CANNOT proceed to Phase 5 until this gate passes.**

**Action Steps:**
```bash
# Working directory + PR metadata (exported in Phase 1)
# Reuse BRANCH_NAME, SAFE_BRANCH, WORK_DIR, REPO, PR_NUMBER from Phase 1 (do NOT recalculate)

# Validate prerequisites
if [ ! -f "$WORK_DIR/comments.json" ]; then
    echo "🛑 ERROR: $WORK_DIR/comments.json not found."
    echo "➡️  Please complete Phases 1-2 before running this step."
    exit 1
fi

# Count all top-level inline review comments (comments on code, not replies)
# Note: commentfetch.py outputs {comments: [...]} with .type field ("inline", "general", "review", "copilot")
TOTAL_INLINE=$(jq '[ (.comments // .)[] | select((.type == "inline") and ((.in_reply_to_id // null) == null)) ] | length' "$WORK_DIR/comments.json")

# Count ALL top-level non-inline comments (PR conversation, reviews, copilot), excluding replies
TOTAL_ISSUE=$(jq '[ (.comments // .)[] | select((.type != "inline") and ((.in_reply_to_id // null) == null)) ] | length' "$WORK_DIR/comments.json")

TOTAL=$((TOTAL_INLINE + TOTAL_ISSUE))
if ! [[ "$TOTAL" =~ ^[0-9]+$ ]]; then
    echo "❌ ERROR: Unable to compute TOTAL from $WORK_DIR/comments.json" && exit 1
fi
echo "📊 Total top-level comments requiring response: $TOTAL"

# Count comments addressed in responses.json
if [ ! -f "$WORK_DIR/responses.json" ]; then
    echo "🛑 ERROR: $WORK_DIR/responses.json not found."
    echo "➡️  Please complete Phase 4 before running this step."
    exit 1
fi

ADDRESSED=$(jq '.responses | length' "$WORK_DIR/responses.json")
if ! [[ "$ADDRESSED" =~ ^[0-9]+$ ]]; then
    echo "❌ ERROR: Unable to compute ADDRESSED from $WORK_DIR/responses.json" && exit 1
fi
echo "📋 Comments addressed in responses.json (including SKIPPED entries): $ADDRESSED"

# HARD GATE: Assert 100% coverage
if [ "$ADDRESSED" -ne "$TOTAL" ]; then
    echo "❌ VERIFICATION FAILED: $ADDRESSED / $TOTAL comments addressed"
    echo "⚠️ MISSING: $((TOTAL - ADDRESSED)) comments without responses"
    echo ""
    echo "🔍 Identifying missing comment IDs..."
    # List all comment IDs from fetched comments (top-level only)
    jq -r '(.comments // .)[] | select(((.in_reply_to_id // null) == null)) | .id | tostring' "$WORK_DIR/comments.json" > "$WORK_DIR/all_comment_ids.txt"
    # List addressed comment IDs (normalize to strings)
    jq -r '.responses[].comment_id | tostring' "$WORK_DIR/responses.json" > "$WORK_DIR/addressed_ids.txt"
    # Find missing
    echo "📌 Missing comment IDs (must address before proceeding):"
    comm -23 <(sort -n "$WORK_DIR/all_comment_ids.txt") <(sort -n "$WORK_DIR/addressed_ids.txt")
    echo ""
    echo "🛑 STOP: Return to Phase 3 and address missing comments"
    # DO NOT PROCEED - loop back to Phase 3
    exit 1
fi

# SUCCESS: Gate passed
echo "✅ VERIFICATION PASSED: $ADDRESSED / $TOTAL (100% coverage)"
echo "➡️ Proceeding to Phase 5..."
rm -f "$WORK_DIR/all_comment_ids.txt" "$WORK_DIR/addressed_ids.txt" 2>/dev/null || true
```

**Gate Rules:**
1. **TOTAL** = All top-level comments (inline + issue) that are NOT replies (SKIPPED comments still count toward this total)
2. **ADDRESSED** = Number of entries in responses.json (including SKIPPED entries)
3. **PASS** = ADDRESSED == TOTAL
4. **FAIL** = Any mismatch → identify missing IDs → return to Phase 3

**If Gate Fails:**
- List all missing comment IDs
- Return to Phase 3 and process each missing comment
- Re-run Phase 4.5 verification
- Repeat until 100% coverage achieved

### Phase 5: Post Responses with Threading

**Action Steps:**
```bash
# Get repo info
OWNER=$(gh repo view --json owner -q '.owner.login')
REPO_NAME=$(gh repo view --json name -q '.name')
PR_NUMBER=$(gh pr view --json number -q '.number')

# Post all responses with proper threading
python3 .claude/commands/commentreply.py "$OWNER" "$REPO_NAME" "$PR_NUMBER"
```

**Threading Contract**:
- `in_reply_to` field enables GitHub's native threading
- Review comments (inline): Uses `POST /repos/{owner}/{repo}/pulls/{pull}/comments` with `in_reply_to`
- Issue comments (general): Uses `POST /repos/{owner}/{repo}/issues/{pull}/comments` with reference link

### Phase 6: Verification

**Action Steps:**
Execute `/commentcheck` to verify 100% comment coverage:
```bash
/commentcheck
```

**Success Criteria**:
- ✅ Every comment has a response in responses.json
- ✅ Every response was successfully posted to GitHub
- ✅ All FIXED responses have valid commit hashes
- ✅ All NOT_DONE responses have real failure reasons

### Phase 7: Push & Summary

**Action Steps:**
```bash
# Push all committed fixes
git push origin HEAD

# Generate summary
echo "📊 COPILOT-LITE SUMMARY:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
jq -r '.responses | group_by(.response) | .[] | "\(.[0].response): \(length)"' "$WORK_DIR/responses.json"
```

## 🚨 CRITICAL RULES

### Rule 1: Ground Truth Verification
```python
# ❌ WRONG (inference without verification)
if comment.suggests("sanitize branch name"):
    response = "ALREADY IMPLEMENTED - .strip() handles this"
    # ^ FALSE! .strip() removes whitespace, NOT path separators

# ✅ RIGHT (actual code verification)
code = read_file("src/utils.py")
if ".replace('/', '_')" in code:
    response = f"ALREADY IMPLEMENTED - See src/utils.py:{line_number}"
    # Show actual code snippet as proof
else:
    # Not implemented - attempt to fix it
    result = attempt_fix(comment)
```

### Rule 2: Try Before Claiming NOT_DONE
```python
# ❌ WRONG (assumption without attempt)
return "NOT DONE: This would require significant refactoring"
# ^ Made up reason without trying

# ✅ RIGHT (real attempt with real outcome)
try:
    apply_fix()
    run_tests()
    commit()
    return f"FIXED: {commit_hash}"
except Exception as e:
    return f"NOT DONE: {str(e)}"
# ^ Actual reason from actual attempt
```

### Rule 3: No False Implementation Claims
```python
# ❌ WRONG (confusing similar operations)
# Comment: "Sanitize branch name for file system"
# Code has: result.stdout.strip()
response = "ALREADY IMPLEMENTED - branch is sanitized"
# ^ .strip() removes whitespace, NOT slashes!

# ✅ RIGHT (verify exact behavior)
# Look for: .replace('/', '_') or similar
# Only claim implemented if actual sanitization exists
```

### Rule 4: Every Comment Gets Response (Human + Bot)
- **FIXED**: Change was made and verified
- **NOT_DONE**: Attempted but failed (include real reason)
- **ACKNOWLEDGED**: Style suggestion, noted
- **ALREADY_IMPLEMENTED**: Code already does this (with evidence)
- **SKIPPED**: Bot status updates, merge conflicts, test failures, or CI (out of scope)

**Bot Comment Handling:**
- Bot comments requesting code changes → Process like human comments (FIXED/NOT_DONE/etc.)
- Bot status updates (CI, merge conflicts) → SKIPPED

**NO COMMENT LEFT BEHIND** - 100% response rate is mandatory (human + bot).

## 📊 Response Categories

| Response | When to Use | Required Fields |
|----------|-------------|-----------------|
| `FIXED` | Successfully implemented change (human or bot comment) | `action_taken`, `files_modified`, `commit`, `verification`, `tracking_reason` |
| `NOT_DONE` | Attempted but couldn't implement (human or bot comment) | `reason` (from actual failure), `tracking_reason` |
| `ACKNOWLEDGED` | Style/non-blocking suggestion (human or bot comment) | `explanation`, `tracking_reason` |
| `ALREADY_IMPLEMENTED` | Code already has this feature (human or bot comment) | `evidence` (file, line, code snippet), `tracking_reason` |
| `SKIPPED` | Bot status updates, merge conflicts, tests, or CI | `reason` (brief explanation + command to use), `tracking_reason` |

## 🔧 Integration with Existing Commands

This command composes with:
- `/commentfetch` - Fetches all PR comments
- `/commentreply` - Posts responses with proper threading
- `/commentcheck` - Verifies 100% coverage
- `/pushl` - For pushing changes

**NOT included** (handle separately):
- `/fixpr` - Use separately for merge conflict resolution
- Test fixing - Handle via separate test commands
- CI troubleshooting - Handle via separate debugging

## ✅ SUCCESS CRITERIA

### Accuracy Requirements (MANDATORY)
- [ ] No miscategorizations (ACKNOWLEDGED when should be FIXED)
- [ ] No false implementation claims
- [ ] Every "ALREADY IMPLEMENTED" includes code evidence
- [ ] Every "FIXED" includes commit hash and verification
- [ ] Every "NOT DONE" includes real failure reason from actual attempt
- [ ] Every "SKIPPED" correctly identifies out-of-scope comments (merge conflicts, tests, CI)

### Coverage Requirements (MANDATORY)
- [ ] 100% comment response rate (human + bot comments)
- [ ] All responses posted with proper threading
- [ ] No comments skipped without explicit reason

### Quality Requirements
- [ ] All FIXED changes pass tests
- [ ] All commit messages reference the comment being addressed
- [ ] Response text clearly explains what was done or why not

## 📝 Usage

```bash
# Run the command
/copilot-lite

# Or use alias
/copilotl
```

**What happens:**
1. Fetches ALL PR comments (human + bot)
2. For EACH comment: attempts fix → verifies → generates truthful response (with `tracking_reason`)
3. Posts ALL responses with proper threading
4. Verifies 100% coverage
5. Updates PR description with comment tracking table (fixed/deferred/ignored/unresolved with reasons)
6. Pushes all committed fixes

**What this does NOT handle:**
- ❌ Merge conflicts (use `/fixpr`)
- ❌ Test failures (handle separately)
- ❌ CI issues (debug separately)

**Key Difference from /copilot:**
- `/copilot`: Multi-phase (Phase 0-3), can lose state between phases
- `/copilot-lite`: Single-pass atomic, each comment fully processed before moving to next
- `/copilot-lite`: ONLY fixes code comments, not merge conflicts or tests

## 🚨 Autonomous Operation

This command operates autonomously without user approval prompts for:
- ✅ Code analysis and fixes
- ✅ Response generation
- ✅ Comment posting
- ✅ Push operations

**EXCEPTION**: Merge operations ALWAYS require explicit user approval ("MERGE APPROVED").
