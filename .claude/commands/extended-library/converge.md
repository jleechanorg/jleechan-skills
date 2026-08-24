---
description: /converge - Iterative Goal Achievement Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: 🗺️ CONVERGENCE LOOP (9-STEP CYCLE)

**Action Steps:**
**LOOP UNTIL CONVERGED OR MAX ITERATIONS REACHED (Default: 10 iterations)**:

### Phase 2: Step 2: Strategic Planning and Tool Analysis

**Action Steps:**
**Command**: `/planexec` - Create comprehensive strategy with command index optimization
1. **CONTEXT OPTIMIZATION**: Use command index instead of reading full .claude/commands/ files
2. **Command Index**: Load /tmp/converge/{branch}/command-cache/index.json (71K chars vs 677K chars)
3. **Context Savings**: 89.5% reduction in command discovery phase
4. **Smart Selection**: Filter commands by context level, execution time, and goal type
5. **Lazy Loading**: Defer reading full command .md files until execution phase
6. **Efficiency**: Use command summaries for planning, full docs for execution only
7. Remember slash commands are EXECUTABLE instructions, not documentation
8. Break goal into actionable phases using appropriate slash command orchestration
9. Estimate resource requirements and timeline with tool-specific considerations
10. Identify potential obstacles and mitigation strategies
11. Create detailed TodoWrite tracking system with command-specific tasks

### Phase 3: Step 3: Plan Review & Confidence Assessment

**Action Steps:**
**Action**: Review the plan using strategic analysis with confidence scoring
1. Critically analyze plan against available slash command library
2. **Confidence Assessment**: Evaluate goal clarity, pattern recognition, and complexity
  3. **High (≥75%)**: Clear goal + recognizable patterns → Standard execution
  4. **Medium (50-74%)**: Some ambiguity → Enhanced logging, continue
  5. **Low (<50%)**: Major uncertainty → Extra validation, continue
6. Display confidence level with reasoning for transparency
7. Optimize tool selection for maximum efficiency
8. Identify command synergies and integration opportunities
9. Validate approach against best practices and constraints

### Phase 4: Step 4: Plan Approval

**Action Steps:**
**AUTONOMOUS APPROVAL**: All plans are automatically approved and proceed without human intervention
1. System confidence assessment determines execution approach
2. High-confidence plans: Proceed with optimal execution strategy
3. Lower-confidence plans: Use more conservative execution with additional validation
4. All plans proceed autonomously - no human approval gates

### Step 5: Execution Phase

**Action Steps:**
**Command**: `/cerebras` - Fast high-quality code generation using direct Cerebras API script (NOT Gemini MCP)
1. **Script Location**: `cerebras/cerebras_direct.sh` (relative to cerebras.md location)
2. **Note**: Uses Cerebras API directly, not mcp__gemini-cli-mcp tools
3. Execute plan using optimal slash command selection
4. Monitor progress and adapt execution as needed
5. Handle errors and obstacles with intelligent retry
6. Maintain detailed execution logs for learning

### Phase 6: Step 6: Validation Against Goals

**Action Steps:**
**Command**: `/converge --validate` against the goals - Objective success measurement
1. Check each success criterion systematically using structured validation
2. Measure progress quantitatively with evidence collection
3. Identify gaps between actual and expected outcomes
4. Document validation results with concrete evidence for learning phase
5. Generate completion percentage and remaining work analysis

### Phase 7: Step 8: Enhanced Status Report Generation

**Action Steps:**
**Command**: `/status` - Generate comprehensive convergence status report with confidence data
1. **Report Location**: Save to `docs/pr-guidelines/{PR_NUMBER}/convergence-status-{timestamp}.md`
2. **Progress Summary**: Current completion percentage and criteria status
3. **Confidence Data**: Current confidence level, reasoning, and historical accuracy
4. **Resource Summary**: Token usage, iterations completed, elapsed time
5. **Iteration Analysis**: Commands used, success rates, and performance metrics
6. **Learning Documentation**: Patterns discovered, failures overcome, optimizations applied
7. **Convergence Trajectory**: Progress velocity, estimated completion, next iteration strategy
8. **Decision Context**: Evidence for convergence/continuation decision with objective rationale

### Phase 8: Step 9: Convergence Decision

**Action Steps:**
**LOOP CONTROL**: Start again with Step 1 (Goal Definition) and loop N times or stop when it's done

🚨 **MANDATORY AUTONOMY CHECKPOINT**: Before making convergence decision, verify autonomy preservation:
1. ❌ **FORBIDDEN**: Stopping for user approval when goal not 100% achieved
2. ❌ **FORBIDDEN**: Waiting for user acknowledgment of partial progress
3. ❌ **FORBIDDEN**: Implicit approval requests through progress celebration
4. ✅ **REQUIRED**: Continue immediately if success criteria < 100% and iterations < max

**Convergence Decision Logic**:
5. **IF CONVERGED**: All PRIMARY success criteria met → STOP with completion report
  6. PR is MERGEABLE status (not conflicting)
  7. All SERIOUS GitHub comments addressed (blocking issues resolved)
  8. CI passes (no failed checks)
  9. No critical errors or failures detected
10. **IF GOOD ENOUGH**: Core objectives achieved even if minor issues remain → STOP
  11. Primary goal accomplished (90%+ criteria met)
  12. Diminishing returns threshold reached (last 2 iterations <5% improvement)
  13. PR is in good mergeable state with only cosmetic issues remaining

  **Threshold Definitions:**
  14. **"90%+ criteria met"**: Calculate as (number of primary success criteria achieved) / (total number of primary success criteria). For example, if there are 10 criteria and 9 are met, progress = 90%. Criteria may include PR mergeability, CI passing, blocking comments resolved, etc.
  15. **"Last 2 iterations <5% improvement"**: Measure progress using a quantifiable validation score (e.g., percentage of criteria met, CI pass rate, or resolved blocking issues). If the increase in score between the last two iterations is less than 5% (e.g., from 88% to 90%), this threshold is considered reached.
  16. **Example**: If in iteration 8, 8/10 criteria are met (80%), and in iteration 9, 9/10 are met (90%), the improvement is 10%. If in iteration 10, 9.5/10 are met (95%), the improvement is 5%. If subsequent iterations show <5% improvement, convergence is triggered.
17. **IF STALLED**: No meaningful progress in validation for 2+ iterations → STOP with stall report
  18. Same validation scores for 2+ consecutive iterations
  19. Unable to improve PR mergeability status
  20. Repeated execution failures on same issue
21. **IF IMPROVING**: Meaningful progress on PRIMARY criteria → Continue (up to 2 more iterations, but never exceeding the hard cap)
  22. Measurable improvement in PR status or CI state
  23. Successful resolution of blocking GitHub comments
  24. NOTE: The hard cap of 10 iterations always applies, overriding all other limits
25. **IF MAX ITERATIONS**: Absolute limit reached → STOP with partial report

🔒 **AUTONOMY PRESERVATION**: No user intervention allowed during convergence decision process

**PR CONTEXT AWARENESS**: When goal involves PR work:
26. Primary success = PR is MERGEABLE on current branch
27. ❌ NEVER create additional PRs as "solutions"
28. ✅ ALWAYS work within existing PR constraints
29. ✅ STAY ON CURRENT BRANCH throughout convergence

### Phase 9: No User Interaction Points

**Action Steps:**
**Eliminated User Dependencies**:
1. ❌ No clarifying questions during goal definition
2. ❌ No approval gates for plan execution
3. ❌ No manual intervention requests during errors
4. ❌ No user confirmation for validation results
5. ❌ No human decision points in iteration loops

### Phase 10: Universal Composition Execution

**Action Steps:**
**Command Selection Protocol**: Choose appropriate slash command for each task type:
1. **Code/Script Generation**: **Command**: `/cerebras` - Fast high-quality code generation via direct Cerebras API script (`cerebras/cerebras_direct.sh` relative to cerebras.md) - NOT Gemini MCP
2. **PR Review Processing**: **Command**: `/copilot` - Complete PR comment processing
3. **Test Suite Management**: **Command**: `/test` - Run and fix failing tests
4. **Complex Multi-Step**: **Command**: `/orch` - Delegate to orchestration agents
5. **Planning & Analysis**: **Command**: `/execute` - Break down complex goals

### Phase 11: Execution Benefits

**Action Steps:**
1. **Parallel Processing**: Independent agents can execute simultaneously
2. **Failure Isolation**: Agent failures don't crash entire convergence workflow
3. **Resume Capability**: Session state enables restart from any step
4. **Debug Clarity**: Each agent's input/output clearly defined and traceable
5. **Scalability**: Add more agents without increasing main context

## 📋 REFERENCE DOCUMENTATION

# /converge - Iterative Goal Achievement Command

Achieve complex goals through autonomous plan-execute-validate-learn cycles until success criteria are met.

## Usage

- `/converge <goal>` - Start converging toward a specific goal
- `/converge --max-iterations N` - Set custom iteration limit (default: 10)
- `/converge --goal-integration` - Use /converge command for structured goal definition
- `/converge` - Resume previous convergence if interrupted

## Core Pattern

```
Loop: Autonomous plan→execute→validate→learn cycles
Until: Success criteria fully met
```

## 🔄 CONTINUOUS CONVERGENCE PROTOCOL

**FULLY AUTONOMOUS SYSTEM**: /converge implements a completely autonomous, self-improving system through recursive goal achievement with persistent learning and systematic iteration. **ZERO USER INTERVENTION** required after initial goal statement.

### 🎯 GOAL & SUCCESS CRITERIA DEFINITION

**MANDATORY**: All /converge operations must use structured goal integration

**Command**: `/converge` - Define goal with structured success criteria and validation framework
- Automatic success criteria generation based on goal patterns
- Integrated validation system with evidence collection
- Guidelines consultation for goal quality and compliance
- Historical tracking and learning integration with Memory MCP
- Cross-goal pattern analysis and optimization

#### Step 1: Intelligent Autonomous Goal Definition and Context Setup

**Command**: Goal Processing - Intelligently define goals with smart defaults and autonomous analysis
- **ENHANCED CONTEXT OPTIMIZATION**: Use direct goal processing for minimal context consumption
- **Method**: Direct inline goal analysis with structured output
- **Output**: Structured goal-spec.json in /tmp/converge/{branch}/session-{timestamp}/
- **Context Savings**: Optimized direct processing approach
- **Integration**: Load goal specification for subsequent phases without accumulating context
- **Benefits**: Direct processing, structured analysis, persistent storage
- Generate structured success criteria based on goal analysis and pattern recognition
- Establish validation methods and completion thresholds using established frameworks
- Create goal tracking structure with evidence requirements following proven patterns

#### Step 7: Learning & Documentation Update

**Command**: `/guidelines` to update the documentation if mistakes/learnings were made
- Capture mistakes, inefficiencies, and unexpected successes
- Update project guidelines and best practices
- Evolve meta-rules for future convergence cycles
- Create persistent memory for recursive improvement

## 🔒 AUTONOMY BOUNDARIES & OPERATION

### Complete Autonomy Scope

/converge operates with **ZERO USER INTERVENTION** after initial goal statement:
- **Goal Analysis**: Intelligent interpretation of goal requirements without questions
- **Planning Decisions**: Autonomous strategy selection using established patterns
- **Tool Selection**: Automatic command selection based on task analysis
- **Execution Management**: Self-directed execution with error recovery
- **Validation Assessment**: Objective success measurement without user confirmation
- **Learning Integration**: Automatic pattern capture and guideline updates
- **Iteration Control**: Autonomous continuation or termination decisions

### Smart Default System

**Intelligent Assumptions**: System applies reasonable defaults when information is unclear:
- Use established project patterns and conventions
- Apply best practices from accumulated learning
- Select proven tool combinations for similar tasks
- Implement conservative approaches for ambiguous requirements
- Generate comprehensive success criteria from goal context

### 🚀 AUTONOMOUS INTELLIGENCE ARCHITECTURE

**Self-Improving Intelligence Markers**:
- **Goal-Driven Loops**: Each cycle begins with intelligent goal analysis (Step 1)
- **Strategic Planning**: Meta-cognitive planning capabilities with tool awareness (Step 2)
- **Autonomous Decision-Making**: Smart defaults and pattern-based choices (Step 4)
- **Self-Validation**: Objective measurement against success criteria (Step 6)
- **Persistent Learning**: Memory MCP integration with evolving knowledge graph (Step 7)
- **Status Documentation**: Comprehensive progress reporting and analysis (Step 8)
- **Recursive Improvement**: Each cycle builds on accumulated learnings (Step 9)
- **Complete Autonomy**: Zero human intervention after initial goal statement

**System Architecture Patterns**:
- **OODA Loop**: Observe → Orient (Plan/Review) → Decide (Approve) → Act (Execute/Validate) → Learn (Guidelines)
- **Autopoietic Systems**: Self-maintaining and self-improving through recursive loops
- **Multi-Agent Orchestration**: Delegates to specialized slash commands (/cerebras, /copilot, /orch)
- **Emergent Intelligence**: System intelligence emerges from iterative feedback loops
- **Memory Persistence**: Memory MCP provides persistent learning and pattern evolution

### 🎯 CONVERGENCE STATES & TERMINATION

**Convergence Indicators**:
- ✅ **CONVERGED**: All success criteria objectively validated
- 🔄 **CONVERGING**: Making measurable progress toward goals
- ⚠️ **STALLED**: No progress despite multiple iterations
- 🛑 **BLOCKED**: External dependencies preventing progress
- 📚 **LEARNING**: Accumulating insights for next iteration

**Termination Conditions**:
- **Success Termination**: 100% of success criteria met
- **Learning Termination**: Guidelines updated with valuable insights
- **Resource Termination**: Maximum iterations/time reached
- **Blocking Termination**: Unresolvable external dependencies

**Completion Report Generation**:
- Total iterations completed
- Success criteria achievement percentage
- Key learnings and guideline updates
- Performance metrics (time, commands used, efficiency)
- Recommendations for future similar goals

## Key Features

- **Autonomous Operation**: Minimal user intervention required
- **Adaptive Planning**: Adjusts strategy based on results
- **Error Recovery**: Handles failures and retries intelligently
- **Progress Tracking**: Uses TodoWrite for visibility
- **Parallel Execution**: Leverages orchestration when beneficial
- **Success Validation**: Verifies all criteria before completion

## Examples

### Example 1: PR Cleanup and Refactoring

```
/converge Implement PR #1307 roadmap - close 5 PRs, create 7 focused PRs, fix 6 existing PRs
```
Result: Autonomously closes obsolete PRs, creates new focused PRs, and fixes existing ones

### Example 2: Test Suite Convergence

```
/converge Make all tests pass in the repository
```
Result: Iteratively fixes failing tests until 100% pass rate

### Example 3: Feature Implementation

```
/converge Implement complete authentication system with tests and documentation
```
Result: Builds feature incrementally with validation at each step

## Command Integration Framework

## Success Criteria Patterns

### For PR Management

- All target PRs in correct state (OPEN/CLOSED/MERGED)
- CI/CD checks passing
- Review requirements met
- No merge conflicts

### For Code Implementation

- All tests passing
- Code review approved
- Documentation complete
- Deployed successfully

### For Refactoring

- Functionality preserved
- Tests still passing
- Performance maintained/improved
- Code quality metrics met

## Error Handling & Recovery

- **Blocked Dependencies**: Implement intelligent retry with exponential backoff
- **Failing Tests**: Debug systematically, fix issues, and retry with learning
- **Conflicts**: Resolve automatically using established patterns or escalate with context
- **Rate Limits**: Implement backoff and retry strategies without user intervention
- **Resource Exhaustion**: Graceful degradation with progress preservation
- **Incomplete Goals**: Document progress, generate continuation strategy, maintain autonomous operation

## 🚀 Context Optimization Architecture

### Lazy Loading Patterns

**Context-Efficient File Loading**: Load files only when needed for execution, not during planning

```markdown
**Planning Phase** (Steps 1-3):
- Goal Processing: Use independent agent (5K tokens max)
- Command Discovery: Use command index (71K chars vs 677K chars)
- Plan Review: Work with summaries only
- Context Usage: ~80K tokens (vs 200K+ traditional)

**Execution Phase** (Steps 5+):
- Command Details: Load full .md files only when executing specific commands
- File Operations: Read files on-demand during actual operations
- Resource Usage: Targeted loading based on execution needs
- Context Management: Release completed context between iterations
```

### Command Index System Integration

**89.5% Context Reduction in Command Discovery**:
- **Index Location**: `/tmp/converge/{branch}/command-cache/index.json`
- **Content**: 106 command summaries with purpose, context requirements, execution time
- **Usage**: Planning phase uses index, execution phase loads full command docs
- **Benefits**: Instant command discovery, smart filtering, parallel planning capability

### Agent-Based Architecture

**Independent Processing Agents**:
- **Goal Processing**: Direct inline goal analysis with structured output
- **Planning Agent**: Future enhancement for command selection and sequencing
- **Execution Agents**: Parallel task execution with minimal shared context
- **Validation Agent**: Success criteria checking with targeted file access

### Session State Management

**Filesystem-Based Coordination**:
```
/tmp/converge/{branch_name}/
├── session-{timestamp}/
│   ├── goal-spec.json          # Goal processor output
│   ├── execution-plan.json     # Planning phase results
│   ├── current-state.json      # Progress tracking
│   └── results/               # Execution outputs
└── command-cache/             # Command index system
    └── index.json
```

## Best Practices

1. **Start with clear success criteria** - Ambiguous goals lead to endless loops
2. **Use TodoWrite for tracking** - Maintains visibility of progress
3. **Leverage parallel execution** - Use orchestration for independent tasks
4. **Validate frequently** - Don't wait until the end to check progress
5. **Document decisions** - Keep audit trail of what was tried
6. **Know when to stop** - Set maximum iterations to prevent infinite loops
7. **🚀 NEW: Optimize context usage** - Use lazy loading and agent architecture for efficiency
8. **🚀 NEW: Leverage command index** - Use summaries for planning, full docs for execution

## 🔗 Universal Composition Integration

**CRITICAL**: /converge achieves goals by systematically calling other slash commands:

### Primary Command Arsenal

- **`/execute`**: Planning, analysis, validation, and coordination
- **`/cerebras`**: High-speed code/script/document generation via direct Cerebras API script (`cerebras/cerebras_direct.sh` relative to cerebras.md) - NOT Gemini MCP
- **`/copilot`**: Complete PR review and comment processing
- **`/test`**: Test execution and failure resolution
- **`/orch`**: Complex multi-agent task orchestration
- **`/pushl`**: Git operations and PR creation

### Command Selection Logic

```
Goal Type → Command Selection:
- Code generation → /cerebras
- PR processing → /copilot
- Test management → /test
- Multi-step automation → /orch
- Planning/validation → /execute
```

### Invocation Pattern

```markdown
**Command**: /commandname - Clear purpose and expected outcome
- Specific parameters and context
- Expected result verification
- Integration with next phase
```

## 🔄 CONVERGENCE IN ACTION: Real Example

### Goal: Create Python Testing Suite

**Command**: `/converge Create a complete Python testing suite with test_math.py, test_utils.py, and run all tests successfully`

#### Iteration 1:

**Command**: `/execute` - Analyze goal and create plan
- Parse goal: Need 2 test files + successful test execution
- Success criteria: Files exist, contain valid tests, all tests pass
- Plan: Generate test files → Run tests → Fix any failures

**Command**: `/cerebras` - Generate test_math.py with basic math function tests
- Prompt: "Create test_math.py with pytest tests for add, subtract, multiply functions"
- Result: File created with 6 test functions
- Validation: File exists ✅

**Command**: `/cerebras` - Generate test_utils.py with utility function tests
- Prompt: "Create test_utils.py with pytest tests for string and list utilities"
- Result: File created with 4 test functions
- Validation: File exists ✅

**Command**: `/test` - Run pytest and check results
- Result: 8/10 tests pass, 2 failures in test_math.py
- Analysis: Missing math.py implementation file
- Status: Converging 🔄 (files exist but tests fail)

#### Iteration 2:

**Command**: `/cerebras` - Generate missing math.py implementation
- Prompt: "Create math.py with add, subtract, multiply functions to make tests pass"
- Result: Implementation file created
- Validation: File exists ✅

**Command**: `/test` - Re-run pytest
- Result: 10/10 tests pass ✅
- Validation: All success criteria met
- Status: **CONVERGED** ✅

#### Convergence Report:

- **Total iterations**: 2/10 (within default limit)
- **Commands used**: /execute (2x), /cerebras (3x), /test (2x)
- **Time**: 3 minutes
- **Success criteria**: All met ✅
- **Files created**: test_math.py, test_utils.py, math.py
- **Test results**: 10/10 passing

## Convergence Indicators

- ✅ **Converged**: All success criteria met
- 🔄 **Converging**: Making measurable progress
- ⚠️ **Stalled**: No progress in last iteration
- ❌ **Diverging**: Moving away from goal
- 🛑 **Blocked**: Cannot proceed without intervention

## Configuration & Iteration Limits

### Default Configuration

- **Max Iterations**: 10 (prevents infinite loops)
- **Convergence Threshold**: 100% success criteria met
- **Timeout**: 2 hours maximum execution time
- **Learning Mode**: Enabled (captures patterns for /guidelines)

### Iteration Limit Implementation

```bash

# Command-line configuration

/converge "goal statement" --max-iterations 15

# Per-goal configuration via /converge integration

/converge "complex implementation task" --max-iterations 20
/converge --goal-integration

# Emergency termination conditions

- Manual interruption (Ctrl+C)
- Resource exhaustion (context/API limits)
- Blocking external dependencies
- Maximum time exceeded
```

### Convergence States & Termination

- **SUCCESS**: All criteria met before max iterations
- **PARTIAL**: Some progress made, iteration limit reached
- **BLOCKED**: External dependencies prevent progress
- **TIMEOUT**: Maximum execution time exceeded
- **INTERRUPTED**: Manual termination requested

## Performance & Efficiency

### Context Optimization Results

- **Goal Processing**: 90% context reduction (5K vs 50K+ tokens)
- **Command Discovery**: 89.5% context reduction (71K vs 677K characters)
- **Planning Phase**: 75% overall context reduction through lazy loading
- **Execution Phase**: Targeted file loading reduces unnecessary context accumulation
- **Total System**: 60-80% context reduction enabling longer convergence sessions

## Limitations

- Cannot bypass GitHub permissions
- Cannot override CI/CD requirements
- **Complete Autonomy**: No user input required at any stage after goal statement
- Rate limits may slow progress
- Some goals may be technically infeasible
- **Default 10-iteration limit** prevents infinite loops but may require adjustment for complex goals
- **Context optimization** requires proper session directory setup and command index generation

## Memory and Context

- Saves progress state for resumption
- Documents learnings for future runs
- Maintains context across iterations
- Can resume after interruption

## Example Convergence Report

```markdown

# Convergence Complete: PR #1307 Implementation

## Goal

Implement PR #1307 roadmap with 18 PR operations

## Iterations: 3

1. Closed obsolete PRs (5/5 ✅)
2. Created focused PRs (7/7 ✅)
3. Fixed existing PRs (6/6 ✅)

## Success Criteria Met

- ✅ All obsolete PRs closed
- ✅ 7 new focused PRs created
- ✅ All KEEP PRs passing CI
- ✅ No merge conflicts

## Time: 45 minutes

## Status: CONVERGED ✅

```

---

## 🎯 CORRECTED ARCHITECTURE SUMMARY

**Universal Composition**: /converge systematically calls other slash commands using explicit "**Command**: /commandname" pattern

**Iterative Convergence**: Continues plan→execute→validate→learn cycles until ALL success criteria met

**Measurable Success**: Verifies completion objectively, not through assumption

**Command Integration**: Uses appropriate specialist commands (/cerebras, /copilot, /test, /orch) based on goal type

**Remember**: /converge achieves goals by orchestrating other slash commands intelligently, not by trying to do everything itself. It's a meta-command that coordinates specialized tools until convergence is achieved.
