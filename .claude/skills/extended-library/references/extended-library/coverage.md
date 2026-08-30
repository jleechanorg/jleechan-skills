---
description: Coverage Command
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

# Coverage Command

**Purpose**: Run Python test coverage analysis and identify coverage gaps

**Usage**: `/coverage [options]`

**Options**:
- No options: Run unit tests with HTML report
- `--text`: Text report only (no HTML)
- `--integration`: Include integration tests
- `--gaps`: Focus on files with low coverage

**Implementation**:
1. Run `coverage.sh` script with appropriate flags
2. Parse coverage report to identify:
   - Overall coverage percentage
   - Files with low coverage (<50%)
   - Specific uncovered lines
3. Generate summary with:
   - Coverage statistics
   - Top 10 files needing coverage
   - Recommendations for improvement
4. Open HTML report in browser (if generated)

**Output Format**:
```
📊 Coverage Analysis Results
========================
Overall Coverage: 67%

✅ Well Covered (>80%):
- game_state.py: 90%
- constants.py: 85%

⚠️ Needs Improvement (<50%):
- firestore_service.py: 45% (missing: lines 234-267, 301-315)
- llm_service.py: 38% (missing: error handling paths)

📍 Coverage Gaps for Planning Blocks:
- narrative_response_schema.py: Line 89-95 (JSON validation edge cases)
- app.js frontend parsing: Not measured (JavaScript)

💡 Recommendations:
1. Add tests for error handling in llm_service.py
2. Test edge cases in planning block JSON validation
3. Add integration tests for full planning block flow

📂 HTML Report: file:///tmp/$PROJECT_NAME/coverage/index.html
```

**Integration with CI**:
- Automatically runs on PRs that modify Python files
- Posts detailed coverage reports as PR comments
- Tracks coverage trends over time
