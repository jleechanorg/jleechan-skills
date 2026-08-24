---
description: /reviewsuper Command - Critical Architecture Reviewer
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: Eligibility Pre-Check (Haiku Agent)

**Action Steps:**
Use a Haiku agent to check if the pull request (a) is closed, (b) is a draft, (c) is an automated/trivial PR not needing review, or (d) already has a recent reviewsuper comment **AND** the PR head SHA has not changed since that comment (i.e., no new commits since the last reviewsuper run). Only skip if **both** conditions are true for (d): the comment is recent AND `getHeadSHA() == sha_recorded_in_last_reviewsuper_comment`. If new commits exist since the last reviewsuper comment, always proceed with re-review. If any other condition (a–c) is true, stop and do not proceed.

### Phase 1: Actionable Feedback

**Action Steps:**
1. Analyze code for architectural issues
2. Identify problems, flaws, and technical debt
3. Provide specific, actionable recommendations

### Phase 2: Confidence Scoring & False-Positive Filtering (from official claude-plugins-official/code-review)

**Action Steps:**
For each issue found in Phase 1, launch a parallel Haiku agent to score it 0-100:
- **0**: False positive, pre-existing issue, or doesn't stand up to light scrutiny
- **25**: Might be real but unverified; stylistic issue not explicitly in CLAUDE.md
- **50**: Verified real issue but minor or infrequent in practice
- **75**: Double-checked, very likely real, directly impacts functionality or in CLAUDE.md
- **100**: Confirmed real, happens frequently, evidence directly confirms it

Filter out ALL issues with score < 80. If no issues survive, post "No high-confidence architectural issues found."

False positives to reject: pre-existing issues; nitpicks a senior engineer wouldn't flag; things linters/CI catch; general quality issues not in CLAUDE.md; issues on lines the PR didn't modify.

### Phase 3: Required Actions

**Action Steps:**
1. Convert high-confidence findings into concrete, PR-specific action items.
2. For each action item, include file/path scope and expected outcome.
3. Mark each action as **Required** or **If applicable** based on direct evidence from the PR.
4. Use sample wording only as templates, never as mandatory hardcoded tasks.

## 📋 REFERENCE DOCUMENTATION

# /reviewsuper Command - Critical Architecture Reviewer

Performs critical architectural reviews of recent PRs with focus on problems, flaws, and technical debt.

## Usage

```
/reviewsuper              # Review latest 10 PRs critically
/reviewsuper 5            # Review latest 5 PRs
/reviewsuper --arch       # Architecture-only focus
/reviewsuper --security   # Security-focused review
/reviewsuper --debt       # Technical debt focus
/reviewsuper --all        # All open PRs
```

## Purpose

Provides critical, problem-focused architectural reviews that identify:
- Design flaws and anti-patterns
- Performance bottlenecks and inefficiencies
- Security vulnerabilities and risks
- Technical debt and maintenance burdens
- Code quality issues and complexity

## Review Standards

### Critical Focus Areas

**1. Architecture Problems**
- Tight coupling between modules
- Violation of SOLID principles
- Missing abstractions and interfaces
- Poor separation of concerns
- Circular dependencies

**2. Performance Issues**
- Inefficient algorithms (O(n²) or worse)
- Memory leaks and resource waste
- Database N+1 problems
- Blocking operations in hot paths
- Excessive memory allocation

**3. Security Concerns**
- Input validation failures
- SQL injection vulnerabilities
- Authentication bypass risks
- Data exposure in logs/errors
- Missing authorization checks

**4. Technical Debt**
- Code duplication and copy-paste
- Magic numbers and hard-coded values
- Complex conditional logic
- Long methods and large classes
- Missing or inadequate tests

**5. Maintainability Problems**
- Poor naming conventions
- Inadequate documentation
- Complex inheritance hierarchies
- Hidden dependencies
- Brittle test structures

## Review Tone Guidelines

### ❌ Avoid (Too Positive)

```
"✅ Excellent work!"
"Great implementation!"
"This looks good!"
Rating: 9/10
```

### ✅ Use (Critical Focus)

```
❌ **Major Issue**: Specific problem with impact
⚠️ **Design Flaw**: Pattern violation with consequences
🔧 **Refactor Needed**: Complex logic requires simplification
📈 **Performance Risk**: Inefficient algorithm in critical path
🚨 **Security Gap**: Missing validation creates vulnerability
```

## Review Process

### 1. Problem Detection

- **File Size Analysis**: Flag files >500 lines
- **Complexity Metrics**: Detect deep nesting (>4 levels)
- **Method Length**: Flag methods >50 lines
- **Duplication Detection**: Identify copy-paste code
- **Pattern Analysis**: Detect anti-patterns and code smells

### 2. Impact Assessment

- **Performance Impact**: High/Medium/Low
- **Security Risk**: Critical/High/Medium/Low
- **Maintenance Burden**: High/Medium/Low
- **Business Risk**: Critical/High/Medium/Low

## Required Changes

1. Extract UserValidator class from AuthController (SRP violation)
2. Add input sanitization before database queries (security)
3. Replace nested loops with hash-based lookup (performance)
4. Add unit tests for edge cases (quality)
```

## Comment Format

```

## 🔍 Critical Architecture Review

**from super reviewer**

### Major Concerns

❌ **[Issue Type]**: [Specific problem with file:line reference]
⚠️ **[Design Flaw]**: [Pattern violation with impact analysis]
🔧 **[Technical Debt]**: [Complexity issue with refactor suggestion]

### Architecture Analysis

[Detailed examination of design decisions and their consequences]

### Security Assessment

[Specific vulnerabilities and attack vectors identified]

### Performance Concerns

[Algorithmic complexity and resource usage issues]

### Risk Assessment

- **Performance Impact**: [Level with reasoning]
- **Security Risk**: [Level with specific threats]
- **Maintenance Burden**: [Level with complexity metrics]

**Critical Rating**: X/10 - [Honest assessment with major issues listed]
```

## Detection Patterns

### Architecture Red Flags

```python

# ❌ Tight Coupling

class UserService:
    def __init__(self):
        self.db = MySQLDatabase()  # Hard dependency

# ❌ God Object

class UserManager:  # 500+ lines doing everything
    def create_user(self): pass
    def authenticate(self): pass
    def send_email(self): pass
    def generate_report(self): pass
```

### Performance Red Flags

```python

# ❌ O(n²) Algorithm

for user in users:
    for other in users:  # Nested iteration
        if user.matches(other):

# ❌ Database in Loop

for item in items:
    db.query(f"SELECT * FROM related WHERE id={item.id}")
```

### Security Red Flags

```python

# ❌ SQL Injection

query = f"SELECT * FROM users WHERE name='{user_input}'"

# ❌ Missing Validation

def update_user(user_id, data):
    db.update(user_id, data)  # No input validation
```

## Integration

### GitHub API Usage

- `gh pr list --limit N` - Get recent PRs
- `gh pr view PR# --json files,body` - Get PR details
- `gh pr comment PR# --body "review"` - Post review

### File Analysis

- Parse changed files for patterns
- Calculate complexity metrics
- Detect architectural violations
- Identify security risks

### Comment Posting

- Post as "from super reviewer"
- Include file:line references
- Provide specific code examples
- Give actionable recommendations

## Quality Standards

### Every Review Must Include:

1. **Specific Problems**: Not generic concerns
2. **Code Examples**: Actual problematic code snippets
3. **Impact Analysis**: Why each issue matters
4. **Actionable Fixes**: Concrete steps to improve
5. **Honest Rating**: Realistic score reflecting issues

### Review Quality Metrics:

- **Problem Detection Rate**: Issues per 100 lines
- **False Positive Rate**: <10% of flagged issues
- **Actionability Score**: >80% of suggestions implementable
- **Developer Response**: Comments address real concerns

## Command Chaining

```bash
/reviewsuper /timeout strict     # Fast critical review
/reviewsuper --security /arch    # Combined security + architecture
/arch /reviewsuper              # Deep analysis then critical review
```

## Example Output

```

## 🔍 Critical Architecture Review

**from super reviewer**

### Major Concerns

❌ **Tight Coupling**: AuthService directly instantiates EmailProvider (auth.py:45)
⚠️ **Missing Validation**: User input passed directly to database (user.py:123)
🔧 **Complex Logic**: 8-level nested conditionals in payment processing (payment.py:67-89)

### Architecture Analysis

The authentication system violates dependency inversion by hard-coding email dependencies. This makes testing difficult and prevents swapping email providers. The payment logic has grown into an unmaintainable nested structure that's error-prone and hard to debug.

### Risk Assessment

- **Performance Impact**: Medium (email blocking auth flow)
- **Security Risk**: High (SQL injection possible)
- **Maintenance Burden**: High (complex nested logic)

**Critical Rating**: 4/10 - Multiple design flaws require immediate attention
```
