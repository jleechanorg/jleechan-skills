# Workflows & Automation Patterns

**Unique workflows from production usage**

---

## Overview

These workflows emerged from 19,044 commits over 6 months. They're not theoretical - they're battle-tested in production.

**Key Philosophy:** "Focus on AI review/quality as much as generation, if not more"

---

## 🎯 The 12-Step Multi-AI Development Workflow

**Source:** Production workflow from WorldArchitect.AI development

### Overview
A complete development lifecycle leveraging multiple AI models, automated review, and quality gates. This workflow uses web-based AI for initial development, local tools for complex changes, and automated systems for review and refinement.

### Phase 1: Web-Based Development (Steps 1-4)

**Step 1: Initial Coding with Claude Web**
- **Tool:** Claude web (claude.ai)
- **Why:** "Most permissive" container capabilities for rapid iteration
- **Use:** First-pass implementation, prototyping

**Step 2: Iteration with Claude or Codex**
- **Tools:** Claude web OR Codex web
- **Decision criteria:**
  - Claude: Speed and creativity
  - Codex: Precision and technical accuracy
  - Consider API quota limitations
- **Pattern:** Iterate until feature complete

**Step 3: Automated Code Review (4 Bots)**
- **Tools:** CodeRabbit, bugbot, GitHub Copilot, Codex
- **Deployment:** GitHub workflows trigger on PR
- **Purpose:** Parallel review from multiple perspectives

**Step 4: Automated Testing**
- **Tool:** GitHub Actions workflows
- **Tests:** Unit, integration, E2E
- **Gate:** Must pass before proceeding

### Phase 2: Local Development (Steps 5-8)

**Step 5: Pull Complex Changes to Local**
- **Trigger:** Web tools reach limitations
- **Environment:** MacBook with local AI tools
- **Advantage:** Full control, custom tooling

**Step 6: Claude for Speed, Codex for Precision**
- **Primary:** Claude Code CLI (fast iteration)
- **Secondary:** Codex (verification, precision)
- **Pattern:** Claude generates → Codex verifies

**Step 7: Multi-Tool Review**
- **Tools:** Cursor Composer, Gemini 3
- **Purpose:** Additional perspectives on code quality

**Step 8: Custom MCP Server Review**
- **Tool:** Multi-model AI MCP server
- **Purpose:** Coordinated review across models
- **Models:** Claude, Gemini, Grok, Perplexity

### Phase 3: Automation & Finalization (Steps 9-12)

**Step 9: Manual Review of AI Summaries**
- **Trigger:** Larger changes requiring human judgment
- **Input:** Aggregated AI feedback
- **Decision:** Proceed, iterate, or redesign

**Step 10: Automated Fix Requests**
- **Tool:** Cron jobs
- **Actions:**
  - Request fixes from Codex
  - Gather review feedback from bots
- **Frequency:** Scheduled automation

**Step 11: Automated Conflict Resolution**
- **Tools:** Automated merge conflict resolution
- **Testing:** Automated test fixing
- **Safety:** Only non-breaking changes

**Step 12: Final Manual Decision**
- **Human:** Make merge decision
- **Inputs:** All AI feedback, test results, conflict status
- **Action:** Merge or request additional changes

### Critical Success Factors

1. **Quality Over Speed**
   - "Focus on AI review/quality as much as generation"
   - Multiple review stages with different tools
   - Automated testing at every step

2. **Tool Specialization**
   - Claude: Speed and creativity
   - Codex: Precision and verification
   - Cursor: Interactive refinement
   - Gemini: Alternative perspective

3. **Automation Where Possible**
   - GitHub workflows for testing
   - Cron jobs for routine fixes
   - Automated conflict resolution
   - Parallel review execution

4. **Human-in-the-Loop**
   - Manual review of summaries (Step 9)
   - Final merge decision (Step 12)
   - Override automation when needed

### Evidence in This Repo

This workflow is visible in the git evidence:
- **4 agent branch prefixes** (copilot/, cursor/, codex/, claude/)
- **343 `/copilot` uses** (automated PR processing)
- **268 Codex mentions** (verification role)
- **1,285 mcp-cli uses** (multi-model coordination)
- **3,308 testing commits** (17.4% of all work)

### Comparison: Web vs Local Development

| Aspect | Web (Steps 1-4) | Local (Steps 5-8) |
|--------|-----------------|-------------------|
| **Speed** | Fast (no setup) | Medium (tool loading) |
| **Customization** | Limited | Full (80+ commands) |
| **Automation** | GitHub only | Full local automation |
| **Models** | Web interfaces | MCP integration |
| **Complexity** | Simple changes | Complex refactors |

---

## 🤖 Multi-Agent Orchestration

### Evidence
- **4 agent branch prefixes:** `copilot/`, `cursor/`, `codex/`, `claude/`
- **287 orchestration commits**
- **1,397 `/orch` command references**
- **28 mcp_mail hits** for agent communication

### How It Works

**1. tmux Session Management**
```bash
# Create orchestration session
tmux new -s orch-session

# Spawn agent windows
tmux new-window -n copilot
tmux new-window -n cursor
tmux new-window -n codex
```

**2. Agent-to-Agent Communication**
- Via **mcp_mail** MCP server
- Repo: https://github.com/jleechanorg/mcp_mail
- Agents send/receive messages
- Async coordination

**3. Task Distribution**
- `orchestration/task_dispatcher.py` (111KB file!)
- Distributes work to specialized agents
- Monitors agent health
- Handles failures and retries

**4. Branch Coordination**
- Each agent creates own branch
- Naming: `{agent_name}/task-description`
- Autonomous PR creation
- Review and merge coordination

### Example Workflow
```
User: /orch fix all PR comments

1. Orchestrator reads PR comments
2. Categorizes by type (CRITICAL, BLOCKING, IMPORTANT)
3. Spawns specialized agents:
   - copilot/ → Security issues
   - cursor/ → UI/UX fixes
   - codex/ → Logic bugs
   - claude/ → Documentation
4. Agents work in parallel
5. Each creates branch and commits
6. Orchestrator merges when all complete
```

### Key Files
- `orchestration/orchestrate_unified.py` - Main orchestrator
- `orchestration/agent_system.py` - Agent management
- `orchestration/a2a_integration.py` - Agent-to-agent messaging
- `orchestration/task_dispatcher.py` - Task distribution

---

## 🔄 `/copilot` - Autonomous PR Processing

### Evidence
- **7,950 diff references** (#1 command)
- **68 file commits** (actively refined)
- **626 commit mentions**

### 4-Phase Workflow

**Phase 0: Critical Bug Scan**
```
Priority: CRITICAL, SECURITY
Action: Immediate fix, no waiting
Output: Critical issues resolved or flagged
```

**Phase 1: Comment Categorization**
```
Categories:
- BLOCKING: Must fix before merge
- IMPORTANT: Should fix before merge
- ROUTINE: Nice to have

Triage: Based on keywords, severity, file impact
```

**Phase 2: Implementation**
```
Hybrid execution:
- Direct implementation: Simple fixes
- Agent delegation: Complex changes

Parallel work:
- Multiple agents on independent issues
- Sequential for dependent changes
```

**Phase 3: Verification**
```
- Run tests for each fix
- Verify no new failures
- Commit tracking
- Evidence generation
```

### Usage
```bash
/copilot

# Automatically:
1. Fetches all PR comments
2. Categorizes by priority
3. Implements fixes
4. Runs tests
5. Commits changes
6. Reports results
```

### Integration
- Uses `/commentfetch` (2,440 refs)
- Uses `/commentreply` (4,007 refs)
- Uses `/commentcheck` (1,269 refs)
- Uses `/fixpr` (5,124 refs) for complex fixes

---

## 🛠️ `/fixpr` - Intelligent PR Fixing

### Evidence
- **5,124 diff references** (#2 command)
- **1,299 commit mentions**
- **20 file commits**

### Workflow

**1. Analysis Phase**
```
- Read PR description
- Analyze failed checks
- Review reviewer comments
- Understand context
```

**2. Root Cause Identification**
```
- Find failing tests
- Identify error patterns
- Trace to source files
- Determine fix scope
```

**3. Implementation**
```
- Minimal code changes
- Fix root cause, not symptoms
- Update tests if needed
- Verify in isolation
```

**4. Validation**
```
- Run affected tests
- Check for regressions
- Verify CI passes
- Update PR description
```

### Usage
```bash
/fixpr

# Or with specific PR
/fixpr 123
```

---

## 🧪 `/redgreen` - Test-Driven Development

### Evidence
- **3,817 combined references** (/redgreen + /tdd)
- **162 commit mentions**
- **3,308 testing commits** (17.4% of all work)

### Red-Green Workflow

**Step 1: Red (Write Failing Test)**
```bash
# Create test that fails
pytest tests/test_new_feature.py

# Expected: FAIL
```

**Step 2: Confirm Failure**
```bash
# Verify test actually fails
# Not false positive
```

**Step 3: Green (Minimal Code)**
```bash
# Write MINIMAL code to pass
# No gold-plating
# No extra features
```

**Step 4: Verify Green**
```bash
# Test should now pass
pytest tests/test_new_feature.py

# Expected: PASS
```

**Step 5: Refactor**
```bash
# Clean up code
# Keep tests passing
# Improve design
```

**Step 6: Commit**
```bash
git add .
git commit -m "feat: Add feature X with TDD

Wrote failing test, confirmed red, implemented minimal code, verified green.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Evidence-Based Testing

**Pattern:** `/tmp/worldarchitect.ai/<branch>/<test>/iteration_XXX/`

```
/tmp/worldarchitect.ai/fix/feature-x/my_test/iteration_001/
├── README.md (test description)
├── evidence.md (results)
├── test_output.log (raw output)
├── screenshots/ (if browser test)
└── network_traces/ (if API test)

# Symlink to latest
/tmp/worldarchitect.ai/fix/feature-x/my_test/latest -> iteration_001
```

**Rules:**
1. ALWAYS use full absolute paths (never abbreviate)
2. Create new iteration for each run
3. Review evidence before claiming success
4. Include in PR as proof

---

## 🔍 `/generatetest` - Test Generation

### Evidence
- **82 file commits** (most-modified command!)
- Active development

### Workflow

**1. Analyze Code**
```
- Read implementation
- Identify edge cases
- Find happy paths
- Spot error conditions
```

**2. Generate Tests**
```
- Unit tests for functions
- Integration tests for flows
- E2E tests for user journeys
- Property tests for invariants
```

**3. Evidence Bundle**
```
- Generate in /tmp/ structure
- Include test file
- Include sample runs
- Document coverage
```

### Usage
```bash
/generatetest path/to/code.py
```

---

## 🌐 Browser Testing

### Tools
- **Playwright** (69 commits)
- **Chrome DevTools Protocol** (407 MCP hits)
- **MCP servers:** chrome-superpower, claude-in-chrome, plugin_superpowers-chrome_chrome

### Pattern

**NOT using `/browser` command** (last commit Nov 2025)

**Instead: Direct MCP calls**
```bash
# Navigate
mcp-cli call chrome-superpower/navigate '{"url": "http://localhost:3000"}'

# Click
mcp-cli call claude-in-chrome/click '{"selector": "#login-button"}'

# Execute JS
mcp-cli call chrome-superpower/eval '{"code": "document.title"}'

# Screenshot
mcp-cli call claude-in-chrome/screenshot '{"path": "/tmp/screenshot.png"}'
```

### Why Direct MCP > Command
- Faster (no command overhead)
- More control (access all MCP features)
- Better for automation (scriptable)

---

## 🧠 Multi-Model Validation (`/secondo`)

### Evidence
- **106 commit mentions**
- **49 file commits**

### Workflow

**1. Primary Implementation**
```
Use primary AI (Claude Code) for implementation
```

**2. Second Opinion**
```bash
/secondo "Review this implementation for correctness"

# Queries multiple models:
- Gemini (via MCP)
- Grok (via MCP)
- Perplexity (via MCP)
```

**3. Comparison**
```
- Identify disagreements
- Investigate discrepancies
- Decide on consensus or best approach
```

**4. Refinement**
```
- Update implementation
- Document decision rationale
- Re-verify with models if needed
```

### Use Cases
- Security-critical code
- Complex algorithms
- Architectural decisions
- Unfamiliar domains

---

## 📦 PR Automation (`automation/`)

### Evidence
- **Directory:** `automation/` in main repo
- **2,323 file touches** in `automation/jleechanorg_pr_automation/`

### Key Components

**1. orchestrated_pr_runner.py**
- Batch PR processing
- Parallel execution
- Rate limiting
- Error handling

**2. simple_pr_batch.sh**
- Shell wrapper for PR batches
- Cron-compatible
- Logging and monitoring

**3. jleechanorg_pr_automation/**
- Python package for PR automation
- GitHub API integration
- Comment parsing
- Status tracking

### Workflow
```
1. Cron job triggers batch run
2. Fetch open PRs
3. For each PR:
   - Fetch comments
   - Categorize issues
   - Delegate to /copilot
   - Monitor progress
4. Aggregate results
5. Send summary notification
```

---

## 🎯 Comment Automation

### Commands
- **`/commentfetch`** (2,440 refs) - Fetch PR comments
- **`/commentreply`** (4,007 refs) - Reply to comments
- **`/commentcheck`** (1,269 refs) - Validate comments addressed

### Workflow

**1. Fetch**
```bash
/commentfetch 123

# Returns:
- All unresolved comments
- Categorized by file
- Priority scored
```

**2. Process**
```
- Group by file
- Identify dependencies
- Plan fix order
```

**3. Reply**
```bash
/commentreply "Fixed in commit abc123"

# Automatically:
- Marks comment as resolved
- Links to commit
- Notifies reviewer
```

**4. Verify**
```bash
/commentcheck

# Confirms:
- All comments addressed
- No new comments
- Ready for review
```

---

## 🚀 Fast Code Generation (`/cerebras`)

### Evidence
- **4,901 combined references** (/cerebras + /cereb)
- **246 commit mentions**

### Workflow

**Standard Mode**
```bash
/cerebras "Implement feature X"

# Structured output
# Design → Implementation → Tests
```

**Light Mode (Faster)**
```bash
/cerebras --light "Quick prototype of Y"

# Raw code generation
# No structure overhead
```

### Use Cases
- Large code scaffolding
- Repetitive patterns
- Documentation generation
- Test fixture creation

### Speed
- **1000+ tokens/second** (fastest inference available)
- Good for bulk generation
- Trade-off: less reasoning than Claude

---

## 🔄 Branch Management (`/sync`)

### Evidence
- **26 file commits**

### Workflow

**1. Fetch Latest Main**
```bash
git fetch origin main
```

**2. Identify Conflicts**
```
Compare current branch with main
Detect potential merge issues
```

**3. Safe Merge**
```
Option 1: Rebase (clean history)
Option 2: Merge (preserve history)
User choice based on context
```

**4. Conflict Resolution**
```
- Show conflicts
- Suggest resolutions
- Verify tests pass
```

### Usage
```bash
/sync

# Automatically:
1. Fetches main
2. Analyzes diff
3. Proposes merge strategy
4. Handles conflicts
5. Runs tests
6. Pushes if clean
```

---

## 📊 Testing Metrics

### Coverage
- **3,308 testing commits** (17.4% of all work)
- **7,670 file touches** in `mvp_site/tests/`

### Test Types
1. **Unit tests** - pytest
2. **Integration tests** - Multi-component
3. **E2E tests** - Full user flows
4. **LLM tests** - Via `/testllm` (2,172 refs)
5. **Browser tests** - Playwright (69 commits)

### Evidence Standard
- Full paths always
- Structured bundles
- Mandatory review
- Linked in PRs

---

## 🎛️ Custom Configuration

### Claude Code Settings
- **290 lines** of custom config
- **150+ pre-approved permissions**
- **12+ hooks** (PreToolUse, PostToolUse, UserPromptSubmit)

### Hooks

**PreToolUse:**
- Context validation
- Command optimization
- File creation blocking

**PostToolUse:**
- **Fake code detection** (automatic quality gate)
- Output trimming
- Evidence validation

**UserPromptSubmit:**
- Command composition
- Slash command expansion

#### Automatic `/fake` Code Quality Hook

**Hook:** `smart_fake_code_detection.sh`

**Trigger:** After EVERY `Write` operation (PostToolUse)

**What it does:**
```bash
# Runs headlessly after each file write
claude -p << EOF
/fake
${FILE_LIST}
Analyze these changes for fake or simulated code,
placeholder logic, speculative API responses, or
fabricated data.
EOF
```

**Evidence:** 343 automatic invocations in last week (Feb 5-12, 2026)

**Configuration:**

1. **Hook Registration** (in `.claude/settings.json`):
```json
{
  "PostToolUse": [
    {
      "matcher": "Write",
      "hooks": [
        {
          "type": "command",
          "command": "bash -c 'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ROOT=$(git rev-parse --show-toplevel); [ -x \"$ROOT/.claude/hooks/smart_fake_code_detection.sh\" ] && exec \"$ROOT/.claude/hooks/smart_fake_code_detection.sh\"; fi; exit 0'",
          "description": "Run automated /fake audits via claude -p after file writes"
        }
      ]
    }
  ]
}
```

2. **Environment Variables:**
- `SMART_FAKE_TIMEOUT` - Timeout for `/fake` audit (default: 120 seconds)
- `SMART_FAKE_HOOK_ACTIVE` - Prevents recursive invocation (set automatically)

3. **Hook File Location:**
- Project: `.claude/hooks/smart_fake_code_detection.sh`
- Global: `~/.claude/hooks/smart_fake_code_detection.sh`

4. **Logs:**
- Location: `/tmp/claude-code-logs/smart_fake_code_detection_${BRANCH}.log`
- Format: Timestamped entries with file lists and results

**Setup Instructions:**

```bash
# 1. Copy hook file to project
cp ~/.claude/hooks/smart_fake_code_detection.sh .claude/hooks/

# 2. Make executable
chmod +x .claude/hooks/smart_fake_code_detection.sh

# 3. Add registration to .claude/settings.json (see above)

# 4. Optional: Set timeout
export SMART_FAKE_TIMEOUT=180  # 3 minutes

# 5. Test - write any file and check logs
echo "test" > test.txt
tail /tmp/claude-code-logs/smart_fake_code_detection_*.log
```

**Why This Matters:**

- **Automatic quality gate** - Every file write is audited
- **No manual invocation** - Runs silently in background
- **Fast feedback** - Catches issues before commit
- **Evidence-based** - Logs all audits for review

**Companion Hook:** `detect_speculation_and_fake_code.sh`
- Runs on ALL PostToolUse events (not just Write)
- AGGRESSIVE detection with strong warnings
- Configured separately in settings.json

### Skill Files
- **40+ skill files** in `.claude/skills/`
- **Most-modified:** evidence-standards.md (68 commits)
- Procedural knowledge base
- Referenced by commands

---

## 🔌 MCP Heavy Usage Pattern

**Evidence:** 1,285 mcp-cli mentions in last week (Feb 5-12, 2026)

### Why MCP is Central

MCP (Model Context Protocol) enables **multi-model coordination** - the key to advanced AI workflows.

**10 Active MCP Servers:**
1. `plugin_superpowers-chrome_chrome` - Obra Superpowers Chrome
2. `sequential-thinking` (649 hits) - Enhanced reasoning
3. `context7` (341 hits) - Library documentation
4. `chrome-superpower` (407 hits) - Browser automation
5. `gemini-cli-mcp` (1,440 hits) - Gemini API (HIGHEST)
6. `grok` (670 hits) - X.ai real-time intelligence
7. `perplexity-ask` (661 hits) - Research/search
8. `beads` (539 hits) - Task tracking
9. `mcp_mail` (28 hits) - Agent messaging
10. `claude-in-chrome` - Chrome extension control

### Usage Pattern

**Direct MCP Calls (Preferred over Commands)**

Instead of:
```bash
/browser navigate http://localhost:3000
```

Use MCP directly:
```bash
mcp-cli call chrome-superpower/navigate '{"url": "http://localhost:3000"}'
```

**Why:**
- Faster (no command overhead)
- More control (access all MCP features)
- Better for automation (scriptable)
- Composable (pipe-able)

### Real Usage Examples

**1. Multi-Model Research (`/perp` command)**
```bash
# Single command queries 4+ sources
mcp-cli call perplexity-ask/perplexity_search_web '{"query": "..."}'
mcp-cli call gemini-cli-mcp/gemini_chat_pro '{"messages": [...]}'
mcp-cli call grok/grok_send_message '{"message": "..."}'
# + WebSearch built-in
# + DuckDuckGo
```

Evidence: 943 `/perp` references = heavy multi-model research

**2. Browser Automation (NOT `/browser` command!)**
```bash
# Navigate
mcp-cli call chrome-superpower/navigate '{"url": "..."}'

# Click element
mcp-cli call claude-in-chrome/click '{"selector": "#login"}'

# Execute JavaScript
mcp-cli call chrome-superpower/eval '{"code": "document.title"}'

# Screenshot
mcp-cli call claude-in-chrome/screenshot '{"path": "/tmp/screenshot.png"}'
```

Evidence: 407 chrome MCP hits, 405 Playwright mentions

**3. Task Tracking with Beads**
```bash
# List tasks
mcp-cli call beads/list '{}'

# Create task
mcp-cli call beads/create '{"subject": "...", "description": "..."}'

# Update task
mcp-cli call beads/update '{"taskId": "123", "status": "completed"}'
```

Evidence: 539 beads MCP hits, binary accessed daily

**4. Sequential Thinking (Enhanced Reasoning)**
```bash
mcp-cli call sequential-thinking/sequentialthinking '{"task": "complex problem"}'
```

Evidence: 649 MCP hits - used for complex architectural decisions

### Setup: Enabling MCP Servers

**1. Install MCP CLI:**
```bash
npm install -g @modelcontextprotocol/cli
```

**2. Verify Servers:**
```bash
mcp-cli servers
# Should show all 10 connected servers
```

**3. Test a Server:**
```bash
# Check schema first
mcp-cli info gemini-cli-mcp/gemini_chat_pro

# Then call
mcp-cli call gemini-cli-mcp/gemini_chat_pro '{"messages": [{"role": "user", "content": "test"}]}'
```

**4. Add to Custom Commands:**
```bash
# In .claude/commands/mycommand.md
/execute Call gemini and perplexity for second opinion:
- mcp-cli call gemini-cli-mcp/gemini_chat_pro '{...}'
- mcp-cli call perplexity-ask/perplexity_search_web '{...}'
Compare results and synthesize
```

### Integration Patterns

**Pattern 1: Multi-Model Validation**
```bash
# /secondo command implementation
query="$1"
gemini_result=$(mcp-cli call gemini-cli-mcp/gemini_chat_pro "{\"messages\": [{\"role\": \"user\", \"content\": \"$query\"}]}")
grok_result=$(mcp-cli call grok/grok_send_message "{\"message\": \"$query\"}")
perplexity_result=$(mcp-cli call perplexity-ask/perplexity_search_web "{\"query\": \"$query\"}")

# Compare and synthesize
claude "Compare these responses:\n1. Gemini: $gemini_result\n2. Grok: $grok_result\n3. Perplexity: $perplexity_result"
```

Evidence: 106 `/secondo` commits

**Pattern 2: Browser + Task Tracking**
```bash
# Run browser test and log to beads
test_result=$(mcp-cli call chrome-superpower/navigate '{"url": "..."}')
if [ $? -ne 0 ]; then
  mcp-cli call beads/create "{\"subject\": \"Browser test failed\", \"description\": \"$test_result\"}"
fi
```

Evidence: 539 beads + 407 chrome MCP hits = integrated workflow

**Pattern 3: Research → Documentation**
```bash
# Research with perplexity, document with claude
research=$(mcp-cli call perplexity-ask/perplexity_search_web '{"query": "..."}')
docs=$(mcp-cli call context7/get-library-docs '{"library": "react"}')

# Synthesize into documentation
claude "Write docs based on:\nResearch: $research\nOfficial docs: $docs"
```

Evidence: 661 perplexity + 341 context7 hits

### Why 1,285 Uses in One Week?

**MCP enables:**
1. **Multi-model workflows** - Query multiple AIs in parallel
2. **Automation** - Script complex workflows
3. **Integration** - Connect disparate tools
4. **Specialization** - Use right model for each task

**Without MCP:** Single AI, limited capabilities
**With MCP:** Coordinated multi-AI system

---

## 💡 Key Patterns

### 1. Terminal-First
- CLI over GUI
- Scriptable workflows
- Composable tools

### 2. Evidence-Based
- Full paths always
- Structured artifacts
- Mandatory review

### 3. Multi-Agent
- Parallel execution
- Specialized agents
- Coordinated merges

### 4. Quality-First
- 17.4% of commits are tests
- Pre/post-commit hooks
- Automated validation

### 5. Cost-Conscious
- Local classification (<50ms)
- Strategic AI use
- Batch operations

---

**Last Updated:** 2026-02-12
**Based On:** 19,044 commits (Aug 2025 - Feb 2026)
