# Statusline Command - Universal Composition with Header

**Purpose**: Display branch and PR status information using universal composition

**Usage**: `/statusline` - Shows current branch, remote, and PR information

## 🚨 UNIVERSAL COMPOSITION PROTOCOL

### Command Flow

**The `/statusline` command uses universal composition**:
1. **`/header`** - Executes the header command to get branch and PR information
2. **Display** - Presents the status line information in a clean format

### Implementation

This command delegates to `/header` using Claude's natural workflow orchestration:
- Calls `/header` command directly
- Uses the same branch and PR detection logic
- Provides status line style output

### Example Output

```
[Local: feature-branch | Remote: upstream/main | PR: #123 https://github.com/user/repo/pull/123]
```

**NOTE**: Remote must NEVER be `origin/main`. Use actual remote name (e.g., `upstream/main`, `origin/branch-name`).

## Command Execution

Execute `/header` command and format output as status line information.