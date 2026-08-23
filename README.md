---
description: Claude Commands - Command Library Overview
type: llm-orchestration
execution_mode: immediate
---

# Claude Commands

<!-- AO worker smoke test 2026-07-24 mac -->

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

## Changelog

### v1.8.0 (2026-08-23)
- **Command consolidation**: archived 51 commands to `archive/commands/` (see [archive/README.md](archive/README.md)) — files selected by empirically measuring invocations across Hermes, Claude Code, and Codex session logs (`/command-research`), then keeping any command with either measured usage or a live reference from a command that stays active (fixed-point dependency closure, not a single-pass check).
- New command: `command-research.md` — dispatcher for the usage-mining skill and its bundled scanner (`count_command_usage_unified.py`).
- Removed stale duplicate `.claude/skills/evidence-review.md` (superseded by `evidence-review/SKILL.md`) and fixed two dangling references to it.
- Active command count: 239 (was 290).

### v1.7.0 (2026-07-07)
- New commands: bashrc.md, callpath.md, crash.md, mac.md, meta.md, repro_developer.md, soak.md, social.md
- New hooks: warn-default-branch-bypass.sh
- New scripts: check_autonomy_time_box.sh
- New skills: agent-orchestrator/, aside-browser-default/, auto-factory/, bashrc.md, browserclaw/, callpath/, codex-evolve-loop/, crash.md, fetch-x-tweet.md
- Updated: automation-publish.md, automation.md, browser.md, exportcommands.md, f.md, playwright.md, automation-audit skill, self-hosted-runner-preflight skill, test-tui-claude-feature-via-cmux skill, test_install_native_scheduler.sh
- Removed: exportcommands.py (2361 lines, legacy export script superseded by exportcommands.md/.sh)

### v1.6.0 (2026-06-21)
- New commands: aar.md, accept-adapt-reject.md, beads.md, bq.md, code-quality.md, cq.md, disk_magician.md, diskm.md, er-node.md, f-pr.md, fable.md, factory-evolve.md, hermes.md, keychain_kill.md, launchd.md, linux.md, llm-testing.md, slack-audit.md, spicy_remove.md
- New hooks: auto-trust-workspace.sh
- Updated: 4layer.md, code-standards.md, commentreply.py, er.md, es.md, evidence_review.md, green.md, integrate.md, testing-layers.md, zfc.md, enforce-gh-account-agentf.sh, evidence-reviewer.md, and many more
- Skills expansions: auton, babysit, claw-dispatch, code-standards, disk-audit, evidence-standards, gcp-deployment, harness-engineering, learn, mem0, memory-search, testing-layers, wiki-ingest, zfc-leveling-roadmap
- Workflow updates: coverage.yml, deploy-dev.yml, design-doc-gate.yml, green-gate.yml, mcp-smoke-tests.yml, pr-preview.yml, presubmit.yml, skeptic-self-verify.yml, styleguide-compliance-gate.yml, test.yml, and more
- Major evidence-standards skill consolidation (large net reduction)

### v1.5.0 (2026-06-01)
- New commands: disk-audit.md, f.md, factory-spec.md, fs.md, gmail.md, history_resume.md, think-level-up-validation.md, wiki-assess.md, wiki-bfs.md, wiki-ingest.md, zfc-adjuster.md, team-claude.md
- New agents: anti-gravity-pair-coder.md, anti-gravity-pair-verifier.md
- New hooks: enforce-claudeaf-agentf.sh, enforce-gh-account-agentf.sh, enforce-gitidentity-agentf.sh
- New skills: adjustment-proof/, disk-audit/, domain-lock-standards.md, factory-spec/
- Updated: copilot.md, factory.md, wiki-evolve.md, wiki-search.md, zfclevel.md, ao.md, code-standards.md, 4layer.md, base.py, mem0_config.py, pre-commit-git-identity.sh, green-gate.yml, test.yml, daily-campaign-report.yml, and many more
- Skills expansions: claw-dispatch, code-standards, dark-factory, evidence-standards, history-search, mem0, pr-green-definition, repro-twin-clone-evidence, wiki-assess, wiki-bfs, wiki-ingest, wiki-search, zero-framework-cognition

### v1.4.0 (2026-05-22)
- New commands: archreview.md, cmux-backup.md, cmux-restore.md, code-standards.md, cs.md, end2end-testing.md, factory.md, goal_harness.md, h.md, thermo.md, thermo-nuclear-code-quality-review.md
- New agents: opencode-pair-coder.md, opencode-pair-verifier.md, openw-pair-coder.md, openw-pair-verifier.md, thermo-nuclear-code-quality-review.md
- New scripts: cmux-backup.sh, cmux-restore.sh
- New skills: ao-model-override/, cmux-backup/, code-standards/
- Updated: exportcommands.md, localexportcommands.md, history.md, copilot.md, evidence_review.md, green-gate.yml, skeptic-self-verify.yml, and many more
- Skills expansions: claw-dispatch, cmux-socket-control, evidence-standards, nextsteps, root-cause-first, skillify, zero-framework-cognition

### v1.3.0 (2026-04-24)
- New commands: ao.md, browserclaw.md, cmux-steer.md, es.md, green.md, loop_level_zfc.md, memory_search.md, ms.md, repro.md, repro_copy.md, wiki-evolve.md, wiki-search.md
- New hooks: allow-claude-dir.sh, autoapprove.py, block-merge.sh, openclaw-config-guard.sh, pre-commit-detached-guard.sh
- New skills: 4layer.md
- Updated: execute.md, copilot.md, claw.md, exportcommands.sh, git-header.sh, command_output_trimmer.py, skeptic-cron.yml
- Removed: ralph.md, localexportcommands.md, compose-commands.sh
- ZFC compliance updates across multiple files

## 🎯 What's Included

**239 active commands** (plus 51 archived for reference — see [archive/README.md](archive/README.md)) including powerful workflow orchestrators and cognitive tools:
- **Workflow Orchestrators**: `/pr`, `/copilot`, `/execute`, `/orch`, `/f-pr`, `/factory-evolve`, `/hermes` - Complete multi-step automation
- **Cognitive Commands**: `/think`, `/arch`, `/debug`, `/learn`, `/aar`, `/accept-adapt-reject` - Analysis and planning
- **Infrastructure**: `/scaffold`, `/launchd`, `/linux` - Repository setup and development environment
- **Testing**: `/test`, `/tdd`, `/end2end-testing`, `/llm-testing` - Comprehensive testing workflows
- **Code Quality**: `/code-standards`, `/cs`, `/thermo`, `/archreview`, `/code-quality`, `/cq` - Standards enforcement and deep review
- **Session Management**: `/cmux-backup`, `/cmux-restore`, `/factory`, `/goal_harness`, `/h` - Workflow tooling
- **Evidence & Review**: `/es`, `/er`, `/green` - Evidence standards and PR review
- **Issue Tracking**: `/beads` - Bead-based issue tracking integration
- **Wiki Tools**: `/wiki-assess`, `/wiki-bfs`, `/wiki-ingest`, `/wiki-evolve`, `/wiki-search` - Knowledge base ingestion and assessment
- **Utilities**: `/disk_magician`, `/diskm`, `/slack-audit`, `/bq`, `/keychain_kill`, `/fable`, `/f`, `/fs`, `/factory-spec`, `/history_resume`, `/team-claude`, `/zfc-adjuster`, `/bashrc`, `/callpath`, `/mac`, `/meta`, `/social` - System, inbox, and misc workflow tools

### Active Core (by measured usage)

Ranked by empirical invocation counts mined from Hermes, Claude Code, and Codex session logs (`/command-research`) — the commands people actually type or that automation actually drives, not a guess:

**Most human-typed**: `/advice`, `/green`, `/repro`, `/research`, `/ms`, `/history`, `/er`, `/linux`, `/f`, `/es`, `/web-advice`, `/browser`, `/skillify`, `/browserclaw`, `/auto`, `/wiki-search`, `/smoke`, `/roadmap`

**Most agent-driven**: `/es`, `/er`, `/green`, `/advice`, `/repro`, `/smoke`, `/execute`, `/copilot`, `/ms`, `/fixpr`, `/f`, `/nextsteps`, `/history`, `/harness`, `/learn`, `/roadmap`, `/web-advice`, `/end2end-testing`

Full methodology and reproducible scanner: `~/.claude/skills/command-research/SKILL.md`.

**60 Hooks** for Claude Code automation and workflow optimization

**22 Scripts** for development tools including git workflow, code analysis, testing, and CI/CD

**915 Skills** providing shared knowledge references and capabilities

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

**Commands**: `/test`, `/tdd`, `/testuif`, `/testhttp`, `/end2end-testing`, `/llm-testing`

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

### v1.2.0 (2026-04-05)
- ZFC compliance fixes across claw.md, auton.md, base.py, exportcommands.sh
- CLAUDE.md ZFC global rule added
- exportcommands.sh: README neutral-dir fix, --tools "" flag, corrupt-detection guard

### Latest Release: v1.1.0 (2025-12-30)

**Export Statistics**:
- **244 Commands**: Complete workflow orchestration system
- **52 Hooks**: Claude Code automation and workflow hooks
- **22 Scripts**: Development and automation tools
- **89 Skills**: Shared knowledge references

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
