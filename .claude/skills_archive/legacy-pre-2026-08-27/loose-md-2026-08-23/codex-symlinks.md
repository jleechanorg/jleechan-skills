# Skill: codex-symlinks

Create or update Codex project symlinks for quick access to key repos.

## Overview
Codex project symlinks let you quickly open repos with `/codex <repo>` or equivalent commands. This skill creates symlinks in `~/bin/` (or similar) for the main project repos.

## Repos to Link
| Name | Path | Symlink |
|------|------|---------|
| ai_universe | `~/projects_other/ai_universe/` | `~/bin/codex-ai-universe` |
| your-project.com | `~/projects_other/your-project.com/` | `~/bin/codex-worldarchitect` |
| agent-orchestrator | `~/projects_other/agent_orchestrator/` or `~/projects/agent_orchestrator/` | `~/bin/codex-orchestrator` |
| user_scope | `~/projects_other/user_scope/` | `~/bin/codex-user-scope` |

## Create Symlinks
```bash
mkdir -p ~/bin

# ai_universe
ln -sf ~/projects_other/ai_universe ~/bin/codex-ai-universe

# your-project.com
ln -sf ~/projects_other/your-project.com ~/bin/codex-worldarchitect

# agent-orchestrator (find actual path first)
find ~/projects_other ~/projects -maxdepth 2 -type d -name "agent_orchestrator" 2>/dev/null | head -1 | xargs -I{} ln -sf {} ~/bin/codex-orchestrator

# user_scope
ln -sf ~/projects_other/user_scope ~/bin/codex-user-scope
```

## Verify Symlinks
```bash
ls -la ~/bin/codex-*
```

## Add ~/bin to PATH (if not already)
```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/bin:$PATH"
```

## Codex Project Config Entries

Codex also tracks projects in `~/.codex/config.toml`. The key paths are:

```
~/.codex/config.toml
```

Add these project entries if not already present:

```toml
[projects."$HOME/projects_other/ai_universe"]
trust_level = "trusted"

[projects."$HOME/projects_other/your-project.com"]
trust_level = "trusted"
```

## Quick Verify
```bash
# Test codex can access repos
cd ~/bin/codex-ai-universe && pwd
cd ~/bin/codex-worldarchitect && pwd
```
