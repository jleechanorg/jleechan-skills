---
description: Comprehensive PR status with GitHub MCP orchestration
type: llm-orchestration
execution_mode: immediate
allowed-tools: Bash
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: 🔄 Orchestration Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 1: GitHub Data Collection via /commentfetch

**Action Steps:**
```bash

### Phase 2: Comprehensive Status Display with CI Analysis

**Action Steps:**
Claude: Check for `gstatus.py` in the trusted locations (look in `~/.claude/commands` first, then in the repository `.claude/commands`). Once you find it, run `python3` with the script path and original arguments. If the script is missing from both locations, surface an error explaining the lookup failure.

## 📋 REFERENCE DOCUMENTATION

# /gstatus - Hybrid Orchestration Architecture

**Purpose**: Enhanced PR status with comprehensive CI analysis via Python implementation

## 🚨 CRITICAL CI STATUS DETECTION

**ENHANCED**: Now properly detects failing tests and CI issues like `/fixpr` command does

### Key Improvements:

- ✅ **statusCheckRollup Analysis**: Properly parses GitHub CI status data
- ✅ **Failing Test Detection**: Identifies specific failing test suites
- ✅ **Merge State Analysis**: Distinguishes between MERGEABLE/UNSTABLE/DIRTY/CONFLICTING
- ✅ **True Mergeable Status**: Don't trust `mergeable: "MERGEABLE"` alone - validate CI passes
- ✅ **Comprehensive Coverage**: Shows passing, failing, and pending checks with details

# Fetch PR comments using existing command (eliminates duplication)

echo "📊 Fetching GitHub data via /commentfetch orchestration..."
/commentfetch
```

## 🏗️ Architecture Benefits

- **✅ Orchestration Over Duplication**: Uses `/commentfetch` instead of reimplementing GitHub API
- **✅ Separation of Concerns**: .md orchestrates, .py implements
- **✅ No Fake Code**: Eliminated `call_github_mcp()` placeholder
- **✅ Clean Composition**: Best of command orchestration + specialized implementation

Claude: Display the orchestrated GitHub status with enhanced architecture messaging.
