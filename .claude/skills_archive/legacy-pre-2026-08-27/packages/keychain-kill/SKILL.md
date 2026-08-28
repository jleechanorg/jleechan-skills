---
description: skill to programmatically dismiss macOS keychain prompts and debug headless keyring access issues
scope: user
---

# macOS Keychain Kill & Headless Keyring Troubleshooting Skill

This skill defines the canonical procedures for programmatically dismissing active macOS credential popups and resolving underlying keychain issues in background or headless development execution environments (such as launchd, cron, or isolated tmux test runners).

## 1. Fast Dismissal (The Hard Kill)

When a headless process triggers keychain lookups, macOS launches `SecurityAgent` to request password entry from the user. If the process is backgrounded, it hangs recursively.

To immediately dismiss every active keychain popup across all displays and spaces, execute a hard kill on the on-demand system processes:

```bash
pkill -9 -f SecurityAgent || killall -9 SecurityAgent || true
pkill -9 -f universalAccessAuthWarn || true
```

*Note: Terminates the system agent. macOS automatically cancels all pending authentication requests, immediately restoring a clean display state.*

## 2. Root Cause & Architectural Permanent Fix

Headless background agents (e.g. running under tmux or `ai.hermes.prod` launchd daemons) operate in separate security sessions where the user's main login keychain (`$HOME/Library/Keychains/login.keychain-db`) is locked. When SCM tools (`gh`, `git`, or `claude` authentication modules) attempt to check credentials, they query the locked login keychain, triggering the OS prompt.

### Bypassing Keychain Lookups inside Background Workers

The permanent solution requires isolating background SCM operations from the locked GUI login keychain:

1. **Temporary Isolated Session Keychains**:
   Detect when Darwin processes execute inside a headless background workspace. Instead of attempting to symlink the locked login keychain, create a password-less, isolated temporary keychain under the session's workspace directory:
   ```bash
   security create-keychain -p "" session.keychain
   security unlock-keychain -p "" session.keychain
   security default-keychain -s session.keychain
   ```
2. **CLI Storage Bypasses (`--bare`)**:
   Always pass the `--bare` option to processes (like `claude --bare`) that support bypassing secure local storage persistence.
3. **Automate Workspace Trust**:
   Pre-populate `trustedFolders.json` under both the session and global configuration namespaces (e.g., `~/.claude/settings.json`) to programmatically authorize newly cloned worktrees, preventing interactive trust prompts.

## 3. Diagnostic Procedures

If keychain prompts continue to appear, perform the following checks:

1. **Find Active Security Agents**:
   Verify if a lingering SecurityAgent process is currently active:
   ```bash
   ps aux | grep -i SecurityAgent | grep -v "grep"
   ```
2. **Verify CLI Health & Non-Canonical Processes**:
   Run `ao doctor` to ensure all active background workers inherit the canonical compiled environment. Terminate outdated processes carrying old environment configurations:
   ```bash
   ao doctor --fix
   ```
