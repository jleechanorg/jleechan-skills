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
INSTALL_MODE="refuse"
INSTALL_ROOT="$CLAUDE_HOME"
STAGING_DIR=""
BACKUP_PATH=""
MIGRATION_LOCK_DIR=""
MIGRATION_LOCK_HELD=false
MIGRATE_ARCHIVES=false
MIGRATION_PREPARED=false
MIGRATION_ACTIVE_PATHS=()
MIGRATION_ARCHIVE_PATHS=()
MIGRATION_SOURCE_IDENTITIES=()

show_usage() {
    cat <<EOF
Usage: $(basename "$0") [--merge [--migrate-archives] | --backup]

Installs into CLAUDE_HOME (default: ~/.claude). A nonempty target is refused
by default. Use --merge to explicitly update source-managed files in place, or
--backup to move the existing target aside before installing. Archive migration
is separate because matching names may be user-authored; combine --merge with
--migrate-archives only after reviewing the reported collisions.
EOF
}

parse_arguments() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --merge) INSTALL_MODE="merge" ;;
            --migrate-archives) MIGRATE_ARCHIVES=true ;;
            --backup) INSTALL_MODE="backup" ;;
            -h|--help) show_usage; exit 0 ;;
            *) log_error "Unknown option: $1"; show_usage >&2; return 1 ;;
        esac
        shift
    done
    if [ "$MIGRATE_ARCHIVES" = true ] && [ "$INSTALL_MODE" != "merge" ]; then
        log_error "--migrate-archives requires --merge"
        return 1
    fi
}

directory_is_nonempty() {
    [ -d "$1" ] && [ -n "$(find "$1" -mindepth 1 -maxdepth 1 -print -quit)" ]
}

path_exists() {
    [ -e "$1" ] || [ -L "$1" ]
}

path_identity() {
    stat -c '%d:%i' "$1" 2>/dev/null || stat -f '%d:%i' "$1"
}

release_migration_lock() {
    [ "$MIGRATION_LOCK_HELD" = true ] || return 0
    rmdir "$MIGRATION_LOCK_DIR" || log_warning "Could not remove migration lock: $MIGRATION_LOCK_DIR"
    MIGRATION_LOCK_HELD=false
}

prepare_target() {
    if [ -e "$CLAUDE_HOME" ] && [ ! -d "$CLAUDE_HOME" ]; then
        log_error "Target exists but is not a directory: $CLAUDE_HOME"
        return 1
    fi

    if directory_is_nonempty "$CLAUDE_HOME"; then
        case "$INSTALL_MODE" in
            refuse)
                log_error "Refusing to modify nonempty target: $CLAUDE_HOME"
                log_error "Re-run with --merge to update it or --backup to preserve it as a backup."
                return 1
                ;;
            backup) ;;
            merge)
                log_warning "Merging source-managed files into explicit target: $CLAUDE_HOME"
                ;;
        esac
    fi
    if [ "$INSTALL_MODE" = "backup" ]; then
        mkdir -p "$(dirname "$CLAUDE_HOME")"
        STAGING_DIR="$(mktemp -d "${CLAUDE_HOME}.staging.XXXXXX")"
        INSTALL_ROOT="$STAGING_DIR"
        log_info "Staging backup installation in $STAGING_DIR"
    else
        mkdir -p "$CLAUDE_HOME"
    fi
}

prepare_archive_migration_on_merge() {
    local archive_group archive_name package_path relative_package package_name
    local command_path active_path archive_path index
    [ "$INSTALL_MODE" = "merge" ] || return 0
    if [ "$MIGRATE_ARCHIVES" != true ]; then
        for archive_group in "$PLUGIN_SRC_DIR/.claude/skills_archive"/*; do
            [ -d "$archive_group" ] || continue
            while IFS= read -r -d '' package_path; do
                package_path="$(dirname "$package_path")"
                active_path="$CLAUDE_HOME/skills/$(basename "$package_path")"
                path_exists "$active_path" && log_warning \
                    "Archive collision preserved; migration requires --migrate-archives: $active_path"
            done < <(find "$archive_group" -mindepth 2 -type f -name SKILL.md -print0)
        done
        for archive_group in "$PLUGIN_SRC_DIR/.claude/commands_archive"/*; do
            [ -d "$archive_group" ] || continue
            while IFS= read -r -d '' command_path; do
                [ "$(basename "$command_path")" = "README.md" ] && continue
                package_name="$(basename "$command_path")"
                for active_path in \
                    "$CLAUDE_HOME/commands/$package_name" \
                    "$CLAUDE_HOME/commands/extended-library/$package_name"; do
                    path_exists "$active_path" && log_warning \
                        "Archive collision preserved; migration requires --migrate-archives: $active_path"
                done
            done < <(find "$archive_group" -type f -name '*.md' -print0)
        done
        return 0
    fi
    MIGRATION_LOCK_DIR="$CLAUDE_HOME/.archive-migration.lock"
    if ! mkdir "$MIGRATION_LOCK_DIR"; then
        log_error "Another archive migration is active or left a lock: $MIGRATION_LOCK_DIR"
        return 1
    fi
    MIGRATION_LOCK_HELD=true

    for archive_group in "$PLUGIN_SRC_DIR/.claude/skills_archive"/*; do
        [ -d "$archive_group" ] || continue
        archive_name="$(basename "$archive_group")"
        while IFS= read -r -d '' package_path; do
            package_path="$(dirname "$package_path")"
            relative_package="${package_path#"$archive_group"/}"
            package_name="$(basename "$package_path")"
            active_path="$CLAUDE_HOME/skills/$package_name"
            path_exists "$active_path" || continue
            MIGRATION_ACTIVE_PATHS+=("$active_path")
            MIGRATION_ARCHIVE_PATHS+=("$CLAUDE_HOME/skills_archive/$archive_name/$relative_package")
            MIGRATION_SOURCE_IDENTITIES+=("$(path_identity "$active_path")")
        done < <(find "$archive_group" -mindepth 2 -type f -name SKILL.md -print0)
    done

    for archive_group in "$PLUGIN_SRC_DIR/.claude/commands_archive"/*; do
        [ -d "$archive_group" ] || continue
        archive_name="$(basename "$archive_group")"
        for command_path in "$archive_group"/*.md; do
            [ -f "$command_path" ] || continue
            [ "$(basename "$command_path")" = "README.md" ] && continue
            package_name="$(basename "$command_path")"
            active_path="$CLAUDE_HOME/commands/$package_name"
            if path_exists "$active_path"; then
                MIGRATION_ACTIVE_PATHS+=("$active_path")
                MIGRATION_ARCHIVE_PATHS+=("$CLAUDE_HOME/commands_archive/$archive_name/top-level/$package_name")
                MIGRATION_SOURCE_IDENTITIES+=("$(path_identity "$active_path")")
            fi
            active_path="$CLAUDE_HOME/commands/extended-library/$package_name"
            if path_exists "$active_path"; then
                MIGRATION_ACTIVE_PATHS+=("$active_path")
                MIGRATION_ARCHIVE_PATHS+=("$CLAUDE_HOME/commands_archive/$archive_name/extended-library/$package_name")
                MIGRATION_SOURCE_IDENTITIES+=("$(path_identity "$active_path")")
            fi
        done
    done

    for index in "${!MIGRATION_ACTIVE_PATHS[@]}"; do
        archive_path="${MIGRATION_ARCHIVE_PATHS[$index]}"
        if path_exists "$archive_path"; then
            log_error "Refusing to overwrite existing archive target: $archive_path"
            return 1
        fi
    done

    for archive_path in "${MIGRATION_ARCHIVE_PATHS[@]}"; do
        if ! mkdir -p "$(dirname "$archive_path")"; then
            log_error "Cannot prepare archive parent for: $archive_path"
            return 1
        fi
    done
    MIGRATION_PREPARED=true
}

execute_archive_migration_on_merge() {
    local active_path archive_path index rollback_index moved_path nested_path migration_ok

    [ "$MIGRATION_PREPARED" = true ] || return 0

    for index in "${!MIGRATION_ACTIVE_PATHS[@]}"; do
        active_path="${MIGRATION_ACTIVE_PATHS[$index]}"
        archive_path="${MIGRATION_ARCHIVE_PATHS[$index]}"
        migration_ok=false
        if mv -n "$active_path" "$archive_path" && ! path_exists "$active_path"; then
            if [ "$(path_identity "$archive_path")" = "${MIGRATION_SOURCE_IDENTITIES[$index]}" ]; then
                migration_ok=true
            fi
        fi
        if [ "$migration_ok" != true ]; then
            log_error "Failed to archive retired installation path: $active_path"
            rollback_index="$index"
            while [ "$rollback_index" -ge 0 ]; do
                active_path="${MIGRATION_ACTIVE_PATHS[$rollback_index]}"
                archive_path="${MIGRATION_ARCHIVE_PATHS[$rollback_index]}"
                if ! path_exists "$active_path"; then
                    nested_path="$archive_path/$(basename "$active_path")"
                    if path_exists "$nested_path"; then
                        moved_path="$nested_path"
                    else
                        moved_path="$archive_path"
                    fi
                    mkdir -p "$(dirname "$active_path")"
                    mv "$moved_path" "$active_path" || \
                        log_error "Failed to restore migration path: $active_path"
                fi
                rollback_index=$((rollback_index - 1))
            done
            return 1
        fi
        log_info "Archived retired installation path: $active_path"
    done
    MIGRATION_PREPARED=false
    release_migration_lock
}

finalize_backup_install() {
    [ "$INSTALL_MODE" = "backup" ] || return 0

    if [ -e "$CLAUDE_HOME" ]; then
        BACKUP_PATH="${CLAUDE_HOME}.backup-$(date +%Y%m%d%H%M%S)"
        if [ -e "$BACKUP_PATH" ]; then
            log_error "Backup path already exists: $BACKUP_PATH"
            return 1
        fi
        mv "$CLAUDE_HOME" "$BACKUP_PATH"
        if ! mv "$STAGING_DIR" "$CLAUDE_HOME"; then
            log_error "Failed to activate staged installation; restoring original target."
            mv "$BACKUP_PATH" "$CLAUDE_HOME" || log_error "Original target remains at $BACKUP_PATH"
            return 1
        fi
        log_info "Moved existing target to $BACKUP_PATH"
    else
        mv "$STAGING_DIR" "$CLAUDE_HOME"
    fi
    STAGING_DIR=""
}

list_installable_files() {
    local component_name="$1"
    if [ "$component_name" = "skills" ]; then
        find . -type d \( \
            -name _archive -o \
            -name '_archived_*' -o \
            -name __pycache__ -o \
            -name .pytest_cache \
        \) -prune -o -type f ! -name '*.py[co]' ! -name '.DS_Store' -print0
    else
        find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune \
            -o -type f ! -name '*.py[co]' ! -name '.DS_Store' -print0
    fi
}

# Shared recursive install function
install_component() {
    local src_dir="$1"
    local dest_dir="$2"
    local component_name="$3"
    local relative

    if [ -d "$src_dir" ]; then
        mkdir -p "$dest_dir"
        while IFS= read -r -d '' relative; do
            relative="${relative#./}"
            mkdir -p "$(dirname "$dest_dir/$relative")"
            cp -a "$src_dir/$relative" "$dest_dir/$relative"
        done < <(
            cd "$src_dir"
            list_installable_files "$component_name"
        )
        log_success "Installed recursive $component_name tree"
    else
        log_warning "No $component_name source directory found at $src_dir"
    fi
}

# Copy agents to ~/.claude/agents/
install_agents() {
    install_component "$SRC_AGENTS_DIR" "$INSTALL_ROOT/agents" "agents"
}

# Copy commands to ~/.claude/commands/
install_commands() {
    install_component "$SRC_COMMANDS_DIR" "$INSTALL_ROOT/commands" "commands"
}

# Copy scripts to ~/.claude/scripts/
install_scripts() {
    install_component "$SRC_SCRIPTS_DIR" "$INSTALL_ROOT/scripts" "scripts"
}

# Copy skills to ~/.claude/skills/
install_skills() {
    install_component "$SRC_SKILLS_DIR" "$INSTALL_ROOT/skills" "skills"
}

# Environment validation
validate_installation() {
    local component source_dir relative destination_file files_checked=0
    for component in agents commands scripts skills; do
        source_dir="$PLUGIN_SRC_DIR/.claude/$component"
        [ -d "$source_dir" ] || continue
        while IFS= read -r -d '' relative; do
            relative="${relative#./}"
            destination_file="$INSTALL_ROOT/$component/$relative"
            if [ ! -f "$destination_file" ] || ! cmp -s "$source_dir/$relative" "$destination_file"; then
                log_error "Manifest validation failed for $component/$relative"
                return 1
            fi
            files_checked=$((files_checked + 1))
        done < <(
            cd "$source_dir"
            list_installable_files "$component"
        )
    done
    log_success "Source-derived manifest validation passed ($files_checked files)"
}

# Post-install information
show_next_steps() {
    log_info "Start Claude Code to use the installed commands and skills."
    log_info "Documentation: https://github.com/jleechanorg/claude-commands"
}

# Main installation flow
main() {
    parse_arguments "$@"
    echo
    log_info "Claude Commands Installation Script"
    log_info "Installing complete Claude Code command system..."
    log_info "Source: $PLUGIN_SRC_DIR"
    log_info "Target: $CLAUDE_HOME"
    echo

    prepare_target
    prepare_archive_migration_on_merge
    install_agents
    install_commands
    install_scripts
    install_skills
    validate_installation
    execute_archive_migration_on_merge
    finalize_backup_install

    echo
    show_next_steps
    echo
    log_success "Installation complete!"
}

cleanup_failed_install() {
    release_migration_lock
    if [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
        rm -rf "$STAGING_DIR"
    fi
    log_error "Installation failed at line $LINENO. Check the output above for details."
    exit 1
}

trap cleanup_failed_install ERR
trap release_migration_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Run main installation if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
