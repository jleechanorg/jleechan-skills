---
description: Code coverage analysis using coverage.sh script and pytest-cov
type: usage
scope: project
---

# Coverage Analysis Guide

## Purpose

Provide Claude with a comprehensive reference for running code coverage analysis in Your Project. This skill covers the coverage.sh script usage, interpreting results, and best practices.

## Activation Cues

- Running coverage analysis
- Checking test coverage before PRs
- Investigating which code paths need more tests
- Generating coverage reports

## Quick Reference

```bash
# Run coverage with HTML report (default)
./coverage.sh

# Run coverage with text report only (faster)
./coverage.sh --no-html

# Include integration tests
./coverage.sh --integration

# Include integration tests, text only
./coverage.sh --integration --no-html
```

## Output Locations

| Output | Location |
|--------|----------|
| Text report | `/tmp/$PROJECT_NAME/coverage/coverage_report.txt` |
| HTML report | `/tmp/$PROJECT_NAME/coverage/index.html` |
| Quick link | `file:///tmp/coverage.html` (symlink) |

## Understanding Results

### Test Summary
```
Test Summary:
  Total tests: 232
  Passed: 204
  Failed: 28
```

### Coverage Summary
```
Overall Coverage: 69%

Key Files Coverage:
main.py                    44%
llm_service.py            74%
game_state.py             57%
firestore_service.py      53%
```

## Coverage Thresholds

### CI Workflow Thresholds
| Coverage | CI Result | Badge Color |
|----------|-----------|-------------|
| ≥80% | Pass | Green (MINIMUM_GREEN: 80) |
| 60-79% | Pass (warning) | Orange (MINIMUM_ORANGE: 60) |
| <60% | **Fail** | Red |

### Quality Guidelines
| Coverage | Status | Action | CI Threshold |
|----------|--------|--------|--------------|
| 80%+ | Excellent | Maintain | Green (MINIMUM_GREEN: 80) |
| 60-79% | Good | Minor improvements | Orange (MINIMUM_ORANGE: 60) |
| 40-59% | Fair | Add targeted tests | Warning |
| <40% | Poor | Prioritize testing | Error |

## Key Files to Monitor

Priority coverage targets for Your Project:

1. **narrative_response_schema.py** - LLM response parsing
2. **llm_service.py** - AI integration
3. **world_logic.py** - Core game mechanics
4. **firestore_service.py** - Data persistence
5. **game_state.py** - State management
6. **main.py** - API endpoints

## Running Single Test Files

For focused development, run individual test files:

```bash
# Using venv with proper PYTHONPATH
source venv/bin/activate
PYTHONPATH="$PWD:$PYTHONPATH" TESTING=true python $PROJECT_ROOT/tests/test_specific.py
```

## Common Issues

### ModuleNotFoundError: No module named 'mvp_site'

**Cause**: PYTHONPATH doesn't include project root.

**Fix**: The coverage.sh script sets `PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"` automatically. For manual runs:

```bash
export PYTHONPATH="$PWD:$PYTHONPATH"
```

### Test Fails with Missing Dependencies

**Fix**: Install test dependencies:
```bash
pip install numpy fastembed onnxruntime
```

### Browser/Integration Tests Failing

Some tests require additional setup:
- Browser tests need Playwright: `playwright install`
- Integration tests may need running services

## GitHub Actions Integration

For CI coverage reporting, use `py-cov-action/python-coverage-comment-action@v3.32` (SHA-pinned in workflow):

```yaml
- name: Coverage comment
  uses: py-cov-action/python-coverage-comment-action@fb02115d6115e7b3325dc3295fe1dcfb1919248a  # v3.32
  with:
    GITHUB_TOKEN: ${{ github.token }}
    MINIMUM_GREEN: 80
    MINIMUM_ORANGE: 60
```

See `.github/workflows/coverage.yml` for the full workflow with threshold checks.

## Best Practices

1. **Run before PRs**: Check coverage impact before submitting
2. **Focus on critical paths**: Prioritize business logic coverage
3. **Don't chase 100%**: Focus on meaningful test coverage
4. **Review uncovered lines**: Use HTML report for line-by-line analysis
5. **Mock external services**: Use `TESTING=true` for isolated testing

## Related Skills

- `end2end-testing.md` - E2E test patterns
- `evidence-standards.md` - Test evidence collection
