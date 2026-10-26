---
description: /commentcheck Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Step 1: Load ALL Individual Comments (ORCHESTRATED)

**Action Steps:**
🚨 **MANDATORY**: Use `/commentfetch` for comprehensive comment data instead of duplicating API calls:

```bash

### Phase 2: Step 2: Individual Comment Threading Verification (JSON-BASED)

**Action Steps:**
🚨 **MANDATORY**: Use commentfetch JSON data for threading analysis instead of duplicate API calls:

```bash

### Phase 3: Step 3: Quality Assessment & Fake Comment Detection (JSON-BASED)

**Action Steps:**
🚨 **CRITICAL**: Use commentfetch data for response quality analysis instead of duplicate API calls:

```bash
echo "=== QUALITY ASSESSMENT & FAKE COMMENT DETECTION (JSON-BASED) ==="

### Phase 4: Step 4: Final Coverage Report (COMPREHENSIVE)

**Action Steps:**
🚨 **CRITICAL**: Generate final coverage report using commentfetch comprehensive data:

```bash
echo "=================================================================="
echo "🚨 COMPREHENSIVE COMMENT COVERAGE REPORT (COMMENTFETCH-BASED)"
echo "=================================================================="

### Phase 5: Integration with Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 6: Actions on Failure

**Action Steps:**
If `/commentcheck` finds issues:
1. **Report specific problems** - List missing/poor responses
2. **Suggest fixes** - Indicate what needs improvement
3. If the current request explicitly asks for replies or complete response coverage, continue the requested `/commentreply` work for in-scope comments and report any exact blocker; task-specific reply coverage is complete only when addressed or explicitly blocked.
4. Do not turn unanswered advisory bot comments into a push, readiness, or merge gate. The explicit reply task's completion scope is separate from PR lifecycle eligibility.

## 📋 REFERENCE DOCUMENTATION

# /commentcheck Command

**Usage**: `/commentcheck [PR_NUMBER] [--verify-urls]`

Report comment coverage and response quality after review. Do not make zero unanswered comments a push, readiness, or merge gate.

Automated reviewer comments are advisory. Report human feedback according to the current PR lifecycle. An unanswered comment alone does not create a gate.

🔒 **Security**: Uses safe jq --arg parameter passing to prevent command injection vulnerabilities and explicit variable validation.

## Universal Composition Integration

**Enhanced with /execute**: `/commentcheck` benefits from universal composition when called through `/execute`, which automatically provides intelligent optimization for large-scale comment verification while preserving systematic coverage analysis.

## 🎯 INDIVIDUAL COMMENT VERIFICATION MANDATE

Review comments against the PR lifecycle and current task scope:
- Human feedback should be recorded and handled when it is required for the requested outcome.
- CodeRabbit, Bugbot, and other automated reviewer comments are advisory, not merge or push gates.
- Our own `[AI responder]` comments are not new findings.
- **Simple counting** - Count comments NOT starting with '[AI responder]'
- **Warning system** - Report unanswered comments without inferring a gate
- **No complex classification** - No bot detection
- **Evidence requirement** - List any comments needing response by ID
- **No zero-comment gate** - An unanswered comment alone does not block push or merge eligibility.
- **Direct reply verification** - Verify a reply only when the current user request explicitly asks to send one.

## Description

Pure markdown command (no Python executable) that reports PR comment and response coverage. When the current request explicitly asks for reply processing, it verifies that task's requested scope after `/commentreply`; it does not require responses to every comment or create a PR lifecycle gate. **ORCHESTRATES /commentfetch for data source** instead of duplicating GitHub API calls.

## COPILOT INTEGRATION

### Reporting (no new lifecycle gate):

- **EXIT CODE 1**: Reserved for a required lifecycle gate only when the authoritative owner defines one
- **EXIT CODE 2**: Comment data unavailable; report the failure. This status alone does not create a push or merge gate.
- **EXIT CODE 0**: Comment count alone is not a failure

### COPILOT INTEGRATION PROTOCOL:

- **PRE-PUSH GATE**: This command is advisory triage; it does not create a new push gate.
- **HARD STOP ENFORCEMENT**: Stop only for a required lifecycle gate, never solely for optional bot feedback.
- **COVERAGE THRESHOLD**: Do not require zero unaddressed comments; report their source and lifecycle status.

## What It Does

1. **Orchestrates /commentfetch** for comprehensive comment data (eliminates duplicate API calls)
2. **Analyzes JSON output** from commentfetch for coverage verification
3. **Cross-references** original comments with posted responses using structured data
4. **Reports coverage** - identifies which comments have responses; complete response coverage is required only when explicitly requested for the current task
5. **Quality check** - confirms responses are substantial, not generic
6. **Reports status** with detailed breakdown using commentfetch metadata

## Individual Comment Verification Process (ORCHESTRATED)

# 1. Get PR number and validate

PR_NUMBER=${1:-$(gh pr view --json number --jq .number)}
if [ -z "$PR_NUMBER" ]; then
  echo "ℹ️ COMMENT DATA UNAVAILABLE: Could not determine PR number."
  echo "EXIT CODE: 2 (UNAVAILABLE - consult canonical lifecycle gates separately)"
  exit 2
fi

echo "🚀 ORCHESTRATING: Fetching comprehensive comment data via /commentfetch..."
echo "🔍 COMPREHENSIVE COMMENT ANALYSIS FOR PR #$PR_NUMBER"
echo "=================================================================="

# 2. Execute commentfetch Python implementation for comprehensive multi-API comment fetching

cd .claude/commands && python3 -c "
import _copilot_modules.commentfetch as cf
import sys
fetch = cf.CommentFetch(sys.argv[1])
fetch.execute()
" "$PR_NUMBER"

# 3. Use structured JSON output from commentfetch

BRANCH_NAME=$(git branch --show-current | tr -cd '[:alnum:]._-')
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)" | tr -cd '[:alnum:]._-')
# Use copilot subdirectory for all copilot workflow files
COPILOT_DIR="/tmp/$REPO_NAME/$BRANCH_NAME/copilot"
COMMENTS_FILE="$COPILOT_DIR/comments.json"
# REV-qcu3t-counting: Also read responses.json for standardized counts
RESPONSES_FILE="$COPILOT_DIR/responses.json"

if [ ! -f "$COMMENTS_FILE" ]; then
  echo "ℹ️ COMMENT DATA UNAVAILABLE: commentfetch did not provide structured data at $COMMENTS_FILE" >&2
  echo "This indicates commentfetch execution failure or missing output file." >&2
  echo "EXIT CODE: 2 (UNAVAILABLE - consult canonical lifecycle gates separately)" >&2
  exit 2
fi

echo "✅ DATA SOURCE: Using commentfetch structured output from $COMMENTS_FILE"

# REV-qcu3t-counting: Read responses.json for standardized count stages
if [ -f "$RESPONSES_FILE" ]; then
  echo "✅ STANDARDIZED COUNTS: Using responses.json for metrics (single source of truth)"

  # Compute metrics from responses.json (matches compute_metrics/get_all_issues in commentreply.py)
  # Handles both single-issue (.response on entry) and multi-issue (.issues[] array) formats
  TOTAL_ISSUES=$(jq '[.responses[] | if (.issues and .analysis) then .issues[] else . end] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")
  FIXED_COUNT=$(jq '[.responses[] | if (.issues and .analysis) then .issues[] else . end | select(.response == "FIXED" or .response == "ALREADY_IMPLEMENTED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")
  ACKNOWLEDGED_COUNT=$(jq '[.responses[] | if (.issues and .analysis) then .issues[] else . end | select((.response // "") as $r | $r == "ACKNOWLEDGED" or $r == "SKIPPED" or ($r != "FIXED" and $r != "ALREADY_IMPLEMENTED" and $r != "DEFERRED" and $r != "NOT_DONE"))] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")
  DEFERRED_COUNT=$(jq '[.responses[] | if (.issues and .analysis) then .issues[] else . end | select(.response == "DEFERRED")] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")
  NOT_DONE_COUNT=$(jq '[.responses[] | if (.issues and .analysis) then .issues[] else . end | select(.response == "NOT_DONE")] | length' "$RESPONSES_FILE" 2>/dev/null || echo "0")

  echo "📊 STANDARDIZED METRICS (from responses.json):"
  echo "   Total issues: $TOTAL_ISSUES"
  echo "   Fixed: $FIXED_COUNT"
  echo "   Acknowledged: $ACKNOWLEDGED_COUNT"
  echo "   Deferred: $DEFERRED_COUNT"
  echo "   Not Done: $NOT_DONE_COUNT"
else
  echo "⚠️ WARNING: responses.json not found - cannot compute standardized metrics"
fi

# 4. Extract comprehensive comment statistics from commentfetch JSON

TOTAL_COMMENTS=$(jq '.metadata.total' "$COMMENTS_FILE" 2>/dev/null || echo "0")
UNRESPONDED_COUNT=$(jq '.metadata.unresponded_count' "$COMMENTS_FILE" 2>/dev/null || echo "0")
INLINE_COUNT=$(jq '.metadata.by_type.inline' "$COMMENTS_FILE" 2>/dev/null || echo "0")
GENERAL_COUNT=$(jq '.metadata.by_type.general' "$COMMENTS_FILE" 2>/dev/null || echo "0")
REVIEW_COUNT=$(jq '.metadata.by_type.review' "$COMMENTS_FILE" 2>/dev/null || echo "0")
COPILOT_COUNT=$(jq '.metadata.by_type.copilot' "$COMMENTS_FILE" 2>/dev/null || echo "0")

echo "📊 COMPREHENSIVE COMMENT BREAKDOWN (via commentfetch):"
echo "   Total comments detected: $TOTAL_COMMENTS"
echo "   Inline review comments: $INLINE_COUNT"
echo "   General PR comments: $GENERAL_COUNT"
echo "   Review summary comments: $REVIEW_COUNT"
echo "   Copilot comments: $COPILOT_COUNT"
echo "   Unresponded comments: $UNRESPONDED_COUNT"

# 5. Validate commentfetch data quality

if [ "$TOTAL_COMMENTS" -eq 0 ]; then
  echo "⚠️ WARNING: No comments detected by commentfetch"
  echo "This may indicate API access issues or an empty PR"
fi

echo "🎯 COMMENTFETCH ORCHESTRATION: Successfully loaded $TOTAL_COMMENTS comments"
echo "📈 UNRESPONDED ANALYSIS: $UNRESPONDED_COUNT comments require attention"
```

# Enhanced threading verification using commentfetch structured data

echo "=== THREADING VERIFICATION ANALYSIS (JSON-BASED) ==="

# Use commentfetch JSON output instead of making new API calls

ALL_COMMENTS=$(jq '.comments' "$COMMENTS_FILE" 2>/dev/null || echo '[]')
if [ "$(echo "$ALL_COMMENTS" | jq length)" -eq 0 ]; then
  echo "ℹ️ COMMENT DATA UNAVAILABLE: No comments were returned by commentfetch" >&2
  echo "EXIT CODE: 2 (UNAVAILABLE - consult canonical lifecycle gates separately)" >&2
  exit 2
fi

echo "✅ USING COMMENTFETCH DATA: $(echo "$ALL_COMMENTS" | jq length) comments loaded"

# Step 2A: Analyze threading status for ALL comments (from commentfetch data)

echo "📊 THREADING STATUS ANALYSIS:"
echo "$ALL_COMMENTS" | jq -r '.[] | "ID: \(.id) | Author: \(.author) | Type: \(.type) | Replied: \(.already_replied)"'

# Step 2B: Count threading success rates (using commentfetch metadata)

TOTAL_COMMENTS=$(echo "$ALL_COMMENTS" | jq length)
REQUIRES_RESPONSE=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.requires_response == true)] | length')
REPLIED_REQUIRED=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.requires_response == true and .already_replied == true)] | length')
OUTSTANDING_REQUIRED=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.requires_response == true and .already_replied != true)] | length')

echo ""
echo "📈 THREADING STATISTICS (from commentfetch):"
echo "   Total comments: $TOTAL_COMMENTS"
echo "   Requested/required response scope: $REQUIRES_RESPONSE"
echo "   Replied within scope: $REPLIED_REQUIRED"
echo "   Outstanding within scope: $OUTSTANDING_REQUIRED"

if [ "$REQUIRES_RESPONSE" -gt 0 ]; then
  RESPONSE_PERCENTAGE=$(( (REPLIED_REQUIRED * 100) / REQUIRES_RESPONSE ))
  echo "   Requested-scope response rate: $RESPONSE_PERCENTAGE%"
else
  echo "   Requested-scope response rate: N/A (no response scope requested or required)"
fi

# Step 2C: Report the response scope marked by commentfetch

echo ""
echo "🔍 REQUESTED RESPONSE SCOPE:"
AI_RESPONDER_COMMENTS=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.body | startswith("[AI responder]"))]')
AI_COUNT=$(echo "$AI_RESPONDER_COMMENTS" | jq length)
NEEDS_RESPONSE_COMMENTS=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.requires_response == true and .already_replied != true)]')
NEEDS_RESPONSE_COUNT=$(echo "$NEEDS_RESPONSE_COMMENTS" | jq length)

echo "   AI responder comments: $AI_COUNT"
echo "   Outstanding requested/required responses: $NEEDS_RESPONSE_COUNT"

# Step 2D: List comments needing response (simple logic)

echo ""
echo "📌 OUTSTANDING REQUESTED/REQUIRED RESPONSES:"
echo "$NEEDS_RESPONSE_COMMENTS" | jq -r '.[] | "• Comment #\(.id) (\(.author)): \(.body[0:80])..."'
```

# Use simple AI responder detection for quality analysis

AI_RESPONDER_RESPONSES=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.body | startswith("[AI responder]"))]')
AI_RESPONSE_COUNT=$(echo "$AI_RESPONDER_RESPONSES" | jq length)

echo "📊 SIMPLE RESPONSE ANALYSIS:"
echo "   AI responder comments found: $AI_RESPONSE_COUNT"

# No complex pattern analysis - just check for basic quality

echo "🔍 BASIC QUALITY CHECK:"

# Only check if AI responder comments exist and have substance

SUBSTANTIAL_RESPONSES=$(echo "$AI_RESPONDER_RESPONSES" | jq '[.[] | select(.body | length > 50)]')
SUBSTANTIAL_COUNT=$(echo "$SUBSTANTIAL_RESPONSES" | jq length)
echo "   Substantial AI responses (>50 chars): $SUBSTANTIAL_COUNT"

# Calculate generic acknowledgments from AI responses

GENERIC_RESPONSES=$(echo "$AI_RESPONDER_RESPONSES" | jq '[.[] | select(.body | length <= 50)]')
GENERIC_COUNT=$(echo "$GENERIC_RESPONSES" | jq length)
echo "   Generic acknowledgments: $GENERIC_COUNT"

# Pattern 3: Bot-specific templating - use AI_RESPONDER_RESPONSES instead of undefined HUMAN_RESPONSES

CODERABBIT_RESPONSES=$(echo "$AI_RESPONDER_RESPONSES" | jq '[.[] | select(.body | test("Thank you CodeRabbit"))]')
CODERABBIT_COUNT=$(echo "$CODERABBIT_RESPONSES" | jq length)
echo "   CodeRabbit-specific templates: $CODERABBIT_COUNT"

# Simple quality assessment - just check for basic response coverage

if [ "$AI_RESPONSE_COUNT" -eq 0 ] && [ "$NEEDS_RESPONSE_COUNT" -gt 0 ]; then
  echo "ℹ️ No AI-responder replies were found in the requested/required response scope; this count alone is not a lifecycle gate."
  echo ""
  echo "EXIT CODE: 0 (report only)"
  exit 0
else
  echo "✅ BASIC QUALITY CHECK PASSED: AI responses detected"
fi
```

# Use simple direct comment counting

TOTAL_COMMENTS=$(jq '.comments | length' "$COMMENTS_FILE" 2>/dev/null || echo "0")
AI_RESPONDER_COMMENTS=$(jq '[.comments[] | select(.body | startswith("[AI responder]"))] | length' "$COMMENTS_FILE" 2>/dev/null || echo "0")
NEEDS_RESPONSE_COUNT=$(jq '[.comments[] | select(.requires_response == true and .already_replied != true)] | length' "$COMMENTS_FILE" 2>/dev/null || echo "0")

if [ "$NEEDS_RESPONSE_COUNT" -eq 0 ]; then
    echo "✅ **COMMENT REPORT**: No outstanding comments marked as requiring a response"
    echo ""
    echo "📊 **SIMPLE STATISTICS:**"
    echo "   - Total comments: $TOTAL_COMMENTS"
    echo "   - AI responder comments: $AI_RESPONDER_COMMENTS"
    echo "   - Outstanding requested/required responses: $NEEDS_RESPONSE_COUNT"
    echo ""
    echo "🎯 **COMMENT REPORT**: Marked response coverage is complete"
    echo ""
    echo "EXIT CODE: 0 (report only)"
    exit 0
else
    echo "ℹ️ $NEEDS_RESPONSE_COUNT responses remain outstanding in the requested/required scope; this count alone is not a lifecycle gate."
    echo ""
    echo "📌 **OUTSTANDING REQUESTED/REQUIRED RESPONSES**:"

    # List comments needing response (simple logic)
    NEEDS_RESPONSE_LIST=$(jq -r '.comments[] | select(.requires_response == true and .already_replied != true) | "• Comment #\(.id) (\(.author)): \(.body[0:80])..."' "$COMMENTS_FILE" 2>/dev/null)
    echo "$NEEDS_RESPONSE_LIST"

    echo ""
    echo "ℹ️ Review the requested task scope and authoritative lifecycle requirements. Unanswered advisory bot comments alone do not block readiness or merge."
    echo ""
    echo "📊 **COMMENTFETCH DATA**: $TOTAL_COMMENTS total, $NEEDS_RESPONSE_COUNT unresponded"
    echo ""
    echo "EXIT CODE: 0 (report only; no gate inferred from comment count)"
    exit 0
fi
```

## Comment Coverage Report

Report unanswered comments by source and lifecycle status. Automated reviewer
comments remain advisory. An unanswered comment alone does not block push,
readiness, or merge eligibility. Verify replies only when the live user request
explicitly asks to send them. Escalate only an unmet gate specified by the
current PR lifecycle owner.

### When to Run

- **After** `/commentreply` completes
- **Before** final `/pushl` when useful for advisory triage
- **Report** comment coverage; defer push/merge gates to their canonical owners

## Command Flow Integration

```
/commentfetch → /fixpr → /commentreply → /commentcheck (advisory) → /pushl (per canonical lifecycle)
                                                        ↓
                                               [comment coverage reported]
```

## Architectural Benefits

- **Orchestration over Duplication** - Follows CLAUDE.md principles
- **Single source of truth** - commentfetch is authoritative for comment data
- **Consistent data format** - Both commands use same JSON structure
- **Reduced maintenance** - Bug fixes in commentfetch benefit both commands
- **Clear separation** - commentfetch fetches, commentcheck verifies
- **Performance** - No duplicate API calls or processing

## Error Handling

- **commentfetch failures**: Clear error with diagnostic information
- **JSON parsing issues**: Graceful fallback with error reporting
- **Missing data files**: Explicit error messages with remediation steps
- **API access problems**: Delegated to commentfetch for handling

## Benefits

- **Quality assurance** - Ensures responses meet professional standards
- **Complete coverage** - Guarantees no comments are missed (via commentfetch)
- **Audit trail** - Provides detailed verification report
- **Process improvement** - Identifies patterns in response quality
- **User confidence** - Confirms all feedback was properly addressed
- **Architectural compliance** - Eliminates code duplication

## Example Usage

```bash

# After running /commentreply

/commentcheck 1603

# Will orchestrate commentfetch and verify:

# ✅ All comments have responses

# ✅ Responses address specific content

# ✅ Proper DONE/NOT DONE classification

# ✅ Professional and substantial replies

# 📊 Generate detailed coverage report

```

This command ensures the comment response process maintains high quality and complete coverage for professional PR management, with proper orchestration of commentfetch eliminating code duplication.
