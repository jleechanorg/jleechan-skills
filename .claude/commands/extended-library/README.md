---
description: Claude Commands Directory
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# Claude Commands Directory

> **Layout note (2026-08-24).** The command surface is now split in two, and **this index file itself moved** — it used to be `.claude/commands/README.md` and is now `.claude/commands/extended-library/README.md`, which means it is invoked as `/extended-library:README`, not `/README`.
>
> - **`.claude/commands/` — 28 Active Core commands**, invoked as `/<name>`. Selected by a hard top-20-human ∪ top-20-agent usage cutoff (union of 27) plus `/innov` as a forced 28th include.
> - **`.claude/commands/extended-library/` — 211 commands**, invoked as **`/extended-library:<name>`**. Still live and still real; only the invocation name changed. Claude Code discovers subdirectories under `.claude/commands/` recursively and namespaces them as `<subdirectory>:<filename>`.
> - **`archive/commands/` (repo root) — 51 commands**, from an older and unrelated 2026-08-23 pass. Reference-only and genuinely *not* invocable, unlike `extended-library/`.
>
> Full reasoning, empirical verification, and the selection criterion: [archive/extended-library-README.md](../../../archive/extended-library-README.md). Two-mechanism comparison: [archive/README.md](../../../archive/README.md).

## 🎯 Philosophy: Explicit > Implicit

This directory contains Claude Code slash commands that follow the **explicit execution principle**:

- ✅ **Documentation-driven workflows** where every command is visible
- ✅ **Python-based tools** for maintainability and cross-platform support
- ✅ **No hidden wrapper scripts** - users see exactly what runs
- ❌ **Shell scripts are NOT preferred** for command implementations

## 📋 Command Guidelines

### ✅ **Preferred Approach: Python + Documentation**

- **Python scripts** (`.py`) for command logic and data processing
- **Markdown documentation** (`.md`) with explicit command sequences
- **Direct tool calls** that users can see and customize

Example workflow in `copilot.md`:
```bash

# Explicit execution - user sees every command

python3 .claude/commands/copilot.py 780
./run_ci_replica.sh
gh pr view 780 --json statusCheckRollup
python3 .claude/commands/copilot_resolver.py [files]
```

### ❌ **Avoid: Shell Script Wrappers**

- **No `.sh` wrappers** that hide the actual commands being executed
- **No abstraction layers** that obscure the workflow
- **No "magic" scripts** that users can't easily understand or modify

### 🚨 **NEVER Create copilot.sh Again**

This was tried and **failed** because it:
- Hid commands behind a wrapper interface
- Contradicted the explicit execution philosophy
- Added unnecessary complexity vs. documentation-driven approach
- Made the workflow less transparent and harder to customize

## 🏗️ **Command Architecture Patterns**

### **Data Collection Commands**

- **Pattern**: `command.py` with clear argument parsing
- **Output**: Structured data files in `/tmp/` for LLM analysis
- **Integration**: Via explicit calls in documentation

### **Analysis Commands**

- **Pattern**: Standalone Python scripts that process collected data
- **Focus**: Single responsibility (conflict resolution, formatting, etc.)
- **Usage**: Direct execution with clear input/output contracts

### **Workflow Documentation**

- **Pattern**: `command.md` with step-by-step explicit execution
- **Includes**: Decision trees, troubleshooting, examples
- **Goal**: User can execute any step manually or automate selectively

## 📁 **Current Commands**

### **copilot.py** - Enhanced PR Analysis

- **Purpose**: Data collection, conflict detection, auto-fixing
- **Usage**: `python3 copilot.py [PR] [flags]`
- **Flags**: `--auto-fix`, `--merge-conflicts`, `--threaded-reply`

### **copilot_resolver.py** - Conflict Resolution

- **Purpose**: Automated conflict resolution with safety mechanisms
- **Usage**: `python3 copilot_resolver.py file1.py file2.py`
- **Features**: Backup, validation, rollback

### **savetmp.py** - Evidence Archiver

- **Purpose**: Creates timestamped `/tmp/<repo>/<branch>/<work>/` evidence packages with methodology, notes, and copied artifacts.
- **Usage**: `python .claude/commands/savetmp.py <work_name> [--methodology ... --artifact ...]`
- **Outputs**: `README.md`, section markdown files, `metadata.json`, and an `artifacts/` directory for preserved logs/screenshots.

## 🔧 **Development Guidelines**

### **Adding New Commands**

1. **Create Python script** with clear argument parsing
2. **Write documentation** with explicit usage examples
3. **Test explicit execution** - no hidden dependencies
4. **Update this README** with the new command

### **Modifying Existing Commands**

1. **Maintain explicit interfaces** - no hidden behavior changes
2. **Update documentation** to reflect new capabilities
3. **Test both automated and manual execution paths**
4. **Preserve backward compatibility** where possible

### **Command Design Principles**

- **Single Responsibility**: Each command does one thing well
- **Clear Interfaces**: Obvious inputs, outputs, and side effects
- **Error Handling**: Graceful degradation with helpful error messages
- **Documentation**: Every command has usage examples and troubleshooting

## 📚 **Learning from copilot.sh Mistake**

**What Happened**: Created `copilot.sh` as a wrapper script for CI integration
**Why It Failed**: Contradicted explicit execution philosophy, hid commands
**Lesson Learned**: Documentation-driven > Script-driven for transparency
**Never Again**: No shell script wrappers for Claude commands

**Correct Approach**: Enhance `copilot.py` with CI features and document explicit usage in `copilot.md`

## 🚨 CRITICAL ANTI-PATTERNS TO AVOID

### **NEVER Recreate Hook Files**

❌ **DO NOT** create `copilot_pre_hook.py` or `copilot_post_hook.py`
❌ **DO NOT** add copilot hook configuration to `.claude/settings.toml`

## Modular Copilot Commands

The copilot system follows a **clean architecture** where only /commentfetch uses Python for data collection, and all other commands work directly through .md files:

### Clean Architecture Commands

#### The 4 Modular Commands (Each Stands Alone):

1. **`/commentfetch`** - Fetch all PR comments ✅
   - Pure Python: Collects comments from all sources
   - Output: Returns fresh data directly (no caching)
   - The ONLY command that needs Python (pure data collection)

2. **`/fixpr`** - Analyze CI failures and conflicts ✅
   - Pure Markdown: fixpr.md provides all functionality
   - Claude reads fixpr.md and executes analysis directly
   - Runs CI checks, analyzes failures, suggests fixes
   - NO Python file needed

3. **`/commentreply`** - Post comment responses ✅
   - Pure Markdown: commentreply.md guides Claude
   - Claude generates and posts replies directly via `gh api`
   - NO Python middleman, NO intermediate files
   - Direct execution with full transparency

4. **`/pushl`** - Push changes to remote ✅
   - Existing command for git operations
   - Handles add, commit, push workflow

#### Orchestration:

- **`/copilot`** - Intelligent orchestrator that chains the above commands
- Adapts workflow based on PR needs
- Ensures 100% comment coverage with DONE/NOT DONE

### Clean Architecture Principles

**Minimal Python, Maximum Claude Intelligence**

The clean approach:
- **Python**: ONLY for /commentfetch data collection
- **.md files**: Complete command implementations for /fixpr and /commentreply
- **Claude**: Executes .md instructions directly, no Python middleman
- **Transparency**: All actions shown before execution
- **Modularity**: Each command stands alone and can be chained

Clean data flow:
```
PHASE 1: DATA COLLECTION (Only /commentfetch uses Python)
commentfetch.py → fresh comment data
fixpr.py → fixes.json, comparison.json, conflicts.json
        ↓
PHASE 2: INTELLIGENT ANALYSIS (Claude + .md)
Claude reads data + applies .md intelligence
        ↓
PHASE 3: EXECUTION
Claude executes fixes directly
commentreply.py posts pre-generated replies
pushl handles git operations
```

### Why Hybrid?

- **Modularity**: Each command can stand alone
- **Composability**: Commands chain together naturally
- **Transparency**: Clear separation of data vs intelligence
- **Maintainability**: Python for stable plumbing, .md for evolving intelligence

## 📚 Version History

### v1.3.0 (2026-08-24)

**Top-20/top-20 split**: 211 of the 239 active commands moved to `.claude/commands/extended-library/`, leaving 28 Active Core commands flat in `.claude/commands/`. Moved commands stay invocable as `/extended-library:<name>` — a rename, not a retirement. `archive/commands/` was untouched by this pass. See [archive/extended-library-README.md](../../../archive/extended-library-README.md).

### v1.2.0 (2026-08-23)

**Consolidation**: 51 zero-usage, zero-reference commands moved to repo-root `archive/commands/` — see [archive/README.md](../../../archive/README.md) for methodology. Active command count at the time: 239.

### v1.1.0 (2025-08-09)

**Export Statistics**:
- Commands: 116 command definitions  
- Hooks: 13 Claude Code automation hooks
- Scripts: 5 infrastructure scripts

**Changes**:
- Comprehensive command system (116 commands) with enhanced automation
- Enhanced hook automation (13 hooks) including speculation detection and root file management
- Infrastructure automation (5 scripts) for development environment setup
- Template-based README generation with dynamic content replacement
- Obsolete file cleanup and maintenance for repository hygiene
- Additive export strategy preserving existing content while adding new features
- Enhanced content filtering and path normalization for cross-project compatibility
- Version tracking and change history management for transparent updates
- Single version history placement at bottom of README with table of contents integration

---

**Remember**: If users can't see exactly what's running, it's probably the wrong approach.
