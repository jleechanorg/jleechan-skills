#!/bin/bash

# 🚨 Claude Commands Installation Script
# Installs a curated Claude Code skill profile (default) or the full library (--all)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Backups, staging and the portable target are derived by appending a suffix to
# CLAUDE_HOME, so every trailing slash must go; one left behind puts them inside
# the target instead of beside it. A bare "/" stays "/".
strip_trailing_slashes() {
    local path="$1"
    while [ "${#path}" -gt 1 ] && [ "${path%/}" != "$path" ]; do
        path="${path%/}"
    done
    printf '%s\n' "$path"
}

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Source directory (where plugin files live)
PLUGIN_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Active Claude Code directories (system-level)
CLAUDE_HOME="$(strip_trailing_slashes "${CLAUDE_HOME:-$HOME/.claude}")"
CLAUDE_AGENTS_DIR="$CLAUDE_HOME/agents"
CLAUDE_COMMANDS_DIR="$CLAUDE_HOME/commands"
CLAUDE_SCRIPTS_DIR="$CLAUDE_HOME/scripts"
CLAUDE_SKILLS_DIR="$CLAUDE_HOME/skills"

# Source directories in plugin repo
SRC_AGENTS_DIR="$PLUGIN_SRC_DIR/.claude/agents"
SRC_COMMANDS_DIR="$PLUGIN_SRC_DIR/.claude/commands"
SRC_SCRIPTS_DIR="$PLUGIN_SRC_DIR/.claude/scripts"
SRC_SKILLS_DIR="$PLUGIN_SRC_DIR/.claude/skills"
SRC_INTEGRATE_SCRIPT="$PLUGIN_SRC_DIR/scripts/integrate.sh"
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
PORTABLE=false
INCLUDE_PROTECTED=false
PROTECTED_NAMES=()
PROTECTED_PATHS=()
MERGE_BACKUP_DIR=""
PROFILE_NAME=""
INSTALL_ALL=false
WITH_ARGS=()
# "|component/path|" entries chosen by the profile; an --all install selects everything.
SELECTION_ACTIVE=false
SELECTED_INDEX="|"
PROFILE_SKILLS=0
PROFILE_COMMANDS=0
PROFILE_AGENTS=0
PROFILE_SCRIPT="$PLUGIN_SRC_DIR/scripts/install_profiles.py"

show_usage() {
    cat <<EOF
Usage: $(basename "$0") [[--profile NAME] [--with SKILL]... | --all] [--merge [--migrate-archives] [--include-protected] | --backup]
       PORTABLE_HOME=/absolute/dedicated/package $(basename "$0") --portable [--backup]

With no profile flag the curated default profile is installed. --profile NAME
installs that profile's named skills plus every in-repo skill they link to,
the command aliases (and their helpers) for the named skills, and the agents
and scripts those files reference. Closure never adds a skill on the profile data's
closure_excluded list (browser, cookie and personal-infra skills); name one in a
profile or add it with --with SKILL (repeatable). --all installs the full
library (the pre-profile behaviour). Profiles are defined in
shared/install-profiles.json.

Installs into CLAUDE_HOME (default: ~/.claude). A nonempty target is refused
by default. Use --merge to explicitly update source-managed files in place, or
--backup to move the existing target aside before installing. Archive migration
is separate because matching names may be user-authored; combine --merge with
--migrate-archives only after reviewing the reported collisions.

--merge first copies every existing path whose content it would change into
CLAUDE_HOME.merge-backup-<timestamp>-<pid>, and aborts before writing if that
backup fails. It skips existing skills and commands named in
CLAUDE_HOME/.jleechan-skills-protected (one name per line, # comments) or in
the source's shared/retain-local.json (a required JSON object of names when the
file is present; unreadable, malformed or empty data aborts the merge), and
--migrate-archives leaves them in place; --include-protected overwrites or
migrates them too.
EOF
    if [ -f "$PROFILE_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        echo
        echo "Profiles:"
        python3 "$PROFILE_SCRIPT" "$PLUGIN_SRC_DIR" --list || true
        echo "  all"
        echo "      The full library (--all)"
    fi
}

parse_arguments() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --merge) INSTALL_MODE="merge" ;;
            --migrate-archives) MIGRATE_ARCHIVES=true ;;
            --include-protected) INCLUDE_PROTECTED=true ;;
            --backup) INSTALL_MODE="backup" ;;
            --portable) PORTABLE=true ;;
            --all) INSTALL_ALL=true ;;
            --profile)
                if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                    log_error "--profile requires a name"
                    return 1
                fi
                PROFILE_NAME="$2"
                shift
                ;;
            --with)
                if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                    log_error "--with requires a skill name"
                    return 1
                fi
                WITH_ARGS+=(--with "$2")
                shift
                ;;
            -h|--help) show_usage; exit 0 ;;
            *) log_error "Unknown option: $1"; show_usage >&2; return 1 ;;
        esac
        shift
    done
    if [ "$MIGRATE_ARCHIVES" = true ] && [ "$INSTALL_MODE" != "merge" ]; then
        log_error "--migrate-archives requires --merge"
        return 1
    fi
    if [ "$INCLUDE_PROTECTED" = true ] && [ "$INSTALL_MODE" != "merge" ]; then
        log_error "--include-protected requires --merge"
        return 1
    fi
    if [ "$INSTALL_ALL" = true ] && [ -n "$PROFILE_NAME" ]; then
        log_error "--all and --profile are mutually exclusive"
        return 1
    fi
    if [ "$INSTALL_ALL" = true ] && [ "${#WITH_ARGS[@]}" -gt 0 ]; then
        log_error "--with adds to a profile; --all already installs every skill"
        return 1
    fi
    if [ "$PORTABLE" = true ] && { [ "$INSTALL_ALL" = true ] || [ -n "$PROFILE_NAME" ] || [ "${#WITH_ARGS[@]}" -gt 0 ]; }; then
        log_error "--portable installs its own manifest; it does not take --profile, --with or --all"
        return 1
    fi
}

# Resolves the profile before any write, so an unknown or malformed profile
# leaves the target untouched.
load_profile_selection() {
    local entries_file entry
    if [ "$INSTALL_ALL" = true ] || [ "$PROFILE_NAME" = "all" ]; then
        if [ "${#WITH_ARGS[@]}" -gt 0 ]; then
            log_error "--with adds to a profile; --all already installs every skill"
            return 1
        fi
        PROFILE_NAME="all"
        return 0
    fi
    if [ ! -f "$PROFILE_SCRIPT" ]; then
        log_error "Profile resolver missing: $PROFILE_SCRIPT (use --all for the full library)"
        return 1
    fi
    if [ -z "$PROFILE_NAME" ]; then
        if ! PROFILE_NAME="$(python3 "$PROFILE_SCRIPT" "$PLUGIN_SRC_DIR" --default)"; then
            log_error "Cannot determine the default install profile"
            return 1
        fi
    fi
    entries_file="$(mktemp "${TMPDIR:-/tmp}/claude-install-profile.XXXXXX")"
    if ! python3 "$PROFILE_SCRIPT" "$PLUGIN_SRC_DIR" --resolve "$PROFILE_NAME" ${WITH_ARGS[@]+"${WITH_ARGS[@]}"} > "$entries_file"; then
        rm -f -- "$entries_file"
        log_error "Cannot resolve install profile: $PROFILE_NAME"
        return 1
    fi
    while IFS= read -r entry; do
        [ -n "$entry" ] || continue
        SELECTED_INDEX="$SELECTED_INDEX$entry|"
        case "$entry" in
            skills/*) PROFILE_SKILLS=$((PROFILE_SKILLS + 1)) ;;
            commands/*.md) PROFILE_COMMANDS=$((PROFILE_COMMANDS + 1)) ;;
            agents/*) PROFILE_AGENTS=$((PROFILE_AGENTS + 1)) ;;
        esac
    done < "$entries_file"
    rm -f -- "$entries_file"
    SELECTION_ACTIVE=true
}

# Succeeds when component $1's relative path $2, or one of its parent
# directories, was selected by the profile; always succeeds for --all.
is_selected_entry() {
    local prefix="" rest="$2" part
    [ "$SELECTION_ACTIVE" = true ] || return 0
    while [ -n "$rest" ]; do
        if [ "${rest#*/}" = "$rest" ]; then
            part="$rest"
            rest=""
        else
            part="${rest%%/*}"
            rest="${rest#*/}"
        fi
        prefix="${prefix:+$prefix/}$part"
        case "$SELECTED_INDEX" in
            *"|$1/$prefix|"*) return 0 ;;
        esac
    done
    return 1
}

profile_label() {
    if [ "$SELECTION_ACTIVE" = true ]; then
        printf '%s\n' "$PROFILE_NAME"
    else
        printf '%s\n' "--all (full library)"
    fi
}

# Counts for an --all install; a component directory the source lacks counts as zero.
count_full_library() {
    if [ -d "$SRC_SKILLS_DIR" ]; then
        PROFILE_SKILLS="$(find "$SRC_SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d \
            ! -name _archive ! -name '_archived_*' | wc -l | tr -d ' ')"
    fi
    if [ -d "$SRC_COMMANDS_DIR" ]; then
        PROFILE_COMMANDS="$(find "$SRC_COMMANDS_DIR" -type d \( -name __pycache__ -o -name .pytest_cache \) -prune \
            -o -type f -name '*.md' -print | wc -l | tr -d ' ')"
    fi
    if [ -d "$SRC_AGENTS_DIR" ]; then
        PROFILE_AGENTS="$(find "$SRC_AGENTS_DIR" -type f -name '*.md' | wc -l | tr -d ' ')"
    fi
}

# Portable derivatives are opt-in and never merge into canonical agent homes.
# Reuse the existing staged backup transaction, copying skills only.
install_portable() {
    local canonical_home="$CLAUDE_HOME"
    if [ "$INSTALL_MODE" = "merge" ] || [ "$MIGRATE_ARCHIVES" = true ]; then
        log_error "Portable packages do not support merge or archive migration"
        return 1
    fi
    python3 "$PLUGIN_SRC_DIR/scripts/verify_portable_skills.py" "$PLUGIN_SRC_DIR/portable"
    CLAUDE_HOME="$(strip_trailing_slashes "$(python3 "$PLUGIN_SRC_DIR/scripts/verify_portable_skills.py" --target "${PORTABLE_HOME:-}" --canonical-home "$canonical_home")")"
    INSTALL_ROOT="$CLAUDE_HOME"
    prepare_target
    install_component "$PLUGIN_SRC_DIR/portable/skills" "$INSTALL_ROOT/skills" "skills"
    cp "$PLUGIN_SRC_DIR/portable/manifest.json" "$INSTALL_ROOT/manifest.json"
    python3 "$PLUGIN_SRC_DIR/scripts/verify_portable_skills.py" "$INSTALL_ROOT"
    finalize_backup_install
    log_success "Portable disk package verified at $CLAUDE_HOME"
    log_info "Discovery and runtime execution are separate checks; see portable/README.md."
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

file_sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
    fi
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

add_archive_migration_plan() {
    local active_path="$1"
    local archive_path="$2"
    local index

    for index in "${!MIGRATION_ACTIVE_PATHS[@]}"; do
        if [ "${MIGRATION_ACTIVE_PATHS[$index]}" = "$active_path" ]; then
            log_error "Ambiguous archive migration for active path: $active_path"
            log_error "First archive target: ${MIGRATION_ARCHIVE_PATHS[$index]}"
            log_error "Second archive target: $archive_path"
            return 1
        fi
    done

    MIGRATION_ACTIVE_PATHS+=("$active_path")
    MIGRATION_ARCHIVE_PATHS+=("$archive_path")
    MIGRATION_SOURCE_IDENTITIES+=("$(path_identity "$active_path")")
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
            is_protected_entry skills "$package_name" && continue
            active_path="$CLAUDE_HOME/skills/$package_name"
            path_exists "$active_path" || continue
            archive_path="$CLAUDE_HOME/skills_archive/$archive_name/$relative_package"
            add_archive_migration_plan "$active_path" "$archive_path" || return 1
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
            if path_exists "$active_path" && ! is_protected_entry commands "$package_name"; then
                archive_path="$CLAUDE_HOME/commands_archive/$archive_name/top-level/$package_name"
                add_archive_migration_plan "$active_path" "$archive_path" || return 1
            fi
            active_path="$CLAUDE_HOME/commands/extended-library/$package_name"
            if path_exists "$active_path" && ! is_protected_entry commands "extended-library/$package_name"; then
                archive_path="$CLAUDE_HOME/commands_archive/$archive_name/extended-library/$package_name"
                add_archive_migration_plan "$active_path" "$archive_path" || return 1
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
        \) -prune -o \( -type f -o -type l \) ! -name '*.py[co]' ! -name '.DS_Store' -print0
    else
        find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune \
            -o \( -type f -o -type l \) ! -name '*.py[co]' ! -name '.DS_Store' -print0
    fi
}

# Protected names come from the operator's local manifest and the source's
# retain-local.json; an unreadable list aborts the merge rather than allowing
# overwrites.
load_protected_names() {
    local manifest="$CLAUDE_HOME/.jleechan-skills-protected"
    local retain_json="$PLUGIN_SRC_DIR/shared/retain-local.json"
    local line names_file
    PROTECTED_NAMES=()
    [ "$INSTALL_MODE" = "merge" ] || return 0
    if path_exists "$manifest"; then
        if [ ! -f "$manifest" ] || [ ! -r "$manifest" ]; then
            log_error "Cannot read protected manifest: $manifest"
            return 1
        fi
        while IFS= read -r line || [ -n "$line" ]; do
            line="${line%%#*}"
            line="${line#"${line%%[![:space:]]*}"}"
            line="${line%"${line##*[![:space:]]}"}"
            [ -n "$line" ] && PROTECTED_NAMES+=("$line")
        done < "$manifest"
    fi
    # Safety metadata: anything that exists at that path must be a readable regular
    # file holding a non-empty JSON object of names. A directory, a dangling
    # symlink, a JSON string or list, or an unreadable file stops the merge here
    # instead of silently protecting nothing and overwriting local edits.
    if [ -e "$retain_json" ] || [ -L "$retain_json" ]; then
        if [ -L "$retain_json" ] || [ ! -f "$retain_json" ] || [ ! -r "$retain_json" ]; then
            log_error "Cannot read protected list (needs a regular readable file): $retain_json"
            return 1
        fi
        names_file="$(mktemp "${TMPDIR:-/tmp}/claude-install-protected.XXXXXX")"
        if ! python3 - "$retain_json" > "$names_file" <<'PROTECTED_NAMES_PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except (OSError, ValueError) as error:
    sys.exit(f"Cannot parse protected list {path}: {error}")
if not isinstance(data, dict):
    sys.exit(f"Cannot parse protected list {path}: expected a JSON object of name -> reason")
names = [key for key in data if isinstance(key, str) and key.strip()]
if not names or len(names) != len(data):
    sys.exit(f"Cannot parse protected list {path}: keys must be non-empty names")
print("\n".join(names))
PROTECTED_NAMES_PY
        then
            log_error "Cannot parse protected list: $retain_json"
            rm -f -- "$names_file"
            return 1
        fi
        while IFS= read -r line; do
            [ -n "$line" ] && PROTECTED_NAMES+=("$line")
        done < "$names_file"
        rm -f -- "$names_file"
    fi
    snapshot_protected_paths
}

# Records, before any write, which existing top-level skill and command entries,
# and entries of commands/extended-library, match a protected name (exactly or
# minus its extension). A fresh install has none, so it is unaffected.
snapshot_protected_paths() {
    local scan_dir entry top name
    PROTECTED_PATHS=()
    [ "$INCLUDE_PROTECTED" != true ] || return 0
    [ "${#PROTECTED_NAMES[@]}" -gt 0 ] || return 0
    for scan_dir in skills commands commands/extended-library; do
        [ -d "$INSTALL_ROOT/$scan_dir" ] || continue
        while IFS= read -r -d '' entry; do
            top="${entry##*/}"
            for name in "${PROTECTED_NAMES[@]}"; do
                if [ "$name" = "$top" ] || [ "$name" = "${top%.*}" ]; then
                    PROTECTED_PATHS+=("$scan_dir/$top")
                    log_warning "Skipping protected ${scan_dir%%/*} path (overwrite needs --include-protected): $INSTALL_ROOT/$scan_dir/$top"
                    break
                fi
            done
        done < <(find "$INSTALL_ROOT/$scan_dir/" -mindepth 1 -maxdepth 1 -print0)
    done
}

# Succeeds when component $1's relative path $2 is a recorded protected entry
# or lies beneath one.
is_protected_entry() {
    local recorded
    for recorded in ${PROTECTED_PATHS[@]+"${PROTECTED_PATHS[@]}"}; do
        case "$1/$2" in
            "$recorded" | "$recorded"/*) return 0 ;;
        esac
    done
    return 1
}

# Succeeds when a directory between $1 and the parent path $2 is a symlink;
# the installer never writes beneath one.
find_linked_parent() {
    local cur_dir="$1" rest="$2" part
    [ "$rest" != "." ] || return 1
    while [ -n "$rest" ]; do
        if [ "${rest#*/}" = "$rest" ]; then
            part="$rest"
            rest=""
        else
            part="${rest%%/*}"
            rest="${rest#*/}"
        fi
        [ -n "$part" ] || continue
        cur_dir="$cur_dir/$part"
        [ -L "$cur_dir" ] && return 0
    done
    return 1
}

paths_differ() {
    local src="$1" dst="$2"
    if [ -L "$src" ] || [ -L "$dst" ]; then
        [ -L "$src" ] && [ -L "$dst" ] && [ "$(readlink "$src")" = "$(readlink "$dst")" ] && return 1
        return 0
    fi
    [ -f "$src" ] && [ -f "$dst" ] && cmp -s "$src" "$dst" && return 1
    return 0
}

backup_merge_path() {
    local relative="$1" parent_rel="."
    if [ -z "$MERGE_BACKUP_DIR" ]; then
        MERGE_BACKUP_DIR="${CLAUDE_HOME}.merge-backup-$(date +%Y%m%d%H%M%S)-$$"
        if ! mkdir "$MERGE_BACKUP_DIR"; then
            log_error "Cannot create merge backup directory: $MERGE_BACKUP_DIR"
            return 1
        fi
    fi
    case "$relative" in */*) parent_rel="${relative%/*}" ;; esac
    if ! mkdir -p "$MERGE_BACKUP_DIR/$parent_rel" ||
       ! cp -a "$INSTALL_ROOT/$relative" "$MERGE_BACKUP_DIR/$relative"; then
        log_error "Cannot back up $INSTALL_ROOT/$relative; nothing was overwritten"
        return 1
    fi
}

# Copies every existing path a merge would change into a sibling of the target
# (outside skill discovery) before any write, so local edits stay recoverable.
backup_merge_collisions() {
    local component src_dir relative parent_rel count=0 listing_file
    local extra receipt
    [ "$INSTALL_MODE" = "merge" ] || return 0
    listing_file="$(mktemp "${TMPDIR:-/tmp}/claude-install-backup.XXXXXX")"
    for component in agents commands scripts skills; do
        src_dir="$PLUGIN_SRC_DIR/.claude/$component"
        [ -d "$src_dir" ] || continue
        [ -L "$INSTALL_ROOT/$component" ] && continue
        if ! ( cd "$src_dir" && list_installable_files "$component" ) > "$listing_file"; then
            log_error "Could not enumerate $component source files under $src_dir"
            rm -f -- "$listing_file"
            return 1
        fi
        while IFS= read -r -d '' relative; do
            relative="${relative#./}"
            is_protected_entry "$component" "$relative" && continue
            is_selected_entry "$component" "$relative" || continue
            parent_rel="."
            case "$relative" in */*) parent_rel="${relative%/*}" ;; esac
            find_linked_parent "$INSTALL_ROOT/$component" "$parent_rel" && continue
            path_exists "$INSTALL_ROOT/$component/$relative" || continue
            paths_differ "$src_dir/$relative" "$INSTALL_ROOT/$component/$relative" || continue
            if ! backup_merge_path "$component/$relative"; then
                rm -f -- "$listing_file"
                return 1
            fi
            count=$((count + 1))
        done < "$listing_file"
    done
    rm -f -- "$listing_file"
    for extra in history_search.py integrate.sh; do
        [ -f "$PLUGIN_SRC_DIR/scripts/$extra" ] || continue
        is_selected_entry extra "$extra" || continue
        path_exists "$INSTALL_ROOT/scripts/$extra" || continue
        paths_differ "$PLUGIN_SRC_DIR/scripts/$extra" "$INSTALL_ROOT/scripts/$extra" || continue
        backup_merge_path "scripts/$extra" || return 1
        count=$((count + 1))
    done
    # Install rewrites the helper's ownership receipt; keep it paired with the
    # backed-up helper so a restored helper is still recognised as installer-owned.
    receipt="$INSTALL_ROOT/scripts/.history_search.py.sha256"
    if [ -f "$PLUGIN_SRC_DIR/scripts/history_search.py" ] && is_selected_entry extra history_search.py &&
       [ -f "$receipt" ] &&
       [ "$(tr -d '[:space:]' < "$receipt")" != "$(file_sha256 "$PLUGIN_SRC_DIR/scripts/history_search.py")" ]; then
        backup_merge_path "scripts/.history_search.py.sha256" || return 1
        count=$((count + 1))
    fi
    if [ "$count" -gt 0 ]; then
        log_warning "Backed up $count path(s) this merge will overwrite: $MERGE_BACKUP_DIR"
    else
        log_info "No existing paths will change; no merge backup written"
    fi
}

# Shared recursive install function
path_within_root() {
    # $1 = directory that will receive the write, $2 = install root. No command
    # substitution anywhere: $(...) strips trailing newlines, and a directory name
    # may legitimately end with one, so `cd -P` plus $PWD keeps the exact bytes.
    # The bash guard-then-copy window cannot be closed atomically, so this runs
    # immediately before and after each write.
    local parent="$1" root="$2" start="$PWD" root_real parent_real
    # Re-anchor at $start before every relative resolution: a bare `cd` into a
    # relative root would otherwise make the second relative path resolve inside it.
    builtin cd -P -- "$root" 2>/dev/null || return 1
    root_real="$PWD"
    builtin cd -- "$start" 2>/dev/null || return 1
    builtin cd -P -- "$parent" 2>/dev/null || { builtin cd -- "$start" 2>/dev/null; return 1; }
    parent_real="$PWD"
    builtin cd -- "$start" 2>/dev/null || true
    [ "$parent_real" != "$root_real" ] || return 0
    case "$parent_real/" in
        "$root_real"/*) return 0 ;;
        *) return 1 ;;
    esac
}

install_component() {
    local src_dir="$1"
    local dest_dir="$2"
    local component_name="$3"
    local relative

    if [ -L "$dest_dir" ]; then
        log_info "Preserving externally owned $component_name directory link: $dest_dir"
        return 0
    fi

    if [ -d "$src_dir" ]; then
        if [ -d "$dest_dir" ] && [ ! -w "$dest_dir" ]; then
            chmod u+w "$dest_dir"
        fi
        mkdir -p "$dest_dir"
        local preserved_count=0
        local listing_file
        listing_file="$(mktemp "${TMPDIR:-/tmp}/claude-install-listing.XXXXXX")"
        local caller_pwd="$PWD"
        if ! cd "$src_dir"; then
            log_error "Cannot enter source directory $src_dir"
            rm -f -- "$listing_file"
            return 1
        fi
        if ! list_installable_files "$component_name" > "$listing_file"; then
            log_error "Could not enumerate $component_name source files under $src_dir"
            cd "$caller_pwd" || true
            rm -f -- "$listing_file"
            return 1
        fi
        cd "$caller_pwd" || return 1
        while IFS= read -r -d '' relative; do
            relative="${relative#./}"
            local cur_dir="$dest_dir"
            local part
            # Split the relative parent without `read` or `dirname`: both stop at a
            # newline, and a directory name may legitimately contain one, which would
            # hide a symlinked parent and let the copy escape the install target.
            local parent_rel="."
            case "$relative" in
                */*) parent_rel="${relative%/*}" ;;
            esac
            is_protected_entry "$component_name" "$relative" && continue
            is_selected_entry "$component_name" "$relative" || continue
            local skip_file=false
            local linked_owner=""
            if [ "$parent_rel" != "." ]; then
                local part rest="$parent_rel"
                while [ -n "$rest" ]; do
                    if [ "${rest#*/}" = "$rest" ]; then
                        part="$rest"
                        rest=""
                    else
                        part="${rest%%/*}"
                        rest="${rest#*/}"
                    fi
                    [ -n "$part" ] || continue
                    cur_dir="$cur_dir/$part"
                    if [ -L "$cur_dir" ]; then
                        skip_file=true
                        linked_owner="$cur_dir"
                        break
                    elif [ -d "$cur_dir" ] && [ ! -w "$cur_dir" ]; then
                        chmod u+w "$cur_dir"
                    fi
                done
            fi
            if [ "$skip_file" = true ]; then
                log_info "Preserving externally owned $component_name link ($linked_owner); skipping $dest_dir/$relative"
                preserved_count=$((preserved_count + 1))
                continue
            fi
            local target_parent
            if [ "$parent_rel" = "." ]; then
                target_parent="$dest_dir"
            else
                target_parent="$dest_dir/$parent_rel"
            fi
            if [ -d "$target_parent" ] && [ ! -w "$target_parent" ]; then
                chmod u+w "$target_parent"
            fi
            mkdir -p "$target_parent"
            local dest_entry="$dest_dir/$relative"
            if ! path_within_root "$target_parent" "$INSTALL_ROOT"; then
                log_error "Refusing to write $dest_entry: its parent resolves outside $INSTALL_ROOT"
                return 1
            fi
            # No recursive delete anywhere: a directory is never removed, only
            # renamed aside, and a single non-directory entry is unlinked before
            # copying.
            if [ -d "$dest_entry" ] && [ ! -L "$dest_entry" ] \
                && { [ ! -d "$src_dir/$relative" ] || [ -L "$src_dir/$relative" ]; }; then
                local replaced_path="${dest_entry}.replaced-$(date +%Y%m%d%H%M%S)-$$"
                if [ -e "$replaced_path" ] || [ -L "$replaced_path" ]; then
                    log_error "Refusing to move $dest_entry aside onto existing $replaced_path"
                    return 1
                fi
                # The destination was just proven absent, so this move has no
                # existing entry to overwrite; the post-condition check catches a
                # race that recreates it.
                if mv -n "$dest_entry" "$replaced_path" 2>/dev/null && [ ! -e "$dest_entry" ] && [ ! -L "$dest_entry" ]; then
                    log_warning "Moved a directory of the wrong kind aside: $replaced_path"
                else
                    log_error "Cannot replace directory $dest_entry with a non-directory; move it aside and re-run"
                    return 1
                fi
            fi
            if { [ -e "$dest_entry" ] || [ -L "$dest_entry" ]; } \
                && { [ ! -d "$dest_entry" ] || [ -L "$dest_entry" ]; }; then
                # Unlink the single entry whatever it is (symlink, read-only
                # file, hard link, FIFO, socket, device) and let the copy create
                # a fresh one. No chmod: chmod follows a symlink and mutates the
                # shared inode of a hard link, both of which reach outside the
                # target. No recursion: a directory is never removed here.
                rm -f -- "$dest_entry"
            fi
            cp -a "$src_dir/$relative" "$dest_dir/$relative"
            if ! path_within_root "$target_parent" "$INSTALL_ROOT"; then
                log_error "Refusing to continue: $dest_entry resolved outside $INSTALL_ROOT after the copy"
                return 1
            fi
        done < "$listing_file"
        rm -f -- "$listing_file"
        if [ "$preserved_count" -gt 0 ]; then
            log_success "Installed recursive $component_name tree (preserved $preserved_count externally owned path(s))"
        else
            log_success "Installed recursive $component_name tree"
        fi
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

preflight_history_helper() {
    local source="$PLUGIN_SRC_DIR/scripts/history_search.py"
    local scripts_dir="$INSTALL_ROOT/scripts"
    local destination="$scripts_dir/history_search.py"
    local receipt="$scripts_dir/.history_search.py.sha256"
    [ -f "$source" ] || return 0
    is_selected_entry extra history_search.py || return 0

    if [ -L "$scripts_dir" ] ||
       { path_exists "$scripts_dir" && [ ! -d "$scripts_dir" ]; }; then
        log_error "Refusing history helper installation through a non-directory or linked scripts path: $scripts_dir"
        return 1
    fi
    if [ -L "$receipt" ]; then
        log_error "Refusing history helper installation through unsafe receipt symlink: $receipt"
        return 1
    fi
    if path_exists "$receipt"; then
        if ! python3 -c 'import sys, os; st = os.lstat(sys.argv[1]); sys.exit(0 if (os.path.isfile(sys.argv[1]) and st.st_nlink == 1) else 1)' "$receipt" 2>/dev/null; then
            log_error "Refusing history helper installation through unsafe hardlinked or non-regular receipt: $receipt"
            return 1
        fi
    fi
    if path_exists "$destination"; then
        if [ -L "$destination" ] || [ ! -f "$destination" ]; then
            log_error "Refusing to replace an existing history helper: $destination"
            log_error "Inspect and preserve that file; --backup deliberately backs up and replaces the entire target."
            return 1
        fi
        if ! python3 -c 'import sys, os; st = os.lstat(sys.argv[1]); sys.exit(0 if (os.path.isfile(sys.argv[1]) and st.st_nlink == 1) else 1)' "$destination" 2>/dev/null; then
            log_error "Refusing to replace hardlinked history helper: $destination"
            return 1
        fi
        if cmp -s "$source" "$destination"; then
            return 0
        fi

        local is_owned=false
        if [ -f "$receipt" ]; then
            local expected_hash dest_hash
            expected_hash="$(tr -d '[:space:]' < "$receipt" 2>/dev/null || true)"
            dest_hash="$(file_sha256 "$destination" | tr -d '[:space:]')"
            if [ -n "$expected_hash" ] && [ "$dest_hash" = "$expected_hash" ]; then
                is_owned=true
            fi
        fi

        if [ "$is_owned" = false ] && git -C "$PLUGIN_SRC_DIR" rev-parse --git-dir >/dev/null 2>&1; then
            local blob_sha
            blob_sha="$(git -C "$PLUGIN_SRC_DIR" hash-object "$destination" 2>/dev/null || true)"
            if [ -n "$blob_sha" ] && git -C "$PLUGIN_SRC_DIR" rev-list --objects HEAD -- scripts/history_search.py 2>/dev/null | grep -E "^${blob_sha}[[:space:]]+scripts/history_search\.py$" >/dev/null 2>&1; then
                is_owned=true
            fi
        fi

        if [ "$is_owned" = false ]; then
            log_error "Refusing to replace an existing history helper: $destination"
            log_error "Inspect and preserve that file; --backup deliberately backs up and replaces the entire target."
            return 1
        fi
    fi
    return 0
}

# Copy scripts to ~/.claude/scripts/
install_scripts() {
    install_component "$SRC_SCRIPTS_DIR" "$INSTALL_ROOT/scripts" "scripts"
    if [ -f "$PLUGIN_SRC_DIR/scripts/history_search.py" ] && is_selected_entry extra history_search.py; then
        preflight_history_helper
        mkdir -p "$INSTALL_ROOT/scripts"
        rm -f "$INSTALL_ROOT/scripts/history_search.py"
        cp -a "$PLUGIN_SRC_DIR/scripts/history_search.py" "$INSTALL_ROOT/scripts/history_search.py"
        local receipt="$INSTALL_ROOT/scripts/.history_search.py.sha256"
        rm -f "$receipt"
        file_sha256 "$INSTALL_ROOT/scripts/history_search.py" > "$receipt"
    fi
    if ! is_selected_entry extra integrate.sh; then
        :
    elif [ -f "$SRC_INTEGRATE_SCRIPT" ]; then
        mkdir -p "$INSTALL_ROOT/scripts"
        rm -f "$INSTALL_ROOT/scripts/integrate.sh"
        cp -a "$SRC_INTEGRATE_SCRIPT" "$INSTALL_ROOT/scripts/integrate.sh"
        log_success "Installed exported integrate script"
    else
        log_warning "No integrate script source found at $SRC_INTEGRATE_SCRIPT"
    fi
}

# Copy skills to ~/.claude/skills/
install_skills() {
    install_component "$SRC_SKILLS_DIR" "$INSTALL_ROOT/skills" "skills"
}

# Environment validation
validate_installation() {
    local component source_dir relative destination_file files_checked=0
    if [ -f "$PLUGIN_SRC_DIR/scripts/history_search.py" ] && is_selected_entry extra history_search.py &&
       ! cmp -s "$PLUGIN_SRC_DIR/scripts/history_search.py" "$INSTALL_ROOT/scripts/history_search.py"; then
        log_error "Manifest validation failed for scripts/history_search.py"
        return 1
    fi
    for component in agents commands scripts skills; do
        source_dir="$PLUGIN_SRC_DIR/.claude/$component"
        [ -d "$source_dir" ] || continue
        if [ -L "$INSTALL_ROOT/$component" ]; then
            log_info "Preserving externally owned $component directory link during validation: $INSTALL_ROOT/$component"
            continue
        fi
        while IFS= read -r -d '' relative; do
            relative="${relative#./}"
            is_protected_entry "$component" "$relative" && continue
            is_selected_entry "$component" "$relative" || continue
            local cur_dir="$INSTALL_ROOT/$component"
            local part
            # Same newline-safe parent split as the install path: `read` and
            # `dirname` stop at a newline and would hide a symlinked parent here.
            local parent_rel="."
            case "$relative" in
                */*) parent_rel="${relative%/*}" ;;
            esac
            local is_linked=false
            local linked_owner=""
            if [ "$parent_rel" != "." ]; then
                local part rest="$parent_rel"
                while [ -n "$rest" ]; do
                    if [ "${rest#*/}" = "$rest" ]; then
                        part="$rest"
                        rest=""
                    else
                        part="${rest%%/*}"
                        rest="${rest#*/}"
                    fi
                    [ -n "$part" ] || continue
                    cur_dir="$cur_dir/$part"
                    if [ -L "$cur_dir" ]; then
                        is_linked=true
                        linked_owner="$cur_dir"
                        break
                    fi
                done
            fi
            if [ "$is_linked" = true ]; then
                log_info "Preserving externally owned $component link ($linked_owner) during validation; skipping $INSTALL_ROOT/$component/$relative"
                continue
            fi
            destination_file="$INSTALL_ROOT/$component/$relative"
            source_file="$source_dir/$relative"
            if [ -L "$source_file" ]; then
                if [ ! -L "$destination_file" ]; then
                    log_error "Manifest validation failed for $component/$relative: expected destination symlink"
                    return 1
                fi
                src_target="$(readlink "$source_file")"
                dst_target="$(readlink "$destination_file")"
                if [ "$src_target" != "$dst_target" ]; then
                    log_error "Manifest validation failed for $component/$relative: symlink target mismatch"
                    return 1
                fi
            else
                if [ -L "$destination_file" ]; then
                    log_error "Manifest validation failed for $component/$relative: destination must not be a symlink for regular file"
                    return 1
                fi
                if [ ! -f "$destination_file" ]; then
                    log_error "Manifest validation failed for $component/$relative: missing destination file"
                    return 1
                fi
                if ! cmp -s "$source_file" "$destination_file"; then
                    log_error "Manifest validation failed for $component/$relative: content mismatch"
                    return 1
                fi
            fi
            files_checked=$((files_checked + 1))
        done < <(
            cd "$source_dir"
            list_installable_files "$component"
        )
    done
    if [ -f "$SRC_INTEGRATE_SCRIPT" ] && is_selected_entry extra integrate.sh; then
        if [ ! -f "$INSTALL_ROOT/scripts/integrate.sh" ] || \
            ! cmp -s "$SRC_INTEGRATE_SCRIPT" "$INSTALL_ROOT/scripts/integrate.sh"; then
            log_error "Manifest validation failed for scripts/integrate.sh"
            return 1
        fi
        files_checked=$((files_checked + 1))
    fi
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
    if [ "$PORTABLE" = true ]; then
        install_portable
        return
    fi
    load_profile_selection
    [ "$SELECTION_ACTIVE" = true ] || count_full_library
    echo
    log_info "Claude Commands Installation Script"
    log_info "Profile: $(profile_label)"
    log_info "Source: $PLUGIN_SRC_DIR"
    log_info "Target: $CLAUDE_HOME"
    echo

    prepare_target
    load_protected_names
    preflight_history_helper
    backup_merge_collisions
    prepare_archive_migration_on_merge
    install_agents
    install_commands
    install_scripts
    install_skills
    validate_installation
    execute_archive_migration_on_merge
    finalize_backup_install

    echo
    if [ "$SELECTION_ACTIVE" = true ]; then
        log_success "Installed profile '$PROFILE_NAME': $PROFILE_SKILLS skills, $PROFILE_COMMANDS commands, $PROFILE_AGENTS agents"
    else
        log_success "Installed --all (full library): $PROFILE_SKILLS skills, $PROFILE_COMMANDS commands, $PROFILE_AGENTS agents"
    fi
    show_next_steps
    echo
    log_success "Installation complete!"
}

on_exit() {
    local rc=$?
    release_migration_lock
    # Failures are handled from the EXIT trap, not from an inherited ERR trap:
    # bash 3.2 has no BASHPID, so a child shell can neither be detected nor
    # trusted not to release the lock or move the staging tree. Only the shell
    # that owns this trap reaches here.
    if [ "$rc" -ne 0 ] && [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
        local failed_path="${STAGING_DIR}.failed-$(date +%Y%m%d%H%M%S)"
        if [ ! -e "$failed_path" ] && mv -n "$STAGING_DIR" "$failed_path" 2>/dev/null; then
            log_warning "Failed staging tree kept for inspection: $failed_path"
        else
            log_warning "Failed staging tree left in place: $STAGING_DIR"
        fi
    fi
    if [ "$rc" -ne 0 ]; then
        log_error "Installation failed (exit $rc). Check the output above for details."
    fi
    return "$rc"
}

trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Run main installation if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
