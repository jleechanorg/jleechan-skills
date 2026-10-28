---
name: commentcheck
description: /commentcheck Command
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

🚨 **CRITICAL PURPOSE**: Verify comment coverage after the reply process using original comment IDs and attributable response or consolidated-summary receipts. Semantic response quality remains a model judgment.

🚨 **CRITICAL CLARIFICATION - Bot Comments Must Be Addressed**:
- ✅ **"ALL comments" includes bot and human comments**: coverage is checked by each original comment ID.
- ✅ A response entry or refreshed consolidated summary must identify the original comment ID.
- 🚫 **Do not infer response quality from keywords, character counts, or author labels**; model judgment handles technical adequacy.

🔒 **Security**: Uses safe jq --arg parameter passing to prevent command injection vulnerabilities and explicit variable validation.

## Universal Composition Integration

**Enhanced with /execute**: `/commentcheck` benefits from universal composition when called through `/execute`, which automatically provides intelligent optimization for large-scale comment verification while preserving systematic coverage analysis.

## 🎯 INDIVIDUAL COMMENT VERIFICATION MANDATE

**MANDATORY**: This command MUST compare original comment IDs with attributable response IDs:
- **Bot and human comments are both in scope**; original IDs, not author classification, define coverage.
- **Response evidence** comes from structured `responses.json` entries or a refreshed consolidated-summary receipt.
- **Evidence requirement** - list any missing original IDs.
- **Semantic response quality** is judged by the model after the mechanical coverage gate; this shell command must not use keyword or length heuristics.

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
- **COVERAGE THRESHOLD**: Every original comment ID must have attributable response evidence before success

## What It Does

1. **Orchestrates /commentfetch** for comprehensive comment data (eliminates duplicate API calls)
2. **Analyzes JSON output** from commentfetch for coverage verification
3. **Cross-references** original comments with posted responses using structured data
4. **Verifies coverage** - ensures every original comment ID has attributable response evidence
5. **Delegates quality judgment** - does not score response prose mechanically
6. **Reports status** with detailed breakdown using commentfetch metadata

## Individual Comment Verification Process (ORCHESTRATED)

# 1. Get PR number and validate

PR_NUMBER=${1:-$(gh pr view --json number --jq .number)}
if [ -z "$PR_NUMBER" ]; then
  echo "❌ ERROR: Could not determine PR number. Please specify PR number or run from PR branch."
  echo "EXIT CODE: 2 (API_FAILURE - Copilot execution must halt)"
  exit 2
fi

FETCH_STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%S)
FETCH_STARTED_EPOCH=$(date +%s)

echo "🚀 ORCHESTRATING: Fetching comprehensive comment data via /commentfetch..."
echo "🔍 COMPREHENSIVE COMMENT ANALYSIS FOR PR #$PR_NUMBER"
echo "=================================================================="

# 2. Execute commentfetch Python implementation for comprehensive multi-API comment fetching

PYTHONPATH=.claude/commands python3 -c "
from _copilot_modules.commentfetch import CommentFetch
import sys
fetch = CommentFetch(sys.argv[1])
result = fetch.execute()
raise SystemExit(0 if result.get('success') else 1)
" "$PR_NUMBER" || {
  echo "🚨 CRITICAL: FRESH COMMENT FETCH FAILED; cached data will not be consumed" >&2
  echo "EXIT CODE: 2 (API_FAILURE - Copilot execution must halt)" >&2
  exit 2
}

# 3. Use structured JSON output from commentfetch

BRANCH_NAME=$(git branch --show-current | tr -cd '[:alnum:]._-')
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)" | tr -cd '[:alnum:]._-')
# Use copilot subdirectory for all copilot workflow files (see ~/.claude/skills/scratch-space/SKILL.md)
SCRATCH_ROOT="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh)" || {
  echo "🚨 CRITICAL: Scratch resolver unavailable; refusing comment cache path" >&2
  exit 2
}
if [ -z "$SCRATCH_ROOT" ]; then
  echo "🚨 CRITICAL: Scratch resolver returned no path; refusing comment cache path" >&2
  exit 2
fi
COPILOT_DIR="$SCRATCH_ROOT/$REPO_NAME/$BRANCH_NAME/copilot"
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

FETCHED_PR=$(jq -r '.pr // empty' "$COMMENTS_FILE" 2>/dev/null || true)
FETCHED_AT=$(jq -r '.fetched_at // empty' "$COMMENTS_FILE" 2>/dev/null || true)
if [ "$FETCHED_PR" != "$PR_NUMBER" ] || [ -z "$FETCHED_AT" ] || [[ "$FETCHED_AT" < "$FETCH_STARTED_AT" ]]; then
  echo "🚨 CRITICAL: commentfetch output is stale or belongs to another PR" >&2
  echo "EXIT CODE: 2 (API_FAILURE - Copilot execution must halt)" >&2
  exit 2
fi
COMMENTS_MTIME=$(stat -c %Y "$COMMENTS_FILE" 2>/dev/null || stat -f %m "$COMMENTS_FILE" 2>/dev/null || echo 0)
if [ "$COMMENTS_MTIME" -lt "$FETCH_STARTED_EPOCH" ]; then
  echo "🚨 CRITICAL: commentfetch did not refresh comments.json" >&2
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

# 5. Validate commentfetch data quality

if [ "$TOTAL_COMMENTS" -eq 0 ]; then
  echo "⚠️ WARNING: No comments detected by commentfetch"
  echo "This may indicate API access issues or an empty PR"
fi

echo "🎯 COMMENTFETCH ORCHESTRATION: Successfully loaded $TOTAL_COMMENTS comments"
echo "📈 ID ANALYSIS: coverage is determined below from original IDs and attributable receipts"
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

# Step 2C: Mechanical original-ID coverage (no semantic heuristics)

echo ""
echo "🔍 ORIGINAL COMMENT ID COVERAGE (MECHANICAL ONLY):"

# Coverage is bound to original comment IDs read back from GitHub.  The cached
# response file is generated intent only; it cannot prove that a reply was
# posted.  Existing commentfetch metadata (`already_replied`) or a refreshed
# consolidated-summary comment body may prove posted attribution; the model,
# not shell text matching, judges whether the response is technically good.
ORIGINAL_IDS=$(echo "$ALL_COMMENTS" | jq -r '.[] | select((.body // "") | startswith("[AI responder]") | not) | .id | tostring' | sort -u)
POSTED_REPLY_IDS=$(echo "$ALL_COMMENTS" | jq -r '.[] | select((.body // "") | startswith("[AI responder]") | not) | select(.already_replied == true) | .id | tostring' | sort -u)
POSTED_SUMMARY_IDS=$(echo "$ALL_COMMENTS" | jq -r '.[] | select((.body // "") | startswith("[AI responder]")) | .body' | grep -oE 'Comment #[0-9]+' | sed 's/[^0-9]//g' | sort -u || true)
ATTRIBUTED_IDS=$(printf '%s\n%s\n' "$POSTED_REPLY_IDS" "$POSTED_SUMMARY_IDS" | sed '/^$/d' | sort -u)
MISSING_IDS=$(comm -23 <(printf '%s\n' "$ORIGINAL_IDS") <(printf '%s\n' "$ATTRIBUTED_IDS"))

echo "   Original comment IDs: $(printf '%s\n' "$ORIGINAL_IDS" | sed '/^$/d' | wc -l | tr -d ' ')"
echo "   Attributable response IDs: $(printf '%s\n' "$ATTRIBUTED_IDS" | sed '/^$/d' | wc -l | tr -d ' ')"

if [ -n "$MISSING_IDS" ]; then
  echo "🚨 CRITICAL: COPILOT EXECUTION HALTED"
  echo "🚨 REASON: original comment IDs lack an attributable response or summary receipt"
  printf '❌ Missing original comment ID: %s\n' $MISSING_IDS
  echo "EXIT CODE: 1 (COVERAGE_FAILURE - Copilot execution must halt)"
  exit 1
fi

echo "✅ Every original comment ID has an attributable response or posted summary receipt"
echo "ℹ️ Semantic response quality is an LLM judgment; this gate performs no keyword or length scoring"
```

## Individual Comment Success Criteria (ZERO TOLERANCE)

🚨 **✅ PASS REQUIREMENTS**:
- Every original comment ID has a posted/read-back reply relationship or refreshed consolidated-summary receipt; generated response intent alone is insufficient.
- Missing IDs are listed and cause a non-zero exit.
- Bot and human comments are treated identically for mechanical coverage.
- Semantic adequacy, resolution state, and professional tone are judged by the model from the actual response text.

🚨 **❌ FAIL CONDITIONS**:
- Any original comment ID lacks attributable response evidence.
- The fetched data or response receipt is missing, malformed, or stale.
- The model determines that a response does not address the comment's technical substance.

The shell gate deliberately performs no character-count, keyword, template, or author-label quality scoring.

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

# ✅ Every original comment ID has attributable response evidence

# ✅ Semantic response quality is reviewed from the actual text by the model

# 📊 Generate detailed coverage report

```

This command ensures the comment response process maintains high quality and complete coverage for professional PR management, with proper orchestration of commentfetch eliminating code duplication.
