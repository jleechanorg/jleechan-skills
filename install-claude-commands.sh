#!/bin/bash

# 🚨 Claude Commands Installation Script
# Installs the complete Claude Code command system for development workflows

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Source directory (where plugin files live)
PLUGIN_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Active Claude Code directories (system-level)
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
CLAUDE_AGENTS_DIR="$CLAUDE_HOME/agents"
CLAUDE_COMMANDS_DIR="$CLAUDE_HOME/commands"
CLAUDE_SCRIPTS_DIR="$CLAUDE_HOME/scripts"
CLAUDE_SKILLS_DIR="$CLAUDE_HOME/skills"

# Source directories in plugin repo
SRC_AGENTS_DIR="$PLUGIN_SRC_DIR/.claude/agents"
SRC_COMMANDS_DIR="$PLUGIN_SRC_DIR/.claude/commands"
SRC_SCRIPTS_DIR="$PLUGIN_SRC_DIR/.claude/scripts"
SRC_SKILLS_DIR="$PLUGIN_SRC_DIR/.claude/skills"

# Installation checks
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check for required tools
    local missing_tools=()

    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v pip >/dev/null 2>&1 || missing_tools+=("pip")

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Please install the missing tools and run this script again."
        exit 1
    fi

    # Check for Claude Code CLI
    if ! command -v claude >/dev/null 2>&1; then
        log_warning "Claude Code CLI not found. Install from: https://claude.ai/code"
        log_info "The commands will still be installed but may require Claude Code CLI for full functionality."
    fi

    log_success "Prerequisites check completed"
}

# Directory setup
setup_directories() {
    log_info "Setting up $CLAUDE_HOME directory structure..."

    mkdir -p "$CLAUDE_AGENTS_DIR"
    mkdir -p "$CLAUDE_COMMANDS_DIR"
    mkdir -p "$CLAUDE_SCRIPTS_DIR"
    mkdir -p "$CLAUDE_SKILLS_DIR"

    log_success "Directory structure ready"
}

# Shared install function
install_component() {
    local src_dir="$1"
    local dest_dir="$2"
    local pattern="$3"
    local component_name="$4"
    local make_executable="${5:-false}"

    log_info "Installing $component_name to $dest_dir ..."
    local count=0

    if [ -d "$src_dir" ]; then
        # Use find to match the pattern but avoid subdirectories initially for basic components
        for file in "$src_dir"/$pattern; do
            # The pattern might not match anything, which leaves the literal string with *
            [ -e "$file" ] || continue
            
            if [ -f "$file" ]; then
                cp -f "$file" "$dest_dir/"
                
                if [ "$make_executable" = "true" ]; then
                    chmod +x "$dest_dir/$(basename "$file")" 2>/dev/null || true
                fi
                
                log_info "  Installed: $(basename "$file")"
                count=$((count + 1))
            fi
        done
    else
        log_warning "No $component_name source directory found at $src_dir"
    fi

    log_success "Installed $count $component_name"
    return 0
}

# Copy agents to ~/.claude/agents/
install_agents() {
    install_component "$SRC_AGENTS_DIR" "$CLAUDE_AGENTS_DIR" "*.md" "agents" "false"
}

# Copy commands to ~/.claude/commands/
install_commands() {
    log_info "Installing commands to $CLAUDE_COMMANDS_DIR ..."

    local command_count=0

    if [ -d "$SRC_COMMANDS_DIR" ]; then
        # Copy all top-level files (including scripts and extensionless files)
        for file in "$SRC_COMMANDS_DIR"/*; do
            [ -e "$file" ] || continue
            if [ -f "$file" ]; then
                cp -f "$file" "$CLAUDE_COMMANDS_DIR/"
                # Set executable if it's a script or has no extension
                if [[ "$file" == *.sh ]] || [[ "$file" == *.py ]] || [[ ! "$(basename "$file")" == *.* ]]; then
                    chmod +x "$CLAUDE_COMMANDS_DIR/$(basename "$file")" 2>/dev/null || true
                fi
                log_info "  Installed: $(basename "$file")"
                command_count=$((command_count + 1))
            fi
        done
        
        # Copy subdirectories (e.g. _copilot_modules, _shared, cerebras)
        for subdir in "$SRC_COMMANDS_DIR"/*/; do
            [ -e "$subdir" ] || continue
            if [ -d "$subdir" ]; then
                local subdir_name
                subdir_name="$(basename "$subdir")"
                mkdir -p "$CLAUDE_COMMANDS_DIR/$subdir_name"
                if ! cp -a "$subdir." "$CLAUDE_COMMANDS_DIR/$subdir_name/" 2>/dev/null; then
                    log_error "  Failed to install command subdir: $subdir_name"
                    continue
                fi
                log_info "  Installed command subdir: $subdir_name"
            fi
        done
    else
        log_warning "No commands source directory found at $SRC_COMMANDS_DIR"
    fi

    log_success "Installed $command_count command files"
}

# Copy scripts to ~/.claude/scripts/
install_scripts() {
    install_component "$SRC_SCRIPTS_DIR" "$CLAUDE_SCRIPTS_DIR" "*" "scripts" "true"
}

# Copy skills to ~/.claude/skills/
install_skills() {
    if [ ! -d "$SRC_SKILLS_DIR" ]; then
        log_warning "No skills source directory found at $SRC_SKILLS_DIR"
        return 0
    fi

    log_info "Installing complete skill packages to $CLAUDE_SKILLS_DIR ..."
    cp -a "$SRC_SKILLS_DIR/." "$CLAUDE_SKILLS_DIR/"
    local skill_count
    skill_count=$(find "$CLAUDE_SKILLS_DIR" -type f -name SKILL.md | wc -l | tr -d ' ')
    log_success "Installed $skill_count skill packages"
}

# Environment validation
validate_installation() {
    log_info "Validating installation..."

    local agents_found=0
    local commands_found=0
    local scripts_found=0
    local skills_found=0

    [ -d "$CLAUDE_AGENTS_DIR" ] && agents_found=$(find "$CLAUDE_AGENTS_DIR" -name "*.md" | wc -l | tr -d ' ')
    [ -d "$CLAUDE_COMMANDS_DIR" ] && commands_found=$(find "$CLAUDE_COMMANDS_DIR" -type f | wc -l | tr -d ' ')
    [ -d "$CLAUDE_SCRIPTS_DIR" ] && scripts_found=$(find "$CLAUDE_SCRIPTS_DIR" -type f | wc -l | tr -d ' ')
    [ -d "$CLAUDE_SKILLS_DIR" ] && skills_found=$(find "$CLAUDE_SKILLS_DIR" -name "*.md" | wc -l | tr -d ' ')

    log_info "Installation summary:"
    log_info "  Agents:   $agents_found  → $CLAUDE_AGENTS_DIR"
    log_info "  Commands: $commands_found  → $CLAUDE_COMMANDS_DIR"
    log_info "  Scripts:  $scripts_found  → $CLAUDE_SCRIPTS_DIR"
    log_info "  Skills:   $skills_found  → $CLAUDE_SKILLS_DIR"

    if [ "$agents_found" -gt 0 ] && [ "$commands_found" -gt 0 ] && [ "$scripts_found" -gt 0 ] && [ "$skills_found" -gt 0 ]; then
        log_success "Claude Commands installation completed successfully!"
    else
        log_warning "Installation completed but some components may be missing"
    fi
}

# Usage information
show_usage() {
    log_info "Next steps:"
    echo
    echo "1. Read CLAUDE.md for complete usage instructions"
    echo "2. Try basic commands: /help, /list, /execute"
    echo "3. Configure systems as needed:"
    echo "   - Claude Bot: See claude-bot-commands/README.md"
    echo "4. Start with cognitive commands: /think, /arch, /debug"
    echo
    log_info "For support, see: https://github.com/jleechanorg/claude-commands"
}

# Main installation flow
main() {
    echo
    log_info "Claude Commands Installation Script"
    log_info "Installing complete Claude Code command system..."
    log_info "Source: $PLUGIN_SRC_DIR"
    log_info "Target: $CLAUDE_HOME"
    echo

    check_prerequisites
    setup_directories
    install_agents
    install_commands
    install_scripts
    install_skills
    validate_installation

    echo
    show_usage
    echo
    log_success "Installation complete!"
}

# Error handling
trap 'log_error "Installation failed at line $LINENO. Check the output above for details."; exit 1' ERR

# Run main installation if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
