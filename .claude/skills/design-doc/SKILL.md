---
description: Generate comprehensive product spec, engineering design, and TDD implementation plan documents for any feature or project. Consolidated 2026-07-11 from the retired /design command (whose newer Phase-0 exit-criteria-first + batch-decision contract is authoritative — see the AUTHORITATIVE ENTRY CONTRACT section) and the retired design HTML skill.
---

> **Start here:** run the "AUTHORITATIVE ENTRY CONTRACT" section (end of file) FIRST — Phase 0
> exit-criteria-first, batch-decision mode. It supersedes conflicting steps in the body below.

# /design — Product & Engineering Design Documentation

**Purpose**: Generate comprehensive product specification and engineering design documents to prevent implementation failures through proper planning.

**Usage**: `/design [feature-name] [--type=feature|bugfix|migration|refactor]` — Creates product spec, eng design, and TDD implementation docs.

**Default Composition**: Requirements gathering → Architecture assessment → Product strategy → Engineering leadership → Critical thinking → Research → Documentation

## ⚡ Execution Instructions

When invoked, execute these steps immediately. This is NOT documentation — these are commands to execute right now.

## 🚨 Execution Workflow

### Phase 0: Exit Criteria First (runs BEFORE any product spec / design content)

1. **Step 0a — Brainstorm the finish line**: Invoke the superpowers brainstorming skill (Skill tool, skill name `superpowers:brainstorming`) to explore with the user/context: "How will we know this project is truly DONE and WORKING? What would an adversarial reviewer verify before sign-off?"
   - **Batch-decision mode (mandatory)**: never ask the user brainstorming questions one-by-one. Answer every brainstorming question yourself (or via a spawned subagent — e.g. a brainstorming subagent that self-answers, or `AskUserQuestion` with all decisions batched) with a recommended decision — including the exit criteria — using repo/conversation context and sensible senior-engineer defaults. Then present ALL recommended decisions to the user AT ONCE in a single review table: decision | recommendation | one-line rationale | rejected alternative worth noting. Contract: zero one-by-one questioning, one consolidated review checkpoint, then proceed.
2. **Step 0b — Write exit criteria FIRST**: Record the resulting exit criteria as the FIRST section of the product spec, before goals/requirements. Each criterion must be:
   - **Binary**: pass/fail, no partial credit
   - **Executable**: a stated command or observable check
   - **Externally anchored**: verified at the layer users experience — real system-of-record state, not implementer-authored logs/telemetry
3. **Ground rules** (per `~/projects/dark-factory/docs/cutover-exit-criteria.md`, R1–R6 + X1–X10 charter, hardened 2026-07-04 by a 3-reviewer adversarial pass): implementer-authored artifacts are corroborating, never sufficient; the verifier reproduces rather than inspects; satisfied-via-mock/dry-run = FAIL; default verdict is FAIL.

### Phase 0.5: Multi-Perspective Analysis

1. **Architecture Assessment**: Technical approach and system design
2. **Product Strategy Review**: User experience and business value
3. **Engineering Leadership**: Technical excellence and scalability
4. **Critical Thinking**: Challenge assumptions and identify risks
5. **Current Research**: Validate against current industry standards and best practices

### Phase 1: Requirements Gathering

1. **Identify Feature Scope**: What are we building?
2. **User Research**: Who uses this and why?
3. **Existing Analysis**: What exists today (if migration)?
4. **Success Definition**: When is it "done"?
5. **Industry Validation**: How do current best practices inform our approach?

### Phase 2: Document Generation

1. **Create Product Spec**: User-focused requirements
2. **Create Eng Design**: Technical implementation details
3. **Cross-Validate**: Ensure eng design satisfies product spec
4. **Review Readiness**: All questions answered before coding

### Phase 3: Validation

Verify all of:
- ✅ All user stories have acceptance criteria
- ✅ All components have data sources defined
- ✅ All APIs have schemas documented
- ✅ Testing strategy covers all user journeys
- ✅ No placeholders or "TBD" sections
- ✅ Multi-perspective analysis completed
- ✅ Current industry standards validation performed
- ✅ Critical thinking challenges addressed

### Phase 4: Adversarial Analysis (Auto-Triggered)

**MANDATORY FINAL STEP**: After completing design documentation, automatically trigger comprehensive adversarial analysis to challenge the proposed approach and identify simpler alternatives.

---

## ⚠️ Selective Documentation Principle

**SKIP sections that don't apply** — Don't force irrelevant content:
- **Bug fixes**: Skip user stories, focus on technical analysis
- **Infrastructure**: Skip UI/UX, focus on system design
- **Small features**: Skip risk assessment if trivial
- **Internal tools**: Skip user journey maps

**Quality over completeness** — Empty sections with good reason > Forced placeholder content

### Section Relevance by Type

| Type | Focus |
|------|-------|
| **Features** | Full product spec + engineering design |
| **Bug fixes** | Technical analysis, testing strategy, minimal product spec |
| **Migrations** | Risk assessment, rollout plan, minimal UI requirements |
| **Refactoring** | Technical goals, success metrics, skip user stories |
| **Infrastructure** | System design, monitoring, automation hooks — skip user journeys |

## 🎯 Command Objectives

1. **Requirements First**: Gather structured requirements through guided questions
2. **Prevent Issues**: Enforce proper planning before implementation
3. **Feature Completeness**: Ensure all requirements are captured upfront
4. **Technical Clarity**: Define implementation approach before coding
5. **Success Criteria**: Clear definition of "done" before starting
6. **TDD Implementation Planning**: Generate detailed sub-milestone breakdown with TDD integration
7. **Granular Progress Tracking**: Break features into ~100 line commits for better tracking and rollback

---

## 📋 Generated Documents

The `/design` command generates **3 comprehensive documents** with TDD integration:

### 1. Product Specification (`[feature]_product_spec.md`)

```markdown
# [Feature] Product Specification

## Table of Contents
1. Exit Criteria
2. Executive Summary
3. Goals & Objectives
4. User Stories
5. Feature Requirements
6. User Journey Maps
7. UI/UX Requirements
8. Success Criteria
9. Metrics & KPIs

## Exit Criteria (FIRST section — from Phase 0)
- Binary (pass/fail) criteria only, each with an executable command or observable check
- Externally anchored: verified at the layer users experience (real system-of-record state)
- Implementer-authored artifacts are corroborating, never sufficient; satisfied-via-mock/dry-run = FAIL

## Executive Summary
- Feature overview
- User value proposition
- Success metrics

## Goals & Objectives
### Primary Goals
- Business goal 1: [Measurable outcome]
- User goal 1: [User benefit]

### Secondary Goals
- Technical debt reduction
- Performance improvements
- Developer experience

## User Stories
- As a [user type], I want [goal] so that [benefit]
- Acceptance criteria for each story

## Feature Requirements
### Functional Requirements
- Core features list
- User interactions
- Data requirements

### Non-Functional Requirements
- Performance targets
- Security requirements
- Accessibility standards

## UI/UX Requirements
### Visual Component Specifications
- Component Tree: diagram of component hierarchy
- State Diagrams: UI state changes
- User Flow Diagrams: user journeys
- Component Library: Existing vs new components

### Responsive Behavior
- Mobile breakpoints
- Accessibility considerations
- Performance targets

## Success Criteria
- Feature complete checklist
- Performance benchmarks
- User acceptance tests

## Metrics & KPIs
- Adoption rate targets
- Performance baselines
```

### 2. Engineering Design Document (`[feature]_eng_design.md`)

```markdown
# [Feature] Engineering Design

## Table of Contents
1. Engineering Goals
2. Engineering Tenets
3. Technical Overview
4. System Design
5. Quality Assurance
6. Testing Strategy
7. Risk Assessment
8. Decision Records
9. Rollout Plan
10. Monitoring & Success Metrics
11. Automation Hooks

## Engineering Goals
### Primary Engineering Goals
- Goal 1: [Technical outcome with metrics]
- Goal 2: [Performance target with baseline]

### Secondary Engineering Goals
- Code maintainability improvements
- Developer productivity enhancements

## Engineering Tenets
1. **Reliability First**: Prefer proven solutions over cutting-edge
2. **Simplicity**: Choose the simplest solution that works
3. **Testability**: All code must be testable
4. **Observability**: Instrument everything for debugging
5. **Performance**: Measure before optimizing

## System Design
### Component Architecture
- Component hierarchy
- Data flow diagram
- State management

### API Design
- Endpoints required
- Request/response schemas
- Error handling

### Database Design
- Schema changes
- Migration strategy

## Testing Strategy
### Unit Tests
- Component testing
- API testing with mocked dependencies
- Edge case handling

### Integration Tests
- User journey tests (end-to-end)
- API integration tests
- Cross-component communication

### Acceptance Tests
- Feature parity checklist
- Performance benchmarks
- User acceptance criteria

## Risk Assessment
### Technical Risks
- **High Risk**: [Description] → [Mitigation]
- **Medium Risk**: [Description] → [Monitoring]
- **Low Risk**: [Description] → [Acceptance criteria]

## Decision Records
**Decision**: [Choice made]
**Context**: [Why needed]
**Options**: [Alternatives considered]
**Rationale**: [Why chosen]
**Consequences**: [Trade-offs accepted]

## Rollout Plan
- Feature flags
- Staged rollout
- Rollback strategy

## Monitoring & Success Metrics
- Logging strategy
- Performance monitoring
- User analytics
```

### 3. TDD Implementation Plan (`[feature]_implementation_plan.md`)

```markdown
# [Feature] TDD Implementation Plan

## Table of Contents
1. Implementation Overview
2. Scope & Delta Analysis
3. Phase Breakdown
4. Sub-Milestone Planning
5. TDD Test Strategy
6. Git Commit Strategy
7. Progress Tracking
8. Success Validation

## Scope & Delta Analysis
### Lines of Code Estimation
- **New Code**: ~X lines
- **Modified Code**: ~Y lines
- **Total Delta**: ~(X+Y) lines
- **Confidence**: High/Medium/Low

## Sub-Milestone Planning
*Each sub-milestone targets ~100 delta lines*

### SM1.1: [Milestone Name] (~100 lines)
**Files**: [Specific files]
**Commit**: `[type](scope): [description]`
**TDD Approach**:
- **Red**: Write failing test for [functionality]
- **Green**: Implement minimal code to pass
- **Refactor**: Clean up implementation

### SM1.2: [Milestone Name] (~100 lines)
[Same structure]

## TDD Test Strategy
### Red-Green-Refactor Cycle
1. **Red**: Write failing test
2. **Green**: Minimal code to pass
3. **Refactor**: Improve quality
4. **Validate**: Acceptance criteria

## Git Commit Strategy
### Commit Message Format
[type](scope): [description]

TDD: [Red/Green/Refactor phase]
Test: [Validation summary]

### Branch Strategy
- Feature branch per phase
- Sub-milestone commits (~100 lines each)

## Progress Tracking
### Per Sub-Milestone Validation
1. Functionality works as designed
2. All tests pass, coverage maintained
3. Code quality standards met
4. No breaking changes to existing code
5. Changes documented

## Success Validation
Feature complete when:
- All phases completed
- End-to-end user journeys tested
- Performance benchmarks achieved
- Documentation complete
```

---

## 📊 Estimation Methodology

### Velocity Stats
- **Base rate**: ~820 lines/hour
- **Sustainable rate**: ~600 lines/hour (recommended for planning)

### PR Overhead
- **Small PR**: 5 min (<50 lines)
- **Medium PR**: 8 min (50-200 lines)
- **Large PR**: 12 min (200+ lines)

### Parallelism Benefit
- 2 agents: 30% time reduction
- 3-4 agents: 40% time reduction
- 5+ agents: 45% time reduction (diminishing returns)

### Integration Buffer
- Simple features: +10%
- Complex features: +20%
- Cross-cutting changes: +30%

---

## 🥊 Adversarial Analysis Framework

### MVP Reality Check Questions
1. **Complexity Challenge**: "Is this over-engineering a simple fix?"
2. **Standard Tools Challenge**: "What existing tools solve this?"
3. **Maintainability Challenge**: "Can this be realistically maintained?"
4. **Speed Challenge**: "Does this ship features faster or slower?"
5. **Technical Debt Challenge**: "Will this create more problems than it solves?"

### Alternative Solutions Analysis
For each major design decision:
- **Simple Fix**: Minimal change that addresses core problem
- **Standard Solution**: Industry-proven tools/frameworks
- **Custom Solution**: Proposed approach (justify why needed)

### Impact Assessment Matrix

| Solution | Time | Maintenance | Risk | Suitability |
|----------|------|-------------|------|-------------|
| Simple Fix | [X min] | Low/Med/High | Low/Med/High | 1-5 |
| Standard Tool | [X hours] | Low/Med/High | Low/Med/High | 1-5 |
| Custom Build | [X days] | Low/Med/High | Low/Med/High | 1-5 |

---

## ✅ Pre-Implementation Checklist

Before coding:
1. [ ] Product spec reviewed and approved
2. [ ] Engineering design addresses all requirements
3. [ ] Implementation plan created with TDD integration
4. [ ] Sub-milestones defined (~100 lines each)
5. [ ] Test cases defined for all user stories
6. [ ] Git commit strategy documented
7. [ ] Success metrics clearly defined
8. [ ] No unanswered questions remain

---

## 💡 Usage Examples

```
/design react-v3-migration
→ [feature]_product_spec.md
→ [feature]_eng_design.md
→ [feature]_implementation_plan.md

/design multiplayer-campaigns --type=feature
→ Full 3-doc suite

/design fix-login-bug --type=bugfix
→ Focused technical analysis + minimal product spec
```

## ✅ Success Criteria

The `/design` command succeeds when:
1. All three documents are generated with no "TBD" sections
2. User journeys are completely mapped
3. Technical approach addresses all requirements
4. Testing strategy covers all scenarios
5. Implementation plan has clear phases with TDD integration
6. Sub-milestones are defined with ~100 line targets
7. Git commit strategy is documented
8. Adversarial analysis completed with simpler alternatives considered

## Source

Generalized from `your-project.com/.claude/commands/design.md` (1140 lines, 35KB).
Original repo-specific backup is preserved in the repository archive at
`.claude/skills_archive/2026-08-27-historical-zero-use/design-doc-backup-worldarchitect/SKILL.md`;
clean installs intentionally omit it.

---

## AUTHORITATIVE ENTRY CONTRACT — consolidated from the retired /design command (2026-07-11, user directive)

The standalone `/design` command (newest of the merged sources, updated 2026-07-11) and `design`
skill were removed; their contracts live here. **Where anything below in this section conflicts
with the older flow above, THIS section wins** — run Phase 0 first, batch-decision mode always.
`/design` with no custom override resolves to Claude Code's builtin (if present).

### Phase 0 — Exit criteria first (runs BEFORE any spec/design content)
- Invoke `superpowers:brainstorming` to explore: "How will we know this is truly DONE and WORKING?
  What would an adversarial reviewer verify before sign-off?"
- **Batch-decision mode (mandatory):** never ask brainstorming questions one-by-one. Answer every
  question yourself with a recommended decision (including exit criteria) from repo/conversation
  context and senior-engineer defaults, then present ALL decisions AT ONCE in a single review table
  (decision, recommendation, one-line rationale, rejected alternative worth noting). Zero one-by-one
  questioning; one consolidated review checkpoint; then proceed.
- Write exit criteria as the FIRST spec section: binary, executable, externally anchored (real
  system-of-record state, never implementer-authored logs). Mock/dry-run satisfaction = FAIL;
  default verdict is FAIL. (Charter: ~/projects/dark-factory/docs/cutover-exit-criteria.md R1-R6+X1-X10.)
- Run an adversarial review (pass|warn|fail, fix all P0/P1) between spec→design and design→plan.

### Optional HTML+MD output mode (from the retired `design` skill)
If the target repo has a `docs/design/*.html` style, ALSO emit a matching HTML+MD pair (both files
written in parallel, single message) matching the repo's canonical HTML (CSS tokens `--bg #f2efe7`,
`--panel #fffdf8`, `--ink #1f1a16`, `--muted #6f6357`, `--brand #165a72`, `--line #dfd3c2`; hero +
tag pills, overview card grid, section-label dividers, summary table + honest-capability callout,
responsive grids at 900px). The markdown three-doc set remains the source of truth.
