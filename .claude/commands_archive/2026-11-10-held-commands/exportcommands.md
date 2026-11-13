---
description: /exportcommands - Export Claude Commands to Reference Repository (your-project.com only — the filter list is hardcoded to worldarchitect/$PROJECT_ROOT/jleechanorg patterns; rename to /export-worldai-commands for clarity)
type: llm-orchestration
execution_mode: immediate
---
> **Worldai-only command.** This command exports Claude commands from
> `$GITHUB_REPOSITORY` to a clean reference repository. The
> `perl -pi -e` substitution list is hardcoded to `worldarchitect`,
> `mvp_site`, `jleechanorg`, `jleechan2015`, `serviceAccountKey`,
> `GOOGLE_APPLICATION`, and `Your Project` — all worldai-specific
> patterns. The repo-local counterpart lives at
> `$GITHUB_REPOSITORY/.claude/commands/exportcommands.md` and
> is preferred when working in that repo. **For non-worldai projects,
> write a project-specific export command with its own filter list.**

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: LLM Pre-flight Analysis (run before any shell script)

**Dry-run detection**: If `--dry-run` argument present, pass it through to `exportcommands.sh` and stop after analysis — do not commit or push.

**Purpose**: Catch content leakage, scope drift, and skip-worthy files before pushing to the public `jleechanorg/claude-commands` repo.

**Action Steps:**

1. **Scope sanity — count what would be exported:**
   ```bash
   echo "~/.claude/commands/: $(ls ~/.claude/commands/*.md 2>/dev/null | wc -l) .md files"
   echo "~/.claude/skills/:   $(ls ~/.claude/skills/ 2>/dev/null | wc -l) skill dirs"
   echo "~/.claude/hooks/:    $(ls ~/.claude/hooks/*.sh 2>/dev/null | wc -l) hooks"
   echo "~/.claude/agents/:   $(ls ~/.claude/agents/*.md 2>/dev/null | wc -l) agents"
   ```

2. **Content filter audit — scan for strings the export filters may miss:**
   ```bash
   # Grep for project-specific strings in ~/.claude/commands/ that should be stripped
   grep -rl "worldarchitect\|jleechanorg\|jleechan2015\|serviceAccountKey\|GOOGLE_APPLICATION\|mvp_site\|worldai" \
     ~/.claude/commands/ ~/.claude/skills/ 2>/dev/null | head -20
   ```
   The shell script has 8 `perl -pi -e` substitutions covering: `$GITHUB_REPOSITORY`, `your-project.com`, `$HOME`, `\bjleechan\b`, email, `Your Project`, `TESTING=true python`, and `$PROJECT_ROOT/`. Flag any match NOT covered by those 8 patterns as a blocker; the rest are expected and filtered automatically.

3. **Skills cap check — skills export should not exceed 300 entries:**
   ```bash
   ls ~/.claude/skills/ | grep -v '^_' | wc -l
   ```
   If > 300: warn "Skills over cap — review before exporting to public repo."

4. **Reference commands check** — verify `.claude_reference/commands/` exists and report count:
   ```bash
   ls .claude_reference/commands/ 2>/dev/null | wc -l
   ```
   These are archived commands moved from `.claude/commands/` — they export to `repo/.claude_reference/commands/`. Confirm count looks right (should be ~204 files).

5. **Target repo diff preview (optional, costs a gh clone):**
   If the user wants to see exactly what would change vs current `jleechanorg/claude-commands`, note: `--dry-run` on the shell script does this without pushing.

6. **Report summary** — list any blockers (content leakage, cap breach) and clearances. If blockers found, STOP and ask user to resolve. If clear, proceed to Phase 1.

6. **Dry-run shortcut**: If `--dry-run` present, skip Phase 1 and run:
   ```bash
   bash ~/.claude/commands/exportcommands.sh --dry-run
   ```
   Report output and stop.

7. **Produce dry-run summary** — always show before executing:
   ```
   === DRY RUN: /exportcommands ===
   Commands: N .md files from ~/.claude/commands/
   Skills: N skill dirs from ~/.claude/skills/
   Hooks: N hooks
   Agents: N agents
   Reference commands: N files from .claude_reference/commands/ → repo/.claude_reference/commands/
   Content filter matches: N (all covered by existing 8 filters / N UNCOVERED — BLOCKER)
   === END DRY RUN ===
   ```

8. **MANDATORY CONFIRMATION GATE — always stop here.**
   Print: `"Proceed with export to jleechanorg/claude-commands? (yes/no)"` and **wait for explicit user confirmation**.
   - If user says yes/y/proceed → continue to Phase 1
   - Any other response → **STOP**. Do not run any shell scripts.
   - Blockers from steps 1-3 also force STOP regardless of confirmation.

---

### Phase 1: Execute Export (only after confirmation)

**Action Steps:**
1. User confirmed in Phase 0 step 8. Proceed.
2. Run the shell script (primary path):
   ```bash
   bash ~/.claude/commands/exportcommands.sh
   ```
3. Report the PR URL printed by the script as the final output.
4. If the shell script fails, diagnose from its error output — there is no separate Python fallback implementation in this repo.

## 📋 REFERENCE DOCUMENTATION

# /exportcommands - Export Claude Commands to Reference Repository

🚨 **CRITICAL SUCCESS REQUIREMENT**: This command MUST always print the export PR URL as the final output. The command is NOT complete without providing the PR URL to the user.

🚨 **REPOSITORY SAFETY RULE**: Export operations NEVER delete, move, or modify files in the current repository. Export only copies files for external sharing. The current repository remains completely unchanged.

**Purpose**: Export your complete command composition system to https://github.com/jleechanorg/claude-commands for reference and sharing

**Implementation**: This command delegates all technical operations to the Python implementation (`exportcommands.py`) while providing LLM-driven README generation and intelligent export analysis.

**Usage**: `/exportcommands` - Executes complete export pipeline with automated PR creation

## 🎯 COMMAND COMPOSITION ARCHITECTURE

**The Simple Hook That Changes Everything**: At its core, `/exportcommands` is just a file export script. But what makes it powerful is that it's exporting a complete **command composition system** that transforms how you interact with Claude Code.

### The Composition Pattern

Each command is designed to **compose** with others through a shared protocol:
- **TodoWrite Integration**: Commands break down into trackable steps
- **Memory Enhancement**: Learning from previous executions
- **Git Workflow Integration**: Automatic branch management and PR creation
- **Testing Integration**: Automatic test running and validation
- **Error Recovery**: Smart handling of failures and retries

### Key Compositional Commands Being Exported

**Workflow Orchestrators**:
- `/pr` - Complete PR workflow (analyze → fix → test → create)
- `/copilot` - Autonomous PR analysis and fixing
- `/execute` - Auto-approval development with TodoWrite tracking
- `/orch` - Multi-agent task delegation system

**Building Blocks**:
- `/think` + `/arch` + `/debug` = Cognitive analysis chain
- `/test` + `/fix` + `/verify` = Quality assurance chain
- `/planexec` + `/implement` + `/validate` = Development chain

**The Hook Architecture**: Simple `.md` files that Claude Code reads as executable instructions, enabling complex behavior through composition rather than complexity.

## ⚡ COMMAND COMBINATION SUPERPOWERS

### Combine Multiple Commands in a Single Prompt

**Revolutionary Feature**: Normally, Claude can only handle one command per sentence. This tool lets you string them together in a single prompt, creating sophisticated multi-step workflows.

**Example**: Give this PR a thorough code review with `/archreview /thinkultra /fake`

This runs:
1. `/archreview` - Architectural analysis of the codebase
2. `/thinkultra` - Deep strategic thinking about the changes
3. `/fake` - Detection of placeholder or incomplete code

**The Foundation**: This command combination capability is the foundation for creating more complex, multi-step workflows that would normally require multiple separate interactions.

### Automate Your PR Lifecycle

**Complete Automation**: You can automate your entire pull request workflow with natural language commands.

**Example**: `/pr fix the settings button`

This automatically runs the whole sequence:
- `/think` - Strategic analysis of the settings button issue
- `/execute` - Implementation with auto-approval
- `/push` - Create PR with comprehensive description
- `/copilot` - Respond to GitHub comments and make fixes
- `/review` - Claude's own comprehensive code review

**The `/copilot` Advantage**: The `/copilot` command even responds to GitHub comments and makes fixes automatically, handling the entire feedback loop without manual intervention.

### Detect Fake Code with AI Analysis

**Quality Assurance**: Built-in detection for "fake" code that Claude sometimes generates when pushed too hard.

**The Problem**: When overloaded, Claude sometimes writes placeholder code instead of implementing what you asked for - like just returning success without actual logic.

**The Solution**: If something seems off, run the `/fake` command to systematically detect:
- Placeholder implementations
- Mock responses without real logic
- TODOs disguised as complete features
- Demo code that doesn't actually work

**Smart Detection**: This isn't just pattern matching - it's AI-powered analysis that understands the difference between legitimate code and fake implementations.

## 🔍 COMMAND DEEP DIVE - The Composition Powerhouses

### `/execute` - Auto-Approval Development Orchestrator

**What It Does**: The ultimate autonomous development command that handles everything from planning to implementation with built-in auto-approval.

**The Magic**: Turns complex development tasks into structured, trackable workflows without manual approval gates.

**Composition Architecture**:
```bash
/execute "implement user authentication"
```

**Internal Workflow**:
1. **Phase 1 - Planning**:
   - Complexity assessment (simple/medium/complex)
   - Execution method decision (parallel vs sequential)
   - Tool requirements analysis
   - Timeline estimation
   - Implementation approach design

2. **Phase 2 - Auto-Approval**:
   - Built-in approval bypass: "User already approves - proceeding with execution"
   - No manual intervention required

3. **Phase 3 - TodoWrite Orchestration**:
   - Breaks task into trackable steps
   - Real-time progress updates
   - Error handling and recovery
   - Completion verification

**Real Example** (This very task demonstrates `/execute`):
```
User: /execute "focus on command composition and explain details on /execute..."
Claude:
  Phase 1 - Planning: [complexity assessment, timeline, approach]
  Phase 2 - Auto-approval: "User already approves - proceeding"
  Phase 3 - Implementation: [TodoWrite tracking, step execution]
```

### `/planexec` - Manual Approval Development Planning

**What It Does**: Structured development planning with explicit user approval required before execution.

**The Magic**: Perfect for complex tasks where you want to review the approach before committing resources.

**Composition Architecture**:
```bash
/planexec "redesign authentication system"
```

**Workflow**:
1. **Deep Analysis**: Research existing system, identify constraints, analyze requirements
2. **Multi-Approach Planning**: Present 2-3 different implementation approaches
3. **Resource Assessment**: Timeline, complexity, tool requirements, risk analysis
4. **Approval Gate**: User must explicitly approve before any implementation begins
5. **Guided Execution**: Step-by-step implementation with checkpoints

**When to Use**:
- Complex architectural changes
- When you want oversight of the approach
- High-risk modifications
- Learning new patterns/technologies

### `/copilot` - Autonomous PR Analysis & Comprehensive Fixing

**What It Does**: Comprehensive PR analysis with autonomous fixing of all detected issues - no approval prompts.

**The Magic**: Scans PRs for every type of issue (conflicts, CI failures, code quality, comments) and fixes everything automatically.

**Composition Architecture**:
```bash
/copilot  # Analyzes current PR context
```

**Autonomous Workflow Chain**:
1. **Comprehensive Scanning**:
   - Merge conflicts detection and resolution
   - CI/CD failure analysis and fixes
   - Code review comment processing
   - Quality gate validation

2. **Intelligent Fixing**:
   - Automated conflict resolution with smart merging
   - Test fixes and dependency updates
   - Code style and formatting corrections
   - Documentation and comment updates

3. **Validation Loop**:
   - Re-run tests after each fix
   - Verify merge status and CI success
   - Continue until all issues resolved

**No Approval Required**: Unlike other commands, `/copilot` operates autonomously - perfect for continuous integration workflows.

**Real Example**:
```
PR has: merge conflicts + failing tests + 5 review comments
/copilot
↓
Resolve conflicts → Fix failing tests → Address all comments →
Re-run validation → Push fixes → Verify success
```

### `/orch` - Multi-Agent Task Delegation System

**What It Does**: Delegates tasks to autonomous tmux-based agents that work in parallel across different branches and contexts.

**The Magic**: Spawns specialized agents (frontend, backend, testing, opus-master) that execute tasks independently with full Git workflow management.

**Composition Architecture**:
```bash
/orch "implement user dashboard with tests and documentation"
```

**Multi-Agent Workflow**:
1. **Task Analysis & Delegation**:
   - Break complex task into parallel workstreams
   - Assign to specialized agents based on capabilities
   - Create isolated tmux sessions with agent workspaces

2. **Autonomous Agent Execution**:
   - Each agent gets dedicated branch and workspace
   - Independent execution with full development lifecycle
   - Real-time progress monitoring and coordination

3. **Agent Coordination**:
   - Redis-based inter-agent communication
   - Task dependency management
   - Resource allocation and load balancing

4. **Integration & Delivery**:
   - Agent results aggregation
   - PR creation from agent branches
   - Success verification and reporting

**Agent Types**:
- **Frontend Agent**: UI/UX implementation, browser testing, styling
- **Backend Agent**: API development, database integration, server logic
- **Testing Agent**: Test automation, validation, performance testing
- **Opus-Master**: Architecture decisions, code review, integration

**Cost**: $0.003-$0.050 per task (highly efficient)

**Real Example**:
```
/orch "add user notifications system"
↓
Frontend Agent: notification UI components
Backend Agent: notification API endpoints
Testing Agent: notification test suite
Opus-Master: architecture review and integration
↓
All agents work in parallel → Create individual PRs → Integration verification
```

**Monitoring**:
```bash
/orch monitor agents    # Check agent status
/orch "What's running?" # Current task overview
tmux attach-session -t task-agents  # Direct agent access
```

## 🚨 EXPORT PROTOCOL

# Clone fresh repository from main

export REPO_DIR="/tmp/claude_commands_repo_fresh"
gh repo clone jleechanorg/claude-commands "$REPO_DIR"
cd "$REPO_DIR" && git checkout main

# Create export branch from clean main

export NEW_BRANCH="export-fresh-$(date +%Y%m%d-%H%M%S)"
git checkout -b "$NEW_BRANCH"

# NOTE: Do NOT wipe existing directories. Only overwrite files that exist in source.
# Files present in the target repo but not in source are preserved intentionally
# (e.g. /harness.md added directly via PR — we don't want exportcommands to delete it).

echo "Preserving existing files in target repo; only overwriting files present in source"
```

**Pre-Export File Filtering**:
```bash

# Create exclusion list for project-specific files

cat > /tmp/export_exclusions.txt << 'EOF'
tests/run_tests.sh
testi.sh
**/test_integration/**
copilot_inline_reply_example.sh
run_ci_replica.sh
testing_http/
testing_ui/
testing_mcp/
ci_replica/
analysis/
claude-bot-commands/
coding_prompts/
prototype/
EOF

# Filter files before export from staging area

while IFS= read -r pattern; do
    case "$pattern" in
        **/*)
            # Use regex for patterns with ** (recursive directory matching)
            find staging -regextype posix-extended -regex ".*/${pattern#**/}" -exec rm -rf {} + 2>/dev/null || true
            ;;
        *)
            # Use path for simple patterns
            find staging -path "*${pattern}" -exec rm -rf {} + 2>/dev/null || true
            ;;
    esac
    # Also remove root directories that may be copied during main export
    rm -rf "staging/${pattern%/}" 2>/dev/null || true
done < /tmp/export_exclusions.txt
```

**CLAUDE.md Export**:
```bash

# Add reference-only warning header

cat > staging/CLAUDE.md << 'EOF'

# 📚 Reference Export - Adaptation Guide

**Note**: This is a reference export from a working Claude Code project. You may need to personally debug some configurations, but Claude Code can easily adjust for your specific needs.

These configurations may include:
- Project-specific paths and settings that need updating for your environment
- Setup assumptions and dependencies specific to the original project
- References to particular GitHub repositories and project structures

Feel free to use these as a starting point - Claude Code excels at helping you adapt and customize them for your specific workflow.

---

EOF

# Filter and append original CLAUDE.md

cp CLAUDE.md /tmp/claude_filtered.md

# Apply content filtering

sed -i 's|$PROJECT_ROOT/|$PROJECT_ROOT/|g' /tmp/claude_filtered.md
sed -i 's|worldarchitect\.ai|your-project.com|g' /tmp/claude_filtered.md
sed -i 's|$USER|${USER}|g' /tmp/claude_filtered.md
cat /tmp/claude_filtered.md >> staging/CLAUDE.md
```

**Commands Export** (`.claude/commands/` → `commands/`):
```bash

# Copy commands with filtering

for file in .claude/commands/*.md .claude/commands/*.py; do
    # Skip project-specific files and template files
    case "$(basename "$file")" in
        "testi.sh"|"run_tests.sh"|"copilot_inline_reply_example.sh"|"README_EXPORT_TEMPLATE.md")
            echo "Skipping project-specific/template file: $file"
            continue
            ;;
    esac

    # Copy and filter content
    cp "$file" "staging/commands/$(basename "$file")"

    # Apply content transformations - completely remove project-specific references
    sed -i 's|$PROJECT_ROOT/|$PROJECT_ROOT/|g' "staging/commands/$(basename "$file")"
    sed -i 's|worldarchitect\.ai|your-project.com|g' "staging/commands/$(basename "$file")"
    sed -i 's|$USER|${USER}|g' "staging/commands/$(basename "$file")"
    sed -i 's|TESTING=true python|TESTING=true python|g' "staging/commands/$(basename "$file")"

    # Remove any remaining project-specific path references
    sed -i 's|/home/${USER}/projects/worldarchitect\.ai/[^/]*||g' "staging/commands/$(basename "$file")"
done
```
- Export filtered command definitions with proper categorization
- Transform hardcoded paths to generic placeholders
- Add compatibility warnings for project-specific commands
- Organize by category: cognitive, operational, testing, development, meta

**Scripts Export** (`.claude/scripts/` → `scripts/`):
```bash

# Export scripts with comprehensive filtering

for script in .claude/scripts/*.sh .claude/scripts/*.py; do
    if [[ -f "$script" ]]; then
        script_name=$(basename "$script")

        # Skip project-specific scripts
        case "$script_name" in
            "run_tests.sh"|"testi.sh"|"*integration*")
                echo "Skipping project-specific script: $script_name"
                continue
                ;;
        esac

        # Copy and transform
        cp "$script" "staging/scripts/$script_name"

        # Apply transformations - completely remove project-specific references
        sed -i 's|$PROJECT_ROOT/|$PROJECT_ROOT/|g' "staging/scripts/$script_name"
        sed -i 's|worldarchitect\.ai|your-project.com|g' "staging/scripts/$script_name"
        sed -i 's|/home/${USER}/projects/worldarchitect\.ai/[^/]*||g' "staging/scripts/$script_name"
        sed -i 's|TESTING=true python|TESTING=true python|g' "staging/scripts/$script_name"

        # Add dependency header
        sed -i '1i\#!/bin/bash\n# ⚠️ REQUIRES PROJECT ADAPTATION\n# This script contains project-specific paths and may need modification\n' "staging/scripts/$script_name"
    fi
done
```
- Export script implementations with dependency documentation
- Transform mvp_site paths to generic PROJECT_ROOT placeholders
- Add setup requirements documentation for each script
- Include execution environment requirements

**🚨 Hooks Export** (`.claude/hooks/` → `hooks/`) - **ESSENTIAL CLAUDE CODE FUNCTIONALITY**:
```bash

# Export Claude Code hooks with comprehensive filtering

echo "📎 Exporting Claude Code hooks..."

# Create hooks destination directory

mkdir -p staging/hooks

# Check if source hooks directory exists

if [[ ! -d ".claude/hooks" ]]; then
    echo "⚠️  Warning: .claude/hooks directory not found - skipping hooks export"
else
    echo "📁 Found .claude/hooks directory - proceeding with export"

    # Enable nullglob to handle cases where no files match patterns
    shopt -s nullglob

    # Export hook scripts with filtering (including nested subdirectories)
    find .claude/hooks -type f \( -name "*.sh" -o -name "*.py" -o -name "*.md" \) -print0 | while IFS= read -r -d '' hook_file; do
        hook_name=$(basename "$hook_file")
        relative_path="${hook_file#.claude/hooks/}"

        # Skip test and example files
        case "$hook_name" in
            *test*|*example*|debug_hook.sh)
                echo "   ⏭ Skipping $hook_name (test/debug file)"
                continue
                ;;
        esac

        echo "   📎 Copying: $relative_path"

        # Create subdirectory structure if needed
        hook_dir=$(dirname "staging/hooks/$relative_path")
        mkdir -p "$hook_dir"

        # Copy and transform hook files
        cp "$hook_file" "staging/hooks/$relative_path"

        # Apply comprehensive content transformations
        sed -i 's|$PROJECT_ROOT/|$PROJECT_ROOT/|g' "staging/hooks/$relative_path"
        sed -i 's|worldarchitect\.ai|your-project.com|g' "staging/hooks/$relative_path"
        sed -i 's|$USER|${USER}|g' "staging/hooks/$relative_path"
        sed -i 's|TESTING=true python|TESTING=true python|g' "staging/hooks/$relative_path"
        sed -i 's|/home/${USER}/projects/worldarchitect\.ai/[^/]*||g' "staging/hooks/$relative_path"

        # Make scripts executable and add adaptation headers
        case "$hook_name" in
            *.sh)
                chmod +x "staging/hooks/$relative_path"
                # Add adaptation header only if file doesn't start with shebang
                if ! head -1 "staging/hooks/$relative_path" | grep -q '^#!'; then
                    sed -i '1i\#!/bin/bash\n# 🚨 CLAUDE CODE HOOK - ESSENTIAL FUNCTIONALITY\n# ⚠️ REQUIRES PROJECT ADAPTATION - Contains project-specific configurations\n# This hook provides core Claude Code workflow automation\n# Adapt paths and project references for your environment\n' "staging/hooks/$relative_path"
                else
                    sed -i '1a\# 🚨 CLAUDE CODE HOOK - ESSENTIAL FUNCTIONALITY\n# ⚠️ REQUIRES PROJECT ADAPTATION - Contains project-specific configurations\n# This hook provides core Claude Code workflow automation\n# Adapt paths and project references for your environment\n' "staging/hooks/$relative_path"
                fi
                ;;
            *.py)
                chmod +x "staging/hooks/$relative_path"
                # Add adaptation note after any existing shebang
                if head -1 "staging/hooks/$relative_path" | grep -q '^#!'; then
                    sed -i '1a\# 🚨 CLAUDE CODE HOOK - ESSENTIAL FUNCTIONALITY\n# ⚠️ REQUIRES PROJECT ADAPTATION - Contains project-specific configurations\n# This hook provides core Claude Code workflow automation\n# Adapt imports and project references for your environment\n' "staging/hooks/$relative_path"
                else
                    sed -i '1i\# 🚨 CLAUDE CODE HOOK - ESSENTIAL FUNCTIONALITY\n# ⚠️ REQUIRES PROJECT ADAPTATION - Contains project-specific configurations\n# This hook provides core Claude Code workflow automation\n# Adapt imports and project references for your environment\n' "staging/hooks/$relative_path"
                fi
                ;;
        esac
    done

    # Restore nullglob setting
    shopt -u nullglob

    # Note: Subdirectories are now handled by the find loop above

    echo "✅ Hooks export completed successfully"
fi
```
- **🔧 Core Claude Code Functionality**: Essential hooks that enable automatic workflow management
- **PreToolUse Hooks**: Code quality validation before file operations (anti_demo_check_claude.sh, check_root_files.sh)
- **PostToolUse Hooks**: Automated sync after git operations (post_commit_sync.sh)
- **PostResponse Hooks**: Response quality validation (detect_speculation_and_fake_code.sh)
- **Command Composition**: Hook utilities for advanced workflow orchestration (compose-commands.sh)
- **Testing Framework**: Complete hook testing utilities for validation and debugging
- **Project Adaptation**: Comprehensive filtering of project-specific paths and references
- **Executable Permissions**: Automatic permission setting for shell scripts
- **Documentation**: Clear adaptation requirements and functionality descriptions

**🚨 Agents Export** (`.claude/agents/` → `agents/`) - **SPECIALIZED AI AGENT CONFIGURATIONS**:
```bash

# Export Claude Code agent configurations with comprehensive filtering

echo "🤖 Exporting Claude Code agent configurations..."

# Create agents destination directory

mkdir -p staging/agents

# Check if source agents directory exists

if [[ ! -d ".claude/agents" ]]; then
    echo "⚠️  Warning: .claude/agents directory not found - skipping agents export"
else
    echo "📁 Found .claude/agents directory - proceeding with export"

    # Enable nullglob to handle cases where no files match patterns
    shopt -s nullglob

    # Export agent configuration files with filtering
    find .claude/agents -type f \( -name "*.md" -o -name "*.py" -o -name "*.json" \) -print0 | while IFS= read -r -d '' agent_file; do
        agent_name=$(basename "$agent_file")
        relative_path="${agent_file#.claude/agents/}"

        # Skip test and example files
        case "$agent_name" in
            *test*|*example*|debug_agent.md)
                echo "   ⏭ Skipping $agent_name (test/debug file)"
                continue
                ;;
        esac

        echo "   🤖 Copying: $relative_path"

        # Create subdirectory structure if needed
        agent_dir=$(dirname "staging/agents/$relative_path")
        mkdir -p "$agent_dir"

        # Copy and transform agent files
        cp "$agent_file" "staging/agents/$relative_path"

        # Apply comprehensive content transformations
        sed -i 's|$PROJECT_ROOT/|$PROJECT_ROOT/|g' "staging/agents/$relative_path"
        sed -i 's|worldarchitect\.ai|your-project.com|g' "staging/agents/$relative_path"
        sed -i 's|$USER|${USER}|g' "staging/agents/$relative_path"
        sed -i 's|TESTING=true python|TESTING=true python|g' "staging/agents/$relative_path"
        sed -i 's|/home/${USER}/projects/worldarchitect\.ai/[^/]*||g' "staging/agents/$relative_path"

        # Add agent configuration header for markdown files
        case "$agent_name" in
            *.md)
                # Add adaptation header only if file doesn't start with existing header
                if ! head -5 "staging/agents/$relative_path" | grep -q '🚨 CLAUDE CODE AGENT'; then
                    sed -i '1i\# 🚨 CLAUDE CODE AGENT CONFIGURATION\n# ⚠️ REQUIRES PROJECT ADAPTATION - Contains project-specific configurations\n# This agent provides specialized AI capabilities for Claude Code workflows\n# Adapt project references and configurations for your environment\n' "staging/agents/$relative_path"
                fi
                ;;
        esac
    done

    # Restore nullglob setting
    shopt -u nullglob

    echo "✅ Agents export completed successfully"
fi
```
- **🤖 Specialized AI Agent System**: Agent configurations for different AI models and tasks
- **Code Review Agents**: Automated code analysis and quality assessment (code-review.md)
- **Consultant Agents**: Integration with various AI models (cerebras-consultant.md, gemini-consultant.md, grok-consultant.md, codex-consultant.md)
- **Testing Agents**: Test execution and validation (testexecutor.md, testvalidator.md)
- **Long-Running Task Agents**: Complex multi-step task execution (long-runner.md)
- **PR Fix Agents**: Automated pull request issue resolution (copilot-fixpr.md)
- **Project Adaptation**: Comprehensive filtering of project-specific paths and references
- **Configuration Templates**: Ready-to-use agent configurations for different workflow needs
- **Documentation**: Clear adaptation requirements and agent capability descriptions

**🚨 Root-Level Infrastructure Scripts Export** (Root → `infrastructure-scripts/`):
```bash

# Export development environment infrastructure scripts

mkdir -p staging/infrastructure-scripts

# Dynamically discover valuable root-level scripts to export

mapfile -t ROOT_SCRIPTS < <(ls -1 *.sh 2>/dev/null | grep -E '^(claude_|start-claude-bot|integrate|resolve_conflicts|sync_branch|setup-github-runner|test_server_manager)\.sh$')

# Export self-hosted runner setup scripts from scripts/ directory
if [[ -f "scripts/setup-runner-with-drift.sh" ]]; then
    echo "Exporting self-hosted runner setup script"
    cp "scripts/setup-runner-with-drift.sh" "staging/infrastructure-scripts/setup-runner-with-drift.sh"

    # Generalize repository references
    sed -i 's|jleechanorg/worldarchitect\.ai|$GITHUB_OWNER/$GITHUB_REPO|g' "staging/infrastructure-scripts/setup-runner-with-drift.sh"
    sed -i 's|claude-drift-runner|$RUNNER_NAME|g' "staging/infrastructure-scripts/setup-runner-with-drift.sh"

    # Add header with setup instructions
    cat > "staging/infrastructure-scripts/RUNNER_SETUP.md" << 'RUNNER_DOC'
# Self-Hosted GitHub Runner Setup

## Overview
The `setup-runner-with-drift.sh` script configures a GitHub Actions self-hosted runner with clock drift support. This enables running workflow jobs on your own infrastructure for cost savings or special requirements (e.g., GPU access, specific OS versions).

## Prerequisites
1. **GitHub CLI (`gh`)**: Install from https://cli.github.com/
   ```bash
   # Verify installation
   gh --version
   gh auth status
   ```

2. **GitHub Actions Runner**: Download from https://github.com/actions/runner/releases
   ```bash
   mkdir -p ~/actions-runner && cd ~/actions-runner
   # Download latest runner (check releases page for current version)
   curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
     https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
   tar xzf actions-runner-linux-x64-2.321.0.tar.gz
   ```

3. **Repository Admin Access**: You need admin access to the target repository to register runners

4. **Clock Sync Capability**: macOS uses `sntp`, Linux typically uses `ntpdate`
   ```bash
   # macOS (already installed)
   sudo sntp -sS time.apple.com

   # Ubuntu/Debian
   sudo apt-get install ntpdate
   sudo ntpdate -s time.nist.gov
   ```

## Usage

### Basic Setup (Default Repository)
```bash
# Uses default repository configured in script
./infrastructure-scripts/setup-runner-with-drift.sh
```

### Custom Repository
```bash
# Format: https://github.com/owner/repo
./infrastructure-scripts/setup-runner-with-drift.sh https://github.com/myorg/myrepo

# With custom runner name
./infrastructure-scripts/setup-runner-with-drift.sh https://github.com/myorg/myrepo my-custom-runner
```

### Alternative Format (owner/repo)
```bash
# Script accepts both full URL and owner/repo format
./infrastructure-scripts/setup-runner-with-drift.sh myorg/myrepo my-runner-name
```

## What the Script Does

1. **Uninstalls existing runner service** (if present)
2. **Syncs system clock** using NTP (requires sudo)
3. **Gets registration token** from GitHub API
4. **Configures runner** with repository while clock is synced
5. **Installs and starts service** to run runner as daemon
6. **Verifies runner** is online via GitHub API
7. **Restores clock drift** (if using drift-testing workflow)

## Workflow Integration

### Create Workflow with Self-Hosted Runner
```yaml
name: My Workflow

on: pull_request

jobs:
  try-self-hosted:
    runs-on: [self-hosted, your-runner-label]
    timeout-minutes: 2
    continue-on-error: true

    steps:
      - uses: actions/checkout@v4
      - name: Run your task
        run: echo "Running on self-hosted runner!"

  fallback-github-hosted:
    needs: try-self-hosted
    if: needs.try-self-hosted.result != 'success'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - name: Run your task
        run: echo "Running on GitHub-hosted fallback"
```

### Key Workflow Patterns

**Fallback Logic**: Use `needs.<job>.result != 'success'` to trigger GitHub-hosted fallback:
```yaml
fallback-job:
  needs: try-self-hosted
  if: needs.try-self-hosted.result != 'success'  # ✅ Correct - checks actual job result
  runs-on: ubuntu-latest
```

**Common Mistake** (DON'T DO THIS):
```yaml
# ❌ WRONG - output set at job start, doesn't reflect actual success/failure
try-self-hosted:
  outputs:
    success: ${{ steps.mark-success.outputs.success }}
  steps:
    - run: echo "success=true" >> $GITHUB_OUTPUT  # Set at START = always true!

fallback-job:
  if: needs.try-self-hosted.outputs.success != 'true'  # Never triggers on failure!
```

## Runner Management

### Check Runner Status
```bash
cd ~/actions-runner
./svc.sh status
```

### Stop/Start Runner
```bash
./svc.sh stop
./svc.sh start
```

### View Runner Logs
```bash
# Service logs (macOS)
tail -f ~/Library/Logs/actions.runner.*

# Service logs (Linux)
journalctl -u actions.runner.*
```

### Uninstall Runner
```bash
cd ~/actions-runner
./svc.sh uninstall
./config.sh remove --token $(gh api -X POST repos/OWNER/REPO/actions/runners/registration-token --jq '.token')
```

## Cost Savings

Self-hosted runners can significantly reduce CI costs:
- **GitHub-hosted**: ~$0.008/minute for Linux
- **Self-hosted**: Free compute time + infrastructure costs
- **Best for**: Long-running tests, frequent CI jobs, GPU/special hardware needs

## Troubleshooting

### Runner Shows Offline
1. Check service status: `./svc.sh status`
2. Verify clock sync (GitHub rejects >5min drift)
3. Check network connectivity to GitHub
4. Review runner logs for errors

### Registration Token Expired
Tokens expire after 1 hour. Re-run the setup script to get a fresh token.

### Permission Denied Errors
Ensure your GitHub token has `repo` and `admin:org` scopes:
```bash
gh auth refresh -s admin:org,repo
```

## Security Considerations

- Runners execute arbitrary code from workflow files
- Only use self-hosted runners on repositories you trust
- Keep runner software updated
- Use dedicated VMs/containers for isolation
- Don't run untrusted PRs from forks on self-hosted runners

For fork PRs, use the try-self-hosted + fallback pattern to run untrusted code only on GitHub-hosted runners.

## References

- [GitHub Self-Hosted Runners Docs](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Runner Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Actions Runner Releases](https://github.com/actions/runner/releases)
RUNNER_DOC
fi

for script_name in "${ROOT_SCRIPTS[@]}"; do
    if [[ -f "$script_name" ]]; then
        echo "Exporting infrastructure script: $script_name"

        # Copy and transform
        cp "$script_name" "staging/infrastructure-scripts/$script_name"

        # Apply comprehensive content transformations
        sed -i 's|/tmp/worldarchitect\.ai|/tmp/$PROJECT_NAME|g' "staging/infrastructure-scripts/$script_name"
        sed -i 's|worldarchitect-memory-backups|$PROJECT_NAME-memory-backups|g' "staging/infrastructure-scripts/$script_name"
        sed -i 's|worldarchitect\.ai|your-project.com|g' "staging/infrastructure-scripts/$script_name"
        sed -i 's|$USER|$USER|g' "staging/infrastructure-scripts/$script_name"
        sed -i 's|D&D campaign management|Content management|g' "staging/infrastructure-scripts/$script_name"
        sed -i 's|Game MCP Server|Content MCP Server|g' "staging/infrastructure-scripts/$script_name"
        sed -i 's|start_game_mcp\.sh|start_content_mcp.sh|g' "staging/infrastructure-scripts/$script_name"

        # Add infrastructure script header with adaptation warning
        sed -i '1i\#!/bin/bash\n# 🚨 DEVELOPMENT INFRASTRUCTURE SCRIPT\n# ⚠️ REQUIRES PROJECT ADAPTATION - Contains project-specific configurations\n# This script provides development environment management patterns\n# Adapt paths, service names, and configurations for your project\n\n' "staging/infrastructure-scripts/$script_name"
    else
        echo "Warning: Infrastructure script not found: $script_name"
    fi
done
```
- Export complete development environment bootstrap and management scripts
- Transform project-specific service names and paths to generic placeholders
- Include comprehensive setup and adaptation documentation
- Document multi-service management patterns (MCP servers, orchestration, bot servers)

**🚨 Orchestration System Export** (`orchestration/` → `orchestration/`) - **WIP PROTOTYPE**:
- Export complete multi-agent task delegation system with Redis coordination
- **Architecture**: tmux-based agents (frontend, backend, testing, opus-master) with A2A communication
- **Usage**: `/orch [task]` for autonomous delegation, costs $0.003-$0.050/task
- **Requirements**: Redis server, tmux, Python venv, specialized agent workspaces
- Document autonomous workflow: task creation → agent assignment → execution → PR creation
- Include monitoring via `/orch monitor agents` and direct tmux attachment procedures
- Add scaling guidance for agent capacity and workload distribution
- **Status**: Active development prototype - successful task completion verified with PR generation


**Configuration Export**:
- Export relevant config files (filtered for sensitive data)
- Include setup templates and environment examples
- Document MCP server requirements and configuration
- Provide installation verification procedures

## IMPLEMENTATION

**🚨 DELEGATION TO PYTHON IMPLEMENTATION**: All technical export operations are handled by the robust Python implementation (`exportcommands.py`), while this command focuses on LLM-driven analysis and README generation.

# Analyze the current .claude/commands directory

import os
import subprocess

# Get project root

result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
project_root = result.stdout.strip()

# Count commands, hooks, and scripts

commands_dir = os.path.join(project_root, '.claude', 'commands')
hooks_dir = os.path.join(project_root, '.claude', 'hooks')

commands_count = len([f for f in os.listdir(commands_dir) if f.endswith(('.md', '.py'))])
hooks_count = sum([len([f for f in files if f.endswith(('.sh', '.py', '.md'))])
                   for root, dirs, files in os.walk(hooks_dir)])

print(f"📊 Analysis: {commands_count} commands, {hooks_count} hooks detected")
```

# Execute the comprehensive Python implementation

python_script = os.path.join(project_root, '.claude', 'commands', 'exportcommands.py')
result = subprocess.run([python_script], capture_output=True, text=True)

if result.returncode != 0:
    print(f"❌ Export failed: {result.stderr}")
    exit(1)

print(result.stdout)
```

# Identify key workflow orchestrators vs building blocks

compositional_commands = ['pr.md', 'copilot.md', 'execute.md', 'orch.md']
building_blocks = ['think.md', 'test.md', 'fix.md', 'plan.md']

print("🎯 Workflow Orchestrators:", compositional_commands)
print("🧱 Building Blocks:", building_blocks)
```

**Usage Pattern Insights**: Generate intelligent insights about command relationships
```python

# Analyze command interdependencies

print("📊 Command Composition Patterns:")
print("- /pr → /think → /execute → /pushl → /copilot → /review")
print("- /copilot → /execute → /commentfetch → /fixpr → /commentreply")
print("- /execute → /planexec → /think → implementation → /test")
```

# Execute the Python implementation

project_root = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True).stdout.strip()
python_script = os.path.join(project_root, '.claude', 'commands', 'exportcommands.py')

print("🚀 Starting export via Python implementation...")
result = subprocess.run(['python3', python_script], capture_output=True, text=True)

if result.returncode \!= 0:
    print(f"❌ Export failed: {result.stderr}")
    exit(1)

# Print the output (including the critical PR URL)

print(result.stdout)
```

**🚨 CRITICAL**: The above execution will print the PR URL as the final output, fulfilling the critical success requirement.

## POST-EXPORT ANALYSIS

After the Python implementation completes, provide intelligent analysis:

```python

# Analyze export results for documentation enhancement

print("\n📊 Export Analysis:")
print("✅ Command composition system exported successfully")
print("✅ Directory exclusions applied per requirements")
print("✅ Content filtering applied for project portability")
print("✅ One-click installation script generated")
print("✅ Comprehensive README with adaptation guide created")
```

# Analyze the current .claude/commands directory

import os
import subprocess

# Get project root

result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
project_root = result.stdout.strip()

# Count commands, hooks, and scripts

commands_dir = os.path.join(project_root, '.claude', 'commands')
hooks_dir = os.path.join(project_root, '.claude', 'hooks')

commands_count = len([f for f in os.listdir(commands_dir) if f.endswith(('.md', '.py'))])
hooks_count = sum([len([f for f in files if f.endswith(('.sh', '.py', '.md'))])
                   for root, dirs, files in os.walk(hooks_dir)])

print(f"📊 Analysis: {commands_count} commands, {hooks_count} hooks detected")
```

# Execute the comprehensive Python implementation

python_script = os.path.join(project_root, '.claude', 'commands', 'exportcommands.py')
result = subprocess.run([python_script], capture_output=True, text=True)

if result.returncode != 0:
    print(f"❌ Export failed: {result.stderr}")
    exit(1)

print(result.stdout)
```

# Identify key workflow orchestrators vs building blocks

compositional_commands = ['pr.md', 'copilot.md', 'execute.md', 'orch.md']
building_blocks = ['think.md', 'test.md', 'fix.md', 'plan.md']

print("🎯 Workflow Orchestrators:", compositional_commands)
print("🧱 Building Blocks:", building_blocks)
```

**Usage Pattern Insights**: Generate intelligent insights about command relationships
```python

# Analyze command interdependencies

print("📊 Command Composition Patterns:")
print("- /pr → /think → /execute → /pushl → /copilot → /review")
print("- /copilot → /execute → /commentfetch → /fixpr → /commentreply")
print("- /execute → /planexec → /think → implementation → /test")
```

# Replace the basic export README with comprehensive command showcase

cat > README.md << 'EOF'

# Claude Commands - Command Composition System

⚠️ **REFERENCE EXPORT** - This is a reference export from a working Claude Code project. These commands have been tested in production but may require adaptation for your specific environment. Claude Code excels at helping you customize them for your workflow.

Transform Claude Code into an autonomous development powerhouse through simple command hooks that enable complex workflow orchestration.

## ⚡ COMMAND COMBINATION SUPERPOWERS

### 🤖 AI-Powered Code Quality Detection

**Smart Fake Code Detection**: Built-in `/fake` command uses AI analysis (not just pattern matching) to detect:
- Placeholder implementations that look real but do nothing
- Mock responses without actual logic
- TODOs disguised as complete features
- Demo code that doesn't actually work

## 🚀 Quick Start Examples

Get started immediately with these powerful command combinations:

```bash

# Comprehensive code analysis

/arch /think /fake

# Full PR workflow automation

/pr implement user authentication

# Advanced testing with auto-fix

/test all features and if any fail /fix then /copilot
```

[Include rest of enhanced README content with installation, setup, and advanced workflows...]
EOF

echo "✅ Enhanced main README.md with command combination superpowers"
```

🚨 **CRITICAL LEARNING**: Always update the actual target file (README.md), never create variants like README_UPDATED.md.

# Execute the Python implementation

project_root = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True).stdout.strip()
python_script = os.path.join(project_root, '.claude', 'commands', 'exportcommands.py')

print("🚀 Starting export via Python implementation...")
result = subprocess.run(['python3', python_script], capture_output=True, text=True)

if result.returncode \!= 0:
    print(f"❌ Export failed: {result.stderr}")
    exit(1)

# Print the output (including the critical PR URL)

print(result.stdout)
```

**🚨 CRITICAL**: The above execution will print the PR URL as the final output, fulfilling the critical success requirement.

## POST-EXPORT ANALYSIS

After the Python implementation completes, provide intelligent analysis:

```python

# Analyze export results for documentation enhancement

print("\n📊 Export Analysis:")
print("✅ Command composition system exported successfully")
print("✅ Directory exclusions applied per requirements")
print("✅ Content filtering applied for project portability")
print("✅ One-click installation script generated")
print("✅ Comprehensive README with adaptation guide created")
```

**🎯 SUCCESS CRITERIA**:
1. ✅ PR URL printed (handled by exportcommands.sh)
2. ✅ Repository safety maintained (no local changes)
3. ✅ Complete workflow composition system exported
4. ✅ Main README.md updated with COMMAND COMBINATION SUPERPOWERS
5. ✅ Installation automation provided
6. ✅ LLM-enhanced documentation generated
