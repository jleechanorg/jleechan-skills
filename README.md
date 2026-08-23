---
description: Claude Commands - Command Library Overview
type: llm-orchestration
execution_mode: immediate
---

# Claude Commands

A comprehensive collection of workflow automation commands for Claude Code that transform your development process through intelligent command composition and orchestration.

The YAML frontmatter at the top of this template provides command metadata and should remain intact for downstream tooling.

## Installation (Human must type the /plugin commands)

To install Claude Commands in Claude Code CLI, first register the marketplace:

```bash
/plugin marketplace add jleechanorg/jleechan-skills
```

Then browse available commands with `/plugin` and install:

```bash
/plugin install jleechan-skills@jleechan-skills
```

After installation, restart your Claude Code CLI session for the plugin to take effect.

To verify successful installation, run `/help` to check that commands appear.

### Alternative: Intelligent Self-Setup

Let Claude Code analyze and set up what you need by asking:

```text
"I want to use commands from https://github.com/jleechanorg/jleechan-skills - analyze what's available and set up the ones useful for my project"
```

### Alternative: Manual Installation

```bash
git clone https://github.com/jleechanorg/jleechan-skills.git
cp -r jleechan-skills/.claude/commands/* ./.claude/commands/
```

See [INSTALL.md](INSTALL.md) for detailed setup, troubleshooting, and platform-specific instructions.

---

⚠️ **PROTOTYPE WIP REPOSITORY** - This is an experimental command system exported from a working development environment. Use as reference but expect adaptation needed for your specific setup.

## 🎯 Active Core (by measured usage)

**239 active commands** (51 archived for reference — see [archive/README.md](archive/README.md)). Ranked by empirical invocation counts mined from Hermes, Claude Code, and Codex session logs (`/command-research`) — the commands people actually type or that automation actually drives, not a guess. Full methodology and reproducible scanner: `~/.claude/skills/command-research/SKILL.md`.

**Top 20 most human-typed**: `/advice`, `/green`, `/repro`, `/research`, `/ms`, `/history`, `/er`, `/linux`, `/f`, `/es`, `/web-advice`, `/browser`, `/skillify`, `/browserclaw`, `/auto`, `/wiki-search`, `/smoke`, `/roadmap`

**Top 20 most agent-driven**: `/es`, `/er`, `/green`, `/advice`, `/repro`, `/smoke`, `/execute`, `/copilot`, `/ms`, `/fixpr`, `/f`, `/nextsteps`, `/history`, `/harness`, `/learn`, `/roadmap`, `/web-advice`, `/end2end-testing`

84 hooks, 19 top-level scripts, and 422 skill directories (plus 129 reference docs) round out the library — browse `.claude/commands/`, `.claude/hooks/`, and `.claude/skills/` directly for the full set.

## 🔍 Key Commands

### `/execute` - Plan-Approve-Execute Workflow

Combines planning, auto-approval, and implementation in one seamless workflow with progress tracking.

```bash
/execute "fix login button styling"
# → Creates plan → Auto-approves → Implements → Tests → Commits
```

### `/pr` - Complete Development Lifecycle

Executes the full 5-phase development workflow from analysis to PR creation.

```bash
/pr "fix authentication bug"
# Think → Execute → Push → Copilot → Review
```

### `/copilot` - Autonomous PR Management

Targets current branch PR and autonomously handles analysis, fixes, testing, and communication.

```bash
/copilot  # Auto-targets current branch PR
# → Analyze → Fix → Test → Document → Reply → Verify
```

### `/cerebras` - High-Speed Code Generation

Hybrid workflow using Cerebras Inference API (up to 19.6x faster per Cerebras benchmarks) with Claude as architect and Cerebras as builder.

```bash
/cerebras "create React component for user dashboard with TypeScript"
# → Example: ~500ms generation time vs 10s standard in benchmark scenarios
```

### `/orch` - Multi-Agent Task Delegation

Delegates tasks to autonomous agents working in parallel across different branches.

```bash
/orch "add user notifications system"
# → Frontend, Backend, and Testing agents work in parallel
```

### `/scaffold` - Repository Infrastructure Setup

Rapidly scaffolds essential development infrastructure with intelligent technology stack adaptation.

```bash
/scaffold
# → Copies 17 development scripts adapted to your tech stack
```

## 💡 Command Composition Architecture

Commands work through **simple .md files** that Claude Code reads as executable instructions. You can chain multiple commands in a single request:

```bash
# Sequential execution
"/think about authentication then /arch the solution then /execute it"

# Conditional execution
"/test the login flow and if it fails /fix it then /pr the changes"

# Full workflow composition
"/analyze the codebase /design a solution /execute with tests /pr with documentation"
```

### How It Works

When you type `/pr "fix bug"`, Claude:
1. **Reads** `.claude/commands/pr.md`
2. **Parses** the structured prompt template
3. **Executes** the workflow defined in the markdown
4. **Composes** with other commands through shared protocols

Commands integrate seamlessly through:
- **TodoWrite**: All commands break down into trackable steps
- **Memory Enhancement**: Commands learn from previous executions
- **Git Workflow**: Automatic branch management and PR creation
- **Error Recovery**: Smart handling of failures and retries

## 🧪 Testing Framework

LLM-Native test patterns that work across any web application using AI to create, execute, and validate complex test scenarios.

**Commands**: `/test`, `/tdd`, `/end2end-testing`, `/llm-testing`

**Capabilities**:
- Multi-domain test patterns (e-commerce, authentication, content management)
- AI-first test development with intelligent generation
- Dynamic assertion creation and failure analysis
- Matrix testing for comprehensive validation

## 🚧 WIP: Orchestration System

Multi-agent task delegation prototype demonstrating autonomous development workflows.

**Architecture**:
- Frontend, Backend, Testing, and Opus-Master agents
- Redis-based coordination and task management
- Individual PR creation per agent with branch isolation
- Cost: $0.003-$0.050 per task

**Performance**: 85% first-time-right with proper specs, 90% cross-agent coordination success

## 🎯 Adaptation Guide

Commands contain placeholders that need adaptation for your project:
- `$PROJECT_ROOT/` → Your project's main directory
- `your-project.com` → Your domain/project name
- `TESTING=true python` → Your test execution pattern

**Example**:
```bash
# Before (exported)
TESTING=true python $PROJECT_ROOT/test_file.py

# After (adapted for Node.js)
npm test src/components/test_file.js
```

## ⚠️ Important Notes

### Requirements

- Claude Code CLI
- Git repository context
- Project-specific adaptations for paths and commands

### Support

- Commands include adaptation warnings where customization needed
- Install script provides clear guidance
- README examples show adaptation patterns

## 📚 Changelog

Full version history moved to [docs/CHANGELOG.md](docs/CHANGELOG.md).

---

🚀 **Generated with [Claude Code](https://claude.ai/code)**

**Co-Authored-By: Claude <noreply@anthropic.com>**
