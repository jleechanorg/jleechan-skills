# Dice Roll Authenticity Standards

## Overview

This document defines the standards for verifying dice roll authenticity in Your Project. It covers statistical validation (chi-squared testing) and code-level RNG verification.

## The Fabrication Problem

LLMs can "fabricate" dice rolls by outputting dice values without using actual random number generation:

```python
# FABRICATION - No actual RNG call!
print('{"rolls": [16], "total": 21}')  # Hardcoded values

# VALID - Uses actual RNG
import random
roll = random.randint(1, 20)
print(f'{{"rolls": [{roll}], "total": {roll + 5}}}')
```

## Chi-Squared Test

### What It Is

A statistical test measuring whether observed dice rolls match expected random distribution.

### Formula

```
χ² = Σ [(observed - expected)² / expected]
```

For a d20 with N total rolls:
- Expected frequency per face: N / 20
- Compare observed counts for each face (1-20)

### Interpretation Thresholds

| Chi-Squared Value | Interpretation | Action |
|-------------------|----------------|--------|
| 0-19 | Excellent - Highly uniform | Pass |
| 19-30 | Normal - Expected random variation | Pass |
| 30-50 | Suspicious - Minor anomaly | Investigate |
| 50-100 | Concerning - Significant deviation | Flag for review |
| 100-200 | Very unlikely from true RNG | Likely fabrication |
| 200+ | Statistically impossible | Confirmed fabrication |
| **411.81** | Reference: PR #2551 bug | Known fabrication case |

### Sample Size Requirements

| Die Type | Minimum Rolls | Recommended |
|----------|---------------|-------------|
| d4 | 40 | 100+ |
| d6 | 60 | 150+ |
| d20 | 200 | 500+ |

Chi-squared is unreliable with small sample sizes.

### Python Implementation

```python
from scipy import stats
import numpy as np

def chi_squared_test(rolls: list[int], die_size: int = 20) -> dict:
    """
    Test dice roll distribution for uniformity.

    Returns:
        dict with chi2 value, p_value, and verdict
    """
    observed = np.zeros(die_size)
    for roll in rolls:
        if 1 <= roll <= die_size:
            observed[roll - 1] += 1

    expected = len(rolls) / die_size
    expected_array = np.full(die_size, expected)

    chi2, p_value = stats.chisquare(observed, expected_array)

    # Interpret results
    if chi2 < 30:
        verdict = "PASS - Normal random variation"
    elif chi2 < 50:
        verdict = "WARNING - Minor anomaly"
    elif chi2 < 100:
        verdict = "FAIL - Significant deviation"
    else:
        verdict = "FAIL - Likely fabrication"

    return {
        "chi_squared": chi2,
        "p_value": p_value,
        "sample_size": len(rolls),
        "verdict": verdict,
        "distribution": dict(zip(range(1, die_size + 1), observed.astype(int).tolist()))
    }
```

## RNG Verification (Code-Level)

### The Problem with Substring Matching

Old approach (vulnerable):
```python
# VULNERABLE - Can be fooled by strings
def _code_contains_rng(code_text: str) -> bool:
    return "random.randint" in code_text  # Matches string literals!
```

### AST-Based Detection (Current Standard)

The fix uses Abstract Syntax Tree parsing to detect **actual function calls**:

```python
import ast

def _code_contains_rng(code_text: str) -> bool:
    """Detect actual RNG function calls using AST parsing."""
    tree = ast.parse(code_text)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if it's a real random.randint() call
            target = _get_call_target(node.func)
            if target in RNG_PATTERNS:
                return True
    return False
```

### Verified RNG Patterns

| Module | Functions |
|--------|-----------|
| `random` | `randint`, `choice`, `random`, `uniform`, `randrange`, `sample`, `shuffle` |
| `secrets` | `randbelow`, `choice` |
| `numpy.random` | `randint`, `choice`, `random`, `uniform`, `integers`, `permutation`, `randrange`, `sample`, `shuffle` |

### Evidence Fields

The `extract_code_execution_evidence()` function returns evidence that is saved to Firestore `story.debug_info`:

| Field | Type | Meaning |
|-------|------|---------|
| `code_execution_used` | bool | Code was executed |
| `executable_code_parts` | int | Count of code blocks executed |
| `code_execution_result_parts` | int | Count of execution results |
| `code_contains_rng` | bool | RNG function found in code |
| `rng_verified` | bool | `code_execution_used AND code_contains_rng` |
| `stdout` | str | JSON output from code execution (dice results) |
| `stdout_is_valid_json` | bool | Output is valid JSON |
| `executed_code` | list[str] | **Actual Python code executed** (for audit) |

### Querying Code Execution Evidence from Firestore

```python
# Query recent story entries to check code execution evidence
from mvp_site.clock_skew_credentials import apply_clock_skew_patch
apply_clock_skew_patch()

import firebase_admin
from firebase_admin import auth, firestore, credentials

cred = credentials.Certificate('~/serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Get story entry
user_record = auth.get_user_by_email('user@example.com')
campaign_ref = db.collection('users').document(user_record.uid).collection('campaigns').document('<campaign_id>')
story_ref = campaign_ref.collection('story')
entries = story_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(5).stream()

for entry in entries:
    data = entry.to_dict()
    if data.get('actor') != 'gemini':
        continue
    debug = data.get('debug_info', {})
    print(f"code_execution_used: {debug.get('code_execution_used')}")
    print(f"rng_verified: {debug.get('rng_verified')}")
    print(f"executed_code: {debug.get('executed_code', [])}")
    print(f"stdout: {debug.get('stdout', '')[:200]}")
```

### Fabrication Detection Logic

```python
def is_fabrication(evidence: dict) -> bool:
    """
    Fabrication = dice values present but no verified RNG.
    """
    if evidence.get("rng_verified", False):
        return False  # Real RNG used

    if evidence.get("code_execution_used", False):
        return True  # Code ran but NO RNG = fabrication

    return False  # No code execution (different path)
```

## Testing Standards

### Unit Test Requirements

1. **RED test**: Must fail without the fix
2. **GREEN test**: Must pass with the fix
3. **Regression protection**: Removal of fix causes test failure

### Chi-Squared Test Coverage

```python
class TestDiceDistribution(unittest.TestCase):
    def test_chi_squared_normal_distribution(self):
        """Verify true RNG produces acceptable chi-squared."""
        rolls = [random.randint(1, 20) for _ in range(500)]
        result = chi_squared_test(rolls, 20)
        self.assertLess(result["chi_squared"], 50)

    def test_chi_squared_detects_fabrication(self):
        """Verify fabricated dice fail chi-squared."""
        # Simulate LLM always picking 16
        fabricated = [16] * 100
        result = chi_squared_test(fabricated, 20)
        self.assertGreater(result["chi_squared"], 100)
```

### RNG Verification Test Coverage

```python
class TestRNGVerification(unittest.TestCase):
    def test_detects_real_rng(self):
        code = "roll = random.randint(1, 20)"
        self.assertTrue(_code_contains_rng(code))

    def test_rejects_string_containing_rng(self):
        code = "print('random.randint is cool')"
        self.assertFalse(_code_contains_rng(code))

    def test_rejects_fabricated_print(self):
        code = 'print(\'{"rolls": [16]}\')'
        self.assertFalse(_code_contains_rng(code))
```

## Audit Workflow

### 1. Statistical Analysis (Chi-Squared)

```bash
WORLDAI_DEV_MODE=true python scripts/audit_dice_rolls.py <campaign_id>
```

Look for:
- Chi-squared value in output
- Distribution skew warnings
- Impossible values (0, 21+ on d20)

### 2. Code-Level Verification

Check GCP logs for:
```
DICE_AUDIT: ... rng_verified=True
CODE_EXEC_NO_RNG: ...  # Warning - fabrication detected
```

### 3. Response to Fabrication

If chi-squared > 100 or `rng_verified=False`:

1. **Immediate**: Reprompt LLM with enforcement warning
2. **Investigation**: Review code_execution samples in logs
3. **Fix**: Ensure AST-based RNG detection is active

## Related Documentation

- `dice-roll-audit.md` - Campaign analysis workflow
- `dice-real-mode-tests.md` - MCP test procedures
- `evidence-standards.md` - Three-evidence rule

## Reference: PR #2551

The chi-squared test and AST-based RNG verification were implemented in PR #2551 to fix dice fabrication:

- **Bug**: Chi-squared 411.81 (vs expected 19-30)
- **Cause**: LLM printed dice values without calling `random.randint()`
- **Fix**: AST parsing + `rng_verified` field + enforcement warning in system prompt
