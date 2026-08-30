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
3. **Prevent completion** - Workflow should not proceed until fixed
4. **Re-run commentreply** - Address missing/poor responses

## 📋 REFERENCE DOCUMENTATION

# /commentcheck Command

**Usage**: `/commentcheck [PR_NUMBER] [--verify-urls]`

🚨 **CRITICAL PURPOSE**: Verify 100% comment coverage and response quality after comment reply process. Count ALL comments requiring response (everything except '[AI responder]' comments).

🚨 **CRITICAL CLARIFICATION - Bot Comments Must Be Addressed**:
- ✅ **"ALL comments" explicitly INCLUDES bot comments**: CodeRabbit, GitHub Copilot, automated reviewers
- ✅ **"ALL comments" explicitly INCLUDES human comments**: Team members, manual reviewers
- ❌ **ONLY EXCEPTION**: Comments starting with "[AI responder]" (our own AI-generated responses)
- 🚨 **MANDATORY**: Bot code review comments MUST have responses - either fixes or "NOT DONE: [reason]"
- 🚨 **ZERO SKIP TOLERANCE**: 100% reply rate means bot AND human comments must be addressed

🔒 **Security**: Uses safe jq --arg parameter passing to prevent command injection vulnerabilities and explicit variable validation.

## Universal Composition Integration

**Enhanced with /execute**: `/commentcheck` benefits from universal composition when called through `/execute`, which automatically provides intelligent optimization for large-scale comment verification while preserving systematic coverage analysis.

## 🎯 INDIVIDUAL COMMENT VERIFICATION MANDATE

**MANDATORY**: This command MUST count ALL comments requiring response:
- **Zero tolerance policy** - Every comment needs response except '[AI responder]' comments
  - 🚨 **Bot comments (CodeRabbit, GitHub Copilot, automated reviewers) = MUST respond**
  - 🚨 **Human comments = MUST respond**
  - ❌ **[AI responder] comments = Skip (our own responses)**
- **Simple counting** - Count comments NOT starting with '[AI responder]'
- **Warning system** - Clear alerts when unaddressed comments > 0
- **No complex classification** - No bot detection
- **Evidence requirement** - List any comments needing response by ID
- **Simple principle** - Address everything (human AND bot) except our own '[AI responder]' responses
- **Direct reply verification** - Every non-AI-responder comment (including bot comments) must have response

## Description

Pure markdown command (no Python executable) that systematically verifies all PR comments have been properly addressed with appropriate responses. **ORCHESTRATES /commentfetch for data source** instead of duplicating GitHub API calls. This command runs AFTER `/commentreply` to ensure nothing was missed.

## 🚨 COPILOT INTEGRATION REQUIREMENTS

### FAILURE ESCALATION (MANDATORY EXIT CODES):

- **EXIT CODE 1**: Unresponded comments detected - HALT copilot execution immediately
- **EXIT CODE 2**: GitHub API failures - HALT with diagnostic information
- **EXIT CODE 0**: Only when 100% coverage verified - ALLOW copilot to continue

### COPILOT INTEGRATION PROTOCOL:

- **PRE-PUSH GATE**: Must run before any push operations in copilot workflow
- **HARD STOP ENFORCEMENT**: Non-zero exit codes must halt copilot execution
- **NO BYPASS ALLOWED**: Cannot be skipped or ignored in copilot automation
- **COVERAGE THRESHOLD**: Exactly 0 unaddressed comments (excluding '[AI responder]') required for success

## What It Does

1. **Orchestrates /commentfetch** for comprehensive comment data (eliminates duplicate API calls)
2. **Analyzes JSON output** from commentfetch for coverage verification
3. **Cross-references** original comments with posted responses using structured data
4. **Verifies coverage** - ensures every comment has a corresponding response
5. **Quality check** - confirms responses are substantial, not generic
6. **Reports status** with detailed breakdown using commentfetch metadata

## Individual Comment Verification Process (ORCHESTRATED)

# 1. Get PR number and validate

PR_NUMBER=${1:-$(gh pr view --json number --jq .number)}
if [ -z "$PR_NUMBER" ]; then
  echo "❌ ERROR: Could not determine PR number. Please specify PR number or run from PR branch."
  echo "EXIT CODE: 2 (API_FAILURE - Copilot execution must halt)"
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
  echo "🚨 CRITICAL: COPILOT EXECUTION HALTED" >&2
  echo "🚨 REASON: commentfetch failed to provide structured data at $COMMENTS_FILE" >&2
  echo "This indicates commentfetch execution failure or missing output file." >&2
  echo "EXIT CODE: 2 (API_FAILURE - Copilot execution must halt)" >&2
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
  echo "🚨 CRITICAL: COPILOT EXECUTION HALTED" >&2
  echo "🚨 REASON: No comment data available from commentfetch JSON" >&2
  echo "EXIT CODE: 2 (API_FAILURE - Copilot execution must halt)" >&2
  exit 2
fi

echo "✅ USING COMMENTFETCH DATA: $(echo "$ALL_COMMENTS" | jq length) comments loaded"

# Step 2A: Analyze threading status for ALL comments (from commentfetch data)

echo "📊 THREADING STATUS ANALYSIS:"
echo "$ALL_COMMENTS" | jq -r '.[] | "ID: \(.id) | Author: \(.author) | Type: \(.type) | Replied: \(.already_replied)"'

# Step 2B: Count threading success rates (using commentfetch metadata)

TOTAL_COMMENTS=$(echo "$ALL_COMMENTS" | jq length)
ALREADY_REPLIED=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.already_replied == true)] | length')
REQUIRES_RESPONSE=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.requires_response == true)] | length')

echo ""
echo "📈 THREADING STATISTICS (from commentfetch):"
echo "   Total comments: $TOTAL_COMMENTS"
echo "   Already replied: $ALREADY_REPLIED"
echo "   Requires response: $REQUIRES_RESPONSE"

if [ "$TOTAL_COMMENTS" -gt 0 ]; then
  RESPONSE_PERCENTAGE=$(( (ALREADY_REPLIED * 100) / TOTAL_COMMENTS ))
  echo "   Response rate: $RESPONSE_PERCENTAGE%"
fi

# Step 2C: Simple comment classification (AI responder vs needs response)

echo ""
echo "🔍 SIMPLE CLASSIFICATION (AI responder detection only):"
AI_RESPONDER_COMMENTS=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.body | startswith("[AI responder]"))]')
AI_COUNT=$(echo "$AI_RESPONDER_COMMENTS" | jq length)
NEEDS_RESPONSE_COMMENTS=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.body | startswith("[AI responder]") | not)]')
NEEDS_RESPONSE_COUNT=$(echo "$NEEDS_RESPONSE_COMMENTS" | jq length)

echo "   AI responder comments: $AI_COUNT"
echo "   Comments needing response: $NEEDS_RESPONSE_COUNT"

# Step 2D: List comments needing response (simple logic)

echo ""
echo "❌ COMMENTS NEEDING RESPONSE (simple logic):"
echo "$NEEDS_RESPONSE_COMMENTS" | jq -r '.[] | "❌ Comment #\(.id) (\(.author)): \(.body[0:80])..."'
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
  echo "🚨 CRITICAL: COPILOT EXECUTION HALTED"
  echo "🚨 REASON: No AI responder comments found but comments need responses"
  echo "🚨 REQUIRED ACTION: Run /commentreply to generate responses"
  echo ""
  echo "EXIT CODE: 1 (FAILURE - No responses provided)"
  exit 1
else
  echo "✅ BASIC QUALITY CHECK PASSED: AI responses detected"
fi
```

# Use simple direct comment counting

TOTAL_COMMENTS=$(jq '.comments | length' "$COMMENTS_FILE" 2>/dev/null || echo "0")
AI_RESPONDER_COMMENTS=$(jq '[.comments[] | select(.body | startswith("[AI responder]"))] | length' "$COMMENTS_FILE" 2>/dev/null || echo "0")
NEEDS_RESPONSE_COUNT=$((TOTAL_COMMENTS - AI_RESPONDER_COMMENTS))

if [ "$NEEDS_RESPONSE_COUNT" -eq 0 ]; then
    echo "✅ **ZERO TOLERANCE POLICY: PASSED**"
    echo "🎉 **SUCCESS**: All comments addressed (only AI responder comments remain)"
    echo "📈 **COVERAGE SCORE**: 100% ✅ PASSED"
    echo ""
    echo "📊 **SIMPLE STATISTICS:**"
    echo "   - Total comments: $TOTAL_COMMENTS"
    echo "   - AI responder comments: $AI_RESPONDER_COMMENTS"
    echo "   - Comments needing response: $NEEDS_RESPONSE_COUNT"
    echo "   - All non-AI comments addressed: ✅"
    echo ""
    echo "🎯 **SIMPLE COVERAGE SUCCESS**: Zero tolerance policy satisfied"
    echo "✅ COPILOT CLEARED: All comments processed successfully"
    echo "✅ PROCEEDING: Copilot execution may continue"
    echo ""
    echo "EXIT CODE: 0 (SUCCESS - Copilot may proceed)"
    exit 0
else
    echo "🚨 **ZERO TOLERANCE POLICY: FAILED**"
    echo "❌ **FAILURE**: $NEEDS_RESPONSE_COUNT comments need responses"
    echo "📈 **COVERAGE SCORE**: $(( AI_RESPONDER_COMMENTS * 100 / TOTAL_COMMENTS ))% ❌ FAILED"
    echo ""
    echo "🚨 **COMMENTS REQUIRING IMMEDIATE ATTENTION**:"

    # List comments needing response (simple logic)
    NEEDS_RESPONSE_LIST=$(jq -r '.comments[] | select(.body | startswith("[AI responder]") | not) | "❌ Comment #\(.id) (\(.author)): \(.body[0:80])..."' "$COMMENTS_FILE" 2>/dev/null)
    echo "$NEEDS_RESPONSE_LIST"

    echo ""
    echo "🚨 CRITICAL: COPILOT EXECUTION HALTED"
    echo "🚨 REASON: $NEEDS_RESPONSE_COUNT unresponded comments detected"
    echo "🚨 REQUIRED ACTION: Address ALL unresponded comments before copilot can continue"
    echo ""
    echo "🔧 **REQUIRED ACTION**: Run /commentreply to address unresponded comments"
    echo "⚠️ **WORKFLOW HALT**: Cannot proceed until all comments addressed"
    echo "📊 **COMMENTFETCH DATA**: $TOTAL_COMMENTS total, $NEEDS_RESPONSE_COUNT unresponded"
    echo ""
    echo "EXIT CODE: 1 (FAILURE - Copilot execution must halt)"
    exit 1
fi
```

## Individual Comment Success Criteria (ZERO TOLERANCE)

🚨 **✅ PASS REQUIREMENTS**: ZERO unresponded comments with quality responses
- **ZERO unresponded comments detected** (explicit count must be 0)
- **Clear warning system shows no alerts** (unresponded count = 0)
- **Every bot comment (CodeRabbit, GitHub Copilot, automated reviewers) has a response** (bot feedback is NOT optional)
- **Every human reviewer comment has a response** (team feedback must be addressed)
- 🚨 **CRITICAL**: Bot comments are NOT skippable - they need 100% reply rate like human comments
- **All responses address specific technical content** (not generic acknowledgments)
- **Appropriate ✅ DONE/❌ NOT DONE status** (clear resolution indication)
- **Professional and substantial replies** (meaningful engagement with feedback)

🚨 **❌ FAIL CONDITIONS**: ANY unresponded comments detected
- **ANY unresponded comment count > 0** (immediate failure with clear warning)
- **Warning system alerts triggered** (explicit alerts when unresponded comments found)
- **Generic/template responses** ("Thanks!" or "Will consider" are insufficient)
- **Bot comment coverage failure** (skipping any Copilot/CodeRabbit/automated reviewer feedback violates 100% reply requirement)
- **Responses don't address technical content** (must engage with specific suggestions from bots or humans)
- **Unprofessional or inadequate replies** (maintain PR review standards for all comment sources)

### 🎯 SPECIFIC FAIL TRIGGERS (UNRESPONDED COMMENT FOCUS)

- **Unresponded comment count > 0** (explicit count detection and warning)
- **Zero individual responses** (like PR #864 - complete failure with 11 unresponded)
- **Skipped bot comment detected** (any Copilot/CodeRabbit/automated reviewer comment without reply = failure)
- **Warning system triggered** (any alerts about unresponded comments)
- **Template responses only** (generic acknowledgments without substance)
- **Ignored technical suggestions** (failing to address specific code feedback from bots or humans)

### When to Run

- **After** `/commentreply` completes
- **Before** final `/pushl` in copilot workflow
- **Verify** comment coverage is complete

## Command Flow Integration

```
/commentfetch → /fixpr → /pushl → /commentreply → /commentcheck → /pushl (final)
                                                        ↓
                                               [100% coverage verified]
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
