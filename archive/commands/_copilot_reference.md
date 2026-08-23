# /copilot Reference Documentation

## Response Data Format Specification (ACTION PROTOCOL)

### MANDATORY: responses.json Format

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
      "tracking_reason": "Implemented UID-based admin check to fix critical authentication bypass. Admin UIDs are now recognized in isAuthenticatedNonVIP() with full test coverage. Verified all rate limit tests pass.",
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
      "tracking_reason": "Addressed all 11 issues from CodeRabbit review including 6 actionable items and 5 nitpicks. Removed phrase-scanning triggers, added edge case validation, and fixed documentation typos across multiple files.",
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

### CRITICAL FORMAT REQUIREMENTS:

**Base Fields (ALL responses):**
- `comment_id` MUST be STRING (not integer)
- `html_url` SHOULD contain the GitHub comment URL for tracking and linking (extracted from comments.json)
- `category` MUST be one of: CRITICAL, BLOCKING, IMPORTANT, ROUTINE
  - **Multi-issue format**: Top-level `category` represents the highest-priority issue in the comment
  - **Single-issue format**: Top-level `category` represents the issue's priority
- `response` MUST be one of: FIXED, DEFERRED, ACKNOWLEDGED, NOT_DONE
  - **Multi-issue format**: Top-level `response` represents the overall status (typically FIXED if all fixed)
  - **Single-issue format**: Top-level `response` represents the issue's status
- `tracking_reason` **MANDATORY** - 2-3 sentence justification for the decision. This appears in the PR description's comment tracking table. Must explain WHY this response type was chosen and WHAT was done or decided. Examples:
  - FIXED: "Implemented the requested null check at the API boundary. Added validation in auth.py:45 to prevent NullPointerException in production. Verified with unit tests."
  - DEFERRED: "Requires architectural changes spanning 3 services that cannot be safely done in this PR. Created bead worktree_worker4-xyz to track the cross-service refactoring effort."
  - ACKNOWLEDGED: "Style suggestion for variable naming consistency. Current naming follows the existing codebase convention and changing it would require a broader refactoring effort."
  - NOT_DONE: "Attempted the fix but it breaks the public API contract used by 3 downstream consumers. Needs a design discussion to determine the migration path."
  - SKIPPED: "Bot status update about CI pipeline status. Not actionable - informational notification only."
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

### INTEGRATION CONTRACT:

- commentreply.py expects `responses` array with `comment_id` and `reply_text`
- `reply_text` is auto-generated from action fields for consistency
- Matching uses `str(response_item.get("comment_id")) == comment_id`
- Missing required fields cause validation failures
- Format validation is MANDATORY before attempting to post responses

### RESPONSE QUALITY STANDARDS (UPDATED):

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

### PR DESCRIPTION COMMENT TRACKING

After processing all comments, `/copilot` updates the PR description with a tracking table at the bottom. The table uses HTML comment markers for idempotent updates.

**Tracking Categories:**

| Category | Maps From | Icon | Meaning |
|----------|-----------|------|---------|
| **Fixed** | `FIXED`, `ALREADY_IMPLEMENTED` | ✅ | Issue was resolved in this PR |
| **Deferred** | `DEFERRED` | 🔄 | Tracked for future implementation |
| **Ignored** | `ACKNOWLEDGED`, `SKIPPED`, `NOT_DONE` | ⏭️ | Intentionally not acting on this |
| **Unresolved** | No response entry | ❓ | Comment was not processed |

**Each entry requires a 2-3 sentence `tracking_reason`** explaining the decision. This is populated from the response's `tracking_reason` field.

**Example PR Description Section:**

```markdown
<!-- COPILOT_TRACKING_START -->
---
## Copilot Comment Tracking

| Status | Comment | Reason |
|--------|---------|--------|
| ✅ Fixed | [#123456](url) by @reviewer | Implemented null check at API boundary. Added validation in auth.py:45. Verified with unit tests. |
| 🔄 Deferred | [#789012](url) by @reviewer | Requires cross-service refactoring spanning 3 services. Created bead worktree_worker4-xyz to track. |
| ⏭️ Ignored | [#345678](url) by @bot | Bot status update about CI pipeline. Not actionable - informational notification only. |
| ❓ Unresolved | [#901234](url) by @reviewer | Comment was not processed in this copilot run. No response entry found in responses.json. |

**Last processed**: 2026-02-16T12:00:00Z | **Coverage**: 15/18 (83%) | **Fixed**: 10 | **Deferred**: 2 | **Ignored**: 3 | **Unresolved**: 3
<!-- COPILOT_TRACKING_END -->
```

**Implementation**: `commentreply.py` calls `update_pr_description_with_tracking()` after posting the consolidated summary comment. Uses `<!-- COPILOT_TRACKING_START -->` / `<!-- COPILOT_TRACKING_END -->` markers for idempotent replacement on re-runs.

## Thread Resolution Policy

- `/copilot` itself does not auto-resolve GitHub review threads as part of the main comment-processing loop.
- `responses.json` stays comment-centric. Follow-up actions derive review-thread IDs from the recorded `comment_id` values by querying GitHub review threads, then log the resulting `comment_id -> thread_id` mapping in their run output.
- If a separate follow-up action is explicitly resolving threads, it must use the real GraphQL `resolveReviewThread` mutation and only for comments already recorded as `FIXED` or `ALREADY_IMPLEMENTED`.
- Record the tracked or resolved thread IDs in the run output so the follow-up action stays auditable and does not silently mutate merge-gate state.
