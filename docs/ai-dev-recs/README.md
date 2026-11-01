# AI Development Recommendations

> Ported from [jleechanorg/ai_dev_recs](https://github.com/jleechanorg/ai_dev_recs) at `fd7b0ad` (2026-02-16). This is a dated snapshot: model names, tool versions, and usage counts reflect that period, not current defaults.

**Production-tested AI development toolchain for terminal-first workflows**

---

## 📑 Table of Contents

- [Executive Summary](#-executive-summary)
  - [**Quick Reference: All Tools**](#quick-reference-all-recommended-tools) ⭐
    - [AI Coding Tools (CLIs & IDEs)](#1-ai-coding-tools-clis--ides)
    - [Utilities & Tools](#2-utilities--tools)
    - [MCP Servers](#3-mcp-servers)
    - [Slash Commands](#4-slash-commands)
  - [Core Tools](#core-tools-daily-use)
  - [AI Assistants](#ai-assistants)
  - [MCP Servers](#mcp-servers)
  - [Automation Commands](#automation-commands)
- [Quick Stats](#-quick-stats)
- [Complete Stack](#-the-complete-stack)
- [Unique Innovations](#-unique-innovations)
- [Documentation](#-documentation)
- [Getting Started](#-getting-started)
- [Cost Breakdown](#-cost-breakdown)
- [Who This Is For](#-who-this-is-for)

---

## 📋 Executive Summary

### Quick Reference: All Recommended Tools

#### 1. AI Coding Tools (CLIs & IDEs)

| Tool | What It Is | Why We Recommend It |
|------|-----------|---------------------|
| **[Claude Code CLI](https://github.com/anthropics/claude-code)** | Anthropic's official command-line AI assistant with 200K context window | Terminal-first workflow enables scripting and automation. Extensible via MCP servers. Supports 80+ custom slash commands and multi-agent coordination. The foundation of the entire toolchain. |
| **[Cursor](https://cursor.sh/)** | VS Code fork with native AI pair programming | Best-in-class autocomplete (multi-line, contextual). Chat with codebase using @ symbols. Cmd+K for inline edits. $20/mo. |
| **[Codex CLI](https://codex.cli/)** | Alternative CLI AI assistant focused on precision | Excellent for precision work and verification. Provides detailed, accurate responses when you need high-quality output without iteration. |
| **[Antigravity](https://antigravity.com/)** | Web-based AI IDE with generous token limits | Unconstrained usage of Opus 4.6 and other premium models. Great for heavy workloads. **Warning:** Agent manager is flaky and crashes frequently - save work often. |

#### 2. Utilities & Tools

| Tool | What It Is | Why We Recommend It |
|------|-----------|---------------------|
| **[AI Usage Tracker](https://github.com/jleechanorg/ai-usage-tracker)** | Token usage and cost tracking for Claude Code and Codex CLI | Essential for monitoring AI spend across platforms. Combines usage data from multiple sources into unified reports with daily averages and cache efficiency metrics. Commands: `ai-usage-tracker` (pip) or `ai-usage-tracker-js` (npm). |
| **[Warp Terminal](https://www.warp.dev/)** | Modern terminal with AI features and enhanced UX | Built-in LLM inference for command suggestions and explanations. Renamable tabs for organization (critical when running multiple AI agents). Block-based output and command palette. Makes multi-agent workflows manageable. Free tier available. |

#### 3. MCP Servers

| MCP Server | What It Is | Why We Recommend It |
|-----------|-----------|---------------------|
| **[Gemini MCP](https://github.com/google/generative-ai-python)** | Google's LLM accessed via MCP integration | Provides structured output with JSON mode, code execution capabilities, and reliable fallback chains for production workloads. Multi-model coordination. |
| **[beads](https://github.com/modelcontextprotocol/servers/tree/main/src/beads)** | MCP-integrated task tracking system | AI agents can read/write tasks in real-time. Superior to Jira/Linear for AI-first workflows. |
| **[grok](https://modelcontextprotocol.io/)** | X.ai's real-time intelligence LLM | Real-time data and current events. Complements Claude and Gemini for fresh information. |
| **[perplexity-ask](https://modelcontextprotocol.io/)** | Research and web search via Perplexity | Fast research with citations. Better than manual Google searches for technical questions. |
| **[sequential-thinking](https://modelcontextprotocol.io/)** | Enhanced reasoning chains | Improves complex problem-solving by breaking down multi-step reasoning. |
| **[chrome-superpower](https://modelcontextprotocol.io/)** | Browser automation via Chrome DevTools Protocol | Automate web interactions, testing, and scraping directly from AI workflows. |
| **[context7](https://modelcontextprotocol.io/)** | Library documentation lookup | Instant access to up-to-date docs for any library without leaving terminal. |
| **[mcp_mail](https://github.com/jleechanorg/mcp_mail)** | Agent-to-agent messaging system | Enables AI agents to communicate, coordinate, and share context. Essential for multi-agent workflows and task handoffs. |

#### 4. Slash Commands

| Command | What It Is | Why We Recommend It |
|---------|-----------|---------------------|
| **[Obra Superpowers](https://superpowers.obra.dev/)** | Browser automation and control via Chrome extension | Direct browser control from Claude Code. Navigate, click, fill forms, screenshot - all from your AI workflow. Powerful for web testing and automation. |
| **/copilot** | Autonomous PR processing command | Handles 100+ comment PRs automatically. 4-phase workflow with priority-based triage (CRITICAL → BLOCKING → IMPORTANT → ROUTINE). Requires [gh CLI](https://cli.github.com/). |
| **/fixpr** | Intelligent PR fix automation | Analyzes failures, identifies root cause, makes minimal code changes. No gold-plating. Integrated verification. Requires [gh CLI](https://cli.github.com/). |
| **/redgreen** | Test-driven development workflow | Enforces red-green pattern with evidence-based testing. Structured artifacts for reproducibility. |
| **/fake** | Automatic code quality gate (hook) | Runs after EVERY Write operation. Catches 15% of code with issues (fake selectors, placeholder code). |
| **/execute** | General task execution command | Versatile command for running complex multi-step tasks. Heavy daily usage across all workflows. |

---

### Core Tools (Daily Use)

#### 1. Claude Code CLI
**What it is:** Anthropic's official command-line AI assistant with 200K context window

**Why valuable:**
- Terminal-first workflow (scriptable, automatable)
- Extensible via MCP servers (10 active integrations)
- Custom commands (80+ slash commands for specific workflows)
- Multi-agent coordination support

**How to install:**
```bash
# Install Claude Code
curl -fsSL https://cli.claude.ai/install.sh | sh

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."
```


**Detailed docs:** [TOOLCHAIN.md](TOOLCHAIN.md#claude-code-cli), [SETUP_GUIDE.md](SETUP_GUIDE.md#claude-code-cli)

---

#### 2. Gemini (Google)
**What it is:** Primary LLM backend via MCP integration

**Why valuable:**
- 1,440 MCP hits + 1,114 commit mentions (highest usage)
- Structured output with JSON mode
- Code execution capabilities
- Fallback chains for reliability

**How to install:**
```bash
# Via MCP server (gemini-cli-mcp)
# See MCP Servers section below
```


**Detailed docs:** [TOOLCHAIN.md](TOOLCHAIN.md#gemini-google), [WORKFLOWS.md](WORKFLOWS.md#-mcp-heavy-usage-pattern)

---

#### 3. beads (bd)
**What it is:** MCP-integrated task tracking system

**Why valuable:**
- AI can read/write tasks in real-time
- Used MORE than traditional issue trackers (259 commits)
- Binary accessed daily (last access: yesterday)

**How to install:**
```bash
# Already installed in the reference setup
bd list
bd create "Task description"
```


**Detailed docs:** [TOOLCHAIN.md](TOOLCHAIN.md#beads-bd), [WORKFLOWS.md](WORKFLOWS.md#-mcp-heavy-usage-pattern)

---

### AI Assistants

#### 4. Cursor
**What it is:** VS Code fork with native AI pair programming

**Why valuable:**
- Best-in-class autocomplete (multi-line, contextual)
- Chat with codebase using @ symbols
- Cmd+K for inline edits
- Active agent branches (`cursor/*`)

**How to install:**
```bash
# Download from https://cursor.sh/
# Install and sign in
```


**Cost:** $20/mo (Pro)

**Detailed docs:** [SETUP_GUIDE.md](SETUP_GUIDE.md#cursor)

---

#### 5. Warp Terminal
**What it is:** Modern terminal with AI features and better UX

**Why valuable:**
- **Built-in LLM inference** - Get command suggestions and explanations without leaving the terminal
- **Renamable tabs** - Critical for organizing multiple AI agent sessions (e.g., "copilot-agent", "cursor-build", "claude-review")
- **Block-based output** - Each command output is a distinct block, easier to scan when running long workflows
- **Command palette** - Search history and saved commands
- **Primary terminal for daily work** - Makes multi-agent orchestration manageable

**How to install:**
```bash
# Download from https://www.warp.dev/
```


**Cost:** Free

**Detailed docs:** [SETUP_GUIDE.md](SETUP_GUIDE.md#warp-terminal)

---

#### 6. Antigravity & Codex
**What they are:** Alternative AI IDEs for specialized tasks

**Why valuable:**
- Antigravity: Experimental features (web-based IDE)
- Codex: Precision and verification (CLI tool)
- Active agent branches (`codex/*`)

**How to install:**
```bash
# Download from official sites
```


**Detailed docs:** [TOOLCHAIN.md](TOOLCHAIN.md#antigravity--codex)

---

### MCP Servers

#### 7. MCP Ecosystem (10 Active Servers)
**What it is:** Model Context Protocol servers for multi-AI coordination

**Why valuable:**
- 1,285 mcp-cli uses in last week alone!
- Multi-model coordination (Gemini + Grok + Perplexity + Claude)
- Browser automation (chrome-superpower, claude-in-chrome)
- Research acceleration (context7 for docs, perplexity for search)

**How to install:**
```bash
npm install -g @modelcontextprotocol/cli
mcp-cli servers  # Verify active servers
```

**Active servers:**
1. **gemini-cli-mcp** (1,440 hits) - Gemini API
2. **grok** (670 hits) - X.ai real-time intelligence
3. **perplexity-ask** (661 hits) - Research/search
4. **sequential-thinking** (649 hits) - Enhanced reasoning
5. **beads** (539 hits) - Task tracking
6. **chrome-superpower** (407 hits) - Browser automation
7. **context7** (341 hits) - Library docs
8. **claude-in-chrome** - Chrome extension
9. **mcp_mail** (28 hits) - Agent messaging
10. **plugin_superpowers-chrome** - Obra Superpowers


**Detailed docs:** [WORKFLOWS.md](WORKFLOWS.md#-mcp-heavy-usage-pattern), [SETUP_GUIDE.md](SETUP_GUIDE.md#mcp-servers-10-active)

---

### Automation Commands

#### 8. /copilot
**What it is:** Autonomous PR processing command

**Why valuable:**
- Handles 100+ comment PRs automatically
- 4-phase workflow (Critical scan → Categorize → Implement → Verify)
- Priority-based triage (CRITICAL → BLOCKING → IMPORTANT → ROUTINE)

**How to use:**
```bash
/copilot  # Processes all open PR comments
```


**Detailed docs:** [WORKFLOWS.md](WORKFLOWS.md#-copilot---autonomous-pr-processing)

---

#### 9. /fixpr
**What it is:** Intelligent PR fix automation

**Why valuable:**
- Analyzes failures, identifies root cause
- Minimal code changes (no gold-plating)
- Integrated verification

**How to use:**
```bash
/fixpr        # Fix current PR
/fixpr 123    # Fix specific PR number
```


**Detailed docs:** [WORKFLOWS.md](WORKFLOWS.md#-fixpr---intelligent-pr-fixing)

---

#### 10. /redgreen (TDD)
**What it is:** Test-driven development workflow

**Why valuable:**
- Red-green pattern (failing test → minimal code → pass → refactor)
- Evidence-based testing with structured artifacts
- 17.4% of commits are tests

**How to use:**
```bash
/redgreen  # or /tdd
```


**Detailed docs:** [WORKFLOWS.md](WORKFLOWS.md#-redgreen---test-driven-development)

---

#### 11. /fake (Automatic Hook)
**What it is:** Automatic code quality gate that runs after EVERY Write operation

**Why valuable:**
- **Proven track record:** Catches 15% of code with issues (speculative logic, fake selectors, placeholder code)
- **Real catches:** Found 9+ violations in `automate_codex_update` branch (fake UI selectors, placeholder URLs)
- **Zero effort:** 343 automatic checks in 30 days, no manual invocation
- **Low cost:** ~$5-10/month in API calls, prevents hours of debugging

**How to setup:**
```bash
# Environment variable
export SMART_FAKE_TIMEOUT=180  # 3 minutes

# Hook runs automatically via PostToolUse
# See WORKFLOWS.md for full setup
```


**Detailed docs:**
- [FAKE_DETECTION_EXAMPLES.md](FAKE_DETECTION_EXAMPLES.md) - **3 real examples: detection → fix**
- [FAKE_HOOK_ANALYSIS.md](FAKE_HOOK_ANALYSIS.md) - Complete value analysis with metrics
- [WORKFLOWS.md](WORKFLOWS.md#automatic-fake-code-quality-hook) - Setup instructions

---

#### 12. Other Commands
**Active commands with evidence:**
- `/execute` (6,332 refs) - General task execution
- `/cerebras` - Fast code generation
- `/commentreply` (4,007 refs) - Comment automation
- `/research` (2,213 refs) - Research patterns
- `/think` (1,743 refs) - Reasoning
- `/pr` (1,821 refs) - PR creation
- `/orch` (1,397 refs) - Multi-agent orchestration

**Detailed docs:** [TOOLCHAIN.md](TOOLCHAIN.md#most-used-slash-commands-18)

---

## 📊 Quick Stats

| Metric | Value |
|--------|-------|
| **Git commits analyzed** | 19,044 (last 6 months) |
| **Custom slash commands** | 80+ total, 18 heavily used |
| **MCP servers active** | 10 of 17 installed |
| **AI assistants** | 6 (Claude Code, MiniMax 2.5, Cursor, Antigravity, Codex, Warp) |
| **Testing commits** | 3,308 (17.4% of all work) |
| **PR automation** | 7,950 /copilot invocations |
| **Multi-agent branches** | 4 agent prefixes (copilot/, cursor/, codex/, claude/) |
| **mcp-cli usage** | 1,285 uses in last week |
| **Docker mentions** | 475 in last week |
| **/fake quality gate** | 343 automatic checks (30 days), 15% catch rate |
| **Monthly AI cost** | ~$40-60 |

---

## 🚀 The Complete Stack

See [TOOLCHAIN.md](TOOLCHAIN.md) for complete tool inventory with evidence scores.

**Tier 1 (Daily):** Claude Code, pytest, gh CLI, Gemini, beads, tmux

**Tier 2 (Heavy):** /copilot, /fixpr, /cerebras, Cursor, MCP servers, comment automation

**Tier 3 (Regular):** Docker, Playwright, cloud services, /secondo, test generation

---

## 💡 Unique Innovations

### 1. 12-Step Multi-AI Workflow
Complete development lifecycle leveraging web + local AI tools.


**Key insight:** "Focus on AI review/quality as much as generation"

**Details:** [WORKFLOWS.md](WORKFLOWS.md#-the-12-step-multi-ai-development-workflow)

---

### 2. Multi-Agent Orchestration
4 AI agents (copilot, cursor, codex, claude) working autonomously in parallel.


**Details:** [WORKFLOWS.md](WORKFLOWS.md#-multi-agent-orchestration)

---

### 3. Automatic Quality Gates
`/fake` runs after EVERY file write (343 times last week).

**Details:** [WORKFLOWS.md](WORKFLOWS.md#automatic-fake-code-quality-hook)

---

### 4. MCP-First Architecture
10 servers, 1,285 uses in last week, multi-model coordination.

**Details:** [WORKFLOWS.md](WORKFLOWS.md#-mcp-heavy-usage-pattern)

---

### 5. Evidence-Based Testing
Full paths, structured bundles, 17.4% of commits are tests.

**Details:** [WORKFLOWS.md](WORKFLOWS.md#-redgreen---test-driven-development)

---

## 📚 Documentation

- **[TOOLCHAIN.md](TOOLCHAIN.md)** - Complete tool inventory with git evidence (60+ tools)
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Installation instructions and environment variables
- **[WORKFLOWS.md](WORKFLOWS.md)** - Unique workflows and automation patterns
- **[LICENSE](https://github.com/jleechanorg/ai_dev_recs/blob/main/LICENSE)** - MIT License

---

## 🚀 Getting Started

### Minimal Setup (30 minutes)
```bash
# 1. Claude Code CLI
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY="sk-ant-..."

# 2. GitHub CLI
brew install gh
gh auth login

# 3. Basic tools
brew install tmux jq

# 4. Test
claude --version
```

### Full Setup (4-8 hours)
See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete installation of all tools.

### Learning Path (4 weeks)
**Week 1:** Claude Code + basic commands
**Week 2:** Add 2-3 MCP servers (sequential-thinking, gemini, perplexity)
**Week 3:** Testing + quality automation (pytest, /fake hook)
**Week 4:** Multi-agent orchestration

---

## 💰 Cost Breakdown

### Current Stack (~$40-60/mo)
- **Claude Code Paid:** $20/mo (200K context)
- **Cursor Pro:** $20/mo
- **Optional:** Perplexity Pro $20/mo
- **Alternative:** MiniMax 2.5 $20/mo - higher capacity than Claude (see [CLAUDE_CODE_MINIMAX_2.5_SETUP.md](CLAUDE_CODE_MINIMAX_2.5_SETUP.md))

### Free Tier ($0/mo)
- VS Code + Copilot free tier
- Claude free tier
- All CLI tools (open source)
- Self-hosted MCP servers

### Power User (~$200-240/mo)
- Claude Enterprise: $200/mo (500K context)
- Cursor Pro: $20/mo
- Premium services: $20-40/mo

---

### 📊 Track Your AI Usage

Using multiple AI tools means tracking costs across platforms. The **[AI Usage Tracker](https://github.com/jleechanorg/ai-usage-tracker)** provides unified token usage and cost reporting for Claude Code and Codex CLI.

**Quick install:**
```bash
# pip
pip install ai-usage-tracker
ai-usage-tracker

# npm
npm install -g ai-usage-tracker
ai-usage-tracker-js
```

**Key features:**
- Combined Claude + Codex usage in one view
- Daily cost breakdown and averages
- Cache efficiency monitoring (90%+ read rates)
- Table or JSON output for automation
- Available as Claude skill: `/combined-usage`

**Typical output:** Daily averages, cost per platform, total spend tracking
```
DAILY AVERAGES (Last 7 complete days)
Claude:      237M tokens/day  |  $123.39/day
Codex:       512M tokens/day  |  $98.76/day
TOTAL:       749M tokens/day  |  $222.15/day
```

Track actual API usage to optimize spending and identify patterns alongside your subscription costs.

---

## 🎓 Who This Is For

**You should use this if:**
- ✅ Building production systems with AI
- ✅ Want terminal-first workflows
- ✅ Need multi-agent coordination
- ✅ Value automation over manual work
- ✅ Cost-conscious but want advanced capabilities
- ✅ Want evidence-based recommendations

**This is NOT for you if:**
- ❌ Prefer GUI-only tools
- ❌ Want simple autocomplete-only AI
- ❌ Unwilling to customize/configure
- ❌ Don't write tests

---

## 🤝 Contributing

Contributions welcome for:
- ✅ Documentation improvements
- ✅ Setup instruction fixes
- ✅ Additional evidence/metrics

Not accepted:
- ❌ "Use X instead" without evidence
- ❌ Tools not actually used
- ❌ Promotional content

---

**Last Updated:** 2026-02-12
**Analysis Period:** Aug 2025 - Feb 2026 (6 months)
**Total Commits Analyzed:** 19,044
