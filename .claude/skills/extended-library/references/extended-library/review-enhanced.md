---
description: Enhanced Code Review Command
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

# Enhanced Code Review Command

**Usage**: `/review-enhanced` or `/reviewe` (alias)

**Purpose**: Perform comprehensive code analysis with multi-pass security review (simplified version of `/reviewdeep`)

## Implementation

When `/reviewe` is invoked, Claude executes directly:

1. **PR/Code Analysis**: 
   - Analyze changed files and code patterns
   - Focus on new code additions and significant modifications
   - Identify potential issues and improvement opportunities

2. **Multi-Pass Security & Quality Analysis**:
   - **Pass 1**: Security vulnerabilities, authentication flaws, input validation
   - **Pass 2**: Runtime errors, null pointers, resource leaks, edge cases  
   - **Pass 3**: Performance issues, inefficient algorithms, optimization opportunities
   - **Pass 4**: Code quality, maintainability, documentation, best practices

3. **Issue Categorization**:
   - **🔴 Critical**: Security vulnerabilities, runtime errors, data corruption risks
   - **🟡 Important**: Performance issues, maintainability problems, architectural concerns  
   - **🔵 Suggestion**: Style improvements, refactoring opportunities, optimizations
   - **🟢 Nitpick**: Minor style issues, documentation improvements, conventions

## Key Security & Testing Patterns

**🚨 Critical Security Issues**:
- `shell=True` usage → Must use list args with `shell=False, timeout=30`
- Missing input validation → Whitelist patterns instead of blind interpolation
- SQL injection risks → Parameterized queries only
- Command injection → Never construct commands from user input

**🚨 Critical Test Issues**:  
- `@unittest.skipIf` or `pytest.skip()` → Use mocks instead
- Environment-dependent tests → Must behave identically everywhere
- Missing cleanup → Use context managers and `finally` blocks

## Output Format

```
🔍 ENHANCED CODE REVIEW ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Summary: [Brief assessment]
🔴 Critical Issues: [Count and key items]
🟡 Important Issues: [Count and key items] 
🔵 Suggestions: [Count and key items]

[Detailed analysis with specific recommendations]
```

**Execution Method**: Direct implementation by Claude with immediate output.
