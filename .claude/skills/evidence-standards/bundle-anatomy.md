# Evidence bundle anatomy

Find the active repository’s evidence policy, bundle producer and configured
artifact location. The paths and filenames below are illustrative, not required
names. Map the actual files to their roles in the claim-to-artifact map. Cite
the producing revision and a specific run or iteration; a mutable “latest”
pointer alone is not proof.

[Evidence standards](./SKILL.md) and the canonical lifecycle own the proof
requirements. This document describes bundle structure, not an additional
evidence gate. The lifecycle’s instruction-only route does not automatically
require a runtime bundle.

## Core documentation

| File | Purpose |
|------|---------|
| **README.md** | Package manifest: test name, run id, how to interpret the bundle. |
| **methodology.md** | How the run was executed (env, commands, pass criteria). |
| **evidence.md** | Human summary + **Claim → Artifact Map** and **What This Evidence Does NOT Prove** section (required by standards). |
| **notes.md** | Follow-ups, warnings, optional narrative. |

## Machine-readable results

| File | Purpose |
|------|---------|
| **metadata.json** | `git_provenance`, `server` (if any), `timestamp` / `bundle_timestamp`, `bundle_version`, `evidence_mode`, optional full `provenance` echo, `summary` counts. |
| **run.json** | Canonical scenario results; record scenario identity, outcomes and applicable fixture or state identity. |
| **scenario_results_checkpoint.json** | Optional: checkpoint for long runs or recovery when the driver writes one. |

## Trace captures (JSONL)

Include the original traces for exercised boundaries when the producer captures them. Use the active producer’s documented options and formats.

| File | Purpose |
|------|---------|
| **request_responses.jsonl** | Optional: MCP tool traffic (`tools/call`, etc.) when MCP capture is provided. |
| **llm_request_responses.jsonl** | Optional: LLM request/response stream (`type`: request/response) when LLM capture exists. |
| **http_request_responses.jsonl** | Optional: HTTP or streaming captures from the application when HTTP capture exists. |
| **provider_http_request_responses.jsonl** | Optional: sanitized transport-level provider traces where captured. |

Duplicate `*_TIMESTAMP.jsonl` files may appear when captures rotate per run.

## Streaming rollup

| File | Purpose |
|------|---------|
| **streaming_evidence.json** | Optional: normalized summary (chunk counts, stream HTTP call counts) for local-server runs that produce it; must stay consistent with raw `http_request_responses.jsonl` when both exist. |

## Raw LLM text

| File | Purpose |
|------|---------|
| **raw_\<model\>_\<scenario\>.txt** | Unparsed LLM output per scenario for forensics. |

## `artifacts/`

| File | Purpose |
|------|---------|
| **server.log** | Server process log copy (sanitized). |
| **lsof_output.txt** / **ps_output.txt** | Port/PID proof. |
| **collection_log.txt** | Inventory of core files, traces, state exports, and other artifacts (reviewer aid). |
| **pre_restart_*.txt** | Optional cross-restart snapshots. |

## State exports

When persistence is claimed, retain the original relevant state readback in the producer’s format.

## Recordings and console

| File | Purpose |
|------|---------|
| **\*.cast** | asciinema session (often converted to hosted GIF/MP4 per canonical video rules). |
| **test_console_output.txt** | Driver stdout/stderr for the iteration. |

## Integrity

Use either a complete aggregate **`checksums.sha256`** manifest OR per-file
**`.sha256`** siblings, not both as a universal requirement. Cover every
substantive artifact, including every artifact referenced by the claim map.
Aggregate entries resolve relative to the bundle root; sibling entries use the
**local basename** and are checked from that sibling's directory.

A canonical producer's different manifest filename is valid when explicitly
mapped to this same aggregate coverage contract under [SKILL.md](./SKILL.md).
Reconcile the actual artifact inventory against coverage and recompute every
digest. Any mismatch, missing listed file, or uncovered substantive/claim-map
artifact is an integrity failure under `/er`; absent checksums leave integrity
unverified and approval withheld. A successful check of listed entries alone
does not establish complete coverage. Checksum manifests do not hash themselves.

Keep the producer's actual inventory and command evidence in its existing
artifacts, with explicit path/field mapping; do not reconstruct stdout or invent
extra sidecars. This changes packaging equivalence only: all required raw proof,
provenance and applicable owner requirements remain binding.

## Mental model

1. **metadata.json + run.json** → *what commit* and *what passed*.  
2. **JSONL captures** → *what happened on the wire*.  
3. **evidence.md** → *what you claim* and *where to look*.  
4. **Logs and state exports** → *environment and persisted state*.
5. **Hosted video URLs in PR** → *human-auditable proof* the bundle was produced honestly (see [SKILL.md](./SKILL.md)).
