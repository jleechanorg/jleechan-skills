---
description: Guidelines Command - Centralized Mistake Prevention Consultation
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Context Detection and Setup

**Action Steps:**
1. **Read CLAUDE.md**: Extract current rules, constraints, and protocols
2. **Detect PR Context**: Use GitHub API and branch name patterns
3. **Determine Guidelines Path**: Set target path for PR or branch-specific guidelines

### Phase 2: Guidelines Consultation

**Action Steps:**
1. **Base Guidelines Reading**: Always read `docs/pr-guidelines/base-guidelines.md`
2. **PR-Specific Guidelines**: Read existing or create template if missing
3. **Pattern Extraction**: Extract relevant anti-patterns and best practices
4. **Tool Selection Guidance**: Apply hierarchy (Serena MCP → Read tool → Bash)

### Phase 3: Application Preparation and Memory Persistence

**Action Steps:**
1. **Context Integration**: Merge base, PR-specific, and memory-based guidance
2. **Anti-Pattern Awareness**: Prepare mistake prevention patterns (enhanced by memory patterns)
3. **Quality Standards**: Set expectations for evidence-based development
4. **Resource Optimization**: Apply efficient tool usage patterns
5. **Memory Learning**: Capture guidelines consultation and application patterns
   - **Command**: `mcp__memory-server__add_observations` - Store guidelines effectiveness and application contexts
   - **Command**: `mcp__memory-server__create_relations` - Link guideline success to specific task types and outcomes
   - Build persistent knowledge graph for continuous guidelines improvement

### Phase 4: Guidelines-Enhanced Execution

**Action Steps:**
1. **Planning Phase**: Apply guidelines to inform execution method decisions
2. **Tool Selection**: Follow guidelines hierarchy for optimal resource usage
3. **Quality Gates**: Apply guidelines standards for systematic change management
4. **Pattern Prevention**: Use anti-patterns to avoid documented mistakes

## 📋 REFERENCE DOCUMENTATION

# Guidelines Command - Centralized Mistake Prevention Consultation

**Usage**: `/guidelines` - Consult and manage mistake prevention guidelines system

**Command Summary**: Centralized command for consulting CLAUDE.md, base guidelines, and PR-specific guidelines with automatic creation

**Purpose**: Provide systematic mistake prevention consultation for all enhanced commands through command composition

**Action**: Read CLAUDE.md, consult base guidelines, detect PR context, create/update PR-specific guidelines as needed

## Core Functionality

### Automatic Guidelines Consultation Protocol

**1. Memory MCP Integration with Query Optimization** (MANDATORY):
- **Enhanced Search**: Use Memory MCP query optimization engine for improved search effectiveness
- **Universal Composition**: Use `/memory search "[guidelines query]"` for optimized query processing
- **Multi-Query Strategy**: Leverage `/memory` command's automatic compound query transformation
- **Command**: `/memory search "relevant guidelines and patterns"` - Search with automatic optimization
- **Command**: `/memory recall "historical guidelines applications"` - Retrieve specific guideline contexts
- **Result Merging**: Automatic through `/memory` command's built-in deduplication and scoring
- Extract learned patterns, successful strategies, and documented anti-patterns from enhanced knowledge retrieval
- Identify context-specific guidelines and decision patterns from improved search results

**2. CLAUDE.md Reading** (MANDATORY):
- Always read CLAUDE.md first to understand current rules and constraints
- Apply meta-rules, critical implementation rules, and system understanding
- Check for any task-specific protocols or recent rule updates

**3. Base Guidelines Discovery**:
- Read `docs/pr-guidelines/base-guidelines.md` for general patterns
- Extract canonical protocols, principles, tenets, anti-patterns
- Apply tool selection hierarchy and subprocess safety rules
- Cross-reference with memory patterns for validation and enhancement

**4. PR Context Detection**:
- **Primary**: Auto-detect PR number from current branch context via GitHub API
- **Fallback 1**: Extract from branch name patterns (e.g., `pr-1286-feature`, `fix-1286-bug`)
- **Fallback 2**: If no PR context, use branch-specific guidelines in `docs/branch-guidelines/{BRANCH_NAME}/guidelines.md`
- **Fallback 3**: If outside any PR/branch context, proceed with base guidelines only
- **Manual Override**: Accept explicit PR number via `/guidelines --pr 1286`
- **Memory Context**: Search for PR-specific patterns and learnings in memory graph

**5. PR-Specific Guidelines Management**:
- Check for existing `docs/pr-guidelines/{PR_NUMBER}/guidelines.md`
- If missing, create basic PR-specific guidelines template
- If exists, read and apply PR-specific patterns and learnings
- **Memory Integration**: Store PR guidelines and outcomes in persistent knowledge graph
  - **Command**: `mcp__memory-server__create_entities` - Create PR guideline entities with metadata
  - **Command**: `mcp__memory-server__create_relations` - Link PR patterns to project and guideline contexts
  - **Command**: `mcp__memory-server__add_observations` - Store specific guideline applications and results
- Auto-update with new patterns discovered during command execution and persist to memory

## Usage Patterns

### Command Composition Integration

```bash

# Called by enhanced commands for systematic consultation

/planexec [task]     → calls /guidelines → proceeds with planning
/execute [task]      → calls /guidelines → proceeds with execution
/review-enhanced     → calls /guidelines → proceeds with review
/reviewdeep          → calls /guidelines → proceeds with deep analysis
```

### Standalone Usage

```bash
/guidelines                    # Consult guidelines for current context
/guidelines --pr 1286         # Consult guidelines for specific PR
/guidelines --create-missing  # Create missing PR guidelines template
/guidelines --update         # Update PR guidelines with new patterns
```

## Implementation Protocol

## Guidelines Creation Template

**When PR-specific guidelines don't exist, automatically create**:

```markdown

# PR #{PR_NUMBER} Guidelines - {PR_TITLE}

**PR**: #{PR_NUMBER} - [Auto-detected PR title]
**Created**: {Current date}
**Purpose**: Specific guidelines for this PR's development and review

## Scope

- This document contains PR-specific deltas, evidence, and decisions for PR #{PR_NUMBER}.
- Canonical, reusable protocols are defined in docs/pr-guidelines/base-guidelines.md.

## 🎯 PR-Specific Principles

[To be populated as patterns are discovered]

## 🚫 PR-Specific Anti-Patterns

[To be populated based on review findings and mistakes discovered]

## 📋 Implementation Patterns for This PR

[To be populated with working patterns and successful approaches]

## 🔧 Specific Implementation Guidelines

[To be populated with actionable guidance for similar future work]

---
**Status**: Template created by /guidelines command - will be enhanced as work progresses
**Last Updated**: {Current date}
```

## Output Format

**Guidelines Consultation Result**:
```markdown

## 📚 Guidelines Consultation Summary

✅ **CLAUDE.md**: Read and applied - Current rules, constraints, and protocols understood
✅ **Base Guidelines**: Consulted docs/pr-guidelines/base-guidelines.md
✅ **PR Context**: Detected PR #{PR_NUMBER} / Branch: {branch_name}
✅ **PR Guidelines**: Found/Created docs/pr-guidelines/{PR_NUMBER}/guidelines.md
✅ **Anti-Patterns**: {count} relevant patterns identified for prevention
✅ **Tool Selection**: Hierarchy validated (Serena MCP → Read tool → Bash commands)

## 🎯 Key Guidance for Current Task

- {Relevant principle 1}
- {Relevant anti-pattern to avoid}
- {Tool selection recommendation}
- {Quality standard to apply}

**Guidelines Integration**: Complete - Proceed with task execution
```

## Error Handling

### Graceful Degradation Protocol

- **Missing Files**: Create templates automatically, never fail execution
- **GitHub API Errors**: Fall back to branch name parsing for PR detection
- **Permission Issues**: Continue with base guidelines if PR-specific access fails
- **Network Issues**: Use cached guidelines or base patterns as fallback

### Fallback Hierarchy

1. **Full Guidelines Suite**: CLAUDE.md + Base + PR-specific
2. **Base Guidelines Only**: CLAUDE.md + Base guidelines (if PR detection fails)
3. **CLAUDE.md Only**: Core rules and constraints (if all guidelines inaccessible)
4. **No Guidelines**: Log warning and proceed (never block execution)

## Integration Requirements

### Command Composition Pattern

**Enhanced commands must call `/guidelines` before proceeding**:

```markdown

## Pre-{Command} Guidelines Check

**Systematic Mistake Prevention**: This command automatically consults the mistake prevention guidelines system through `/guidelines` command composition.

**Execution Flow**:
1. Call `/guidelines` for comprehensive consultation
2. Apply guidelines output to inform {command-specific} approach
3. Proceed with {command-specific} workflow using guidelines context
```

## Quality Assurance

### Verification Protocol

- **Guidelines Accessibility**: Verify all target guideline files are readable
- **PR Detection Accuracy**: Confirm correct PR context identification
- **Template Creation**: Ensure proper template generation when files missing
- **Integration Success**: Validate that calling commands receive proper guidance

### Performance Considerations

- **Caching Strategy**: Cache guidelines content within session to avoid re-reading
- **Efficient Consultation**: Batch file operations where possible
- **Quick Feedback**: Provide immediate guidance without extended processing
- **Resource Management**: Monitor context usage during guidelines reading

## Advanced Features

### Enhanced Pattern Learning with Memory MCP

- **Memory MCP Connection**: Full persistent knowledge graph integration
  - **Command**: `mcp__memory-server__create_entities` - Store guideline patterns as structured entities
  - **Command**: `mcp__memory-server__create_relations` - Link patterns to contexts, outcomes, and effectiveness
  - **Command**: `/memory search "[relevant patterns]"` - Query with automatic optimization during consultation
- **Evidence Collection**: Document specific incidents with PR references and structured metadata
- **Continuous Improvement**: Update guidelines based on execution outcomes with persistent learning
- **Cross-PR Learning**: Apply patterns learned in one PR to future work through memory graph analysis
- **Pattern Recognition**: Identify recurring patterns and anti-patterns across multiple contexts
- **Success Correlation**: Track guideline effectiveness and optimization opportunities

### Automation Capabilities

- **Auto-Update Detection**: Identify when guidelines need pattern additions
- **Conflict Resolution**: Handle conflicts between base and PR-specific guidance
- **Version Management**: Track guidelines evolution and maintain historical context
- **Integration Monitoring**: Ensure consistent usage across all enhanced commands

---

**Implementation Method**: This command provides centralized guidelines consultation that other enhanced commands (`/execute`, `/planexec`, `/review-enhanced`, `/reviewdeep`) call through command composition for systematic mistake prevention.
