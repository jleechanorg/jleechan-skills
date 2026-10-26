---
description: /commentfetch Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# /commentfetch Command

**Usage**: `/commentfetch <PR_NUMBER>` or `/commentfetch [natural language instruction]`

**Purpose**: Fetch ALL comments from a GitHub PR including inline code reviews, general comments, review comments, and Copilot suggestions. Also fetches GitHub CI status using /fixpr methodology. Always fetches fresh data from GitHub API - no caching.

## 🤖 ENHANCED: Intelligent Natural Language Processing

**NEW CAPABILITY**: Parse natural language instructions like:
- `/commentfetch print all comments here`
- `/commentfetch get all comments`
- `/commentfetch show me unresponded from PR 1436`

## 🚨 CRITICAL: Comprehensive Comment Detection Function

**MANDATORY**: Fixed copilot skip detection bug that was ignoring inline review comments:
```bash

# 🚨 COMPREHENSIVE COMMENT DETECTION FUNCTION

# CRITICAL FIX: Include ALL comment sources (inline review comments were missing)

get_comprehensive_comment_count() {
    local pr_number=$1
    local owner_repo=$(gh repo view --json owner,name | jq -r '.owner.login + "/" + .name')

    # Get all three comment sources
    local general_comments=$(gh pr view $pr_number --json comments | jq '.comments | length')
    local review_comments=$(gh pr view $pr_number --json reviews | jq '.reviews | length')
    # Robust pagination-safe counting for inline comments
    local inline_comments=$(gh api "repos/$owner_repo/pulls/$pr_number/comments" --paginate --jq '.[].id' 2>/dev/null | wc -l | tr -d ' ')
    inline_comments=${inline_comments:-0}

    local total=$((general_comments + review_comments + inline_comments))

    # Silent operation - only output on errors or warnings

    echo "$total"
}
```

**Usage**: Call `get_comprehensive_comment_count <PR_NUMBER>` from any command that needs accurate comment counting for skip conditions or processing decisions.

## Description

Pure Python implementation that collects ALL comments from all GitHub PR sources AND GitHub CI status. Marks comments starting with '[AI responder]' as our responses. Implements /fixpr CI status methodology with defensive programming patterns. Always fetches fresh data on each execution and saves to `/tmp/{repo_name}/{branch_name}/copilot/comments.json` for downstream processing by `/commentreply`.

## Output Format

Saves structured JSON data to `/tmp/{repo_name}/{branch_name}/copilot/comments.json` with:

```json
{
  "pr": "820",
  "fetched_at": "2025-01-21T12:00:00Z",
  "comments": [
    {
      "id": "12345",
      "type": "inline|general|review|copilot",
      "body": "Comment text",
      "author": "username",
      "created_at": "2025-01-21T11:00:00Z",
      "file": "path/to/file.py",  // for inline comments
      "line": 42,                  // for inline comments
      "already_replied": false,
      "requires_response": true
    }
  ],
  "ci_status": {
    "overall_state": "FAILING|PASSING|PENDING|ERROR",
    "mergeable": true,
    "merge_state_status": "clean",
    "checks": [
      {
        "name": "test",
        "status": "FAILURE",
        "description": "Process completed with exit code 1",
        "url": "https://github.com/owner/repo/actions/runs/123"
      }
    ],
    "summary": {"total": 4, "passing": 2, "failing": 1, "pending": 1},
    "failing_checks": [...],
    "pending_checks": [...],
    "fetched_at": "2025-01-21T12:00:00Z"
  },
  "metadata": {
    "total": 17,
    "by_type": {
      "inline": 8,
      "general": 1,
      "review": 2,
      "copilot": 6
    },
    "unresponded_count": 8,
    "repo": "owner/repo"
  }
}
```

`requires_response` is fetcher metadata used to report and support downstream
comment processing. It does not itself authorize a reply or create a lifecycle
gate. Automated reviewer comments remain advisory for readiness and merge;
honor their coverage when the current request explicitly asks for comment
processing or replies.

## Comment Types

- **inline**: Code review comments on specific lines
- **general**: Issue-style comments on the PR
- **review**: Review summary comments
- **copilot**: GitHub Copilot suggestions (including suppressed)

## Simple Comment Processing

🚨 **ZERO TOLERANCE APPROACH**: Process ALL comments without complex filtering:

### 1. AI Responder Detection (ONLY FILTER)

- **Method**: Check if comment body starts with '[AI responder]'
- **Logic**: If comment starts with '[AI responder]', mark as our response
- **Simple Rule**: Fetch every comment. A response is required only when the current request explicitly asks for reply coverage or an authoritative lifecycle owner requires it.

🚨 **CRITICAL CLARIFICATION - Bot Comments Included**:
- ✅ **"ALL comments" explicitly INCLUDES bot comments**: CodeRabbit, GitHub Copilot, automated reviewers
- ✅ **"ALL comments" explicitly INCLUDES human comments**: Team members, manual reviewers
- ❌ **ONLY EXCEPTION**: Comments starting with "[AI responder]" (our own AI-generated responses)
- Automated reviewer comments are advisory for push, readiness, and merge eligibility; an unanswered bot comment alone is not a lifecycle gate.
- If the current request explicitly asks to process or reply to bot comments, preserve that task's requested coverage and report any remaining blocker without converting it into a general PR gate.

### 2. Reuse Fetcher Metadata

- This command reports the metadata supplied by the commentfetch implementation; it does not add another classification pass.
- A `requires_response` flag is processing metadata, not authorization to post a reply or a readiness/merge gate.
- Follow an explicit current-task request for reply coverage, including the comments within that requested scope.

### 3. Output Simplification

- **JSON field**: `"is_ai_responder": true/false` (simple boolean)
- **Metadata**: `"requires_response_count": X` for verification
- **Fresh Data**: Always fetches current GitHub state
- **Principle**: Fetch and report all comments except our own '[AI responder]' comments as new findings.
  - Automated reviewer comments remain advisory for lifecycle eligibility.
  - Honor explicit current-task requests for response coverage, including bot comments.
  - Do not infer that every comment needs a reply merely because it was fetched.

## Implementation

### Intelligent Argument Processing

```bash

# Parse natural language instructions intelligently

ARGS="$*"
echo "📝 Processing instruction: $ARGS"

# Extract PR number from current branch if not specified

# Fixed: Only match explicit PR patterns (PR123, pr#123, #123) to avoid matching standalone numbers

if ! echo "$ARGS" | grep -qE '([Pp][Rr][#[:space:]]*|#)[0-9]+'; then
    PR_NUMBER=$(gh pr list --head $(git branch --show-current) --json number --jq '.[0].number' 2>/dev/null)
    if [ -z "$PR_NUMBER" ]; then
        echo "❌ ERROR: Could not determine PR number. Please specify PR number or run from PR branch."
        exit 1
    fi
    echo "🔍 Auto-detected PR number: $PR_NUMBER"
else
    # Extract PR number from arguments using the improved pattern
    # Fixed: Use two-step extraction to get only the number portion from valid PR patterns
    PR_NUMBER=$(
      echo "$ARGS" \
      | grep -oE '([Pp][Rr][#[:space:]]*|#)[0-9]+' \
      | grep -oE '[0-9]+' \
      | head -1
    )
fi

# The model resolves requested output format and any explicit limit, then passes
# `--print-inline` and `--limit N` as applicable. Shell parses these options; it
# does not infer intent from words in the natural-language request.

PRINT_INLINE=false
LIMIT=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --print-inline)
            PRINT_INLINE=true
            shift
            ;;
        --limit)
            [ "$#" -ge 2 ] || { echo "--limit requires a value" >&2; exit 2; }
            LIMIT="$2"
            case "$LIMIT" in ''|*[!0-9]*) echo "--limit must be a non-negative integer" >&2; exit 2 ;; esac
            shift 2
            ;;
        *) shift ;;
    esac
done

[ "$PRINT_INLINE" = true ] && echo "📺 Will display comments inline"
[ -n "$LIMIT" ] && echo "🔢 Comment limit: $LIMIT"

echo "🚀 Fetching comments for PR #$PR_NUMBER..."
cd .claude/commands && python3 -c "
import _copilot_modules.commentfetch as cf
import sys
fetch = cf.CommentFetch(sys.argv[1])
fetch.execute()
" "$PR_NUMBER"

# If user requested inline display, show the results

if [ "$PRINT_INLINE" = "true" ]; then
    BRANCH_NAME=$(git branch --show-current | tr -cd '[:alnum:]._-')
    REPO_NAME=$(basename "$(git rev-parse --show-toplevel)" | tr -cd '[:alnum:]._-')
    COPILOT_DIR="/tmp/$REPO_NAME/$BRANCH_NAME/copilot"
    COMMENTS_FILE="$COPILOT_DIR/comments.json"

    if [ -f "$COMMENTS_FILE" ]; then
        echo ""
        echo "📋 UNRESPONDED COMMENTS (Last fetched: $(date)):"
        echo "=================================================="

        if [ -n "$LIMIT" ]; then
            # Show limited number of recent comments
            echo "🔍 Showing last $LIMIT unresponded comments:"
            jq -r --argjson limit "$LIMIT" '.comments | sort_by(.created_at) | reverse | .[:$limit] | .[] | "👤 \(.author) (\(.type)) - \(.created_at)\n📝 \(.body[0:200])...\n📍 \(.file // "General"):\(.line // "")\n---"' "$COMMENTS_FILE" 2>/dev/null || echo "❌ Error parsing comments JSON"
        else
            # Show all unresponded comments
            echo "📊 Total unresponded: $(jq '.metadata.unresponded_count' "$COMMENTS_FILE" 2>/dev/null || echo "unknown")"
            jq -r '.comments | sort_by(.created_at) | reverse | .[] | "👤 \(.author) (\(.type)) - \(.created_at)\n📝 \(.body[0:200])...\n📍 \(.file // "General"):\(.line // "")\n---"' "$COMMENTS_FILE" 2>/dev/null || echo "❌ Error parsing comments JSON"
        fi
    else
        echo "❌ Comments file not found: $COMMENTS_FILE"
    fi
fi
```

## Examples

```bash

# Fetch all fresh comments for PR 820

/commentfetch 820

# Internally runs: cd .claude/commands && python3 -c "import _copilot_modules.commentfetch as cf; ..."

# Saves comments to /tmp/{repo_name}/{branch_name}/copilot/comments.json

# Downstream commands read from the saved file

```

## Integration

This command is typically the first step in the `/copilot` workflow, providing fresh comment data AND CI status to `/tmp/{repo_name}/{branch_name}/copilot/comments.json` for other commands like `/fixpr` and `/commentreply`. Uses /fixpr methodology for authoritative GitHub CI status with defensive programming patterns. Always fetches current data and overwrites the comments file.

## CI Status Integration

**Enhanced with /fixpr methodology**:
- Uses `gh pr view --json statusCheckRollup,mergeable,mergeStateStatus` for authoritative GitHub CI data
- Implements defensive programming patterns (statusCheckRollup is a LIST, safe access)
- Provides overall state assessment (FAILING/PASSING/PENDING/ERROR)
- Categorizes checks for quick analysis (failing_checks, pending_checks)
- Includes merge status and detailed check information
- Fetched in parallel with comments for optimal performance
