---
name: generalized-testing
description: "Generate comprehensive, systematic test suites for any system component using a structured test design methodology. Creates tests that catch real bugs through state lifecycle, integration, and consistency testing."
---

# Generalized Test Suite Generation

## Overview

Generate comprehensive test suites for any system component by systematically analyzing failure modes, state transitions, and integration points. This methodology is derived from the successful modal state management test suite that caught routing consistency bugs.

## The Process

### 1. Understanding the Component

**Analyze the system you're testing:**
- Read the production code to understand behavior
- Identify state variables and flags
- Map out decision points and routing logic
- Review recent bug fixes for patterns

**Ask clarifying questions:**
- What are the critical behaviors this component must maintain?
- What state does it manage?
- How does it interact with other components?
- What bugs have occurred recently?

### 2. Test Architecture Planning

**Ask these questions one at a time:**

1. **Test Organization**: Single file, modular by concern, or hybrid with base class?
   - Recommend: Hybrid (base class + specialized files) for code reuse

2. **Test Data Strategy**: Factory functions, builder pattern, or fixture dataclasses?
   - Recommend: Fixture dataclasses for declarative, parametrized testing

3. **Component Coverage**: Which components/subsystems to prioritize?
   - Recommend: Start focused on problem areas, design for extensibility

4. **Assertion Strategy**: Direct assertions, snapshot-based, or custom semantic helpers?
   - Recommend: Custom semantic helpers for readability and maintenance

5. **Test Execution Level**: Pure unit tests, integration via public APIs, or hybrid?
   - Recommend: Integration tests for catching real interaction bugs

6. **Advanced Testing**: Include property-based tests now or later?
   - Recommend: Start without, document opportunities for later

### 3. Test Categories to Design

**State Lifecycle Tests**
- Initial state → Active state → Complete/Cancel state
- Flag clearing when new conditions trigger
- Stale flag removal (not just setting to False)
- Sequential operations maintaining clean state

**Cross-Component Interaction Tests**
- Component A exit cleans up flags from Component B
- Component B activation with stale flags from Component A
- Priority ordering when multiple conditions exist

**Logic Consistency Tests**
- Compare decision point A vs decision point B
- Ensure all code paths use identical checks
- Detect drift between parallel implementations

**Property-Based Invariants** (document for later)
- At most one component active at a time
- Mutually exclusive conditions
- State cleanup always completes

### 4. Creating the Test Suite

**File Structure Pattern:**
```
tests/
├── test_<component>_base.py           # Base class + fixtures + assertions
├── test_<component>_lifecycle.py      # State transition tests
└── test_<component>_integration.py    # Cross-component + consistency tests
```

**Base Class Components:**
```python
@dataclass
class TestScenario:
    name: str
    initial_state: dict
    action: Callable | str
    expected_state: dict
    description: str = ""

class TestBase(unittest.TestCase):
    # Custom assertion helpers (semantic)
    def assert_no_component_active(self, state): ...
    def assert_only_component_active(self, state, name): ...
    def assert_stale_flags_cleared(self, state, component): ...
    def assert_logic_consistency(self, state, action): ...

    # Scenario execution
    def run_scenario(self, scenario: TestScenario): ...

    # Test fixtures
    def create_base_state(self, **kwargs): ...
```

**Test Pattern:**
```python
def test_<bug_or_behavior_description>(self):
    """
    BUG FIX TEST or BEHAVIOR TEST:
    Clear description of what this verifies and why it matters.
    """
    scenario = TestScenario(
        name="descriptive_name",
        initial_state=self.create_base_state(...),
        action="user_action" or callable,
        expected_state={...},
        description="Why this test matters"
    )
    self.run_scenario(scenario)
```

### 5. Validation

**Tests must:**
- ✅ Pass with current correct code
- ❌ Fail if we revert recent bug fixes
- ✅ Use integration-level testing (public APIs)
- ✅ Have clear, informative failure messages
- ✅ Be maintainable and well-documented

**Run tests and verify:**
```bash
pytest tests/test_<component>_*.py -v
```

## Key Principles

**1. Test Real Failure Modes**
- Look at recent bug fixes for patterns
- Tests should have caught those bugs if they existed earlier

**2. Use Semantic Assertions**
- `assert_no_modal_active()` > `assert state["flag"] is None`
- Makes tests self-documenting
- Easier to maintain

**3. Declarative Test Scenarios**
- Dataclass scenarios over imperative test code
- Easy to add new scenarios
- Clear what's being tested

**4. Integration Over Unit**
- Test via public APIs, not internal functions
- Catches real interaction bugs
- More realistic test coverage

**5. Design for Extensibility**
- Start focused, design base class for easy expansion
- Document where property-based tests could add value
- YAGNI but stay prepared

## Example: Modal State Management Tests

**Context**: Modal routing system with character creation, level-up, and campaign upgrade modals.

**Bugs Found**:
- Stale `level_up_in_progress=False` blocking future level-ups
- `character_creation_in_progress` not cleared on level-up exit
- Routing and injection logic using different active detection

**Test Suite Created**:
- 22 tests across 3 files
- 6 custom semantic assertions
- Dataclass-driven scenarios
- All tests pass, would have caught all 3 bugs

**Files**:
- `test_modal_base.py`: Base class, fixtures, assertions
- `test_modal_state_lifecycle.py`: 11 state transition tests
- `test_modal_integration.py`: 11 cross-modal and consistency tests

## After Creating Tests

**Documentation:**
- Commit tests with clear message referencing bugs caught
- Update test documentation with patterns and lessons
- Link to design beads or tickets

**Maintenance:**
- Run tests in CI
- Keep tests updated as system evolves
- Add new scenarios when new bugs are discovered

## Common Patterns

**State Transition Pattern:**
```python
def test_state_clears_stale_flags():
    """When condition X triggers, stale flags Y should be removed."""
    # initial_state with stale flags
    # action that triggers new condition
    # verify flags removed (not just set False)
```

**Cross-Component Pattern:**
```python
def test_component_exit_cleans_all_flags():
    """Exiting component A clears flags from ALL components."""
    # initial_state with mixed flags
    # exit action
    # verify ALL component flags cleared
```

**Consistency Pattern:**
```python
def test_decision_points_agree():
    """Decision point A and B must use identical logic."""
    # state that could be ambiguous
    # check both decision points
    # verify they agree on outcome
```

## Meta-Advice

**When to use this skill:**
- After fixing multiple related bugs
- When adding complex stateful features
- When refactoring critical system components
- When tests are missing for problem areas

**When NOT to use:**
- Simple, well-tested features
- Components with no state management
- Systems that already have comprehensive tests

**Success metrics:**
- Tests catch real bugs when code is reverted
- New bugs in this area are caught by existing tests
- Test suite is maintainable and well-documented
- Team uses tests as documentation

## Integration with Other Skills

- Use `/tdd` for test-first development
- Use `/review-enhanced` to validate test coverage
- Use `/fake3` to detect test quality issues
- Use `/solid` to ensure testable code design
