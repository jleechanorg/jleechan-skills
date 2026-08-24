# Installation Guide - Claude Commands

This guide covers installation methods for Claude Commands across different platforms.

## Claude Code (Plugin Marketplace)

### Prerequisites
- Claude Code CLI or Web interface
- GitHub account

### Installation Steps

#### Option 1: Marketplace Installation (Recommended)

1. **Register the marketplace** (first-time setup):
   ```bash
   /plugin marketplace add jleechanorg/jleechan-skills
   ```

2. **Install the plugin**:
   ```bash
   /plugin install jleechan-skills@jleechan-skills
   ```

3. **Verify installation**:
   ```bash
   /help
   ```
   You should see 239 commands available (30 Active Core + 209 Extended Library), including:
   - `/pr` - Complete PR lifecycle automation
   - `/copilot` - Autonomous PR analysis and fixing
   - `/orch` - Multi-agent orchestration
   - `/execute` - Plan-approve-execute workflow
   - `/test` - Comprehensive testing commands
   - And many more...

#### Option 2: Manual Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jleechanorg/jleechan-skills.git
   cd jleechan-skills
   ```

2. **Copy commands to your project**:
   ```bash
   # Copy entire command directory
   cp -r .claude/commands/* /path/to/your/project/.claude/commands/

   # Or link specific commands you need
   ln -s $(pwd)/.claude/commands/pr.md /path/to/your/project/.claude/commands/pr.md
   ```

3. **Verify with Claude Code**:
   ```bash
   cd /path/to/your/project
   /list
   ```

## Other Platforms

### Codex / OpenCode

For platforms that support remote instruction fetching:

1. **Fetch and follow remote instructions**:
   ```text
   Please fetch and follow the installation instructions from:
   https://raw.githubusercontent.com/jleechanorg/jleechan-skills/main/INSTALL.md
   ```

2. **Manual setup** (if remote fetch not supported):
   - Clone the repository
   - Copy `.claude/commands/` directory to your project
   - Reference CLAUDE.md for operating protocols

## GitHub CLI Setup (Required for GitHub Operations)

Many commands require GitHub CLI. For detailed installation and usage instructions, see:
- **Installation Guide**: [`.claude/skills/github-cli-reference.md`](.claude/skills/github-cli-reference.md)
- **Authentication**: Automatic via `GITHUB_TOKEN` environment variable
- **Quick Check**: Run `~/.local/bin/gh auth status` to verify

**Quick Install** (if not already installed):
```bash
# See .claude/skills/github-cli-reference.md for full installation steps
~/.local/bin/gh --version || echo "Run installation from .claude/skills/github-cli-reference.md"
```

## Post-Installation

### First Steps

1. **Review the command guide**:
   ```bash
   /README
   ```

2. **Check available commands**:
   ```bash
   /list
   ```

3. **Try your first automation**:
   ```bash
   /think "How do I use the PR automation workflow?"
   ```

### Key Commands to Explore

- **`/pr`** - Complete PR lifecycle: analyze → fix → test → review
- **`/copilot`** - Autonomous PR fixing and GitHub Copilot integration
- **`/execute`** - Plan-approve-execute workflow for complex tasks
- **`/orch`** - Multi-agent orchestration for parallel development
- **`/test`** - Comprehensive testing (unit, integration, e2e)
- **`/think`** - Enhanced reasoning with memory integration
- **`/debug`** - Red-green debugging protocol
- **`/arch`** - Architecture analysis and design

### Configuration

1. **Review CLAUDE.md** for operating protocols and rules
2. **Configure GitHub token** in your environment:
   ```bash
   export GITHUB_TOKEN="your_github_token"
   ```

3. **Set up Memory MCP** (optional, for enhanced /learn and /think):
   - Follow instructions in `.claude/commands/MEMORY_INTEGRATION.md`

## Verification

After installation, verify the system is working:

```bash
# Check command availability
/list

# Test basic command
/help

# Test GitHub integration
/gstatus

# Test orchestration (if Redis available)
/orch status
```

## Troubleshooting

### Commands not showing up

1. Ensure `.claude/commands/` directory exists in your project root
2. Check file permissions (commands should be readable)
3. Restart Claude Code session

### GitHub operations failing

1. Verify GitHub token is set: `echo $GITHUB_TOKEN`
2. Check gh CLI authentication: `gh auth status`
3. If not authenticated, run: `gh auth login` (see [gh auth login manual](https://cli.github.com/manual/gh_auth_login) for details)
4. Ensure network connectivity to GitHub

### Orchestration not working

1. Check Redis installation: `redis-cli ping`
2. Verify tmux is available: `which tmux`
3. Review orchestration logs in `/tmp/orchestration/`

## Updating

### Marketplace Installation

```bash
/plugin update jleechan-skills
```

### Manual Installation

```bash
cd /path/to/jleechan-skills
git pull origin main
cp -r .claude/commands/* /path/to/your/project/.claude/commands/
```

## Uninstallation

### Marketplace Installation

```bash
/plugin uninstall jleechan-skills
```

### Manual Installation

```bash
rm -rf /path/to/your/project/.claude/commands/
```

## Support

- **Issues**: [GitHub Issues](https://github.com/jleechanorg/jleechan-skills/issues)
- **Documentation**: See `.claude/commands/README.md` in your project after installation
- **Examples**: See `.claude/commands/pair-examples.md` in your project after installation

## License

MIT License - See LICENSE file for details
