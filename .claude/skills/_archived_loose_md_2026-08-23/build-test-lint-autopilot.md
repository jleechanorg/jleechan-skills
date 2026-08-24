---
description: Turnkey workflow for running tests, lint, and quality automation
type: usage
scope: project
---

# Build, Test & Lint Autopilot

## Purpose
Provide Claude with a turnkey workflow for orchestrating the project's automated quality checks, including when to run full suites and how to interpret failures.

## Activation cues
- Requests to run tests, lint, or end-to-end quality checks.
- Follow-up questions after CI failures.
- Planning sessions that need a recommended verification order.

## Primary commands
| Scenario | Command |
| --- | --- |
| Standard unit tests | `./run_tests.sh` |
| Integration focus | `./run_tests.sh --integration` |
| Coverage report | `./run_tests_with_coverage.sh` |
| UI/browser suite | `./run_ui_tests.sh` |
| Lint & format | `./run_lint.sh` or `pre-commit run -a` |

## Automation helper
Use the bundled script to run tests followed by linting in one step:
```bash
skills/build_test_lint_autopilot/scripts/run_quality_suite.sh [<run_tests.sh flags>]
```
The script executes from repo root, forwards any `run_tests.sh` options (e.g., `--integration`, `--full`), and stops on the first failure.

## Decision guide
1. **Small backend change** → `./run_tests.sh`
2. **Firestore or external APIs** → add `--integration`
3. **Pre-merge confidence** → `./run_tests_with_coverage.sh`
4. **Frontend tweaks** → `./run_ui_tests.sh`
5. **Any code touch** → `./run_lint.sh` (or bundled script)

## Failure triage tips
- **Unit failures**: Inspect stack traces in `latest_ci_logs.txt` or re-run specific modules via `./run_tests.sh path/to/test.py -k name`.
- **Integration issues**: Confirm `TEST_MODE` environment and check service credentials in `.env`.
- **Lint errors**: Run `pre-commit run -a` for auto-fixes; review Ruff output for rule IDs.
- **UI flakes**: Re-run with `./run_ui_tests.sh --headed` when available to capture screenshots.

## Reporting expectations
- Summarize command(s) executed and whether they passed.
- Highlight failing modules and recommend next steps (e.g., enable verbose logging, update fixtures).
- Suggest follow-up commands such as `pytest -k` filters or rerunning coverage after fixes.
