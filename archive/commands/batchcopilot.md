---
description: /batchcopilot Command - Batch PR Processing
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 1: Batch Planning

**Action Steps:**
1. **Validate PRs**: Check that all PRs exist and are accessible
2. **Group by complexity**: Simple fixes vs. complex analyses
3. **Estimate resources**: Total expected token usage and time
4. **Create processing queue**: Order PRs by priority/dependency

### Phase 2: Context Loading (Once)

**Action Steps:**
1. **Load project context**: Load CLAUDE.md and project state once
2. **Cache common patterns**: Store frequent PR patterns in session memory
3. **Prepare tools**: Initialize git, GitHub CLI, testing frameworks

### Phase 3: Batch Processing

**Action Steps:**
For each PR in the batch:
1. **Load PR-specific context**: Only incremental context for this PR
2. **Run intelligent copilot workflow**: 6-phase analysis with stage optimization
3. **Track results**: Success/failure status per PR + optimization metrics
4. **Context preservation**: Keep loaded patterns for next PR

### Phase 4: Batch Summary

**Action Steps:**
1. **Results report**: Success/failure for each PR
2. **Token usage**: Actual vs. estimated consumption
3. **Follow-up actions**: PRs requiring manual intervention

### Phase 6: Workflow Improvement

**Action Steps:**
1. **Processing speed**: Faster total time despite larger scope
2. **Context reuse**: Higher accuracy from pattern recognition
3. **Reduced overhead**: Less authentication and tool setup

## 📋 REFERENCE DOCUMENTATION

# /batchcopilot Command - Batch PR Processing

**Usage**: `/batchcopilot --prs <PR_NUMBERS> [--limit N]`

**Implementation**: This command uses Claude Code's command composition architecture where Claude reads this markdown file and executes the workflow through natural language understanding and tool orchestration.

**Purpose**: Process multiple PRs in a single session to reduce token overhead from context reloading.

## 🚨 CRITICAL: BATCH PROCESSING FOR TOKEN OPTIMIZATION

**Token Efficiency**:
- **Individual runs**: 72 × 4M tokens = 288M tokens
- **Batch processing**: 15 sessions × 8M tokens = 120M tokens
- **With optimization**: Additional 20-40% savings for clean PRs
- **Combined savings**: 65-75% reduction

## Usage Examples

```bash

# Process 5 PRs in one session

/batchcopilot --prs 1001,1002,1003,1004,1005

# Process up to 10 PRs with limit

/batchcopilot --prs 1001,1002,1003,1004,1005,1006,1007,1008,1009,1010 --limit 5

# Process all open PRs needing copilot attention

/batchcopilot --all-pending

# Analyze batch suitability without processing

/batchcopilot --prs 1001,1002,1003 --analyze-only
```

## Context Optimization

### Shared Context (Loaded Once)

- Project documentation (CLAUDE.md, README files)
- Common code patterns and utilities
- Testing frameworks and CI configuration
- Standard PR review patterns

### PR-Specific Context (Loaded Per PR)

- PR description and conversation
- Changed files and diffs
- CI failure logs specific to PR
- Review comments and suggestions

### Context Reuse

- **Pattern recognition**: Similar issues across PRs
- **Code pattern caching**: Common fixes applied multiple times
- **Tool state preservation**: Keep git/GitHub CLI authenticated

## Error Handling

### Individual PR Failures

- **Isolation**: One PR failure doesn't stop batch processing
- **Detailed logging**: Specific error for failed PR
- **Retry mechanism**: Option to retry failed PRs in separate session

### Batch-Level Failures

- **Graceful degradation**: Fall back to individual processing if needed
- **State preservation**: Save progress on successful PRs
- **Recovery protocol**: Resume from where batch failed

## Quality Assurance

### Batch Size Limits

- **Optimal size**: 5-7 PRs per batch for balance of efficiency vs. accuracy
- **Maximum size**: 10 PRs to prevent context overflow
- **Complexity adjustment**: Fewer PRs if they're large/complex

### Quality Checks

- **Per-PR verification**: Ensure each PR gets adequate attention
- **Cross-PR conflict detection**: Check for conflicting changes
- **Resource monitoring**: Stop if token usage exceeds limits

## Integration with Existing Commands

### Replaces Individual /copilot Calls

```bash

# Old inefficient pattern

/copilot 1001
/copilot 1002
/copilot 1003
/copilot 1004
/copilot 1005

# New efficient pattern

/batchcopilot --prs 1001,1002,1003,1004,1005
```

### Works with Orchestration

- **Scheduled batching**: Run batch processing at specific times
- **Queue integration**: Add PRs to batch queue for later processing
- **Priority handling**: Process urgent PRs individually, batch others

## Success Metrics

### Token Efficiency

- **Target**: 50%+ reduction in copilot-related token usage
- **Measurement**: Compare before/after token consumption
- **Quality**: Maintain same level of PR analysis accuracy

## Implementation Notes

- **Backward compatibility**: Individual /copilot commands still work
- **Progressive rollout**: Start with small batches, expand as proven
- **Monitoring**: Track token usage and quality metrics
- **User feedback**: Adjust batch sizes based on results

## Expected Impact

**Current state**: $288/week for copilot operations
**With batching**: $120/week for same work
**Annual savings**: $8,736

This command directly addresses the second-largest source of token waste identified in the comprehensive analysis.
