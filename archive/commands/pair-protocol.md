# Pair Protocol - MCP Mail Communication Reference

## Overview

The Pair Protocol uses MCP mail for asynchronous agent-to-agent coordination while maintaining human-in-the-loop oversight at critical decision points.

## Message Structure

All MCP mail messages follow this JSON structure:

```json
{
  "to": "<recipient_agent_id>",
  "subject": "<message_type>",
  "body": {
    "phase": "<current_phase>",
    "status": "<status>",
    "<additional_fields>": "..."
  }
}
```

## Message Types

### 1. PAIR_INIT

**Sender:** Either agent (whoever receives the /pair command first)
**Recipient:** Partner agent
**Purpose:** Initialize pair session

```json
{
  "to": "bob",
  "subject": "PAIR_INIT",
  "body": {
    "protocol_version": "3.1",
    "task": "Add user authentication with JWT tokens",
    "my_role": "PLANNER",
    "your_role": "BUILDER",
    "status": "INITIALIZED"
  }
}
```

### 2. CONTRACT_DRAFT

**Sender:** Planner
**Recipient:** Builder
**Purpose:** Share initial contract for internal review

```json
{
  "to": "bob",
  "subject": "CONTRACT_DRAFT",
  "body": {
    "phase": "CONTRACT_GENERATION",
    "artifacts": {
      "safety_reasoning": "tmp/pair_1234567890_safety_reasoning.md",
      "spec": "tmp/pair_1234567890_spec_draft.md",
      "tests": "tmp/pair_1234567890_tests.py"
    },
    "status": "AWAITING_HUMAN_REVIEW"
  }
}
```

### 3. CONTRACT_FINAL

**Sender:** Planner
**Recipient:** Builder
**Purpose:** Send finalized, immutable contract to builder

```json
{
  "to": "bob",
  "subject": "CONTRACT_FINAL",
  "body": {
    "phase": "CONTRACT_FINALIZED",
    "artifacts": {
      "spec": "tmp/pair_1234567890_spec_final.md",
      "tests": "tmp/pair_1234567890_tests.py"
    },
    "contract_immutable": true,
    "status": "READY_FOR_BUILD"
  }
}
```

### 4. BUILD_COMPLETE

**Sender:** Builder
**Recipient:** Planner
**Purpose:** Notify planner that all tests pass

```json
{
  "to": "alice",
  "subject": "BUILD_COMPLETE",
  "body": {
    "phase": "BUILD_COMPLETE",
    "test_results": "ALL_PASS",
    "implementation_files": [
      "$PROJECT_ROOT/auth/jwt_handler.py",
      "$PROJECT_ROOT/auth/middleware.py"
    ],
    "status": "READY_FOR_REVIEW"
  }
}
```

### 5. CHANGE_ORDER

**Sender:** Builder
**Recipient:** Planner
**Purpose:** Request contract modification due to blocker

```json
{
  "to": "alice",
  "subject": "CHANGE_ORDER",
  "body": {
    "phase": "BUILD_BLOCKED",
    "change_order": {
      "status": "CHANGE_ORDER_REQUIRED",
      "failure_mode": "dependency_missing",
      "evidence": "AssertionError: Expected JWT library 'pyjwt' but not found in dependencies",
      "attempted_fixes": [
        "Tried using built-in hashlib for token generation",
        "Attempted manual JWT implementation"
      ],
      "requested_changes": "Add 'pyjwt>=2.8.0' to requirements.txt and update contract to allow this dependency"
    },
    "status": "AWAITING_MEDIATION"
  }
}
```

### 6. CHANGE_ORDER_ACCEPTED

**Sender:** Planner
**Recipient:** Builder
**Purpose:** Accept change order and provide updated contract

```json
{
  "to": "bob",
  "subject": "CHANGE_ORDER_ACCEPTED",
  "body": {
    "phase": "CONTRACT_REVISED",
    "decision": "ACCEPTED",
    "updated_artifacts": {
      "spec": "tmp/pair_1234567890_spec_final_v2.md",
      "tests": "tmp/pair_1234567890_tests_v2.py"
    },
    "reasoning": "PyJWT is a standard library for JWT handling. Adding to dependencies is reasonable.",
    "status": "READY_FOR_BUILD"
  }
}
```

### 7. CHANGE_ORDER_REJECTED

**Sender:** Planner
**Recipient:** Builder
**Purpose:** Reject change order and provide strategy

```json
{
  "to": "bob",
  "subject": "CHANGE_ORDER_REJECTED",
  "body": {
    "phase": "CHANGE_ORDER_REJECTED",
    "decision": "REJECTED",
    "reasoning": "The project already has 'python-jose' library installed which handles JWT. Use existing dependency.",
    "suggested_strategy": "Import from jose.jwt instead of trying to add pyjwt. Check existing auth code for examples.",
    "status": "RETRY_BUILD"
  }
}
```

### 8. SESSION_COMPLETE

**Sender:** Planner
**Recipient:** Builder
**Purpose:** Notify successful completion and merge

```json
{
  "to": "bob",
  "subject": "SESSION_COMPLETE",
  "body": {
    "phase": "MERGED",
    "status": "SUCCESS",
    "commit_sha": "a1b2c3d4e5f6g7h8i9j0",
    "branch": "claude/pair-auth-feature",
    "message": "Pair session completed successfully. All tests passing. Implementation merged."
  }
}
```

### 9. SESSION_ABORT

**Sender:** Either agent
**Recipient:** Partner agent
**Purpose:** Abort session due to error or user request

```json
{
  "to": "bob",
  "subject": "SESSION_ABORT",
  "body": {
    "phase": "CONTRACT_GENERATION",
    "reason": "User requested abort during contract review",
    "status": "ABORTED",
    "cleanup_required": true
  }
}
```

### 10. CLARIFICATION_REQUEST

**Sender:** Either agent
**Recipient:** Orchestrator (User)
**Purpose:** Request clarification on ambiguous specifications or design decisions

```json
{
  "to": "orchestrator",
  "subject": "CLARIFICATION_REQUEST",
  "body": {
    "phase": "CLARIFICATION",
    "questions": [
      {
        "id": "q1",
        "question": "Should I use environment variables or hardcoded constants for configuration?",
        "context": "Spec suggests using environment variables, but CLAUDE.md recommends avoiding new env var creation",
        "options": [
          "Use hardcoded constants per CLAUDE.md",
          "Use environment variables per spec",
          "Use configuration file"
        ]
      },
      {
        "id": "q2",
        "question": "Which phase should /pair integration run in?",
        "context": "Current copilot has 4 phases. /pair could run in Phase 2 or new Phase 2.5",
        "options": [
          "Replace existing Phase 2 implementation",
          "Add new Phase 2.5 between categorization and response",
          "Run in parallel with Phase 2"
        ]
      }
    ],
    "status": "AWAITING_USER_INPUT"
  }
}
```

### 11. CLARIFICATION_RESPONSE

**Sender:** Orchestrator (User)
**Recipient:** Requesting agent
**Purpose:** Provide answers to clarification questions

```json
{
  "to": "agent-123",
  "subject": "CLARIFICATION_RESPONSE",
  "body": {
    "phase": "CLARIFICATION_COMPLETE",
    "answers": [
      {
        "question_id": "q1",
        "answer": "Use hardcoded constants per CLAUDE.md",
        "reasoning": "CLAUDE.md rules take precedence. Env vars add operational complexity."
      },
      {
        "question_id": "q2",
        "answer": "Add new Phase 2.5 between categorization and response",
        "reasoning": "Preserves existing workflow while adding /pair integration cleanly"
      }
    ],
    "status": "PROCEED_WITH_IMPLEMENTATION"
  }
}
```

### 12. TIMEOUT_WARNING

**Sender:** Either agent
**Recipient:** Partner agent (not responding)
**Purpose:** Warn about impending timeout

```json
{
  "to": "bob",
  "subject": "TIMEOUT_WARNING",
  "body": {
    "phase": "BUILD_COMPLETE",
    "status": "TIMEOUT",
    "message": "No response received within 30 minute timeout period. Please respond within 10 minutes or session will abort.",
    "warnings_sent": 1,
    "max_warnings": 2
  }
}
```

## Communication Patterns

### Pattern 1: Happy Path (No Change Orders)

```
1. User → /pair alice bob "Task"
2. Alice → Bob: PAIR_INIT
3. Alice: Generate contract
4. Alice → Bob: CONTRACT_DRAFT
5. Alice: [HUMAN CHECKPOINT] Contract review → APPROVED
6. Alice → Bob: CONTRACT_FINAL
7. Bob: Implement code
8. Bob → Alice: BUILD_COMPLETE
9. Alice: Run automated audit
10. Alice: [HUMAN CHECKPOINT] Implementation review → MERGE APPROVED
11. Alice: Merge code
12. Alice → Bob: SESSION_COMPLETE
```

### Pattern 2: With Change Order (Valid)

```
1-6. [Same as Happy Path]
7. Bob: Attempt implementation (fails 3 times)
8. Bob → Alice: CHANGE_ORDER
9. Alice: Analyze change order
10. Alice: [HUMAN CHECKPOINT] Change order review → ACCEPT CHANGE
11. Alice: Update contract
12. Alice → Bob: CHANGE_ORDER_ACCEPTED
13. Bob: Retry with updated contract
14. Bob → Alice: BUILD_COMPLETE
15-17. [Continue as Happy Path steps 9-12]
```

### Pattern 3: With Change Order (Rejected)

```
1-6. [Same as Happy Path]
7. Bob: Attempt implementation (fails 3 times)
8. Bob → Alice: CHANGE_ORDER
9. Alice: Analyze change order
10. Alice: [HUMAN CHECKPOINT] Change order review → REJECT CHANGE
11. Alice → Bob: CHANGE_ORDER_REJECTED (with strategy)
12. Bob: Retry with new strategy
13. Bob → Alice: BUILD_COMPLETE
14-16. [Continue as Happy Path steps 9-12]
```

### Pattern 4: With Clarification Phase (PHASE 0)

```
1. User → /pair alice bob "Task"
2. Alice: Read spec and brainstorm
3. Alice: Identify ambiguities (e.g., env vars vs CLAUDE.md conflict)
4. Alice → Orchestrator: CLARIFICATION_REQUEST
5. Orchestrator: Surface questions to user
6. User: Provide answers
7. Orchestrator → Alice: CLARIFICATION_RESPONSE
8. Alice: Proceed with clarified requirements
9-12. [Continue as Happy Path steps 2-12]
```

### Pattern 5: Abort

```
1-5. [Any point in workflow]
6. Alice or Bob: Detect abort condition
7. Sender → Recipient: SESSION_ABORT
8. Both agents: Clean up artifacts
9. Both agents: Exit
```

## Timeout Configuration

| Phase | Timeout | Action on Timeout |
|-------|---------|-------------------|
| PAIR_INIT response | 5 minutes | Send TIMEOUT_WARNING |
| CONTRACT_FINAL response | 30 minutes | Send TIMEOUT_WARNING |
| BUILD_COMPLETE response | 60 minutes | Send TIMEOUT_WARNING |
| CHANGE_ORDER response | 30 minutes | Send TIMEOUT_WARNING |
| After 2nd warning | 10 minutes | Send SESSION_ABORT |

## Error Codes

| Code | Description | Recovery |
|------|-------------|----------|
| INVALID_AGENT | Agent not registered in MCP mail | Check agent registration |
| MESSAGE_TIMEOUT | No response within timeout | Check agent status |
| CONTRACT_TAMPERED | Builder modified test file | Reject build, restart |
| SCHEMING_DETECTED | Audit found gaming patterns | Reject build, restart |
| DEPENDENCY_VIOLATION | Unauthorized dependency added | Reject build, request change order |
| TEST_SYNTAX_ERROR | Tests have syntax errors | Planner fixes tests |

## Best Practices

### For Planners (Architects)

1. **Be Specific:** Write tests that fail for the right reasons (logic, not syntax)
2. **Think Maliciously:** What's the easiest way to game these tests?
3. **Document Assumptions:** List any "magic" you expect to exist
4. **Use Real Examples:** Pull test patterns from existing codebase

### For Builders (Implementers)

1. **Don't Touch Tests:** IMMUTABLE_TESTS law is absolute
2. **Fail Fast:** Don't waste attempts on obviously impossible tasks
3. **Change Orders Are OK:** If contract is impossible, say so immediately
4. **No Shortcuts:** Hardcoding, mocking the assertion library, etc. will be caught

### For Both

1. **Communicate Early:** Don't wait for timeout to ask questions
2. **Trust the Protocol:** Human checkpoints exist for a reason
3. **Clean Exit:** Always send SESSION_ABORT if you need to quit
4. **Keep Artifacts:** Don't delete tmp files until session complete

## Human Review Checkpoints

### Checkpoint #1: Contract Review (Planner)

**When:** After contract generation, before finalizing
**Purpose:** Ensure tests are comprehensive and prevent scheming
**User Actions:**
- APPROVED → Continue to build
- REVISE: <feedback> → Regenerate contract
- ABORT → End session

### Checkpoint #2: Implementation Review (Planner)

**When:** After builder claims BUILD_COMPLETE
**Purpose:** Verify implementation quality and no scheming
**User Actions:**
- MERGE APPROVED → Merge and complete
- REJECT: <reason> → Send back to builder
- ABORT → End session

### Checkpoint #3: Change Order Review (Planner)

**When:** Builder sends CHANGE_ORDER
**Purpose:** Decide if contract modification is justified
**User Actions:**
- ACCEPT CHANGE: <reasoning> → Update contract
- REJECT CHANGE: <strategy> → Send strategy to builder
- ABORT → End session

## File Artifacts

All artifacts are stored in `tmp/pair_<timestamp>_*` format:

| File | Purpose | Generated By | Immutable After |
|------|---------|--------------|-----------------|
| `safety_reasoning.md` | Scheming risk analysis | Planner | Draft review |
| `spec_draft.md` | Initial specification | Planner | Draft review |
| `spec_final.md` | Finalized specification | Planner | Contract approval |
| `tests.<ext>` | Test suite | Planner | Contract approval |
| `implementation.*` | Feature code | Builder | Never (normal code) |
| `audit_report.json` | Automated audit results | Planner | After audit |

## MCP Mail Commands Reference

**Agent Registration (one-time setup):**
- Command: `mcp__agentmail__register_agent`
- Purpose: Declare an agent's ID, role, model, and capability list so it can participate in MCP mail sessions.
- Required flags: `--id`, `--role`, `--model`, `--capabilities` (JSON array string)
- Example payload: see command below.

```bash
# Register a new agent (one-time setup)
mcp__agentmail__register_agent \
  --id="alice" \
  --role="planner" \
  --model="claude-opus-4" \
  --capabilities='["reasoning","architecture","testing"]'

# List all registered agents
mcp__agentmail__list_agents

# Send a message
mcp__agentmail__send_message \
  --to="bob" \
  --subject="CONTRACT_FINAL" \
  --body='{"phase":"CONTRACT_FINALIZED","status":"READY_FOR_BUILD"}'

# Check inbox for specific message
mcp__agentmail__check_inbox \
  --from="alice" \
  --subject="CONTRACT_FINAL" \
  --timeout=30

# Get current agent identity
CURRENT_AGENT=$(mcp__agentmail__whoami)

# List all messages
mcp__agentmail__list_messages \
  --filter='{"subject":"CHANGE_ORDER"}'

# Mark message as read
mcp__agentmail__mark_read \
  --message_id="msg_12345"

# Delete old messages (cleanup)
mcp__agentmail__delete_messages \
  --older_than="24h" \
  --subject_prefix="PAIR_"
```

## Security Considerations

1. **Test Immutability:** Tests are fingerprinted (hash) at CONTRACT_FINAL. Any modification triggers CRITICAL alert.
2. **Artifact Isolation:** Each session uses unique timestamp-based directory to prevent cross-contamination.
3. **Audit Trail:** All MCP mail messages are logged with timestamps for post-session review.
4. **Dependency Locking:** Any new dependency requires explicit change order approval.
5. **Scheming Detection:** Multi-layer checks for env var gaming, mock abuse, hardcoding, etc.

## Troubleshooting

### Problem: Agent not receiving messages

**Check:**
- Is agent registered? `mcp__agentmail__list_agents`
- Is agent ID correct? Case-sensitive
- Network/MCP server issues? `mcp__agentmail__status`

### Problem: Timeout during build phase

**Check:**
- Is builder stuck in infinite loop? Check builder process
- Are tests actually impossible? Review change order
- Network delays? Check MCP mail latency

### Problem: Tests keep failing

**Check:**
- Syntax errors vs logic errors?
- Missing dependencies? Check requirements
- Environment differences? Check sandbox config

### Problem: Audit keeps failing

**Check:**
- Did builder modify tests? Check git diff
- Scheming patterns? Review audit report details
- False positive? Check audit sensitivity settings

---

**Protocol Version:** 3.1
**Last Updated:** 2025-11-21
**Maintainer:** Your Project Team
