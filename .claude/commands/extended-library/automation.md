---
description: /automation - GitHub PR Automation System Integration
type: automation-integration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: ✅ Preflight Installation & Token Check

**Action Steps:**
**Always run these checks before executing any other phase.**

1. **Check Package Installation**: Verify `jleechanorg-pr-automation` is installed
2. **If Not Installed**:
   - Display installation instructions
   - Suggest: `pip install jleechanorg-pr-automation`
   - Exit with helpful error message
3. **Check GitHub Token**: Verify GITHUB_TOKEN environment variable exists
4. **If Token Missing**:
   - Display token setup instructions
   - Suggest: `export GITHUB_TOKEN="your_token_here"`
   - Exit with helpful error message
5. **Verify Dependencies**: Check optional dependencies (email, dev) if needed

### Phase 1: 🎯 Parse Action and Arguments

**Action Steps:**
1. **Parse Command Arguments**: Extract action (status, monitor, process, safety) and parameters from $ARGUMENTS
2. **Validate Action**: Ensure action is one of: status, monitor, process, safety
3. **Extract Parameters**: Get repository name, PR number, and additional flags
4. **Set Defaults**: Use current repository if not specified

### Phase 2: 📊 STATUS Action

**Action Steps:**
**When**: `/automation status`

1. **Confirm Preflight Complete**: Ensure Phase 0 completed successfully
2. **Load Safety Manager**: Initialize safety manager with data directory
   ```python
   import os
   import sys
   from pathlib import Path

   project_name = os.environ.get("PROJECT_NAME") or Path.cwd().name
   data_dir = os.environ.get('AUTOMATION_SAFETY_DATA_DIR')
   if not data_dir:
       if sys.platform == "darwin":
           default_dir = Path.home() / "Library" / "Application Support" / f"{project_name}-automation"
       else:
           default_dir = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / f"{project_name}-automation"
       default_dir.mkdir(parents=True, exist_ok=True)
       data_dir = str(default_dir)

   safety = AutomationSafetyManager(data_dir)
   ```
3. **Display Current Status**:
   - Global automation runs used vs limit
   - Per-PR attempt counts for recent PRs
   - Last reset timestamp
   - Current configuration (PR_LIMIT, GLOBAL_LIMIT, APPROVAL_HOURS)
4. **Show Active PRs**: List PRs currently being tracked in safety system
5. **Display Environment**: Show configured environment variables (GITHUB_TOKEN status, workspace, email config)

### Phase 3: 🔍 MONITOR Action

**Action Steps:**
**When**: `/automation monitor [repository]`

1. **Verify GitHub Token**: Check GITHUB_TOKEN environment variable is set
2. **Initialize Monitor**: Create JleechanorgPRMonitor instance
3. **Configure Repository**: Set target repository or use all repositories if not specified
4. **Execute Monitoring Cycle**:
   - Run `run_monitoring_cycle_with_actionable_count(target_actionable_count=20)`
   - Display actionable PRs discovered
   - Show skipped PRs (already processed, not actionable)
5. **Report Results**:
   - Total PRs scanned
   - Actionable PRs processed
   - Skipped PRs (with reasons)
   - Safety limit status
   - Any errors encountered

### Phase 4: 🎯 PROCESS Action

**Action Steps:**
**When**: `/automation process <pr_number> --repo <repository>`

1. **Validate Arguments**: Ensure PR number and repository are provided
2. **Initialize Safety Manager**: Initialize with data directory and verify PR can be processed
   ```python
   import os
   import sys
   from pathlib import Path

   project_name = os.environ.get("PROJECT_NAME") or Path.cwd().name
   data_dir = os.environ.get('AUTOMATION_SAFETY_DATA_DIR')
   if not data_dir:
       if sys.platform == "darwin":
           default_dir = Path.home() / "Library" / "Application Support" / f"{project_name}-automation"
       else:
           default_dir = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / f"{project_name}-automation"
       default_dir.mkdir(parents=True, exist_ok=True)
       data_dir = str(default_dir)

   safety = AutomationSafetyManager(data_dir)
   # Then check: safety.can_process_pr(pr_number, repo)
   ```
3. **Initialize Monitor**: Create JleechanorgPRMonitor with target PR configuration
4. **Process Single PR**:
   - Run `run_monitoring_cycle_with_actionable_count(target_actionable_count=1)`
   - Target specific PR number and repository
5. **Record Result**:
   - Use the initialized safety manager: `safety.record_pr_attempt(pr_number, result, repo)`
   - Display success/failure status
   - Show remaining attempts for this PR
6. **Error Handling**: If processing fails, display error and suggest remediation

### Phase 5: 🛡️ SAFETY Action

**Action Steps:**
**When**: `/automation safety <subaction>`

**Subactions**:

**5a. Safety Check**: `/automation safety check`
1. Load AutomationSafetyManager with data directory (reuse `safety` from Phase 2/4 when available)
2. Display current safety limits configuration
3. Show per-PR attempt counts
4. Show global automation run count
5. Display last reset timestamp

**5b. Safety Clear**: `/automation safety clear`
1. **WARNING**: Display confirmation message about clearing all safety data
2. Load AutomationSafetyManager with data directory (reuse `safety` when already initialized)
3. Execute clear operation (removes all attempt tracking)
4. Display success message with reset statistics
5. **NOTE**: Only use when explicitly requested by user

**5c. Safety Check PR**: `/automation safety check-pr <pr_number> --repo <repository>`
1. Load AutomationSafetyManager with data directory (reuse `safety` when already initialized)
2. Check if specific PR can be processed
3. Display current attempt count for PR
4. Show remaining attempts before limit
5. Display last attempt timestamp and result

### Phase 6: 🔄 TodoWrite Integration

**Action Steps:**
**For complex operations (monitor, process with multiple PRs)**

1. **Create Todo Items**: Break down automation task into trackable steps
2. **Track Progress**: Update todo status as each step completes
3. **Mark Completion**: Mark todos complete when operation finishes
4. **Error Tracking**: If errors occur, keep todo in_progress with error details

## 📋 REFERENCE DOCUMENTATION

# /automation - GitHub PR Automation System

**Purpose**: Seamless integration of jleechanorg-pr-automation with Claude Code workflows

**Installation**: `pip install jleechanorg-pr-automation`

## 📚 Usage Examples

```bash
# Check automation system status
/automation status

# Monitor all repositories for actionable PRs
/automation monitor

# Monitor specific repository
/automation monitor your-project.com

# Process a specific PR
/automation process 123 --repo jleechanorg/your-project.com

# Check safety limits
/automation safety check

# Check if specific PR can be processed
/automation safety check-pr 123 --repo jleechanorg/your-project.com

# Clear all safety data (use with caution)
/automation safety clear
```

## 🚀 Features

- **Actionable PR Counting**: Only processes PRs that need attention
- **Safety Limits**: Built-in rate limiting prevents automation abuse
- **Cross-Process Safety**: Thread-safe operations with file-based persistence
- **Email Notifications**: Optional SMTP integration for automation alerts
- **Commit-Based Tracking**: Avoids duplicate processing using commit SHAs
- **TodoWrite Integration**: Tracks automation tasks in Claude Code

## ⚙️ Configuration

Set these environment variables in your shell profile or `.env` file:

```bash
# Required
export GITHUB_TOKEN="your_github_token_here"

# Optional - Safety Limits
export AUTOMATION_PR_LIMIT=5           # Max attempts per PR (default: 5)
export AUTOMATION_GLOBAL_LIMIT=50      # Max global runs (default: 50)
export AUTOMATION_APPROVAL_HOURS=24    # Approval expiry (default: 24)

# Optional - Custom Workspace
export PR_AUTOMATION_WORKSPACE="/custom/path"

# Optional - Email Notifications
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT=587
export EMAIL_USER="your-email@gmail.com"
export EMAIL_PASS="your-app-password"
export EMAIL_TO="recipient@example.com"
```

## 🔧 Advanced Integration

### Claude Code Hooks

Automatically trigger PR automation after push:

**.claude/hooks/post-push.sh**:
```bash
#!/bin/bash
# Automatically check for PRs after pushing

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
BRANCH=$(git branch --show-current)
PR_NUMBER=$(gh pr list --head "$BRANCH" --json number -q '.[0].number')

if [[ -n "$PR_NUMBER" ]]; then
    echo "🤖 PR #$PR_NUMBER detected - triggering automation"
    jleechanorg-pr-monitor --target-pr "$PR_NUMBER" --target-repo "$REPO"
fi
```

### Scheduled Monitoring

Add to crontab for hourly PR monitoring:

```bash
0 * * * * cd $(git rev-parse --show-toplevel) && jleechanorg-pr-monitor
```

## 📊 Safety System

The automation system includes comprehensive safety limits:

- **Per-PR Limits**: Maximum consecutive attempts per PR (default: 5)
- **Global Limits**: Maximum total automation runs (default: 50, resets daily)
- **Attempt Tracking**: Full history of success/failure with timestamps
- **Cross-Process Safety**: File-based locking for concurrent automation

## 🤝 Integration with Other Commands

The automation command composes well with other Claude Code commands:

```bash
# Comprehensive PR workflow
/pr "implement user auth" && /automation monitor

# Review and automate
/copilot && /automation process $PR_NUMBER --repo $REPO

# Execute and monitor
/execute "add new feature" && /automation monitor
```

## 📖 Command Line Interface

Direct CLI usage (outside Claude Code):

```bash
# Monitor all repositories
jleechanorg-pr-monitor

# Process specific repository
jleechanorg-pr-monitor --single-repo your-project.com

# Process specific PR
jleechanorg-pr-monitor --target-pr 123 --target-repo jleechanorg/your-project.com

# Dry run (discovery only)
jleechanorg-pr-monitor --dry-run

# Safety CLI
automation-safety-cli status
automation-safety-cli clear
automation-safety-cli check-pr 123 --repo my-repo
```

## 🔗 Related Documentation

- **Package README**: `automation/README.md`
- **Safety Limits**: `automation/AUTOMATION_SAFETY_LIMITS.md`
- **Full Documentation**: `automation/JLEECHANORG_AUTOMATION.md`
- **PyPI Package**: https://pypi.org/project/jleechanorg-pr-automation/

## 🎯 Success Criteria

1. ✅ GitHub token configured and valid
2. ✅ Package installed and importable
3. ✅ Safety limits properly enforced
4. ✅ Actionable PRs correctly identified
5. ✅ Results clearly reported to user
6. ✅ TodoWrite integration for complex operations
