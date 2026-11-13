---
name: CLAUDE
description: Reference documentation for understanding and using the custom agent system
---

# Claude Code Agent System Documentation

**Purpose**: Reference documentation for understanding and using the custom agent system implemented in this project's `.claude/agents/` directory.

## 🎯 Critical Understanding: These Are Custom Project Agents

**IMPORTANT**: The agents in this directory are **custom implementations** created specifically for this project, NOT Anthropic pre-installed defaults. Claude Code ships with ZERO default agents - all agents are user-created.

## 📊 Agent Architecture Overview

### **Core Concept**
- **Task Tool Delegation**: `Task` tool accepts `subagent_type` parameter that maps to agent file names
- **Separate Context**: Each agent gets independent context window when invoked
- **Specialized Expertise**: Each agent has focused domain knowledge and capabilities
- **Tool Access**: Agents inherit all tools unless specifically restricted

### **Invocation Pattern**
```javascript
Task({
  subagent_type: "code-review",  // Maps to code-review.md
  description: "Review PR changes",
  prompt: "Detailed task instructions..."
})
```

## 🔧 Current Agent Inventory

### **1. `code-review.md` - Multi-Language Code Analysis Specialist**
- **Focus**: Security vulnerabilities, bug detection, performance, code quality
- **Specializations**: Python (Django/Flask), JavaScript/Node.js, Web Security (OWASP Top 10)
- **Output**: Structured severity-based reviews (🔴 Critical → 🟢 Nitpicks)
- **Integration**: Uses Context7 MCP for up-to-date API documentation
- **When to Use**: Comprehensive code review, security analysis, quality assessment

### **2. `copilot-fixpr.md` - PR Issue Implementation Specialist**
- **Focus**: **Actual code fixes** for GitHub PR blockers (NOT just acknowledgment)
- **CRITICAL**: Must execute `/fixpr` command first to resolve merge conflicts/CI failures
- **Protocol**: File Justification Protocol compliance mandatory for all changes
- **Anti-Pattern**: Prevents "performative fixes" - requires actual file modifications
- **When to Use**: Implementing fixes for security, runtime errors, test failures, merge conflicts

### **3. `copilot-verifier.md` - Copilot Run Quality Auditor**
- **Focus**: Independent post-run verification of `/copilot` work against KPIs (REV-962a7)
- **Independence**: Zero execution context from copilot - only artifacts and git history
- **Tools**: Read-only (Read, Glob, Grep, Bash for git/gh, WebFetch) - cannot modify files
- **Checks**: 7 verification checks: closure rate, scope discipline, tracking_reason quality, status truthfulness, pair-workflow compliance, STYLE budget, reply consistency
- **Output**: `verification_report.json` with PASS/FAIL/PARTIAL verdict per check
- **Model**: Sonnet recommended (judgment checks 3/4), haiku acceptable for mechanical-only checks (1/2/5/6/7)
- **When to Use**: After `/copilot` Step 9 (push) as a blocking gate before tracking table update
- **Pattern**: Mirrors testexecutor → testvalidator separation applied to the copilot workflow

### **4. `long-runner.md` - Extended Task Execution Specialist**
- **Focus**: Tasks >5 minutes with 10-minute timeout enforcement and forced summarization
- **Output**: File-based results in `/tmp/long-runner/{branch}/task_{timestamp}_{uuid}.md`
- **Timeout**: Hard 10-minute limit with progress tracking and partial result preservation
- **Context Optimization**: Detailed logs to files, 3-sentence summaries to main conversation
- **When to Use**: Complex analysis, research, multi-step workflows, large codebase operations

### **5. `testexecutor.md` - Evidence Collection Testing Specialist**
- **Focus**: **Evidence collection ONLY** - NO success/failure judgments
- **Constraint**: Pure documentation robot - captures observations without interpretation
- **Tools**: Playwright MCP browser automation, real authentication testing
- **Output**: Structured JSON evidence packages with screenshots, logs, console output
- **When to Use**: Systematic testing with evidence collection for later validation

### **6. `testvalidator.md` - Independent Test Assessment Specialist**
- **Focus**: Critical auditor analyzing evidence against original specifications
- **Independence**: Zero context from TestExecutor - fresh eyes evaluation only
- **Authority**: Validator assessment is final in case of disagreements
- **Output**: Pass/Fail decisions with confidence ratings based on evidence quality
- **When to Use**: Independent validation of test results, evidence quality assessment

### **7. `codex-consultant.md` - External AI Analysis Specialist**
- **Focus**: Deep code analysis using external Codex CLI (`codex exec`)
- **CRITICAL**: Must execute actual `codex exec` command - no self-analysis allowed
- **Methodology**: Multi-stage analysis (static, security, performance, architectural)
- **When to Use**: Claude gets stuck, needs alternative perspective, complex pattern analysis

### **8. `gemini-consultant.md` - External Consultation Specialist**
- **Focus**: External AI guidance using Gemini CLI (`gemini -p`)
- **CRITICAL**: Must execute actual `gemini -p` command - no self-analysis allowed
- **Analysis**: Correctness, architecture, security, performance, PR goal alignment
- **When to Use**: User explicitly requests Gemini opinion, technical decision validation

### **9. `opencode-pair-coder.md` - OpenCode CLI Coder (Wafer)**
- **Focus**: Delegates implementation to OpenCode CLI via `opencodew()` wrapper
- **Backend**: Wafer API (`https://pass.wafer.ai/v1`), model `wafer.ai/GLM-5.2`
- **CLI Routing**: Mirrors `opencodew()` case statement — subcommands pass through, `run` mode uses `--dangerously-skip-permissions`, flags use interactive mode
- **Requires**: `WAFER_API_KEY` env var, `opencode` binary at `~/.opencode/bin/`
- **When to Use**: Pair programming with Wafer-powered OpenCode as coder teammate

### **10. `opencode-pair-verifier.md` - OpenCode CLI Verifier (Wafer)**
- **Focus**: Delegates verification to OpenCode CLI via `opencodew()` wrapper
- **Backend**: Same Wafer API as coder, runs independently
- **Fallback**: Falls back to native verification if CLI unavailable
- **When to Use**: Pair programming with Wafer-powered OpenCode as verifier teammate

### **11. `openw-pair-coder.md` - OpenCode CLI Coder via openw()**
- **Focus**: Delegates implementation to OpenCode CLI via `openw()` / `opencodew()` wrapper
- **Backend**: Wafer API (`https://pass.wafer.ai/v1`), model `wafer.ai/GLM-5.2`
- **CLI Routing**: Mirrors `openw()` / `opencodew()` case statement from `~/.bashrc` exactly
- **Requires**: `WAFER_API_KEY` env var, `opencode` binary at `~/.opencode/bin/`
- **When to Use**: Pair programming with Wafer-powered OpenCode — prefer this over `opencode-pair-coder` for bashrc-native routing

### **12. `openw-pair-verifier.md` - OpenCode CLI Verifier via openw()**
- **Focus**: Delegates verification to OpenCode CLI via `openw()` / `opencodew()` wrapper
- **Backend**: Same Wafer API as coder, runs independently
- **Fallback**: Falls back to native verification if CLI unavailable
- **When to Use**: Pair programming verification with Wafer-powered OpenCode — prefer this over `opencode-pair-verifier` for bashrc-native routing

## 🔄 Agent Coordination Patterns

### **Parallel Execution**
- **copilot-fixpr + analysis agents**: Implementation and communication coordination
- **testexecutor + testvalidator**: Evidence collection → independent validation pipeline
- **Multiple review agents**: code-review, codex-consultant, gemini-consultant work simultaneously

### **Sequential Workflows**
- **Testing Pipeline**: testexecutor (evidence) → testvalidator (assessment)
- **Copilot Pipeline**: /copilot (fix + respond) → copilot-verifier (audit) → tracking table update
- **PR Review**: code-review → copilot-fixpr → external consultants (if needed)
- **Complex Analysis**: long-runner → specialized agents for deep investigation

### **Timeout Behavior**
- **long-runner**: 10-minute hard timeout with forced summarization
- **External consultants**: 5-minute timeout with explicit error reporting
- **Other agents**: No specific timeout - rely on natural task completion

## 🚨 Critical Implementation Notes

### **Timeout Enforcement Gap**
- **Documentation Promise**: long-runner.md specifies 10-minute hard timeout
- **Implementation Reality**: Currently instruction-based (unreliable)
- **Production Risk**: Agents may not reliably self-enforce timeout constraints
- **Solution Needed**: System-level enforcement mechanism required

### **Tool Execution Requirements**
- **External Consultants**: MUST use `codex exec` and `gemini -p` commands
- **File Modifications**: copilot-fixpr MUST use Edit/MultiEdit tools for actual changes
- **Evidence Collection**: testexecutor MUST use Playwright MCP for real browser testing
- **Anti-Pattern**: Agents providing self-analysis instead of using specified tools

### **Protocol Compliance**
- **File Justification**: copilot-fixpr must document necessity for all file changes
- **Integration-First**: Prefer existing file modification over new file creation
- **Evidence-Based**: testvalidator requires proof files for all claims
- **Independence**: testvalidator gets zero context from testexecutor

### **File Tracking & Proactive Beads Usage**
- **NEVER gitignore .beads/**: Issue tracking database must be version controlled
- **User Requirement**: `.beads/` directory and contents MUST be tracked in git
- **Proactive Bead Creation**: When agents discover bugs, regressions, test failures, or architectural issues during their work, they should proactively create beads using `bd create "<description>"` rather than only logging or reporting the issue. Beads are the project's canonical issue tracker — if something is worth mentioning, it's worth a bead.
- **Bead Lifecycle**: Update beads as work progresses (`bd update <id> --status in_progress`), and close them when resolved (`bd update <id> --status done`). Always include `.beads/` diffs in commits.

## 🎯 Usage Guidelines

### **Task Tool Best Practices**
```javascript
// Good - Specific agent with clear task
Task({
  subagent_type: "code-review",
  description: "Security analysis of auth system",
  prompt: "Analyze authentication implementation for security vulnerabilities..."
})

// Bad - Wrong agent for task
Task({
  subagent_type: "testexecutor",
  description: "Fix the failing tests",  // testexecutor only collects evidence
  prompt: "Make the tests pass..."
})
```

### **Agent Selection Matrix**
| Task Type | Agent | Reason |
|-----------|--------|---------|
| Code Review | code-review | Comprehensive analysis with severity categorization |
| Implement Fixes | copilot-fixpr | Actual file modifications with protocol compliance |
| Copilot Run Audit | copilot-verifier | Post-run quality verification (sonnet for judgment, haiku for mechanical) |
| Complex Research | long-runner | Extended analysis with timeout management |
| Test Evidence | testexecutor | Systematic evidence collection without judgment |
| Test Validation | testvalidator | Independent assessment with fresh context |
| Alternative Analysis | codex/gemini-consultant | External AI perspective when needed |
| Wafer Pair Coder | opencode-pair-coder | OpenCode CLI + Wafer API for implementation |
| Wafer Pair Verifier | opencode-pair-verifier | OpenCode CLI + Wafer API for independent verification |
| openw Pair Coder | openw-pair-coder | OpenCode CLI via openw() + Wafer API (mirrors bashrc) |
| openw Pair Verifier | openw-pair-verifier | OpenCode CLI via openw() + Wafer API (mirrors bashrc) |

### **When NOT to Use Agents**
- **Simple Tasks**: Direct execution often more efficient than agent overhead
- **Interactive Workflows**: Agents work in isolation - use for autonomous tasks
- **Real-time Debugging**: Agent context isolation prevents interactive troubleshooting

## 🔍 Troubleshooting Agent Issues

### **Agent Not Found**
- Check file exists in `.claude/agents/` with exact name matching `subagent_type`
- Verify Markdown format with proper YAML frontmatter

### **Agent Not Responding**
- Timeout may have occurred (check for timeout-related error messages)
- Agent may be waiting for external tool execution (codex, gemini commands)

### **Agent Giving Wrong Output**
- Check if using correct agent type for the task
- Review agent's documented focus area and constraints
- Consider if task requires different agent or direct execution

### **File Modification Not Happening**
- Verify copilot-fixpr is being used for actual implementations
- Check that agent has proper tool access (Edit, MultiEdit capabilities)
- Ensure File Justification Protocol is being followed

## 🚀 Future Improvements Needed

### **System-Level Timeout Enforcement**
- Implement actual process-level timeouts for long-runner
- Add timer-based termination beyond instruction compliance
- Ensure partial result preservation under forced termination

### **Agent Coordination Enhancement**
- Standardize parallel execution patterns
- Define clear handoff protocols between specialized agents
- Implement coordination data sharing for complex workflows

### **External Tool Validation**
- Add tool availability checks before agent deployment
- Implement graceful degradation when external tools unavailable
- Standardize timeout and error handling across external consultants

---

**Remember**: These agents are sophisticated custom implementations that demonstrate expert-level Claude Code architecture understanding, not Anthropic defaults. They provide production-ready specialized capabilities through the Task tool delegation system.
