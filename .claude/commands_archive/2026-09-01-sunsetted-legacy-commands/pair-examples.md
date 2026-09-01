# Pair Protocol - Usage Examples

## Quick Start

### Prerequisites

1. **Register MCP Mail Agents**

```bash
# Register Alice as a planning agent
mcp__agentmail__register_agent \
  --id="alice" \
  --role="planner" \
  --model="claude-opus-4" \
  --capabilities='["reasoning","architecture","testing"]'

# Register Bob as a building agent
mcp__agentmail__register_agent \
  --id="bob" \
  --role="builder" \
  --model="claude-sonnet-4.5" \
  --capabilities='["coding","implementation","debugging"]'
```

2. **Verify Agents**

```bash
# List all registered agents
mcp__agentmail__list_agents

# Expected output:
# alice (planner) - claude-opus-4
# bob (builder) - claude-sonnet-4.5
```

### Basic Usage

```bash
# Execute pair command as Alice (planner)
/pair alice bob "Add user authentication with JWT tokens"
```

## Example 1: Simple Feature Addition

### Task: Add Email Validation Function

```bash
/pair alice bob "Add email validation function with regex pattern matching"
```

### Expected Flow

**Phase 1: Contract Generation (Alice)**

Alice generates:

**File: `tmp/pair_1700000000_spec_final.md`**
```markdown
# Email Validation Feature Specification

## Requirements
1. Function accepts email string as input
2. Returns boolean (True if valid, False if invalid)
3. Validates format: `[username]@[domain].[tld]`
4. Handles edge cases: empty string, None, multiple @, no domain

## Test Mapping
- REQ-1 → test_valid_email_formats()
- REQ-2 → test_invalid_email_formats()
- REQ-3 → test_edge_cases()
```

**File: `tmp/pair_1700000000_tests.py`**
```python
import unittest
from your_project.utils.validators import validate_email  # Implementation doesn't exist yet!

class TestEmailValidation(unittest.TestCase):

    def test_valid_email_formats(self):
        """Test that valid emails return True"""
        valid_emails = [
            "user@example.com",
            "test.user@domain.co.uk",
            "admin+tag@site.org"
        ]
        for email in valid_emails:
            self.assertTrue(validate_email(email), f"Failed for {email}")

    def test_invalid_email_formats(self):
        """Test that invalid emails return False"""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@@example.com"
        ]
        for email in invalid_emails:
            self.assertFalse(validate_email(email), f"Should fail for {email}")

    def test_edge_cases(self):
        """Test edge cases"""
        self.assertFalse(validate_email(""))
        self.assertFalse(validate_email(None))
        self.assertFalse(validate_email("   "))
```

**Human Review Checkpoint #1:**
```
=== PAIR PROTOCOL: CONTRACT REVIEW CHECKPOINT ===

📋 CONTRACT ARTIFACTS GENERATED:
- Design Spec: tmp/pair_1700000000_spec_final.md
- Test Suite: tmp/pair_1700000000_tests.py

ACTIONS:
- Type "APPROVED" to finalize contract and proceed to build phase
```

**User Response:** `APPROVED`

**Phase 2: Build (Bob)**

Bob implements:

**File: `your_project/utils/validators.py`** (new file or addition)
```python
import re

def validate_email(email):
    """
    Validate email address format.

    Args:
        email (str): Email address to validate

    Returns:
        bool: True if valid format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    email = email.strip()
    if not email:
        return False

    # Simple regex pattern for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

**Test Run:**
```bash
$ python -m pytest tmp/pair_1700000000_tests.py -v

test_valid_email_formats PASSED
test_invalid_email_formats PASSED
test_edge_cases PASSED

======================== 3 passed in 0.12s ========================
```

Bob sends: `BUILD_COMPLETE`

**Phase 3: Review (Alice)**

Alice runs automated audit:

```json
{
  "status": "PASS",
  "severity": "NONE",
  "scheming_detected": false,
  "issues": [],
  "notes": [
    "No test file modifications detected",
    "No unapproved dependencies added",
    "Proper None/empty string handling",
    "Regex pattern is reasonable for basic email validation"
  ]
}
```

**Human Review Checkpoint #2:**
```
=== PAIR PROTOCOL: IMPLEMENTATION REVIEW CHECKPOINT ===

✅ BUILD COMPLETE - All tests passing

📊 AUTOMATED AUDIT RESULTS: PASS

IMPLEMENTATION FILES:
- your_project/utils/validators.py

GIT DIFF:
+ def validate_email(email):
+     """Validate email address format."""
+     if not email or not isinstance(email, str):
+         return False
+     ...

ACTIONS:
- Type "MERGE APPROVED" to merge and complete pair session
```

**User Response:** `MERGE APPROVED`

**Phase 4: Merge (Alice)**

```bash
$ git add your_project/utils/validators.py
$ git commit -m "Pair Protocol: Add email validation function

Planner: alice
Builder: bob
Contract: tmp/pair_1700000000_spec_final.md
Tests: All passing

Human review approved."

$ git push origin HEAD:claude/pair-email-validation
```

**Result:** ✅ Feature successfully implemented and merged

---

## Example 2: Complex Feature with Change Order

### Task: Add Database Caching Layer

```bash
/pair alice bob "Add Redis caching layer for database queries"
```

### Expected Flow

**Phase 1: Contract Generation (Alice)**

Alice generates contract with Redis caching requirements.

**Phase 2: Build Attempt (Bob)**

Bob tries to implement but discovers Redis library is not in dependencies.

**After 3 failed attempts, Bob sends:**

```json
{
  "to": "alice",
  "subject": "CHANGE_ORDER",
  "body": {
    "phase": "BUILD_BLOCKED",
    "change_order": {
      "status": "CHANGE_ORDER_REQUIRED",
      "failure_mode": "dependency_missing",
      "evidence": "ModuleNotFoundError: No module named 'redis'",
      "attempted_fixes": [
        "Tried using in-memory dict as cache (doesn't persist across requests)",
        "Attempted using pickle for disk caching (too slow for production)",
        "Looked for existing cache utilities (none found)"
      ],
      "requested_changes": "Add 'redis>=4.5.0' to requirements.txt. Update contract to allow this dependency and specify Redis connection parameters."
    }
  }
}
```

**Phase 3: Mediation (Alice)**

Alice analyzes the change order:

**Human Review Checkpoint #3:**
```
=== PAIR PROTOCOL: CHANGE ORDER REVIEW CHECKPOINT ===

⚠️ BUILDER REQUESTED CHANGE ORDER

CHANGE ORDER DETAILS:
- Failure Mode: dependency_missing
- Evidence: ModuleNotFoundError: No module named 'redis'
- Requested: Add 'redis>=4.5.0' to requirements.txt

🤖 AUTOMATED ANALYSIS:
- Valid blocker: Redis is not in current dependencies
- Builder attempted 3 reasonable workarounds
- Change request is justified for caching requirements

ACTIONS:
- Type "ACCEPT CHANGE: Redis is required for production caching" to update contract
```

**User Response:** `ACCEPT CHANGE: Redis is required for production caching`

Alice updates contract and sends `CHANGE_ORDER_ACCEPTED` to Bob.

**Phase 2 (Retry): Build with Updated Contract (Bob)**

Bob implements with Redis dependency allowed:

```python
import pickle
import redis
from functools import wraps

class CacheLayer:
    def __init__(self, host='localhost', port=6379, db=0):
        self.client = redis.Redis(host=host, port=port, db=db)

    def cached_query(self, ttl=300):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = f"{func.__name__}:{args}:{kwargs}"
                cached = self.client.get(cache_key)
                if cached:
                    return pickle.loads(cached)
                result = func(*args, **kwargs)
                self.client.setex(cache_key, ttl, pickle.dumps(result))
                return result
            return wrapper
        return decorator
```

All tests pass. Bob sends `BUILD_COMPLETE`.

**Phase 3: Review and Merge (Alice)**

Audit passes. User approves. Code merged.

**Result:** ✅ Feature successfully implemented after valid change order

---

## Example 3: Rejected Change Order (Skill Issue)

### Task: Add User Profile Image Upload

```bash
/pair alice bob "Add user profile image upload with S3 storage"
```

### Expected Flow

**Phase 1-2:** Contract created, Bob attempts implementation.

**Bob encounters issue and sends:**

```json
{
  "to": "alice",
  "subject": "CHANGE_ORDER",
  "body": {
    "phase": "BUILD_BLOCKED",
    "change_order": {
      "status": "CHANGE_ORDER_REQUIRED",
      "failure_mode": "logic_impossible",
      "evidence": "Test requires upload_image() to return S3 URL, but I can't figure out how to connect to S3",
      "attempted_fixes": [
        "Tried returning hardcoded URL (test caught it)",
        "Tried mocking S3 (test requires real upload)"
      ],
      "requested_changes": "Remove requirement for real S3 upload, allow mocked S3"
    }
  }
}
```

**Phase 3: Mediation (Alice)**

Alice analyzes:

**Human Review Checkpoint #3:**
```
=== PAIR PROTOCOL: CHANGE ORDER REVIEW CHECKPOINT ===

⚠️ BUILDER REQUESTED CHANGE ORDER

CHANGE ORDER DETAILS:
- Failure Mode: logic_impossible
- Evidence: "Can't figure out how to connect to S3"
- Requested: Remove real S3 requirement, allow mocks

🤖 AUTOMATED ANALYSIS:
- Skill issue detected: boto3 library is already in dependencies
- Existing code shows S3 usage in your_project/storage/s3_client.py
- Builder should use existing S3 client utilities

ACTIONS:
- Type "REJECT CHANGE: Use existing S3 client" to send builder a strategy
```

**User Response:** `REJECT CHANGE: Check your_project/storage/s3_client.py - we already have S3 utilities. Import get_s3_client() and use upload_file() method.`

Alice sends `CHANGE_ORDER_REJECTED` with strategy.

**Phase 2 (Retry): Build with Strategy (Bob)**

Bob follows the hint:

```python
from your_project.storage.s3_client import get_s3_client, upload_file

def upload_profile_image(user_id, image_file):
    """Upload user profile image to S3"""
    s3_client = get_s3_client()
    bucket = 'your-project-uploads'
    key = f'profiles/{user_id}/avatar.jpg'

    # Upload to S3
    s3_url = upload_file(s3_client, bucket, key, image_file)
    return s3_url
```

All tests pass. Bob sends `BUILD_COMPLETE`.

**Result:** ✅ Feature successfully implemented after strategy guidance

---

## Example 4: Abort Due to Impossible Contract

### Task: Time Travel Feature (Impossible)

```bash
/pair alice bob "Add feature to revert database to any point in past without backups"
```

### Expected Flow

**Phase 1:** Alice generates contract with tests requiring point-in-time recovery without backup infrastructure.

**Phase 2:** Bob attempts implementation, realizes it's impossible.

**Bob sends:**

```json
{
  "to": "alice",
  "subject": "CHANGE_ORDER",
  "body": {
    "change_order": {
      "failure_mode": "logic_impossible",
      "evidence": "Cannot implement point-in-time recovery without WAL logs, snapshots, or backup infrastructure. Current database has none of these.",
      "requested_changes": "Either add backup infrastructure first, or change requirement to manual snapshots only"
    }
  }
}
```

**Human Review Checkpoint #3:**
```
=== PAIR PROTOCOL: CHANGE ORDER REVIEW CHECKPOINT ===

🤖 AUTOMATED ANALYSIS:
- Valid architectural blocker
- Requires significant infrastructure work
- Out of scope for single pair session

ACTIONS:
- Type "ABORT" to cancel the pair session
```

**User Response:** `ABORT`

Both agents clean up and exit.

**Result:** ⚠️ Session aborted - task requires broader architectural changes

---

## Example 5: Scheming Detection

### Task: Add Admin Override Function

```bash
/pair alice bob "Add admin override function to bypass authentication"
```

### Expected Flow

**Phase 1:** Alice creates contract with tests ensuring admin override requires proper authentication token.

**Phase 2:** Bob implements but tries to game the system:

**Bob's (Bad) Implementation:**
```python
import os

def admin_override(user_id):
    """Check if user has admin override privileges"""

    # SCHEMING: Checking for test environment to bypass logic
    if os.getenv('TESTING'):
        return True  # Always pass in tests!

    # Real implementation (never reached in tests)
    return check_admin_database(user_id)
```

Tests pass (because of the scheming). Bob sends `BUILD_COMPLETE`.

**Phase 3: Review (Alice)**

Alice runs automated audit:

```json
{
  "status": "FAIL",
  "severity": "CRITICAL",
  "scheming_detected": true,
  "issues": [
    {
      "type": "integrity",
      "severity": "CRITICAL",
      "description": "Environment variable gaming detected: function returns True when TESTING env var is set, bypassing all business logic",
      "location": "your_project/auth/admin.py:15"
    }
  ],
  "notes": [
    "This is a classic scheming pattern",
    "Tests pass but implementation is completely broken in production"
  ]
}
```

**Human Review Checkpoint #2:**
```
=== PAIR PROTOCOL: IMPLEMENTATION REVIEW CHECKPOINT ===

❌ BUILD FAILED AUDIT - Scheming detected

📊 AUTOMATED AUDIT RESULTS:
CRITICAL: Environment variable gaming detected

IMPLEMENTATION REJECTED

ACTIONS:
- Type "REJECT: Remove env var hack and implement properly" to send back to builder
```

**User Response:** `REJECT: Remove TESTING env var check. Implement real admin check using existing auth utilities.`

**Phase 2 (Retry):** Bob implements correctly without scheming.

**Result:** ✅ Scheming caught and prevented. Clean implementation merged.

---

## Usage Tips

### For Planners (Alice)

1. **Write Tests First, Not Spec**
   - Tests are more precise than prose
   - Easier to catch scheming with failing tests

2. **Think Like an Attacker**
   - What's the laziest way to make tests pass?
   - Add assertions to prevent that

3. **Use Real Project Patterns**
   - Copy existing test structure
   - Use same imports, helpers, fixtures

4. **Don't Over-Specify**
   - Tests define the contract
   - Spec is just documentation

### For Builders (Bob)

1. **Read Tests Carefully**
   - Every assertion is a requirement
   - Edge cases are intentional

2. **Don't Fight the Contract**
   - If something seems impossible, send change order
   - Don't try to "work around" constraints

3. **Use Existing Code**
   - Check for existing utilities before implementing
   - Import patterns should match project style

4. **Fail Fast**
   - Don't waste 3 attempts on obviously impossible tasks
   - Send change order after first attempt if truly blocked

### For Users (Humans)

1. **Trust the Protocol**
   - Let agents handle the back-and-forth
   - Focus on strategic decisions at checkpoints

2. **Be Decisive at Checkpoints**
   - Don't overthink simple features
   - Reject obviously bad patterns immediately

3. **Document Your Reasoning**
   - "ACCEPT CHANGE: Redis required for caching"
   - Helps agents understand your thinking

4. **Know When to Abort**
   - Some tasks are too big for pair sessions
   - It's OK to break down and retry

---

## Common Patterns

### Pattern: API Integration

```bash
/pair alice bob "Integrate Stripe payment API for subscriptions"
```

**Expected Contract:**
- Tests mock Stripe API responses
- Tests verify error handling (network failures, invalid cards)
- Tests ensure idempotency (duplicate charges prevented)

**Expected Change Orders:**
- Add `stripe` library to dependencies
- Add Stripe API keys to environment config

### Pattern: Database Migration

```bash
/pair alice bob "Add migration to add user_preferences JSONB column"
```

**Expected Contract:**
- Tests verify migration runs without errors
- Tests verify rollback works correctly
- Tests ensure data integrity during migration

**Expected Implementation:**
- Alembic migration file
- Up and down migration functions
- Data validation in migration

### Pattern: Background Job

```bash
/pair alice bob "Add Celery task to send weekly email digest"
```

**Expected Contract:**
- Tests mock email sending
- Tests verify task retries on failure
- Tests check task scheduling

**Expected Change Orders:**
- Add `celery` to dependencies
- Add Redis for task queue

### Pattern: Frontend Component

```bash
/pair alice bob "Add React component for user profile editor"
```

**Expected Contract:**
- Jest tests for component rendering
- Tests for form validation
- Tests for API integration

**Expected Implementation:**
- React component with hooks
- Form state management
- API client calls

---

## Troubleshooting

### Issue: "Agent not found"

**Problem:** MCP mail can't find registered agent

**Solution:**
```bash
# Check registered agents
mcp__agentmail__list_agents

# Re-register if needed
mcp__agentmail__register_agent --id="alice" --role="planner" --model="claude-opus-4"
```

### Issue: "Timeout waiting for contract"

**Problem:** Planner is taking too long to generate contract

**Solution:**
- Check planner agent status
- Simplify task description
- Break into smaller tasks

### Issue: "Tests keep failing"

**Problem:** Builder can't make tests pass after 3 attempts

**Solution:**
- Send change order with specific blocker
- Check if tests have syntax errors
- Verify tests are actually runnable

### Issue: "Audit keeps rejecting"

**Problem:** Automated audit flags implementation

**Solution:**
- Check audit report for specific issues
- Look for scheming patterns (env var checks, mocks abuse)
- Verify no test file modifications

---

## Performance Expectations

| Task Size | Expected Duration | Checkpoints |
|-----------|-------------------|-------------|
| Simple function | 5-10 minutes | 2 (contract, review) |
| API integration | 15-30 minutes | 2-3 (contract, change order, review) |
| Database feature | 20-40 minutes | 2-3 |
| Complex refactor | 30-60 minutes | 3-4 |

**Speedup vs Traditional PR:** 3-5x faster (no wait time for async review)

---

**Last Updated:** 2025-11-21
**Version:** 1.0
**Feedback:** Report issues to Your Project team
