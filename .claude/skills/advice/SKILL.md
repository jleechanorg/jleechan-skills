---
name: advice
description: "Token-efficient second opinion /advice. Extracts a decision and change pointer, runs the Codex + Opus CLI primary pair concurrently where available, and uses eligible independent CLI reviewers to reach the mandatory two-vote quorum. Reviewer attempts are bounded to 600 seconds. /research is nonvoting; /extended-library:secondo is an eligible approval reviewer. Use instead of advisor() which ships the full conversation uncached."
---

# /advice — Token-Efficient Second Opinion

**Replaces `advisor()`. Never call advisor() — use this instead.**

For PR lifecycle applicability, follow `pr-lifecycle` § Advice applicability;
its size exception does not change this command's reviewer quorum when it runs.
Record each run under that owner's Review records in the PR description contract.

## When invoked

`/advice [optional: specific question]` — invoked manually or automatically at a decision point.

## Step 1: Build the review packet

From the current conversation, extract:
- **Decision** (3–5 sentences): what specifically needs a second opinion — be concrete about constraints and tradeoffs
- **Pointer**: where the reviewer can read the change *itself* — a PR number, a `base...head` ref, or an explicit file-path list. Include `git diff --stat` (or `gh pr diff --name-only`) so the reviewer sees the shape of what it is about to read.

If no specific question was passed, infer from most recent context.

**Send the pointer, not a transcription.** Every reviewer transport in Step 2 is an *agent* that can read the repo for itself — Codex and Opus run in independent exact-SHA clones, `cursor -p` has access to write and shell tools, `agy`/`claude -p` run with permissions pre-approved, and `/secondo` gathers its own `git diff origin/main...HEAD`. Handing them a pre-chewed excerpt does not save them a fetch; it *removes* their ability to look. Give the pointer and let each one pull the context it decides it needs.

### The inline-artifact fallback (≤150 lines) — narrow, and it caps the verdict

Inline an artifact only when the reviewer genuinely cannot fetch: no repo access, no PR, or the subject is not in version control (a plan, a pasted stack trace, an architecture sketch). Then keep it under ~150 lines.

**A verdict built on a truncated inline artifact may not be `APPROVED`.** Record `REVIEWED: <n> of <total> lines (<what was omitted>)`, carry it into the synthesis, and emit `WITHHELD` — see Quorum. This is not a formality: across the last 300 merged PRs in `jleechanorg/worldarchitect.ai`, **65% exceed 150 changed lines** (median 349), and for those, a 150-line cap shows a reviewer a median **22.5%** of the diff. A gate that says `APPROVED at <SHA>` after seeing a fifth of the change is asserting something it did not check.

## Document-only review (including /sq plans)

For saved specifications or plans, add repeated `--document <repo-relative-path.md>`
arguments to the same primary-pair runner. Read the complete documents; do not truncate
them to the inline-artifact limit. Documents may be committed, staged, modified, or
untracked. No commit, stash, clean checkout, or publication is required for this mode.
The runner overlays only explicitly named, non-ignored, non-symlink Markdown documents
into each independent reviewer clone, records their SHA256 hashes and bundle identity,
and checks that source and reviewer copies remain unchanged. HEAD is context only;
unrelated uncommitted code is outside this review and is not approved.

Preserve normal reviewer selection, quorum, coverage, authorization, and failure rules.
Bind the final verdict to `DOCUMENTS sha256:<document_bundle_sha256>` plus the per-file
hashes in the receipt. This is document approval only, never `APPROVED at <HEAD>` for
code or a PR. Save the synthesis with the local review receipt; the PR/commit publication
section below applies only to revision reviews. External publication still requires
applicable user authority. If a selected document changes, re-review its new bytes.

## Step 2: Fan out the reviewers in parallel

**Size/risk gate first.** For low-risk diffs (docs/tests/config-only, or under ~100 changed production lines with no schema/security/prompt-contract surface), the concurrent Codex + Opus primary pair is sufficient when both return independent, full-coverage verdicts; skip B/C. Reserve the full A+B+C fan-out for diffs touching production behavior, schemas, security, or above that threshold. Whenever `/advice` runs, `APPROVED` still requires two independent, full-coverage approval votes. The quorum, coverage, and inline-artifact rules below apply unchanged regardless of which lanes run.

Before dispatch, use existing quota/session receipts and non-model capability
checks to identify viable reviewers and whether they can meet the approval quorum.
Do not spend a separate paid model call solely to probe quota; when availability is
unknown, launch selected review lanes concurrently. Independent CLI reviewers
and Reviewer C may vote. `/research` seats, including Gemini, may inform the
synthesis but never substitute for a quorum vote.

Dispatch independent eligible reviewers concurrently where practical. If a primary seat is unavailable, fails, or times out, dispatch an eligible independent reviewer when needed to reach two votes. Do not serialize healthy reviewer attempts; sequential dispatch is only for a replacement after an earlier attempt failed or timed out. Eligible executions are `claude`, `claudewa`, `codex`, `agy`, and Cursor (`agent` / `cursor agent`). Declare the actual CLI, account or reviewer identity, and model for every execution. A wrapper, alias, retry, or second call does not create another vote when it represents the same execution or reviewer; record each distinct execution separately. Independent CLI reviewers and Reviewer C may vote. `/research` seats, including Gemini, may inform the synthesis but never substitute for a quorum vote. **C depends on personal infrastructure** and is skipped, not faked, when unavailable.

---

**Reviewer A — Primary pair fired IN PARALLEL:**

**Codex + Opus run concurrently when both are available.** Each reviewer reads
the change independently and returns its own verdict. Use the executable runner
below for this supported pair. If either seat is unavailable or fails, continue
with another eligible CLI execution on an independent clone so the final review
can still reach two independent votes. Dispatch healthy reviewers concurrently;
do not wait for one healthy reviewer before starting another.

Use the same review packet for both reviewers:

The raw runner CLI accepts `--reviewers codex,opus`, but that mode uses its
1200-second per-reviewer default and does not enforce this skill's full
600-second attempt deadline. Do not use that CLI mode for an approval attempt.
The bounded recipe below supervises one reviewer execution. To run the Codex +
Opus primary pair, prepare a separate scratch directory, clone, command file,
and receipt for each reviewer, then launch both bounded attempts concurrently.
Do not run one foreground attempt and then repeat it for the other. A missing
primary vote may be paired with a separately bounded eligible CLI reviewer on
its own clone; it never shares or inherits another reviewer's vote.

```
You are a senior engineer giving a focused second opinion.

DECISION:
[decision, 3–5 sentences]

WHAT TO REVIEW:
[PR number / base...head ref / file-path list, plus diff --stat]

Read the change yourself — do not rely on any summary in this prompt.
Read as much of it as your judgment requires. If you could not read
what you needed, say so in COVERAGE rather than guessing.
Apply `/ponytail` (`~/.claude/skills/ponytail/SKILL.md`): reject parallel-module
duplication (re-implementing an existing pipeline in a new module), post-hoc
undo / mutate-then-reverse-diff machinery (mutating shared state before
preconditions or persistence succeed and building an inverse-diff engine instead
of staging before merge), and additive compensator accretion across review
rounds (never demand round-trip preservation of malformed legacy wrappers when
canonicalizing at the ingestion boundary suffices).

Return exactly:
VERDICT: [recommended approach, one line]
REASONING: [3–4 sentences]
RISK: [main risk, one sentence]
COVERAGE: [what you actually read; note anything you could not reach]
CONFIDENCE: [high / medium / low]
```

Write that packet to a temporary file before starting the attempt clock, then
use the bounded invocation below.

Create `$ADVICE_TMP/review-packet.txt` before invoking the runner. The output
directory is deliberately outside the repository and must be a fresh path that
does not already exist. The runner atomically reserves that path and exits 2
before dispatch if it already exists, preserving its contents; create a new
results directory for every invocation. Read `codex.txt`, `opus.txt`,
and `receipt.json`; the receipt records the resolved SHA, each transport, launch
times, each clone SHA, cleanup status, and any changed original-repository
fingerprint components. The
input checkout must be clean, including untracked files, for revision reviews only.
For document-only review, use `--document` as described above; that mode accepts saved
documents regardless of their commit status. The runner refuses a
dirty checkout because those changes are not represented by the requested SHA.

The runner creates two independent disposable clones with `git clone --no-local`,
removes their `origin` remotes, and detaches both at the exact same SHA. It then
starts A1 and A2 behind one concurrency barrier, gives them disjoint output
files, and removes the clones afterward. It preserves the requested
full-permission transports explicitly: `codex exec --yolo` for A1 and
`claude -p --model opus --dangerously-skip-permissions` for A2. Independent
clones prevent reviewer writes to refs, config, or hooks from sharing the
original repository's `.git` state; they are deliberately **not** an OS security
sandbox. If the original checkout, refs, local config, or hooks change, the
runner fails closed and its verdicts may not be used.

While each reviewer root is alive, the runner samples the macOS/Linux process
tree, retains PID plus process-start identity for discovered descendants even
after reparenting, and on timeout terminates those descendants before/with the
root process group. The receipt lists discovered, signaled, and surviving PIDs
plus whether termination was verified. Bounded drain then guarantees that a
remaining inherited pipe cannot block runner return or clone cleanup.

This lifecycle supervision does not change full-permission mode and is not an
OS sandbox: it does not restrict network, environment, or process creation. An
arbitrary daemon that forks, reparents, and disappears from the sampled lineage
before the first observation can evade user-space process-tree tracking. For
descendants observed while the reviewer root is alive, a surviving verified PID
is recorded as a termination failure rather than silently treated as contained;
after successful cleanup the runner exits 7 even if the peer returned a verdict.

Each reviewer gets an independent maximum 600-second attempt. Shared immutable
packet preparation may happen before attempts begin, but all reviewer-specific
setup, including clone creation, remote removal, checkout, SHA/status checks,
argument parsing, imports, input reads and verification, process startup, and
dispatch, is inside that reviewer's deadline. The supervisor starts a monotonic
clock before parsing or importing inputs and bounds the whole worker with its
outer `execute()` call; the worker starts its own monotonic deadline as its first
instruction. Never queue or wait for a reviewer after the attempt clock begins.
Use the runner's existing
`execute()` supervisor API for exactly one reviewer process per attempt. It
tracks the reviewer process tree, signals observed descendants on timeout,
bounds pipe draining, and reports surviving PIDs. Never wrap the Python runner
in an external timeout or kill the supervisor to enforce this deadline: that
can strand detached reviewer children and skip clone cleanup.

The 600 seconds is a total attempt cap, not 600 seconds of model runtime. The
outer `execute()` call supervises the complete adapter worker, including its
clone and checkout setup, imports, input reads, repository snapshots, nested
reviewer `execute()` call, post-run snapshots, and detailed receipt write. The
supervisor starts its monotonic attempt clock before importing or parsing inputs
and computes the outer budget from time remaining on that clock. The worker also
starts its monotonic deadline as its first instruction. Reserve time inside the same 600-second window for a separately
supervised cleanup/finalization helper; a timeout,
surviving process, missing worker receipt, failed cleanup, or deadline overrun
leaves the pre-created receipt WITHHELD. Never start a successor unless the
outer supervisor verified that the worker and reviewer descendants stopped and
the prior clone was removed.
The runner's raw `--timeout-seconds` default remains 1200, but the CLI wrapper
does not expose a single-reviewer invocation with a caller-computed absolute
deadline. Use the ephemeral `/tmp` driver below to call the existing `execute()`
API directly. A timeout, absent/incomplete receipt, surviving owned reviewer
process, or failed clone cleanup means WITHHELD. Before dispatching a successor,
verify the prior reviewer stopped and its clone was cleaned; if either is
unverified, stop and withhold. A successor is a new attempt with its own clock,
started only after that verification.

```bash
set -eo pipefail
ADVICE_TMP="$(mktemp -d)"
# Set PACKET_SOURCE to the complete packet prepared above before starting this block.
: "${PACKET_SOURCE:?Set PACKET_SOURCE to the prepared review packet}"
test -s "$PACKET_SOURCE" || { echo "review packet is missing or empty" >&2; exit 2; }
cp "$PACKET_SOURCE" "$ADVICE_TMP/review-packet.txt" || exit 2
# Set this to the complete list for document-only review; leave empty for a revision review.
DOCUMENTS=()
# Example: DOCUMENTS=("docs/spec.md" "docs/plan.md")
REVIEW_SHA="$(git rev-parse HEAD)"
SOURCE_REPO="$(git rev-parse --show-toplevel)"
ADVICE_RUNNER="${CLAUDE_HOME:-$HOME/.claude}/skills/advice/scripts/run_primary_pair.py"
test -r "$ADVICE_RUNNER" || { echo "installed advice runner is missing or unreadable: $ADVICE_RUNNER" >&2; exit 2; }
cat > "$ADVICE_TMP/run_one_reviewer.py" <<'PY'
import time
started = time.monotonic()
deadline = started + 450.0

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# The outer runner appends its prompt as the worker's final argv element.
if sys.argv[-1:] == [""]:
    sys.argv.pop()
parser = argparse.ArgumentParser()
parser.add_argument("--runner", type=Path, required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--clone", type=Path, required=True)
parser.add_argument("--packet", type=Path, required=True)
parser.add_argument("--command", type=Path, required=True)
parser.add_argument("--receipt", type=Path, required=True)
parser.add_argument("--sha", required=True)
parser.add_argument("--identity", required=True)
parser.add_argument("--model", required=True)
parser.add_argument("--document", action="append", default=[])
args = parser.parse_args()
spec = importlib.util.spec_from_file_location("advice_runner", args.runner)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
clone = args.clone.resolve()
source = args.source.resolve()
clone.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "clone", "--no-local", str(source), str(clone)],
    check=True, timeout=max(1.0, deadline - time.monotonic() - 40.0))
subprocess.run(["git", "-C", str(clone), "remote", "remove", "origin"],
    check=True, timeout=max(1.0, deadline - time.monotonic() - 35.0))
subprocess.run(["git", "-C", str(clone), "checkout", "--detach", args.sha],
    check=True, timeout=max(1.0, deadline - time.monotonic() - 30.0))
if subprocess.check_output(["git", "-C", str(clone), "rev-parse", "HEAD"],
        text=True, timeout=max(1.0, deadline - time.monotonic() - 25.0)).strip() != args.sha:
    raise SystemExit("clone SHA mismatch; WITHHELD")
if subprocess.check_output(["git", "-C", str(clone), "remote"],
        text=True, timeout=max(1.0, deadline - time.monotonic() - 20.0)).strip():
    raise SystemExit("reviewer clone retains a remote; WITHHELD")
if subprocess.check_output(["git", "-C", str(clone), "status", "--porcelain"],
        text=True, timeout=max(1.0, deadline - time.monotonic() - 15.0)).strip():
    raise SystemExit("reviewer clone is dirty before dispatch; WITHHELD")
documents = runner.read_review_documents(source, args.document)
document_hashes = {name: runner.digest_bytes(data) for name, data in documents.items()}
document_bundle_sha256 = runner.digest_bytes(json.dumps(document_hashes, sort_keys=True).encode()) if documents else None
document_root = clone / ".advice-review-documents"
if documents:
    document_root.mkdir(exist_ok=False)
    for index, data in enumerate(documents.values()):
        (document_root / f"{index}.md").write_bytes(data)
source_before = runner.repository_snapshot(source)
clone_before = runner.repository_snapshot(clone)
command = json.loads(args.command.read_text())
if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
    raise SystemExit("command must be a nonempty JSON string array; WITHHELD")
prompt = args.packet.read_text()
if documents:
    mapping = {f"{index}.md": {"source": name, "sha256": document_hashes[name]}
        for index, name in enumerate(documents)}
    prompt = ("DOCUMENT-ONLY REVIEW; repository HEAD is context, not the document identity.\n"
        f"CONTEXT SHA: {args.sha}\nDOCUMENT BUNDLE SHA256: {document_bundle_sha256}\n"
        "Read the complete selected files under .advice-review-documents in this clone.\n"
        "Do not approve code, a PR, or HEAD from this document review.\n"
        + json.dumps(mapping, sort_keys=True) + "\n\n" + prompt)
budget = max(0.0, deadline - time.monotonic() - 30.0)
if budget <= 0:
    raise SystemExit("reviewer budget exhausted; WITHHELD")
dispatch_ns = time.time_ns()
code, stdout, stderr, timed_out, forced_pipe_close, supervision = runner.execute(
    command, clone, prompt, budget, 2.0
)
ended_ns = time.time_ns()
source_documents_unchanged = runner.read_review_documents(source, args.document) == documents
clone_documents_unchanged = all(
    (document_root / f"{index}.md").read_bytes() == data
    for index, data in enumerate(documents.values())
) if documents else True
try:
    source_after = runner.repository_snapshot(source)
    clone_after = runner.repository_snapshot(clone)
    source_unchanged = source_before == source_after
    clone_unchanged = clone_before == clone_after
    source_changed_components = sorted(
        key for key in source_before if source_before[key] != source_after[key]
    )
    clone_changed_components = sorted(
        key for key in clone_before if clone_before[key] != clone_after[key]
    )
except Exception as error:
    source_unchanged = clone_unchanged = False
    source_changed_components = clone_changed_components = [
        f"fingerprint_error:{type(error).__name__}"
    ]
survivors = supervision["descendants_surviving"]
elapsed = time.monotonic() - started
receipt = {
    "sha": args.sha,
    "identity": args.identity,
    "model": args.model,
    "review_kind": "documents" if documents else "revision",
    "document_hashes": document_hashes,
    "document_bundle_sha256": document_bundle_sha256,
    "source_documents_unchanged": source_documents_unchanged,
    "reviewer_documents_unchanged": clone_documents_unchanged,
    "document_integrity_verified": source_documents_unchanged and clone_documents_unchanged,
    "command": command,
    "dispatch_ns": dispatch_ns,
    "ended_ns": ended_ns,
    "elapsed_seconds": elapsed,
    "exit_code": code,
    "timed_out": timed_out,
    "forced_pipe_close": forced_pipe_close,
    "source_repository_unchanged": source_unchanged,
    "source_changed_components": source_changed_components,
    "reviewer_clone_unchanged": clone_unchanged,
    "clone_changed_components": clone_changed_components,
    "supervision": supervision,
    "over_deadline": elapsed > 450.0,
    "stdout": stdout,
    "stderr": stderr,
}
args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
approved_candidate = (
    code == 0 and not timed_out and runner.has_verdict(stdout)
    and not forced_pipe_close and "COVERAGE" in stdout
    and source_unchanged and clone_unchanged and not survivors
    and receipt["document_integrity_verified"]
    and supervision["descendant_termination_verified"]
    and not receipt["over_deadline"]
)
raise SystemExit(0 if approved_candidate else 4)
PY
cat > "$ADVICE_TMP/supervise_attempt.py" <<'PY'
import time
attempt_started = time.monotonic()

import importlib.util
import json
import sys
from pathlib import Path

runner_path, worker, source, clone, packet, command_file, worker_receipt, receipt = map(Path, sys.argv[1:9])
sha, identity, model = sys.argv[9:12]
document_names = sys.argv[12:]
def mark_withheld(reason, outer=None):
    record = {"status": "WITHHELD", "sha": sha, "identity": identity,
        "model": model, "reason": reason,
        "full_attempt_elapsed_seconds": time.monotonic() - attempt_started}
    if outer is not None:
        record["outer_supervision"] = outer
    receipt.write_text(json.dumps(record, indent=2) + "\n")

spec = importlib.util.spec_from_file_location("advice_runner", runner_path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
command = [sys.executable, str(worker), "--runner", str(runner_path),
    "--source", str(source), "--clone", str(clone), "--packet", str(packet),
    "--command", str(command_file), "--receipt", str(worker_receipt),
    "--sha", sha, "--identity", identity, "--model", model]
for name in document_names:
    command.extend(["--document", name])
outer_budget = min(500.0, 600.0 - (time.monotonic() - attempt_started) - 35.0)
if outer_budget <= 0:
    mark_withheld("attempt deadline reserve exhausted")
    raise SystemExit(4)
code, out, err, timed_out, forced, supervision = runner.execute(command, source, "", outer_budget, 5.0)
elapsed = time.monotonic() - attempt_started
outer = {"exit_code": code, "timed_out": timed_out, "forced_pipe_close": forced,
    "elapsed_seconds": elapsed, "supervision": supervision}
if supervision["descendants_surviving"] or not supervision["descendant_termination_verified"]:
    mark_withheld("outer process supervision incomplete", outer)
    print(json.dumps({"status": "WITHHELD", "outer": outer, "stdout": out, "stderr": err}))
    raise SystemExit(4)
# A 20-second cleanup timeout and 1-second grace reserve fit inside the 600s
# attempt cap after the 500s outer timeout and its bounded process-tree teardown.
finalizer = '''
import json, shutil, sys, time
from pathlib import Path
if sys.argv[-1:] == [""]:
    sys.argv.pop()
clone, worker_receipt, receipt = map(Path, sys.argv[1:4])
outer = json.loads(sys.argv[4])
record = json.loads(receipt.read_text())
record["outer_supervision"] = outer
record["full_attempt_elapsed_seconds"] = time.monotonic() - float(sys.argv[5])
try:
    detail = json.loads(worker_receipt.read_text())
except Exception as error:
    detail = {"worker_receipt_error": type(error).__name__}
record["reviewer"] = detail
try:
    if clone.exists():
        shutil.rmtree(clone)
    record["clone_cleanup_success"] = not clone.exists()
except Exception as error:
    record["clone_cleanup_success"] = False
    record["clone_cleanup_error"] = type(error).__name__
    if isinstance(error, FileNotFoundError):
        record["clone_cleanup_success"] = not clone.exists()
candidate = (outer["exit_code"] == 0 and not outer["timed_out"]
    and not outer["forced_pipe_close"] and detail.get("exit_code") == 0
    and not detail.get("timed_out") and not detail.get("forced_pipe_close")
    and detail.get("source_repository_unchanged") is True
    and detail.get("reviewer_clone_unchanged") is True
    and detail.get("document_integrity_verified") is True
    and detail.get("supervision", {}).get("descendant_termination_verified") is True
    and record["clone_cleanup_success"])
record["status"] = "FINALIZED" if candidate else "WITHHELD"
receipt.write_text(json.dumps(record, indent=2) + "\\n")
raise SystemExit(0 if candidate else 4)
'''
remaining = 600.0 - (time.monotonic() - attempt_started)
if remaining <= 31.0:
    mark_withheld("cleanup reserve exhausted", outer)
    print(json.dumps({"status": "WITHHELD", "reason": "cleanup reserve exhausted", "outer": outer}))
    raise SystemExit(4)
final_command = [sys.executable, "-c", finalizer, str(clone), str(worker_receipt),
    str(receipt), json.dumps(outer), repr(attempt_started)]
final_code, final_out, final_err, final_timed_out, final_forced, final_supervision = runner.execute(
    final_command, clone.parent, "", min(20.0, remaining - 10.0), 1.0)
if final_timed_out or final_forced or final_supervision["descendants_surviving"] or final_code not in (0, 4):
    mark_withheld("cleanup/finalization supervision incomplete", outer)
    print(json.dumps({"status": "WITHHELD", "reason": "cleanup/finalization incomplete",
        "finalizer_exit": final_code, "finalizer_output": final_out,
        "finalizer_error": final_err, "finalizer_timed_out": final_timed_out,
        "finalizer_forced_pipe_close": final_forced,
        "finalizer_supervision": final_supervision, "outer": outer}))
    raise SystemExit(4)
record = json.loads(receipt.read_text())
full_elapsed = time.monotonic() - attempt_started
record["full_attempt_elapsed_seconds"] = full_elapsed
record["finalizer_supervision"] = final_supervision
record["over_deadline"] = full_elapsed > 600.0
reviewer = record.get("reviewer", {})
candidate = (final_code == 0 and record.get("status") == "FINALIZED"
    and not record["over_deadline"]
    and final_supervision["descendant_termination_verified"]
    and not final_supervision["descendants_surviving"]
    and reviewer.get("over_deadline") is False
    and reviewer.get("supervision", {}).get("descendants_surviving") == []
    and reviewer.get("supervision", {}).get("descendant_termination_verified") is True
    and reviewer.get("document_integrity_verified") is True
    and record.get("clone_cleanup_success") is True)
record["status"] = "CANDIDATE" if candidate else "WITHHELD"
if not candidate:
    record["withheld_reason"] = "final receipt validation failed"
receipt.write_text(json.dumps(record, indent=2) + "\n")
if not candidate:
    raise SystemExit(4)
print(json.dumps({"outer": outer, "finalizer_exit": final_code, "finalizer_output": final_out}))
raise SystemExit(0)
PY
prepare_attempt() {
  local identity="$1" model="$2" argv_json="$3"
  local attempt_dir="$ADVICE_TMP/$identity-attempt"
  mkdir "$attempt_dir"
  printf '%s\n' "$argv_json" > "$attempt_dir/command.json"
  printf '{"status":"WITHHELD","sha":"%s","identity":"%s","model":"%s"}\n' \
    "$REVIEW_SHA" "$identity" "$model" > "$attempt_dir/receipt.json"
}
prepare_attempt codex gpt-6-sol \
  '["codex","exec","--yolo","-m","gpt-6-sol","--config","model_reasoning_effort=high"]'
prepare_attempt opus claude-opus \
  '["claude","-p","--model","opus","--dangerously-skip-permissions"]'
run_attempt() {
  local identity="$1" model="$2"
  local attempt_dir="$ADVICE_TMP/$identity-attempt"
  if python3 "$ADVICE_TMP/supervise_attempt.py" \
    "$ADVICE_RUNNER" "$ADVICE_TMP/run_one_reviewer.py" "$SOURCE_REPO" \
    "$attempt_dir/reviewer-clone" "$ADVICE_TMP/review-packet.txt" \
    "$attempt_dir/command.json" "$attempt_dir/worker-receipt.json" \
    "$attempt_dir/receipt.json" "$REVIEW_SHA" "$identity" "$model" \
    "${DOCUMENTS[@]}" \
    > "$attempt_dir/console.log" 2>&1; then
    local status=0
  else
    local status=$?
  fi
  printf '%s\n' "$status" > "$attempt_dir/exit-code.txt"
  return "$status"
}
run_attempt codex gpt-6-sol &
CODEX_PID=$!
run_attempt opus claude-opus &
OPUS_PID=$!
if wait "$CODEX_PID"; then CODEX_EXIT=0; else CODEX_EXIT=$?; fi
if wait "$OPUS_PID"; then OPUS_EXIT=0; else OPUS_EXIT=$?; fi
printf 'codex exit=%s receipt=%s\n' "$CODEX_EXIT" "$ADVICE_TMP/codex-attempt/receipt.json"
printf 'opus exit=%s receipt=%s\n' "$OPUS_EXIT" "$ADVICE_TMP/opus-attempt/receipt.json"
python3 -c 'import json, pathlib, sys; [(print(p, json.dumps(json.loads(pathlib.Path(p).read_text()), sort_keys=True))) for p in sys.argv[1:]]' \
  "$ADVICE_TMP/codex-attempt/receipt.json" "$ADVICE_TMP/opus-attempt/receipt.json"
```

The outer call uses `execute()` with a 500-second timeout and 5-second grace;
the helper call reserves at most 30 more seconds for cleanup, receipt
finalization, process inspection, and teardown. This leaves over 40 seconds
under the 600-second attempt cap for supervisor startup and bookkeeping. The
model runtime is smaller still because adapter setup and verification consume
the worker's budget. This `/tmp` driver is a thin adapter around the existing
supervisor, not a new reviewer runner. Put the exact approved CLI argv in
`command.json`, excluding
the final prompt argument (the adapter appends it). For Codex use
`["codex", "exec", "--yolo", "-m", "gpt-6-sol", "--config", "model_reasoning_effort=high"]`;
for Opus use `["claude", "-p", "--model", "opus", "--dangerously-skip-permissions"]`.
For an alternate, use its listed full-permission argv only if that CLI is
supported by the same adapter. The receipt preserves the return tuple,
supervision evidence, exact SHA, identity/model, timestamps, output, and cleanup
result. An over-deadline cleanup is WITHHELD even if the reviewer returned a
verdict. If the driver reports survivors or cleanup failure, stop and verify
the exact attempt-owned processes before any successor; do not remove a clone
while a process may still use it. Preserve each attempt's output and receipt.

This code block describes one reviewer attempt. Run every reviewer in its own
fresh scratch directory and clone, with its own command file and receipt. For
the Codex + Opus pair, stage both attempts and launch both supervisor commands
concurrently; do not wait for one healthy reviewer before launching the other.
For a missing primary vote, an eligible alternate CLI may use this same adapter
with its exact full-permission argv, identity, model, clone, and receipt. The
raw `run_primary_pair.py` CLI does not supervise alternates; never launch an
alternate with an unbounded raw CLI or outer timeout. Reviewer C may vote only
through its native `/extended-library:secondo` route when that route provides
the same independent scope, full-coverage verdict, and bounded attempt receipt;
otherwise mark C unavailable. Do not represent C as a CLI invocation.
Research remains nonvoting.

Ignored regular files may contain credentials, so the fingerprint never opens
or hashes their contents. It records each ignored relative path plus `lstat`
mode, size, and nanosecond modification time; for a symlink it additionally
records the link target without following it. This detects ordinary ignored-file
creation, deletion, replacement, and modification while keeping secret content
unread. It is a mutation tripwire, not a defense against an adversarial process
that deliberately restores identical metadata, and it does not change the
runner's non-sandbox boundary.

Hook coverage follows Git's effective `core.hooksPath`, including configured
absolute or relative hook locations. The fingerprint includes ordinary hook
content and `lstat` metadata; symlinks, including dangling ones, contribute
their link target without being followed. This avoids unsafe traversal while
detecting hook-path and dangling-link mutations.

An exit code of zero is not enough: each successful lane must return a nonempty
line beginning with `VERDICT:`. Empty or malformed output records
`missing_verdict` and counts as an errored lane. A primary vote is usable only
when the process exits zero, returns a nonempty `VERDICT:` line, and the receipt
shows no original-checkout mutation, surviving reviewer process, or cleanup
failure. If either primary lane fails
to return a recognizable verdict, use an eligible alternate reviewer when
needed to reach two independent full-coverage votes. The primary runner only
launches and supervises Codex and Opus; it does not launch, time, or receipt
alternate CLI executions. For each alternate, create a separate disposable
clone detached at the same reviewed SHA, remove its origin remote, run the
selected full-permission CLI in that clone, and remove the clone afterward.
Retain a receipt with the resolved SHA, reviewer identity and model, exact CLI
transport, dispatch/start/end times, timeout or exit status, complete verdict
and coverage, and clone cleanup result. If the clone cannot be cleaned up, do
not use that attempt as approval evidence.

**A1 — Codex CLI (primary):** `codex exec --yolo -m gpt-6-sol --config
model_reasoning_effort=high`. The explicit command guarantees full-permission
mode without relying on wrapper internals. Only the exact catalog IDs
`gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, and `gpt-6.1-sol` are accepted;
5.6 and unknown model IDs are forbidden.

**A2 — Opus CLI (primary):** `claude -p --model opus
--dangerously-skip-permissions`. It is dispatched concurrently with A1, not
after A1 returns.

**Alternate reviewer executions (when a primary vote is missing):**

Run eligible reviewers as needed until there are two independent, full-coverage
votes or every viable option has failed or timed out. An alternate vote may
pair with a successful Codex or Opus vote; alternates are not restricted to the
case where both primary lanes fail. Preserve concurrent Codex + Opus dispatch
when both are viable. Use the following CLI forms, adapting only model and
identity settings needed to declare the actual execution:

**`claude -p` or `claudewa -p`:**
```bash
claude -p --dangerously-skip-permissions "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```
For `claudewa`, invoke the existing wrapper and pass the same packet; record
the actual account/profile and resolved model. Do not count `claude` and
`claudewa` as independent votes when they are merely aliases or duplicate
execution of the same reviewer. Distinct executions count only when each has
its own reviewer identity/model declaration, independent clone, output, and
receipt. Do not use `--cwd /tmp` if it would replace the required clone cwd.

**Cursor (`cursor agent -p` or the `agent` wrapper):**
```bash
cursor agent -p --force "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```

**`agy`:**
```bash
agy --print --model gemini-3.8-flash-high --dangerously-skip-permissions "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```
Note: agy is the Antigravity CLI (reads CLAUDE.md on startup like any CC session, but starts fresh — no current conversation history). Independent perspective, slightly slower than cursor. When selecting Gemini models, never use `gemini-3.1-pro` (or older Gemini Pro models); always use `gemini-3.8-flash` or later (`gemini-3.8-flash-high`).

All attempts must use the same pinned review scope and independent clones. Do
not reuse one execution's result under another CLI name. If fewer than two
independent full-coverage votes succeed after viable options are attempted,
record each unavailable, failed, or timed-out reviewer and emit `WITHHELD` (or
`NOT APPROVED` if any competent reviewer blocks).

The alternate CLI steps identify eligible transports; every attempt, primary
or alternate, must use the bounded adapter and produce its own receipt. The raw
`run_primary_pair.py` CLI only accepts `codex,opus` and does not supervise
alternate attempts. A single surviving primary or alternate vote can block,
but cannot approve.

---

**Reviewer B — Research:**

Invoke `/research [decision topic distilled to 6 words]`

---

**Reviewer C — Secondo (optional — needs infrastructure):**

Invoke `/extended-library:secondo` with the decision and declared review scope, and let it gather
its own context — it already captures `git diff origin/main...HEAD` under its own
budget (`SECOND_OPINION_MAX_DIFF_CHARS`, default 32,000 chars). Require
`COVERAGE: <files/diff scope actually read>` in its response. Do **not** hand it
a ≤150-line extract instead; that throttles it to a fraction of the context it
would have collected on its own.

Requires the AI-Universe MCP endpoint (`AI_UNIVERSE_MCP_ENDPOINT`) and its OAuth flow. `/extended-library:secondo` bans substituting WebSearch or direct provider MCPs, so there is no portable fallback — if the endpoint is unreachable, mark **C unavailable** and continue.

---

## Step 3: Synthesize

Present:

```
| Reviewer    | Verdict              | Key concern         | Confidence |
|-------------|----------------------|---------------------|------------|
| A1 Codex    | ...                  | ...                 | high/med/low |
| A2 Opus     | ...                  | ...                 | high/med/low |
| B Research  | [consensus finding]  | [main caveat]       | —          |
| C Secondo   | ...                  | ...                 | —          |
```

- Give every reviewer a row, including the ones that failed — write `unavailable (<reason>)` in the Verdict column. Never drop a row; a missing row hides a missing opinion.
- 2+ available reviewers may inform a recommendation. Only the full-coverage
  reviewer quorum below may emit `APPROVED`.
- Available reviewers diverge → surface the disagreement, ask user which axis matters most (speed / safety / cost).

## Quorum — what you are allowed to conclude (mandatory)

**The orchestrating agent and research-only output are not approval reviewers.**
They write or inform the table; they do not vote. Approval votes come from
independent CLI reviewer executions or Reviewer C; each must declare
`COVERAGE` after reading the change. Distinct reviewer identities and
executions, not fallback labels, determine independence.

| Independent full-coverage reviewers that returned a verdict | What you may emit |
|---|---|
| 2 or more | `APPROVED` or `NOT APPROVED`, per the synthesis |
| exactly 1 | `NOT APPROVED` allowed; `APPROVED` is **not** — emit `WITHHELD` |
| 0 | `WITHHELD` |

Below quorum a lone reviewer may still block — one competent objection is enough to stop — but may never approve. Never resolve unreachable reviewers into `APPROVED`: an unreachable reviewer is missing evidence, not assent.

**Worked seats (examples, not a second rule set):**

| Reviewers that returned a verdict | Votes | May emit |
|---|---|---|
| Codex PASS + Opus PASS, both declare full `COVERAGE`, neither blocks | 2 (A) | `APPROVED` (or `NOT APPROVED` if either blocks) |
| Codex PASS + Opus unavailable | 1 (A) | `WITHHELD`, or `NOT APPROVED` when the single vote blocks |
| Codex unavailable + Opus unavailable + one alternate APPROVE | 1 | `WITHHELD` |
| One primary PASS **plus** one distinct alternate APPROVE, both full coverage | 2 | `APPROVED` (or `NOT APPROVED` if either blocks) |
| One primary PASS plus a retry, wrapper alias, or duplicate reviewer execution | 1 | `WITHHELD` |
| A vote + C (`/extended-library:secondo`) vote, both full `COVERAGE`, neither blocks | 2 (A + C) | `APPROVED` (or `NOT APPROVED` if either blocks) |

No row relaxes coverage or single-objection blocking: one competent objection still stops the change.

**Coverage gates approval too.** A reviewer whose `COVERAGE` does not cover the
declared diff/scope counts toward *blocking* but not toward *approving* — it is
an opinion, not a review. `APPROVED` requires two independent coverage declarations
whose combined scope covers the whole declared change. Otherwise emit `WITHHELD`.

## Final verdict format — SHA-bound (mandatory)

When `/advice` is being run as the gate in the `pr-lifecycle` lifecycle (`~/.claude/skills/pr-lifecycle/SKILL.md`), the synthesis MUST end with exactly one verdict line, bound to what was reviewed:

```
VERDICT: APPROVED at <SHA>
```
```
VERDICT: NOT APPROVED at <SHA>
```
```
VERDICT: WITHHELD at <SHA> — <quorum or availability reason>
```

`WITHHELD` means the review did not happen, not that it failed. It fails the gate exactly like `NOT APPROVED`, so consumers that look for `APPROVED` need no change — the distinction only tells a later reader whether to re-run reviewers or fix the code.

**Capturing `<SHA>`:**
- Reviewing a PR — `gh pr view <N> --json headRefOid --jq '.headRefOid'`
- Reviewing the working tree — `git rev-parse HEAD`, **but HEAD does not identify uncommitted changes.** If `git status --porcelain` is non-empty, that SHA does not name the tree you reviewed. Commit the intended state before review; the primary-pair runner refuses dirty input and no approval verdict may be emitted for it.

The verdict records the exact state actually reviewed. Apply the reasoned SHA-applicability rule in `pr-lifecycle/SKILL.md`: compare it with the candidate and inspect the complete actual delta, claims, evidence and phase. Preserve the original reviewers and reviewed SHAs. An assessor may document that their existing approvals remain applicable without recalling every reviewer solely to restamp a new SHA. This is an applicability record, not a new independent vote or a claim that a reviewer inspected new bytes. Uncovered material changes, changed evidence within the review scope, unresolved findings or uncertain applicability require affected independent review. Classify runner, script and skill-instruction changes by behavior and contract effect, never by directory or path alone. A genuinely harmless non-behavioral delta may be re-affirmed after documenting why its coverage remains intact; do not force a full `/advice` rerun for the hash change alone.
Preserve the two independent full-coverage approvals required by Quorum;
re-affirmation never turns one reviewer into approval. Do not emit a bare
"APPROVED"/"looks good" without the SHA — an unbound verdict cannot be checked
for staleness.

## Token budget

What `/advice` saves is **the conversation**, not the change. `advisor()` ships the entire uncached transcript; `/advice` sends a decision plus a pointer, and each reviewer pulls only the code it decides it needs. That is the whole economy — and it is preserved without capping the diff.

| Reviewer | What you send |
|---|---|
| A1 Codex | Decision + pointer (reviewer fetches the rest) |
| A2 Opus CLI | Decision + pointer (reviewer fetches the rest) |
| B — /research | Web queries only |
| C — /extended-library:secondo | Decision; it gathers its own diff under its own budget |

Do not cite a percentage saving — none has ever been measured here. And do not shrink the pointer to buy tokens: sending a 349-line diff is nothing like sending an 80K-token transcript, so trading review coverage for that margin is a bad trade in the only direction that matters.

## Fallback chain summary

| Priority | CLI | When |
|---|---|---|
| Primary 1 | `codex exec --yolo -m gpt-6-sol --config model_reasoning_effort=high` | Concurrent primary pair (exact IDs: `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-sol`; 5.6 and unknown IDs forbidden) |
| Primary 2 | `claude -p --model opus --dangerously-skip-permissions` | Concurrent primary pair |
| Alternate | `claude -p` or `claudewa -p` | Dispatch when needed for a second independent vote |
| Alternate | `cursor agent -p --force` (or the configured Cursor print wrapper) | Dispatch when needed for a second independent vote |
| Alternate | `agy --print --model gemini-3.8-flash-high --dangerously-skip-permissions` | Dispatch when needed for a second independent vote |

Notes:
- Codex + Opus remain the concurrent primary pair whenever both are viable. If either is unavailable or fails, record that result and dispatch an eligible alternate reviewer when needed to reach two independent full-coverage votes; a successful primary vote may pair with a successful alternate vote.
- A fallback or retry is not an additional vote when it reuses the same execution or reviewer identity. The same scope SHA, reviewer identity and model, actual CLI transport, independent clone, separate output, and receipt must be recorded for every counted execution.
- Check a CLI is on `PATH` before counting it as a rung. An absent CLI is an unavailable rung, not a failed reviewer — drop to the next rung without recording a failure.
- `agy --print-timeout` defaults to 5m. For a full 150-line artifact, pass a longer value only when it fits within the remaining 600-second end-to-end deadline; otherwise record the timeout and continue with another eligible reviewer.
- A reviewer attempt counts as a successful approval vote only when it exits zero, emits a nonempty `VERDICT:` line, declares full coverage, and its receipt shows no original-checkout mutation, surviving reviewer process, or clone-cleanup failure. Otherwise preserve the failure in its receipt and dispatch a replacement reviewer if needed; a failed or timed-out reviewer does not prevent another healthy reviewer from running concurrently.
