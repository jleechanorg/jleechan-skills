#!/usr/bin/env bash
# Portable copy from jleechanorg/worldarchitect.ai's scripts/check_beads_jsonl_drift.sh
# (hardened over 4 rounds of adversarial review against a "competing writable
# authority" bypass; see rev-8xvey). Fully repo-path-agnostic already — no
# edits needed beyond resolving its sibling compare script from its own
# directory instead of a hardcoded scripts/ path.
#
# Operational gate check for .beads/issues.jsonl:
# 1. Ordinary feature branches MUST NOT flush or commit .beads/issues.jsonl.
# 2. A canonical export PR is allowed only when CI explicitly authorizes it and
#    its complete diff is limited to the canonical export files.
# 3. If .beads/issues.jsonl is untouched, verify active local DB health
#    (if present) with nonblocking doctor warning semantics, or pass.
#
# Exit code 0 = operational gate satisfied (JSONL untouched / healthy local DB).
# Exit code 1 = fail-closed error (feature branch mutated JSONL, or hard DB/doctor error).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$SCRIPT_DIR/.." && pwd))"
cd "$REPO_ROOT"

TRACKED_JSONL="$REPO_ROOT/.beads/issues.jsonl"

if ! command -v br >/dev/null 2>&1; then
  echo "::error title=beads drift check::br CLI not found; drift check requires br"
  exit 1
fi

if [ ! -f "$TRACKED_JSONL" ]; then
  echo "::error title=beads drift check::tracked export $TRACKED_JSONL missing"
  exit 1
fi

# Use the event base supplied by CI. Local callers may use their exact fetched
# origin/main commit, but never a branch-name or parent-commit heuristic.
TARGET_REF="${BEADS_DRIFT_BASE_SHA:-}"
if [ -z "$TARGET_REF" ]; then
  if [ "${CI:-false}" = "true" ] || [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
    echo "::error title=beads operational gate::BEADS_DRIFT_BASE_SHA is required in CI."
    exit 1
  fi
  TARGET_REF="$(git rev-parse --verify 'refs/remotes/origin/main^{commit}' 2>/dev/null || true)"
fi

IS_TOUCHED="false"
if ! printf '%s\n' "$TARGET_REF" | grep -qE '^[0-9a-fA-F]{40}$'; then
  echo "::error title=beads operational gate::Trusted diff base is missing or malformed."
  exit 1
fi
RESOLVED_TARGET="$(git rev-parse --verify "${TARGET_REF}^{commit}" 2>/dev/null || true)"
if [ -z "$RESOLVED_TARGET" ] || [ "$RESOLVED_TARGET" != "$TARGET_REF" ]; then
  echo "::error title=beads operational gate::Trusted diff base $TARGET_REF is not an exact available commit."
  exit 1
fi

PR_CHANGED_PATHS=""
if ! PR_CHANGED_PATHS="$(git diff --name-only "$TARGET_REF"...HEAD 2>/dev/null)"; then
  echo "::error title=beads operational gate::Cannot inspect the complete diff from $TARGET_REF to HEAD."
  exit 1
fi
if printf '%s\n' "$PR_CHANGED_PATHS" | grep -qxF ".beads/issues.jsonl"; then
  IS_TOUCHED="true"
fi

if [ "$IS_TOUCHED" = "true" ]; then
  if [ "${CANONICAL_EXPORT_PR:-0}" != "1" ]; then
    echo "::error title=beads operational gate::Feature branches are forbidden from modifying or committing .beads/issues.jsonl. Only an explicitly authorized canonical export PR may advance it."
    exit 1
  fi

  CHANGED_PATHS="$PR_CHANGED_PATHS"
  OUT_OF_SCOPE="$(
    printf '%s\n' "$CHANGED_PATHS" \
      | sed '/^$/d' \
      | grep -vxE '\.beads/(issues\.jsonl|\.gitignore)' \
      || true
  )"
  if [ -n "$OUT_OF_SCOPE" ]; then
    echo "::error title=beads operational gate::Authorized canonical export PR contains out-of-scope paths:"
    printf '%s\n' "$OUT_OF_SCOPE" | sed 's/^/  /'
    exit 1
  fi

  echo "OK: explicitly authorized canonical export PR is limited to canonical export files"
  exit 0
fi

# Resolve store through br without treating command or parse failures as no DB.
set +e
STORE_INFO="$(br --no-db where --json 2>&1)"
STORE_INFO_EXIT_CODE=$?
set -e
if [ "$STORE_INFO_EXIT_CODE" -ne 0 ]; then
  echo "::error title=beads drift check::br --no-db where --json failed " \
    "with exit code $STORE_INFO_EXIT_CODE: $STORE_INFO"
  exit 1
fi

# Each field is parsed and printed by its own invocation so that no
# delimiter-joined value (e.g. a tab-and-cut handoff) can let an embedded
# tab/newline in one field shift bytes into the other field's variable.
if ! ACTIVE_BEADS_DIR="$(python3 - "$STORE_INFO" <<'PY'
import json
import sys

try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, TypeError, ValueError) as exc:
    raise SystemExit(f"invalid JSON: {exc}") from exc
if not isinstance(data, dict):
    raise SystemExit("store discovery result must be a JSON object")
beads_dir = data.get("path", "")
if not isinstance(beads_dir, str):
    raise SystemExit("path must be a string when present")
print(beads_dir)
PY
)"; then
  echo "::error title=beads drift check::br --no-db where --json returned invalid JSON"
  exit 1
fi
if ! ACTIVE_DB="$(python3 - "$STORE_INFO" <<'PY'
import json
import sys

try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, TypeError, ValueError) as exc:
    raise SystemExit(f"invalid JSON: {exc}") from exc
if not isinstance(data, dict):
    raise SystemExit("store discovery result must be a JSON object")
database_path = data.get("database_path", "")
if not isinstance(database_path, str):
    raise SystemExit("database_path must be a string when present")
print(database_path)
PY
)"; then
  echo "::error title=beads drift check::br --no-db where --json returned invalid JSON"
  exit 1
fi

# Resolve the owning checkout's authorized store unconditionally -- not only
# when `br` reports a path/database_path. `br` reporting NOTHING must not
# skip validation of a real DB that is actually sitting on disk any more than
# `br` reporting a partial or self-serving payload should: DB discovery must
# not depend on br's self-report at all. When `br` DOES report something,
# that report is validated against this authorized location and rejected as
# a competing writable authority on any mismatch.
if ! AUTHORIZED_DB="$(python3 - "$ACTIVE_BEADS_DIR" "$ACTIVE_DB" <<'PY'
import subprocess
import sys
from pathlib import Path

active_beads_dir_raw = sys.argv[1]
active_db_raw = sys.argv[2]

try:
    git_common_dir_raw = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).strip()
except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
    print(f"::error title=beads drift check::Cannot determine git common dir: {exc}", file=sys.stderr)
    sys.exit(1)

common_dir = (Path.cwd() / git_common_dir_raw).resolve()
# Standard linked worktrees share the owning checkout's .git directory.
owning_checkout = common_dir.parent if common_dir.name == ".git" else common_dir
authorized_beads_dir = (owning_checkout / ".beads").resolve()
authorized_db = authorized_beads_dir / "beads.db"

if active_beads_dir_raw or active_db_raw:
    if not active_beads_dir_raw:
        print("::error title=beads drift check::Resolved beads store path is a competing writable authority: discovery path is empty", file=sys.stderr)
        sys.exit(1)

    resolved_discovery_dir = (Path.cwd() / active_beads_dir_raw).resolve()

    if resolved_discovery_dir != authorized_beads_dir:
        print(
            f"::error title=beads drift check::Resolved beads store path is a competing writable authority "
            f"(discovery='{resolved_discovery_dir}', authorized='{authorized_beads_dir}')",
            file=sys.stderr,
        )
        sys.exit(1)

    if active_db_raw:
        resolved_db = (Path.cwd() / active_db_raw).resolve()
        if resolved_db != authorized_db:
            print(
                f"::error title=beads drift check::Resolved beads store path is a competing writable authority "
                f"(db='{resolved_db}', authorized='{authorized_db}')",
                file=sys.stderr,
            )
            sys.exit(1)

print(authorized_db)
PY
)"; then
  exit 1
fi
if [ -f "$AUTHORIZED_DB" ]; then
  ACTIVE_DB="$AUTHORIZED_DB"
else
  ACTIVE_DB=""
fi

if [ -n "$ACTIVE_DB" ] && [ -f "$ACTIVE_DB" ]; then
  SCRATCH_DIR="$(mktemp -d)"
  trap 'rm -rf "$SCRATCH_DIR"' EXIT

  mkdir -p "$SCRATCH_DIR/.beads"
  cp "$TRACKED_JSONL" "$SCRATCH_DIR/.beads/issues.jsonl"

  db_family_fingerprint() {
    python3 - "$ACTIVE_DB" "${ACTIVE_DB}-wal" "${ACTIVE_DB}-shm" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

records = []
for raw_path in sys.argv[1:]:
    path = pathlib.Path(raw_path)
    if not os.path.lexists(path):
        records.append({"path": str(path), "exists": False})
        continue
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"active DB source is not a physical file: {path}")
    records.append(
        {
            "path": str(path),
            "exists": True,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
    )
print(json.dumps(records, sort_keys=True, separators=(",", ":")))
PY
  }

  SOURCE_FINGERPRINT_BEFORE="$(db_family_fingerprint)" || {
    echo "::error title=beads drift check::Cannot fingerprint active DB family"
    exit 1
  }

  # Copy durable DB/WAL bytes without opening SQLite against the live family.
  # Scratch SQLite reconstructs its own transient SHM index.
  SCRATCH_DB="$SCRATCH_DIR/.beads/beads.db"
  if ! python3 - "$ACTIVE_DB" "$SCRATCH_DB" <<'PY'
import os
import pathlib
import shutil
import sys

source_path = pathlib.Path(sys.argv[1])
destination_path = pathlib.Path(sys.argv[2])


def copy_physical(source: pathlib.Path, destination: pathlib.Path) -> None:
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(source_fd, "rb", closefd=False) as source_handle:
            with destination.open("xb") as destination_handle:
                shutil.copyfileobj(source_handle, destination_handle)
    finally:
        os.close(source_fd)


copy_physical(source_path, destination_path)
source_wal = pathlib.Path(f"{source_path}-wal")
if os.path.lexists(source_wal):
    if source_wal.is_symlink() or not source_wal.is_file():
        raise SystemExit(f"active WAL is not a physical file: {source_wal}")
    copy_physical(source_wal, pathlib.Path(f"{destination_path}-wal"))
PY
  then
    echo "::error title=beads drift check::Raw DB/WAL snapshot failed"
    exit 1
  fi

  SOURCE_FINGERPRINT_AFTER_COPY="$(db_family_fingerprint)" || {
    echo "::error title=beads drift check::Cannot re-fingerprint active DB family"
    exit 1
  }
  if [ "$SOURCE_FINGERPRINT_BEFORE" != "$SOURCE_FINGERPRINT_AFTER_COPY" ]; then
    echo "::error title=beads drift check::Active DB changed during snapshot"
    exit 1
  fi

  pushd "$SCRATCH_DIR" >/dev/null

  STATUS_LOG="$SCRATCH_DIR/status.json"
  STATUS_ERR="$SCRATCH_DIR/status.err"
  status_exit=0
  br sync --status --json >"$STATUS_LOG" 2>"$STATUS_ERR" || status_exit=$?

  DOCTOR_LOG="$SCRATCH_DIR/doctor.json"
  DOCTOR_ERR="$SCRATCH_DIR/doctor.err"
  doctor_exit=0
  br doctor --quick --json >"$DOCTOR_LOG" 2>"$DOCTOR_ERR" || doctor_exit=$?

  python3 - "$STATUS_LOG" "$DOCTOR_LOG" "$status_exit" "$doctor_exit" <<'PY' || { popd >/dev/null; exit 1; }
import json
import sys

status_path, doctor_path, status_exit_str, doctor_exit_str = sys.argv[1:5]
status_exit = int(status_exit_str)
doctor_exit = int(doctor_exit_str)

if status_exit != 0:
    print(f"::error title=beads drift check::br sync --status exited with code {status_exit}")
    sys.exit(1)

if doctor_exit not in (0, 1):
    print(f"::error title=beads drift check::br doctor --quick execution failed with code {doctor_exit}")
    sys.exit(1)

try:
    with open(status_path, encoding="utf-8") as f:
        status_data = json.load(f)
except Exception as exc:
    print(f"::error title=beads drift check::failed to parse br sync --status JSON: {exc}")
    sys.exit(1)

if not isinstance(status_data, dict):
    print("::error title=beads drift check::br sync --status output is not a JSON object")
    sys.exit(1)

db_newer = bool(status_data.get("db_newer", False))
jsonl_newer = bool(status_data.get("jsonl_newer", False))
dirty_count = status_data.get("dirty_count", 0)
workspace_health = status_data.get("workspace_health")

try:
    with open(doctor_path, encoding="utf-8") as f:
        doctor_data = json.load(f)
except Exception as exc:
    print(f"::error title=beads drift check::failed to parse br doctor --quick JSON: {exc}")
    sys.exit(1)

if not isinstance(doctor_data, dict):
    print("::error title=beads drift check::br doctor --quick output is not a JSON object")
    sys.exit(1)

checks = doctor_data.get("checks")
if not isinstance(checks, list) or not checks or any(
    not isinstance(check_item, dict) for check_item in checks
):
    print(
        "::error title=beads drift check::br doctor --quick checks must be a non-empty list of objects"
    )
    sys.exit(1)
error_checks = [
    c for c in checks
    if isinstance(c, dict) and c.get("status") == "error"
]
unknown_checks = [
    c for c in checks
    if isinstance(c, dict) and c.get("status") not in {"ok", "warn", "error"}
]
warning_checks = [
    c for c in checks
    if isinstance(c, dict) and c.get("status") == "warn"
]
doc_health = doctor_data.get("workspace_health")
UNHEALTHY_STATES = {"unhealthy", "recoverable", "corrupt", "failed", "error"}

if unknown_checks:
    unknown_names = ", ".join(c.get("name", "unknown") for c in unknown_checks)
    print(
        "::error title=beads drift check::br doctor --quick reported "
        f"unknown check states: [{unknown_names}]"
    )
    sys.exit(1)

if doctor_exit == 1 and not warning_checks and not error_checks:
    print(
        "::error title=beads drift check::br doctor --quick returned warning exit "
        "without any warning finding"
    )
    sys.exit(1)

if error_checks or doc_health in UNHEALTHY_STATES:
    err_names = ", ".join(c.get("name", "unknown") for c in error_checks)
    print(
        f"::error title=beads drift check::br doctor --quick reported hard unhealthy state "
        f"(workspace_health='{doc_health}', error_checks=[{err_names}])"
    )
    sys.exit(1)

if db_newer and jsonl_newer:
    print("::error title=beads drift check::Dual-newer split-brain detected: both SQLite database and JSONL have newer writes. Mutation blocked.")
    sys.exit(1)

if jsonl_newer and not db_newer:
    print("::error title=beads drift check::Unimported tracked drift detected (jsonl_newer=true). Sync/import required.")
    sys.exit(1)

if db_newer and not jsonl_newer:
    print(f"::notice title=beads drift check::Beads store has deferred export (db_newer=true, dirty_count={dirty_count}). Normal under --no-auto-flush.")
    sys.exit(0)

if workspace_health not in ("healthy", "warnings"):
    print(f"::error title=beads drift check::br sync --status reported workspace_health '{workspace_health}' (expected 'healthy' or 'warnings')")
    sys.exit(1)

PY

  SOURCE_FINGERPRINT_FINAL="$(db_family_fingerprint)" || {
    popd >/dev/null
    echo "::error title=beads drift check::Cannot finalize active DB fingerprint"
    exit 1
  }
  if [ "$SOURCE_FINGERPRINT_BEFORE" != "$SOURCE_FINGERPRINT_FINAL" ]; then
    popd >/dev/null
    echo "::error title=beads drift check::Active DB changed during validation"
    exit 1
  fi

  # If store had deferred export (db_newer=true), validation passed without needing semantic JSONL comparison
  IS_DEFERRED="$(python3 -c 'import json, sys; d=json.load(open(sys.argv[1])); print("true" if d.get("db_newer") and not d.get("jsonl_newer") else "false")' "$STATUS_LOG" 2>/dev/null || echo "false")"
  if [ "$IS_DEFERRED" = "true" ]; then
    popd >/dev/null
    echo "OK: Feature branch does not modify .beads/issues.jsonl (operational gate satisfied with deferred export)"
    exit 0
  fi

  FLUSH_LOG="$SCRATCH_DIR/flush.log"
  br sync --flush-only >"$FLUSH_LOG" 2>&1 || {
    echo "::error title=beads drift check::br sync --flush-only failed:"
    cat "$FLUSH_LOG"
    popd >/dev/null
    exit 1
  }
  popd >/dev/null

  CANONICAL_JSONL="$SCRATCH_DIR/.beads/issues.jsonl"
  if [ ! -f "$CANONICAL_JSONL" ]; then
    echo "::error title=beads drift check::expected canonical export missing at $CANONICAL_JSONL"
    exit 1
  fi

  python3 "$SCRIPT_DIR/compare_beads_jsonl_semantic.py" \
    --tracked "$TRACKED_JSONL" \
    --canonical "$CANONICAL_JSONL"
  exit $?
fi

echo "OK: Feature branch does not modify .beads/issues.jsonl (operational gate satisfied)"
exit 0
