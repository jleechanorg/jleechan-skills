#!/usr/bin/env bash
# Export the canonical Beads database through an isolated SQLite snapshot.
#
# Portable copy from jleechanorg/worldarchitect.ai's scripts/beads_sync_canonical.sh
# (source of the hardening history: rev-8xvey.6). Any repo adopting the
# single-canonical-authority Beads architecture can reuse this as-is; unlike
# the origin repo, this copy has no baked-in default canonical path — set
# CANONICAL_BEADS_DIR explicitly for your checkout.

set -euo pipefail

PINNED_BR_VERSION="0.4.0"
if [ -z "${CANONICAL_BEADS_DIR:-}" ]; then
    echo "::error::CANONICAL_BEADS_DIR is required (no default in the portable copy; point it at your canonical checkout's .beads dir)." >&2
    exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail() {
    echo "::error::$*" >&2
    exit 1
}

for helper in validate_beads_issues_jsonl.py sort_beads_jsonl.py; do
    [ -f "$SCRIPT_DIR/$helper" ] || fail "Missing bundled export checker: $helper"
done

if [ -z "${BEADS_EXPORT_BUNDLE_DIR:-}" ]; then
    fail "BEADS_EXPORT_BUNDLE_DIR is required."
fi
case "$BEADS_EXPORT_BUNDLE_DIR" in
    /*) ;;
    *) fail "BEADS_EXPORT_BUNDLE_DIR must be an absolute path." ;;
esac

BEADS_EXPORT_JSONL="${BEADS_EXPORT_JSONL:-$BEADS_EXPORT_BUNDLE_DIR/issues.jsonl}"
BEADS_EXPORT_RECEIPT="${BEADS_EXPORT_RECEIPT:-$BEADS_EXPORT_BUNDLE_DIR/receipt.json}"
BEADS_EXPORT_SEAL="${BEADS_EXPORT_SEAL:-$BEADS_EXPORT_BUNDLE_DIR/seal.json}"
BUNDLE_PARENT="$(dirname "$BEADS_EXPORT_BUNDLE_DIR")"
BUNDLE_NAME="$(basename "$BEADS_EXPORT_BUNDLE_DIR")"
if [ "$BUNDLE_NAME" = "." ] || [ "$BUNDLE_NAME" = ".." ] \
    || [ -z "$BUNDLE_NAME" ]; then
    fail "Export bundle name is invalid."
fi
if [ ! -d "$BUNDLE_PARENT" ]; then
    fail "Export bundle parent does not exist: $BUNDLE_PARENT"
fi
if [ -e "$BEADS_EXPORT_BUNDLE_DIR" ] || [ -L "$BEADS_EXPORT_BUNDLE_DIR" ]; then
    fail "Refusing to overwrite preexisting export bundle: $BEADS_EXPORT_BUNDLE_DIR"
fi
for output_path in \
    "$BEADS_EXPORT_JSONL" "$BEADS_EXPORT_RECEIPT" "$BEADS_EXPORT_SEAL"; do
    case "$output_path" in
        /*) ;;
        *) fail "Export output must be an absolute path: $output_path" ;;
    esac
    if [ "$(dirname "$output_path")" != "$BEADS_EXPORT_BUNDLE_DIR" ]; then
        fail "Every export output must be inside $BEADS_EXPORT_BUNDLE_DIR."
    fi
done
if [ "$BEADS_EXPORT_JSONL" = "$BEADS_EXPORT_RECEIPT" ] \
    || [ "$BEADS_EXPORT_JSONL" = "$BEADS_EXPORT_SEAL" ] \
    || [ "$BEADS_EXPORT_RECEIPT" = "$BEADS_EXPORT_SEAL" ]; then
    fail "Export artifact, receipt, and seal paths must differ."
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
    || fail "Exporter must run from a Git checkout."
cd "$REPO_ROOT"

CURRENT_HEAD="$(git rev-parse --verify 'HEAD^{commit}' 2>/dev/null)" \
    || fail "Cannot resolve checkout HEAD."
REMOTE_MAIN_RECORDS="$(git ls-remote --exit-code origin refs/heads/main 2>/dev/null)" \
    || fail "Cannot resolve fresh origin refs/heads/main."
REMOTE_MAIN_HEAD="$(printf '%s\n' "$REMOTE_MAIN_RECORDS" | awk '$2 == "refs/heads/main" {print $1}')"
REMOTE_MAIN_COUNT="$(printf '%s\n' "$REMOTE_MAIN_HEAD" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$REMOTE_MAIN_COUNT" != "1" ] \
    || ! printf '%s\n' "$REMOTE_MAIN_HEAD" | grep -qE '^[0-9a-f]{40}$'; then
    fail "Fresh origin main lookup returned malformed or ambiguous output."
fi
if [ "$CURRENT_HEAD" != "$REMOTE_MAIN_HEAD" ]; then
    fail "Exporter checkout HEAD $CURRENT_HEAD does not equal fresh origin/main $REMOTE_MAIN_HEAD."
fi

TRACKED_JSONL="$REPO_ROOT/.beads/issues.jsonl"
if ! git ls-files --error-unmatch -- .beads/issues.jsonl >/dev/null 2>&1; then
    fail "Exporter checkout does not track .beads/issues.jsonl."
fi
HEAD_JSONL_HASH="$(git rev-parse 'HEAD:.beads/issues.jsonl' 2>/dev/null)" \
    || fail "HEAD does not contain .beads/issues.jsonl."
INDEX_JSONL_HASH="$(git rev-parse ':.beads/issues.jsonl' 2>/dev/null)" \
    || fail "Index does not contain .beads/issues.jsonl."
if [ ! -f "$TRACKED_JSONL" ] || [ -L "$TRACKED_JSONL" ]; then
    fail "Tracked .beads/issues.jsonl must be a physical regular file."
fi
WORKTREE_JSONL_HASH="$(git hash-object -- "$TRACKED_JSONL" 2>/dev/null)" \
    || fail "Cannot hash tracked .beads/issues.jsonl."
if [ "$HEAD_JSONL_HASH" != "$INDEX_JSONL_HASH" ] \
    || [ "$HEAD_JSONL_HASH" != "$WORKTREE_JSONL_HASH" ]; then
    fail "Tracked .beads/issues.jsonl must match HEAD, index, and worktree."
fi
if grep -qE '^(<<<<<<<|=======|>>>>>>>)' "$TRACKED_JSONL"; then
    fail "Tracked .beads/issues.jsonl contains merge conflict markers."
fi

case "$CANONICAL_BEADS_DIR" in
    /*) ;;
    *) fail "CANONICAL_BEADS_DIR must be an absolute path." ;;
esac
if [ -L "$CANONICAL_BEADS_DIR" ] || [ ! -d "$CANONICAL_BEADS_DIR" ]; then
    fail "Canonical Beads directory must be a physical directory: $CANONICAL_BEADS_DIR"
fi
REAL_CANONICAL_BEADS_DIR="$(cd -P "$CANONICAL_BEADS_DIR" && pwd)"
if [ "$REAL_CANONICAL_BEADS_DIR" != "${CANONICAL_BEADS_DIR%/}" ]; then
    fail "Canonical Beads directory does not match its physical path."
fi
if [ -e "$CANONICAL_BEADS_DIR/redirect" ] \
    || [ -L "$CANONICAL_BEADS_DIR/redirect" ]; then
    fail "Canonical Beads directory must not contain a redirect."
fi

CANONICAL_DB="$CANONICAL_BEADS_DIR/beads.db"
CANONICAL_JSONL="$CANONICAL_BEADS_DIR/issues.jsonl"
for source_path in "$CANONICAL_DB" "$CANONICAL_JSONL"; do
    if [ ! -f "$source_path" ] || [ -L "$source_path" ]; then
        fail "Canonical source must be a physical regular file: $source_path"
    fi
done
for sidecar in "$CANONICAL_DB-wal" "$CANONICAL_DB-shm"; do
    if [ -L "$sidecar" ]; then
        fail "Canonical SQLite sidecar must not be a symlink: $sidecar"
    fi
done

exec {CANONICAL_LOCK_FD}<"$CANONICAL_JSONL" \
    || fail "Cannot open canonical source for export locking."
python3 - "$CANONICAL_LOCK_FD" "$CANONICAL_JSONL" <<'PY'
import errno
import fcntl
import os
import pathlib
import stat
import sys

lock_fd = int(sys.argv[1])
canonical_lock_path = pathlib.Path(sys.argv[2])
descriptor_stat = os.fstat(lock_fd)
path_stat = canonical_lock_path.lstat()
if not stat.S_ISREG(descriptor_stat.st_mode):
    raise SystemExit("canonical source export lock is not regular")
if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (
    path_stat.st_dev,
    path_stat.st_ino,
):
    raise SystemExit("canonical source export lock identity changed")
try:
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError as exc:
    if exc.errno in {errno.EACCES, errno.EAGAIN}:
        raise SystemExit("another canonical Beads export is already running")
    raise
PY

if ! command -v br >/dev/null 2>&1; then
    fail "br CLI not found in PATH."
fi
BR_VERSION_OUTPUT="$(br --version 2>&1)" || fail "Cannot execute br --version."
if [ "$BR_VERSION_OUTPUT" != "br $PINNED_BR_VERSION" ]; then
    fail "Exporter requires exactly br $PINNED_BR_VERSION; got '$BR_VERSION_OUTPUT'."
fi

source_fingerprint() {
    python3 - "$CANONICAL_DB" "$CANONICAL_DB-wal" \
        "$CANONICAL_DB-shm" "$CANONICAL_JSONL" <<'PY'
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
        raise SystemExit(f"canonical source is not a physical file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    records.append(
        {
            "path": str(path),
            "exists": True,
            "size": path.stat().st_size,
            "sha256": digest.hexdigest(),
        }
    )
print(json.dumps(records, sort_keys=True, separators=(",", ":")))
PY
}

SOURCE_FINGERPRINT_BEFORE="$(source_fingerprint)" \
    || fail "Cannot fingerprint canonical Beads sources."

SCRATCH_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/beads-export.XXXXXX")"
cleanup() {
    rm -rf "$SCRATCH_ROOT"
}
trap cleanup EXIT
mkdir -p "$SCRATCH_ROOT/.beads"
SCRATCH_DB="$SCRATCH_ROOT/.beads/beads.db"
SCRATCH_JSONL="$SCRATCH_ROOT/.beads/issues.jsonl"

python3 - "$CANONICAL_DB" "$SCRATCH_DB" <<'PY'
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
        raise SystemExit(f"canonical WAL is not a physical file: {source_wal}")
    copy_physical(source_wal, pathlib.Path(f"{destination_path}-wal"))
PY

SOURCE_FINGERPRINT_AFTER_COPY="$(source_fingerprint)" \
    || fail "Cannot re-fingerprint canonical Beads sources after copy."
if [ "$SOURCE_FINGERPRINT_BEFORE" != "$SOURCE_FINGERPRINT_AFTER_COPY" ]; then
    fail "Canonical Beads sources changed during the isolated raw snapshot."
fi

BR_COMMON=(
    --db "$SCRATCH_DB"
    --no-auto-flush
    --no-auto-import
    --no-daemon
)
pushd "$SCRATCH_ROOT" >/dev/null
# The scratch starts without JSONL, so flush-only creates a projection directly
# from the copied database without importing tracked Git state or bypassing guards.
br "${BR_COMMON[@]}" sync --flush-only
STATUS_JSON="$(br "${BR_COMMON[@]}" sync --status --json)"
set +e
DOCTOR_JSON="$(br "${BR_COMMON[@]}" doctor --quick --json)"
DOCTOR_EXIT_CODE=$?
set -e
popd >/dev/null

if [ "$DOCTOR_EXIT_CODE" -gt 1 ]; then
    fail "br doctor failed with exit code $DOCTOR_EXIT_CODE."
fi

python3 - "$STATUS_JSON" "$DOCTOR_JSON" <<'PY'
import json
import sys

try:
    status = json.loads(sys.argv[1])
    doctor = json.loads(sys.argv[2])
except (json.JSONDecodeError, TypeError, ValueError) as exc:
    raise SystemExit(f"invalid Beads health JSON: {exc}") from exc
if not isinstance(status, dict) or not isinstance(doctor, dict):
    raise SystemExit("Beads health outputs must be JSON objects")
if status.get("dirty_count") != 0:
    raise SystemExit("scratch Beads database remains dirty")
if status.get("db_newer") is not False or status.get("jsonl_newer") is not False:
    raise SystemExit("scratch Beads database and JSONL did not converge")
if status.get("workspace_health") not in {"healthy", "warnings"}:
    raise SystemExit("scratch Beads workspace is not healthy")
checks = doctor.get("checks")
if not isinstance(checks, list) or not checks or any(
    not isinstance(check, dict) for check in checks
):
    raise SystemExit("br doctor returned malformed checks")
allowed = {"ok", "warn"}
if any(check.get("status") not in allowed for check in checks):
    raise SystemExit("br doctor reported an error or unknown check status")
if doctor.get("workspace_health") not in {"ok", "healthy", "clean", "warnings"}:
    raise SystemExit("br doctor reported an unhealthy scratch workspace")
PY

python3 "$SCRIPT_DIR/validate_beads_issues_jsonl.py" "$SCRATCH_JSONL"
python3 "$SCRIPT_DIR/sort_beads_jsonl.py" --check "$SCRATCH_JSONL"

SOURCE_FINGERPRINT_FINAL="$(source_fingerprint)" \
    || fail "Cannot re-fingerprint canonical Beads sources before publication."
if [ "$SOURCE_FINGERPRINT_BEFORE" != "$SOURCE_FINGERPRINT_FINAL" ]; then
    fail "Canonical Beads sources changed while the isolated export ran."
fi
python3 - "$CANONICAL_LOCK_FD" "$CANONICAL_JSONL" <<'PY'
import os
import pathlib
import sys

descriptor_stat = os.fstat(int(sys.argv[1]))
path_stat = pathlib.Path(sys.argv[2]).lstat()
if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (
    path_stat.st_dev,
    path_stat.st_ino,
):
    raise SystemExit("canonical source export lock identity changed")
PY

RECEIPT_SOURCE="$SCRATCH_ROOT/export-receipt.json"
python3 - "$SCRATCH_JSONL" "$RECEIPT_SOURCE" "$BEADS_EXPORT_JSONL" \
    "$BEADS_EXPORT_RECEIPT" "$CURRENT_HEAD" "$BR_VERSION_OUTPUT" \
    "$HEAD_JSONL_HASH" "$SOURCE_FINGERPRINT_FINAL" "$STATUS_JSON" \
    "$DOCTOR_JSON" "$REMOTE_MAIN_HEAD" <<'PY'
import datetime
import hashlib
import json
import pathlib
import sys

(
    artifact_source_raw,
    receipt_source_raw,
    artifact_target,
    receipt_target,
    head,
    br_version,
    tracked_blob,
    source_fingerprint_raw,
    status_raw,
    doctor_raw,
    remote_main,
) = sys.argv[1:]
artifact_source = pathlib.Path(artifact_source_raw)
payload = artifact_source.read_bytes()
receipt = {
    "schema_version": 1,
    "status": "success",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "checkout": {
        "head": head,
        "remote_main": remote_main,
        "tracked_jsonl_blob": tracked_blob,
    },
    "canonical_source": json.loads(source_fingerprint_raw),
    "artifact": {
        "path": artifact_target,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    },
    "receipt_path": receipt_target,
    "br_version": br_version,
    "scratch_health": {
        "status": json.loads(status_raw),
        "doctor": json.loads(doctor_raw),
    },
}
pathlib.Path(receipt_source_raw).write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

python3 - "$SCRATCH_JSONL" "$RECEIPT_SOURCE" \
    "$BEADS_EXPORT_BUNDLE_DIR" "$(basename "$BEADS_EXPORT_JSONL")" \
    "$(basename "$BEADS_EXPORT_RECEIPT")" "$(basename "$BEADS_EXPORT_SEAL")" <<'PY'
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

artifact_source = pathlib.Path(sys.argv[1])
receipt_source = pathlib.Path(sys.argv[2])
bundle = pathlib.Path(sys.argv[3])
artifact_name, receipt_name, seal_name = sys.argv[4:]
stage = pathlib.Path(
    tempfile.mkdtemp(dir=bundle.parent, prefix=f".{bundle.name}.tmp.")
)


def copy_and_sync(source: pathlib.Path, target: pathlib.Path) -> bytes:
    payload = source.read_bytes()
    with target.open("xb") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(destination.fileno())
    os.chmod(target, 0o644)
    return payload


try:
    artifact_payload = copy_and_sync(artifact_source, stage / artifact_name)
    receipt_payload = copy_and_sync(receipt_source, stage / receipt_name)
    seal = {
        "schema_version": 1,
        "status": "sealed",
        "artifact": artifact_name,
        "artifact_sha256": hashlib.sha256(artifact_payload).hexdigest(),
        "receipt": receipt_name,
        "receipt_sha256": hashlib.sha256(receipt_payload).hexdigest(),
    }
    seal_path = stage / seal_name
    with seal_path.open("x", encoding="utf-8") as destination:
        json.dump(seal, destination, indent=2, sort_keys=True)
        destination.write("\n")
        destination.flush()
        os.fsync(destination.fileno())
    os.chmod(seal_path, 0o644)

    stage_fd = os.open(stage, os.O_RDONLY)
    try:
        os.fsync(stage_fd)
    finally:
        os.close(stage_fd)
    if os.path.lexists(bundle):
        raise FileExistsError(f"refusing to overwrite {bundle}")
    os.rename(stage, bundle)
    parent_fd = os.open(bundle.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
except BaseException:
    if stage.exists():
        shutil.rmtree(stage)
    raise
PY

echo "Canonical Beads snapshot bundle sealed at $BEADS_EXPORT_BUNDLE_DIR"
echo "Artifact written to $BEADS_EXPORT_JSONL"
echo "Receipt written to $BEADS_EXPORT_RECEIPT"
echo "Seal written to $BEADS_EXPORT_SEAL"
