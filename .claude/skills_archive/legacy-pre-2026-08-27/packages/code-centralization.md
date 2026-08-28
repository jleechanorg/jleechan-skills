# Code Centralization - Mandatory Investigation Protocol

**Purpose**: Before writing ANY new code, you MUST investigate existing code to prevent duplication. This is not optional.

## CRITICAL: Investigation Before Implementation

**DEFAULT: REUSE EXISTING CODE** - You must prove similar code doesn't already exist before writing new code.

### Mandatory Pre-Implementation Checklist

Before writing ANY new function, class, or module:

1. **Search for existing implementations**
   ```bash
   # Search for similar function names
   grep -r "def similar_name" --include="*.py"

   # Search for similar logic patterns
   grep -r "pattern_keyword" --include="*.py"

   # Search imports to find utility modules
   grep -r "from.*utils import" --include="*.py"
   ```

2. **Document what you found**
   - List ALL similar functions/modules discovered
   - Explain why each cannot be reused (or CAN be reused)

3. **Justify new code only if reuse is impossible**
   - "Couldn't find similar code" is only valid with search evidence
   - "Existing code doesn't quite fit" requires explanation of gap

### Evidence Required

```markdown
### Code Investigation for: <what you're implementing>

**Search performed:**
- `grep -r "keyword1" --include="*.py"` → Found: <results>
- `grep -r "keyword2" --include="*.py"` → Found: <results>

**Similar code found:**
- `file1.py:function_name()` - Does X, but not Y (can't reuse because...)
- `file2.py:other_function()` - Does Y, can be extended to also do X

**Decision:**
- [ ] Reuse existing: <which function>
- [ ] Extend existing: <which function + what extension>
- [ ] New code justified: <why reuse/extension impossible>
```

## Core Principle

**Duplication is a maintenance liability.** When the same logic exists in multiple places, changes must be made in multiple locations, increasing the risk of inconsistencies and bugs.

## When to Centralize

### Red Flags: Code That Should Be Centralized

1. **Identical Logic in Multiple Files**
   - Same `hasattr()` checks repeated
   - Same fallback logic duplicated
   - Same validation patterns copied

2. **Similar Patterns with Minor Variations**
   - Type coercion logic repeated with slight differences
   - Property accessors with same fallback chains
   - API response building with duplicated field handling

3. **Maintenance Burden**
   - Bug fixes require changes in multiple places
   - Feature additions need updates across files
   - Tests must cover the same logic multiple times

### Example: action_resolution/outcome_resolution Duplication

**Before (Duplicated Logic)**:

```python
# ❌ BAD - llm_response.py (22 lines)
@property
def action_resolution(self) -> dict[str, Any]:
    if self.structured_response:
        if hasattr(self.structured_response, "action_resolution"):
            ar = self.structured_response.action_resolution
            if ar is not None:
                return ar
        if hasattr(self.structured_response, "outcome_resolution"):
            or_val = self.structured_response.outcome_resolution
            if or_val is not None:
                return or_val
    return {}

# ❌ BAD - world_logic.py (13 lines) - Same logic duplicated
if hasattr(structured_response, "action_resolution"):
    action_resolution = getattr(structured_response, "action_resolution", None)
    if action_resolution is not None:
        unified_response["action_resolution"] = (
            action_resolution if isinstance(action_resolution, dict) else {}
        )
if hasattr(structured_response, "outcome_resolution"):
    outcome_resolution = getattr(structured_response, "outcome_resolution", None)
    if outcome_resolution is not None:
        unified_response["outcome_resolution"] = (
            outcome_resolution if isinstance(outcome_resolution, dict) else {}
        )
```

**After (Centralized)**:

```python
# ✅ GOOD - action_resolution_utils.py (single source of truth)
def get_action_resolution(structured_response: Any) -> dict[str, Any]:
    """Get action_resolution with backward compat fallback."""
    if structured_response is None:
        return {}
    if hasattr(structured_response, "action_resolution"):
        ar = structured_response.action_resolution
        if ar is not None:
            return ar
    if hasattr(structured_response, "outcome_resolution"):
        or_val = structured_response.outcome_resolution
        if or_val is not None:
            return or_val
    return {}

def add_action_resolution_to_response(structured_response: Any, unified_response: dict[str, Any]) -> None:
    """Add action_resolution/outcome_resolution to API response."""
    if structured_response is None:
        return
    if hasattr(structured_response, "action_resolution"):
        ar = getattr(structured_response, "action_resolution", None)
        if ar is not None:
            unified_response["action_resolution"] = (
                ar if isinstance(ar, dict) else {}
            )
    if hasattr(structured_response, "outcome_resolution"):
        or_val = getattr(structured_response, "outcome_resolution", None)
        if or_val is not None:
            unified_response["outcome_resolution"] = (
                or_val if isinstance(or_val, dict) else {}
            )

# ✅ GOOD - llm_response.py (2 lines)
@property
def action_resolution(self) -> dict[str, Any]:
    return get_action_resolution(self.structured_response)

# ✅ GOOD - world_logic.py (1 line)
add_action_resolution_to_response(structured_response, unified_response)
```

**Results**:
- **Before**: 35 lines of duplicated logic across 2 files
- **After**: 20 lines in helper module + 3 lines total in consuming files
- **Net reduction**: 12 lines + single source of truth

## TDD Approach to Centralization

### Step 1: Write Tests First (RED)

Before extracting code, write comprehensive tests for the helper functions:

```python
# ✅ GOOD - Test all edge cases before extraction
def test_get_action_resolution_with_action_resolution(self):
    """Test returns action_resolution when present"""
    mock_response = MagicMock()
    mock_response.action_resolution = {"player_input": "I attack"}
    result = get_action_resolution(mock_response)
    self.assertEqual(result["player_input"], "I attack")

def test_get_action_resolution_falls_back_to_outcome_resolution(self):
    """Test falls back to outcome_resolution when action_resolution missing"""
    # ... test implementation

def test_get_action_resolution_handles_none(self):
    """Test handles None structured_response"""
    result = get_action_resolution(None)
    self.assertEqual(result, {})

# ... 15+ more edge case tests
```

### Step 2: Extract Helper Functions (GREEN)

Create helper module with functions that make tests pass:

```python
# ✅ GOOD - Helper module with clear responsibilities
# $PROJECT_ROOT/action_resolution_utils.py

def get_action_resolution(structured_response: Any) -> dict[str, Any]:
    """Single source of truth for fallback logic."""
    # Implementation that passes all tests

def add_action_resolution_to_response(structured_response: Any, unified_response: dict[str, Any]) -> None:
    """API response builder with type coercion."""
    # Implementation that passes all tests
```

### Step 3: Refactor Existing Code (REFACTOR)

Replace duplicated logic with helper calls:

```python
# ✅ GOOD - Replace 22 lines with 1 function call
@property
def action_resolution(self) -> dict[str, Any]:
    return get_action_resolution(self.structured_response)
```

### Step 4: Verify No Regressions

Run all existing tests to ensure behavior unchanged:

```bash
# ✅ GOOD - Verify backward compatibility
pytest $PROJECT_ROOT/tests/test_action_resolution.py
pytest $PROJECT_ROOT/tests/test_end2end/test_action_resolution_backward_compat_end2end.py
pytest $PROJECT_ROOT/tests/test_action_resolution_utils.py  # New helper tests
```

## Helper Module Design Principles

### 1. Single Responsibility

Each helper function should do one thing well:

```python
# ✅ GOOD - Clear, focused function
def get_action_resolution(structured_response: Any) -> dict[str, Any]:
    """Get action_resolution with backward compat fallback."""
    # Only handles retrieval logic

# ❌ BAD - Does too much
def process_action_resolution(structured_response: Any, validate: bool, coerce: bool) -> dict[str, Any]:
    """Gets, validates, and coerces action_resolution."""
    # Mixes retrieval, validation, and coercion
```

### 2. Backward Compatibility

Helper functions must maintain exact same behavior:

```python
# ✅ GOOD - Preserves empty dict {} as "present" (not None)
if ar is not None:  # Empty dict {} passes this check
    return ar

# ❌ BAD - Would break existing behavior
if ar:  # Empty dict {} fails this check
    return ar
```

### 3. Type Safety

Handle None and invalid types gracefully:

```python
# ✅ GOOD - Defensive None checks
if structured_response is None:
    return {}

# ✅ GOOD - Type coercion for API responses
unified_response["action_resolution"] = (
    action_resolution if isinstance(action_resolution, dict) else {}
)
```

### 4. Clear Naming

Function names should clearly indicate purpose:

```python
# ✅ GOOD - Self-documenting names
get_action_resolution()  # Retrieves with fallback
add_action_resolution_to_response()  # Adds to API response

# ❌ BAD - Ambiguous names
process_resolution()  # What does it do?
handle_action()  # Too generic
```

## When NOT to Centralize

### Keep Separate If:

1. **Different Purposes**
   - Initialization-time validation vs runtime property access
   - Schema normalization vs API response building
   - Different contexts require different logic

2. **Performance Critical**
   - Inline logic avoids function call overhead
   - Hot paths where microseconds matter
   - (Rare - usually premature optimization)

3. **Tight Coupling**
   - Logic is tightly coupled to specific class internals
   - Extraction would require exposing private state
   - Helper would need too many parameters

**Example**: `narrative_response_schema.py` initialization logic stays separate because it handles validation/normalization at object creation time, which is different from runtime property access.

## Test Coverage Requirements

### Before Refactoring

Ensure existing tests provide safety net:

- ✅ Unit tests for schema layer
- ✅ End-to-end tests for integration paths
- ✅ Edge case coverage (None, empty dict, type coercion)

### After Extraction

Add comprehensive tests for helpers:

- ✅ Unit tests for each helper function
- ✅ Edge cases (None, empty dict, invalid types)
- ✅ Backward compatibility verification
- ✅ Integration tests with refactored code

**Minimum**: 15-20 test cases per helper function to cover all edge cases.

## Code Reduction Metrics

Track improvements:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lines of duplicated logic | 35 | 0 | -35 lines |
| Helper module lines | 0 | 20 | +20 lines |
| Consuming code lines | 35 | 3 | -32 lines |
| **Net change** | 35 | 23 | **-12 lines** |
| **Test coverage** | 19 tests | 37 tests | **+18 tests** |

## Banned Patterns (ZERO TOLERANCE)

These patterns are **explicitly banned** and must never appear in code:

### 1. `_v2`/`_new`/`_backup`/`_old` File Names

```python
# ❌ BANNED - Never create these files
auth_service_v2.py      # Edit the original instead
user_model_new.py       # Edit the original instead
config_backup.py        # Use git for backups
helper_old.py           # Delete and replace

# ✅ CORRECT - Edit existing files directly
auth_service.py         # Modify in place
user_model.py           # Modify in place
```

**Why banned:** Creates confusion about which file is authoritative. Use git for version history.

### 2. "Pre-existing Issue" Excuse

```python
# ❌ BANNED PHRASES - Never use these
"This is a pre-existing issue"
"This test was already failing"
"Not caused by my changes"
"Unrelated to this PR"

# ✅ CORRECT - Fix ALL failures
# If a test fails vs origin/main, FIX IT. No excuses.
```

**Why banned:** All test failures must be fixed in the current PR. There are no "pre-existing" issues - if it fails, fix it.

### 3. Direct `import logging` (in `$PROJECT_ROOT/`)

```python
# ❌ BANNED - Direct logging module in $PROJECT_ROOT/
import logging
logger = logging.getLogger(__name__)
logger.info("message")

# ✅ CORRECT - Use unified logging_util
from mvp_site import logging_util
logging_util.info("message")
logging_util.warning("something concerning")
logging_util.error("something failed")
```

**Why banned:** `logging_util` provides unified output to both GCP Cloud Logging and local files with consistent formatting. Direct `import logging` bypasses this.

**Exception:** Test files (`$PROJECT_ROOT/tests/*`) may use direct logging.

---

## Anti-Patterns

### ❌ Premature Centralization

Don't extract code that's only used once:

```python
# ❌ BAD - Over-engineering for single use
def get_single_use_helper():
    """Only called once - not worth extracting"""
    pass
```

### ❌ Over-Abstracting

Don't create helpers that are harder to use than inline code:

```python
# ❌ BAD - More complex than original
def process_with_fallback(obj, primary_field, fallback_field, default_value, type_check, coerce_func):
    """Too many parameters - harder to use than inline"""
    pass

# ✅ GOOD - Simple, focused helper
def get_action_resolution(structured_response: Any) -> dict[str, Any]:
    """Clear purpose, minimal parameters"""
    pass
```

### ❌ Breaking Backward Compatibility

Don't change behavior when centralizing:

```python
# ❌ BAD - Changed behavior (empty dict now returns fallback)
if ar:  # Changed from "if ar is not None"
    return ar

# ✅ GOOD - Preserves exact behavior
if ar is not None:  # Same as original
    return ar
```

## Checklist for Centralization

Before extracting duplicated code:

- [ ] Identified 2+ locations with similar logic
- [ ] Written comprehensive tests for helper functions (TDD)
- [ ] Verified existing tests provide safety net
- [ ] Extracted helper functions that pass all tests
- [ ] Refactored consuming code to use helpers
- [ ] All existing tests still pass (no regressions)
- [ ] Helper functions have 15+ test cases covering edge cases
- [ ] Code reduction achieved (net lines saved)
- [ ] Documentation updated if needed

## Related Patterns

- **DRY Principle**: Don't Repeat Yourself
- **Single Source of Truth**: One place for each piece of logic
- **Test-Driven Development**: Write tests before refactoring
- **Backward Compatibility**: Maintain exact same behavior

## Real-World Example

See `$PROJECT_ROOT/action_resolution_utils.py` for a complete example:
- Helper functions with comprehensive tests
- Refactored `llm_response.py` and `world_logic.py`
- 37 tests passing (18 new + 19 existing)
- 20 lines saved + eliminated duplication
