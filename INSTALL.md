# Installation Guide - Claude Commands

This guide covers installation across supported coding agents. Skills are the
portable interface; commands are optional shortcuts.

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
   You should see the installed skills and commands, including `/repro`,
   `/evidence-review`, and `/parallel`.

#### Option 2: Manual Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jleechanorg/jleechan-skills.git
   cd jleechan-skills
   ```

2. **Run the installer**:
   ```bash
   bash ./install-claude-commands.sh
   ```

3. **Verify with Claude Code**:
   ```bash
   cd /path/to/your/project
   /help
   ```

## Other Platforms

### Codex, Antigravity, and Cursor

For platforms that support remote instruction fetching:

1. **Fetch and follow remote instructions**:
   ```text
   Please fetch and follow the installation instructions from:
   https://raw.githubusercontent.com/jleechanorg/jleechan-skills/main/INSTALL.md
   ```

2. **Manual setup** (if remote fetch is unavailable):
   ```bash
   git clone https://github.com/jleechanorg/jleechan-skills.git /tmp/jleechan-skills
   bash /tmp/jleechan-skills/install-claude-commands.sh
   ```

   For project-local discovery, copy complete skill directories into your
   target project's `.claude/skills/` directory. Do not copy standalone
   `SKILL.md` files: some packages include helper files.

## GitHub CLI Setup (Required for GitHub Operations)

Many commands require GitHub CLI. For detailed installation and usage instructions, see:
- **Installation Guide**: [`.claude/skills/github-cli-reference/SKILL.md`](.claude/skills/github-cli-reference/SKILL.md)
- **Authentication**: Automatic via `GITHUB_TOKEN` environment variable
- **Quick Check**: Run `~/.local/bin/gh auth status` to verify

**Quick Install** (if not already installed):
```bash
# See the skill for full installation steps
gh --version
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

3. **Try a skill**:
   ```bash
   /repro "describe a problem to reproduce"
   ```

### Key Commands to Explore

- **`/repro`** - Reproduce a reported problem with evidence
- **`/evidence-review`** (`/er`) - Review an evidence bundle
- **`/parallel`** - Plan safe concurrent work
- **`/redgreen`** (`/rg`) - Debug through RED, CODE, and GREEN

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

# Inspect a skill
/help
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

## Updating

### Marketplace Installation

```bash
/plugin update jleechan-skills
```

### Manual Installation

```bash
cd /path/to/jleechan-skills
git pull origin main
bash ./install-claude-commands.sh
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
