#!/usr/bin/env bash
# cleanup-projects-worktrees.sh — Age-based cleanup for ~/projects/worktree_* directories.
#
# Companion to launchd/com.jleechan.cleanup-projects-worktrees.plist.
# Cleans or archives worktree_* directories older than 21 days with clean git status,
# strictly protecting all worktrees modified within 14 days (zero exceptions).
#
# Usage:
#   cleanup-projects-worktrees.sh                     # dry-run preview (default: 21 days)
#   cleanup-projects-worktrees.sh --clean             # actually delete eligible worktrees
#   cleanup-projects-worktrees.sh --clean --archive-dir /path/to/archive  # move instead of delete
#   cleanup-projects-worktrees.sh --days 30           # custom threshold in days (must be >= 14)
#   cleanup-projects-worktrees.sh --target-dir ~/projects  # target folder
#
# Safety invariants:
# 1. Dry-run by default. Pass --clean to apply changes.
# 2. Minimum age floor is 14 days. Worktrees modified within 14 days are ALWAYS protected.
# 3. Only clean worktrees (no uncommitted edits, no untracked files, no active rebases/merges)
#    are eligible. Any dirty worktree is skipped.
# 4. Strict path confinement: only direct subdirectories of target-dir matching the prefix
#    (default: worktree_*) are evaluated.
# 5. Never runs git worktree prune (worktree prune is forbidden).

set -euo pipefail

# ── Config & Defaults ─────────────────────────────────────────────────────────
TARGET_DIR="${TARGET_DIR:-$HOME/projects}"
PREFIX="${WORKTREE_PREFIX:-worktree_}"
THRESHOLD_DAYS=21
MIN_AGE_DAYS=14
DRY_RUN=true
ARCHIVE_DIR=""
LOG_FILE="${CLEANUP_WORKTREES_LOG:-$HOME/Library/Logs/cleanup-projects-worktrees.log}"

# ── Logging helper ────────────────────────────────────────────────────────────
log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$msg"
  if [[ -n "$LOG_FILE" ]]; then
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
  fi
}

log_err() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*"
  echo "$msg" >&2
  if [[ -n "$LOG_FILE" ]]; then
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
  fi
}

# ── Arg parsing ───────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Safely clean or archive old ~/projects/worktree_* directories.

Options:
  --clean               Apply deletion/archiving. Default: dry-run.
  --days N              Age threshold in days for cleanup (default: 21, min: 14).
  --min-age-days N      Absolute protection floor in days (default: 14, min: 14).
  --target-dir DIR      Directory containing worktrees (default: ~/projects).
  --prefix STR          Directory prefix to match (default: worktree_).
  --archive-dir DIR     Archive destination directory. If omitted, removes directory.
  --log-file FILE       Log output file (default: ~/Library/Logs/cleanup-projects-worktrees.log).
  -h, --help            Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "${1:-}" in
    --clean)          DRY_RUN=false ;;
    --days)           shift; THRESHOLD_DAYS="${1:?--days requires a number}" ;;
    --min-age-days)   shift; MIN_AGE_DAYS="${1:?--min-age-days requires a number}" ;;
    --target-dir)     shift; TARGET_DIR="${1:?--target-dir requires a path}" ;;
    --prefix)         shift; PREFIX="${1:?--prefix requires a string}" ;;
    --archive-dir)    shift; ARCHIVE_DIR="${1:?--archive-dir requires a path}" ;;
    --log-file)       shift; LOG_FILE="${1:?--log-file requires a path}" ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# ── Safety Validation ─────────────────────────────────────────────────────────
if (( MIN_AGE_DAYS < 14 )); then
  log_err "Safety violation: --min-age-days ($MIN_AGE_DAYS) cannot be less than 14 days per repo CLAUDE.md"
  exit 2
fi

if (( THRESHOLD_DAYS < MIN_AGE_DAYS )); then
  log_err "Safety violation: --days ($THRESHOLD_DAYS) cannot be less than minimum age floor ($MIN_AGE_DAYS)"
  exit 2
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  log "Target directory $TARGET_DIR does not exist. Nothing to do."
  exit 0
fi

# ── Helper Functions ──────────────────────────────────────────────────────────
# Find newest mtime excluding build/dependency caches
_RECENCY_PRUNE_NAMES=(.git node_modules venv .venv __pycache__ .pytest_cache .ruff_cache)

get_worktree_newest_mtime() {
  local wt="$1" now newest=0 candidate
  now="$(date +%s)"
  [[ -d "$wt" && -r "$wt" ]] || { echo "$now"; return 0; }

  local prune_expr=() name first=true
  for name in "${_RECENCY_PRUNE_NAMES[@]}"; do
    if [[ "$first" == true ]]; then
      prune_expr=(-name "$name")
      first=false
    else
      prune_expr+=(-o -name "$name")
    fi
  done

  # Search files (GNU stat on Linux, BSD stat on macOS)
  local stat_exec=(-exec stat -f '%m' {} +)
  if stat -c '%Y' "$wt" >/dev/null 2>&1; then
    stat_exec=(-exec stat -c '%Y' {} +)
  fi
  candidate="$(find "$wt" \( "${prune_expr[@]}" \) -prune -o -type f "${stat_exec[@]}" 2>/dev/null \
    | awk '$1 ~ /^[0-9]+$/ && $1+0>m{m=$1+0} END{if (m>0) print m}')" || candidate=""
  [[ -n "$candidate" ]] && (( candidate > newest )) && newest="$candidate"

  # Fallback to directory mtime itself if no files found
  if (( newest <= 0 )); then
    newest="$(stat -c '%Y' "$wt" 2>/dev/null || stat -f '%m' "$wt" 2>/dev/null || echo "$now")"
  fi

  (( newest > now )) && newest="$now"
  echo "$newest"
}

get_worktree_age_days() {
  local wt="$1" now newest
  now="$(date +%s)"
  newest="$(get_worktree_newest_mtime "$wt")"
  echo "$(( (now - newest) / 86400 ))"
}

is_worktree_git_clean() {
  local wt="$1"
  # Check if directory has git metadata
  if ! git -C "$wt" rev-parse --git-dir >/dev/null 2>&1; then
    # Not a git repository or broken git link
    return 1
  fi

  local git_dir
  git_dir="$(git -C "$wt" rev-parse --absolute-git-dir 2>/dev/null || true)"
  if [[ -z "$git_dir" ]]; then
    git_dir="$(git -C "$wt" rev-parse --git-dir 2>/dev/null || true)"
    [[ "$git_dir" != /* ]] && git_dir="$wt/$git_dir"
  fi

  # Check in-progress git states (rebase, merge, cherry-pick, bisect)
  if [[ -d "$git_dir/rebase-merge" || -d "$git_dir/rebase-apply" || \
        -f "$git_dir/MERGE_HEAD" || -f "$git_dir/CHERRY_PICK_HEAD" || \
        -f "$git_dir/BISECT_LOG" ]]; then
    return 1
  fi

  # Check for uncommitted, staged, or untracked changes
  local changes
  changes="$(git -C "$wt" status --porcelain 2>/dev/null || echo "error")"
  if [[ -n "$changes" ]]; then
    return 1
  fi

  # Check if standalone clone vs linked worktree
  local git_common_dir
  git_common_dir="$(git -C "$wt" rev-parse --git-common-dir 2>/dev/null || true)"
  if [[ -n "$git_common_dir" && "$git_common_dir" != /* ]]; then
    git_common_dir="$wt/$git_common_dir"
  fi
  local is_standalone=false
  if [[ -z "$git_common_dir" || "$git_dir" == "$git_common_dir" || -d "$wt/.git/refs" ]]; then
    is_standalone=true
  fi

  if [[ "$is_standalone" == true ]]; then
    # Standalone clone: deleting the folder destroys .git, so protect stashes
    if git -C "$wt" stash list 2>/dev/null | grep -q .; then
      return 1
    fi
    # If upstream tracking branch exists, ensure HEAD has been pushed
    if git -C "$wt" rev-parse --verify "@{u}" >/dev/null 2>&1; then
      local unpushed
      unpushed="$(git -C "$wt" log '@{u}..HEAD' --oneline 2>/dev/null || true)"
      if [[ -n "$unpushed" ]]; then
        return 1
      fi
    fi
  fi

  return 0
}

# ── Main Sweep ────────────────────────────────────────────────────────────────
mode_label="DRY RUN (pass --clean to apply)"
[[ "$DRY_RUN" == false ]] && mode_label="CLEAN MODE (applying actions)"

log "======================================================================"
log "Starting worktree cleanup ($mode_label)"
log "Target: $TARGET_DIR/${PREFIX}* | Threshold: ${THRESHOLD_DAYS}d | Floor: ${MIN_AGE_DAYS}d"
log "======================================================================"

total_found=0
protected_active=0
skipped_threshold=0
skipped_dirty=0
eligible_count=0
reclaimed_bytes=0

# Scan direct children matching prefix
shopt -s nullglob
candidates=("$TARGET_DIR"/"$PREFIX"*)
shopt -u nullglob

if [[ ${#candidates[@]} -eq 0 ]]; then
  log "No directories matching $TARGET_DIR/${PREFIX}* found."
  exit 0
fi

for wt in "${candidates[@]}"; do
  [[ -d "$wt" ]] || continue
  total_found=$((total_found + 1))
  dir_name="$(basename "$wt")"

  # 1. Recency check (14-day absolute floor)
  age_days="$(get_worktree_age_days "$wt")"
  if (( age_days < MIN_AGE_DAYS )); then
    log "[PROTECTED] $dir_name: modified within last ${MIN_AGE_DAYS} days (age: ${age_days}d)"
    protected_active=$((protected_active + 1))
    continue
  fi

  # 2. Threshold check (e.g. 21 days)
  if (( age_days < THRESHOLD_DAYS )); then
    log "[SKIPPED] $dir_name: age ${age_days}d is below threshold ${THRESHOLD_DAYS}d"
    skipped_threshold=$((skipped_threshold + 1))
    continue
  fi

  # 3. Git cleanliness check
  if ! is_worktree_git_clean "$wt"; then
    log "[DIRTY] $dir_name: has uncommitted changes, untracked files, or git error; skipping for safety"
    skipped_dirty=$((skipped_dirty + 1))
    continue
  fi

  # Worktree is clean and older than threshold
  eligible_count=$((eligible_count + 1))
  dir_size="$(du -sk "$wt" 2>/dev/null | awk '{print $1 * 1024}' || echo 0)"
  reclaimed_bytes=$((reclaimed_bytes + dir_size))

  if [[ "$DRY_RUN" == true ]]; then
    log "[DRY RUN] Would clean $dir_name (age: ${age_days}d, clean git status, size: $((dir_size / 1024 / 1024)) MB)"
  else
    if [[ -n "$ARCHIVE_DIR" ]]; then
      mkdir -p "$ARCHIVE_DIR"
      mv "$wt" "$ARCHIVE_DIR/$dir_name"
      log "[ARCHIVED] $dir_name -> $ARCHIVE_DIR/$dir_name"
    else
      rm -rf "$wt"
      log "[REMOVED] $dir_name (reclaimed $((dir_size / 1024 / 1024)) MB)"
    fi
  fi
done

log "----------------------------------------------------------------------"
log "Summary: Scanned: $total_found | Protected (<${MIN_AGE_DAYS}d): $protected_active | Below threshold: $skipped_threshold | Dirty: $skipped_dirty | Cleaned/Eligible: $eligible_count"
log "Total space reclaimed/eligible: $((reclaimed_bytes / 1024 / 1024)) MB"
log "======================================================================"
