---
description: Clarify Command - Specification Clarification Protocol
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Ambiguity Detection

**Action Steps:**
1. **Load Target Specification** (from argument or current goal)
2. **Scan for Ambiguity Markers**:
   - [NEEDS CLARIFICATION: ...] tags
   - Vague adjectives ("good", "fast", "secure")
   - Unresolved technical choices
   - Missing user scenarios
   - Undefined data flows

### Phase 2: Interactive Clarification

**Action Steps:**
1. **Present Ambiguities** to user in structured format
2. **Ask Targeted Questions** for each unclear aspect
3. **Capture User Responses** in structured format
4. **Validate Completeness** - ensure all ambiguities addressed

### Phase 3: Specification Update

**Action Steps:**
1. **Create Clarifications Section** in specification
2. **Document Each Resolution** with:
   - Original ambiguity
   - User's clarification
   - Implementation implications
3. **Remove [NEEDS CLARIFICATION] markers**
4. **Add validation criteria** for each clarification

### Phase 4: Validation Gate Setup

**Action Steps:**
1. **Generate Test Cases** from clarifications
2. **Create Acceptance Criteria** for each resolved ambiguity
3. **Document Anti-Mock Patterns** specific to clarifications
4. **Update Genesis Success Criteria** with clarification-based validation

### Phase 5: 🔗 INTEGRATION WITH WORKFLOW

**Action Steps:**
**Mandatory Gate for /planexec Command**:
1. `/planexec` checks for clarifications before execution
2. If ambiguities exist → automatically trigger `/clarify`
3. Only proceed after clarification completion

**Genesis Integration**:
4. Genesis validates against clarification criteria
5. Anti-mock validation includes clarification-specific patterns
6. Cannot complete until all clarified requirements met

## 📋 REFERENCE DOCUMENTATION

# Clarify Command - Specification Clarification Protocol

**Purpose**: Resolve ambiguous requirements before implementation to prevent fake code

**Usage**: `/clarify [specification-file-or-description]` - Interactive clarification workflow

## 🎯 CRITICAL ROLE: Fake Code Prevention

**Inspired by GitHub Spec Kit's clarification gate** - this command prevents Genesis from implementing based on ambiguous requirements that lead to mock/placeholder code.

## 🚀 EXECUTION PROTOCOL

## Example Output Format

```markdown

## Clarifications

### Session 1: 2024-09-24

**Ambiguity**: "secure authentication system"
**Clarification**: OAuth2 with Google/GitHub providers, JWT tokens, 24-hour expiry
**Test Criteria**: Can authenticate with Google OAuth2, JWT validation works, tokens expire properly

**Ambiguity**: "good performance"
**Clarification**: <200ms API response time, supports 1000 concurrent users
**Test Criteria**: Load test passes with 1000 users, all API calls <200ms p95
```

## 🚨 ANTI-MOCK INTEGRATION

**Clarification-Specific Validation**:
- Each clarification generates specific anti-mock patterns
- Genesis cannot claim completion without proving clarified requirements
- Test cases derived from clarifications must pass with real implementations

**Example Anti-Mock Pattern**:
```
If clarification specifies "OAuth2 integration":
- Mock patterns: "mock_oauth_response", "fake_token_validation"
- Required evidence: Real OAuth2 provider integration, actual token validation
```

This command is **essential** for preventing the Genesis fake code issues we experienced.
