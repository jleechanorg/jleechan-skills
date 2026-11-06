# Setup Guide

**Installation instructions for confirmed tools from the production stack**

---

## Quick Start (30 minutes)

```bash
# 1. Claude Code CLI
npm install -g @anthropic-ai/claude-code
export ANTHROPIC_API_KEY="sk-ant-..."

# 2. GitHub CLI
brew install gh
gh auth login

# 3. Basic tools
brew install tmux jq

# 4. Test
claude --version
gh --version
```

---

## Complete Setup by Category

### AI Assistants

#### Claude Code CLI ⭐ PRIMARY
```bash
# Install
npm install -g @anthropic-ai/claude-code

# Configure
export ANTHROPIC_API_KEY="sk-ant-..."
claude --setup

# Verify
claude --version
```

**Cost:** $20/mo (Paid tier with 200K context)

**Links:**
- Official: https://docs.anthropic.com/claude/docs/claude-code
- npm: https://www.npmjs.com/package/@anthropic-ai/claude-code
- MiniMax 2.5: [CLAUDE_CODE_MINIMAX_2.5_SETUP.md](CLAUDE_CODE_MINIMAX_2.5_SETUP.md)

---

#### MiniMax 2.5 ⭐ Alternative (Cost-Optimized)

**Purpose:** Use MiniMax 2.5 as Claude Code model ($20/mo)

```bash
# Edit ~/.claude/settings.json with your API key
# See full setup: [CLAUDE_CODE_MINIMAX_2.5_SETUP.md](CLAUDE_CODE_MINIMAX_2.5_SETUP.md)
```

**Cost:** $20/mo - higher capacity than Claude Enterprise

---

#### Cursor
**Download:** https://cursor.sh/

**Cost:** $20/mo (Pro)

**Setup:**
1. Download and install
2. Sign in
3. Configure API keys in Settings → Features

---

#### Antigravity
**Status:** Experimental AI IDE

**Location:** Check official site for download

---

#### Codex
**Status:** Alternative AI assistant

**Note:** App + CLI version available

---

#### Warp Terminal
**Download:** https://www.warp.dev/

**Cost:** Free, Team plans available

**Why:** AI-enhanced terminal with better UX

---

### MCP Servers (10 Active)

**Check current servers:**
```bash
mcp-cli servers
```

**Active servers:**
1. **plugin_superpowers-chrome_chrome** - Obra Superpowers Chrome
2. **sequential-thinking** - Enhanced reasoning
3. **context7** - Library documentation
4. **chrome-superpower** - Browser automation
5. **gemini-cli-mcp** - Gemini API
6. **grok** - X.ai integration
7. **perplexity-ask** - Research/search
8. **beads** - Task tracking
9. **mcp_mail** - Agent messaging
10. **openclaw** - Task orchestration

**Related repos:**
- mcp_mail: https://github.com/jleechanorg/mcp_mail
- claude-commands: https://github.com/jleechanorg/claude-commands

---

### Claude Code Plugins

#### superpowers-chrome
**Status:** Enabled in `~/.claude/settings.json`

```json
"enabledPlugins": {
  "superpowers-chrome@superpowers-marketplace": true
}
```

**Purpose:** Enhanced Chrome browser control

---

### Development Tools

#### gh CLI (GitHub)
```bash
# macOS
brew install gh

# Linux
curl -sL https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz | tar -xz -C /tmp
mkdir -p ~/.local/bin && cp /tmp/gh_2.40.1_linux_amd64/bin/gh ~/.local/bin/

# Authenticate
gh auth login
```

**Key commands:**
```bash
gh pr create
gh pr view 123
gh pr checks
gh issue list
```

---

#### pytest
```bash
pip install pytest pytest-cov
```

**Usage:**
```bash
pytest tests/
pytest --cov=myapp
```

---

#### Docker + Docker Compose
**Download:** https://www.docker.com/get-docker

**Install Docker Desktop** (includes Compose)

**Verify:**
```bash
docker --version
docker compose version
```

---

#### tmux
```bash
brew install tmux
```

**Usage:**
```bash
tmux new -s mysession
tmux attach -t mysession
tmux list-sessions
```

---

### Browser Testing

#### Playwright
```bash
npm install -g playwright
npx playwright install
```

**Usage:**
```bash
npx playwright test
npx playwright codegen  # Record tests
```

---

#### Chrome DevTools Protocol
**Via MCP:** chrome-superpower, claude-in-chrome servers

---

### Cloud & Deployment

#### Google Cloud SDK
```bash
brew install google-cloud-sdk

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT
```

---

#### Firebase
```bash
npm install -g firebase-tools

# Authenticate
firebase login

# Initialize
firebase init
```

---

### Task Tracking

#### beads (bd)
**MCP-integrated task system**

```bash
# Already installed in your setup
bd list
bd create "Task description"
bd update TASK_ID --status completed
```

**Location:** `~/.local/bin/bd` (33MB binary)

---

### Other Tools

#### httpie
```bash
brew install httpie
```

**Usage:**
```bash
http GET api.example.com/users
http POST api.example.com/users name="John"
```

---

## Custom Repos & Directories

### automation/
**Purpose:** PR automation system

**Location:** `automation/` in WorldArchitect.AI repo

**Key files:**
- `orchestrated_pr_runner.py` - Main automation
- `simple_pr_batch.sh` - Batch PR processing
- `jleechanorg_pr_automation/` - PR automation package

---

### orchestration/
**Purpose:** Multi-agent orchestration system

**Location:** `orchestration/` in WorldArchitect.AI repo

**Key files:**
- `orchestrate_unified.py` - Main orchestrator
- `task_dispatcher.py` - Task distribution (111KB!)
- `agent_system.py` - Agent management
- `a2a_integration.py` - Agent-to-agent communication

---

### claude-commands
**Repo:** https://github.com/jleechanorg/claude-commands

**Purpose:** Shared Claude Code commands

**Contents:**
- 80+ custom slash commands
- Automation scripts
- Orchestration integration

---

### mcp_mail
**Repo:** https://github.com/jleechanorg/mcp_mail

**Purpose:** MCP server for agent-to-agent messaging

**Usage:** Inter-agent communication in orchestration workflows

---

## Environment Variables

```bash
# AI Services
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."

# Google Cloud
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/serviceAccountKey.json"

# Add to ~/.bashrc or ~/.zshrc for persistence
```

---

## Verification Script

```bash
#!/bin/bash
echo "🔍 Toolchain Health Check"

# Core tools
command -v claude >/dev/null && echo "✅ Claude Code" || echo "❌ Claude Code MISSING"
command -v gh >/dev/null && echo "✅ gh CLI" || echo "❌ gh CLI MISSING"
command -v pytest >/dev/null && echo "✅ pytest" || echo "❌ pytest MISSING"
command -v docker >/dev/null && echo "✅ Docker" || echo "❌ Docker MISSING"
command -v tmux >/dev/null && echo "✅ tmux" || echo "❌ tmux MISSING"

# MCP
command -v mcp-cli >/dev/null && echo "✅ MCP CLI" || echo "❌ MCP CLI MISSING"
mcp-cli servers 2>/dev/null | wc -l | xargs echo "📊 MCP servers active:"

# Environment
[ -n "$ANTHROPIC_API_KEY" ] && echo "✅ ANTHROPIC_API_KEY set" || echo "⚠️  ANTHROPIC_API_KEY not set"
[ -n "$GITHUB_TOKEN" ] && echo "✅ GITHUB_TOKEN set" || echo "⚠️  GITHUB_TOKEN not set"

echo "✅ Health check complete"
```

---

## Next Steps

1. **Week 1:** Set up Claude Code + basic commands
2. **Week 2:** Add 2-3 MCP servers (sequential-thinking, gemini, perplexity)
3. **Week 3:** Set up testing infrastructure (pytest, Playwright)
4. **Week 4:** Explore orchestration and multi-agent workflows

---

**Last Updated:** 2026-02-12
