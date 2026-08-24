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
/plugin marketplace add jleechanorg/claude-commands
```

Then browse available commands with `/plugin` and install:

```bash
/plugin install claude-commands@claude-commands
```

After installation, restart your Claude Code CLI session for the plugin to take effect.

To verify successful installation, run `/help` to check that commands appear.

### Alternative: Intelligent Self-Setup

Let Claude Code analyze and set up what you need by asking:

```text
"I want to use commands from https://github.com/jleechanorg/claude-commands - analyze what's available and set up the ones useful for my project"
```

### Alternative: Manual Installation

```bash
git clone https://github.com/jleechanorg/claude-commands.git
cp -r claude-commands/.claude/commands/* ./.claude/commands/
```

See [INSTALL.md](INSTALL.md) for detailed setup, troubleshooting, and platform-specific instructions.

---

⚠️ **PROTOTYPE WIP REPOSITORY** - This is an experimental command system exported from a working development environment. Use as reference but expect adaptation needed for your specific setup.

## 🎯 What's Included

**195+ Commands** including powerful workflow orchestrators and cognitive tools:
- **Workflow Orchestrators**: `/pr`, `/copilot`, `/execute`, `/orch` - Complete multi-step automation
- **Cognitive Commands**: `/think`, `/arch`, `/debug`, `/learn` - Analysis and planning
- **Infrastructure**: `/scaffold` - Repository setup and development environment
- **Testing**: `/test`, `/tdd`, `/testuif` - Comprehensive testing workflows

**43 Hooks** for Claude Code automation and workflow optimization

**19 Scripts** for development tools including git workflow, code analysis, testing, and CI/CD

**33 Skills** providing shared knowledge references and capabilities

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

**Commands**: `/test`, `/tdd`, `/testuif`, `/testhttp`

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

## 📚 Command Categories

- **Workflow Orchestrators**: Complete multi-step workflows
- **Cognitive Commands**: Analysis and planning capabilities
- **Infrastructure Commands**: Repository setup and configuration
- **Operational Commands**: Protocol enforcement and execution
- **Testing Commands**: Test creation, execution, and validation

## ⚠️ Important Notes

### Requirements

- Claude Code CLI
- Git repository context
- Project-specific adaptations for paths and commands

### Support

- Commands include adaptation warnings where customization needed
- Install script provides clear guidance
- README examples show adaptation patterns

## 📚 Version History

See bottom of README for complete version history.

---

### Latest Release: v1.1.0 (2025-12-30)

**Export Statistics**:
- **195 Commands**: Complete workflow orchestration system
- **43 Hooks**: Claude Code automation and workflow hooks
- **19 Scripts**: Development and automation tools
- **33 Skills**: Shared knowledge references

**Recent Changes**:
- Script allowlist expansion (12 additional development scripts)
- Enhanced export utility with broader infrastructure coverage
- Improved documentation for cross-project usage

For complete version history, see [Version History Archive](#version-history-archive) below.

---

## <a id="version-history-archive"></a>Version History Archive

<details>
<summary>Click to expand complete version history</summary>

### v1.1.0 (2025-12-30)
- 195 Commands, 43 Hooks, 19 Scripts, 33 Skills
- Script allowlist expansion for development tools
- Enhanced export utility coverage

### v1.0.9 (2025-12-19)
- 194 Commands, 43 Hooks, 19 Scripts, 28 Skills
- Development workflow tools integration
- Improved script categorization

### v1.0.8 (2025-12-16)
- 194 Commands, 43 Hooks, 19 Scripts, 25 Skills
- Enhanced automation patterns
- Documentation improvements

### v1.0.7 (2025-12-11)
- 194 Commands, 43 Hooks, 19 Scripts, 24 Skills
- Infrastructure deployment enhancements
- Cross-project compatibility improvements

### v1.0.6 (2025-11-22)
- 191 Commands, 43 Hooks, 19 Scripts, 20 Skills
- Testing framework enhancements
- Command composition improvements

### v1.0.5 (2025-11-15)
- 186 Commands, 41 Hooks, 19 Scripts, 14 Skills
- Multi-agent orchestration improvements
- Performance optimizations

</details>

---

🚀 **Generated with [Claude Code](https://claude.ai/code)**

**Co-Authored-By: Claude <noreply@anthropic.com>**
