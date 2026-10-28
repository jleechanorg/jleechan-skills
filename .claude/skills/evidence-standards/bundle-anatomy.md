# Evidence bundle anatomy (MCP / `create_evidence_bundle`)

_Last updated: 2026-04-26_

**Repo mirror (WorldArchitect):** [docs/evidence-standards/bundle-anatomy.md](https://github.com/$GITHUB_REPOSITORY/blob/main/docs/evidence-standards/bundle-anatomy.md) on `main` (or the branch that introduced it) — keep in sync when editing either copy.

This describes artifacts produced under a typical path on the dedicated Scratch volume resolved dynamically via `~/.claude/skills/scratch-space/SKILL.md` (`diskm scratch-new <repo-path> <purpose> --kind evidence` or `$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh "<repo>/evidence/<date>-<slug>")`):

`<scratch-root>/your-project.com/<branch-alias>/<test_name>/iteration_NNN/`
(resolved dynamically via `diskm scratch-new` or `~/.claude/skills/scratch-space/scripts/scratch-dir.sh`)

and the [`latest`](https://github.com/$GITHUB_REPOSITORY/blob/main/testing_mcp/lib/evidence_utils.py#L1878) symlink (points at the newest `iteration_*`; see [`create_evidence_bundle()`](https://github.com/$GITHUB_REPOSITORY/blob/main/testing_mcp/lib/evidence_utils.py#L1833)). **Normative process rules** (video, hosted URLs, mock vs real) live in [SKILL.md](./SKILL.md) in this directory; this doc is **structural**.

## Core documentation

| File | Purpose |
|------|---------|
| **README.md** | Package manifest: test name, run id, how to interpret the bundle. |
| **methodology.md** | How the run was executed (env, commands, pass criteria). |
| **evidence.md** | Human summary + **Claim → Artifact Map** (required by standards). |
| **notes.md** | Follow-ups, warnings, optional narrative. |

## Machine-readable results

| File | Purpose |
|------|---------|
| **metadata.json** | `git_provenance`, `server` (if any), `timestamp` / `bundle_timestamp`, `bundle_version`, `evidence_mode`, optional full `provenance` echo, `summary` counts. |
| **run.json** | Canonical scenario results; must include `scenarios[]` with `name`, `errors`, and `campaign_id` when campaigns exist. |
| **scenario_results_checkpoint.json** | Optional: harness checkpoint (e.g. `MCPTestBase`) for long runs / recovery when the test driver writes it. |

## Trace captures (JSONL)

Emitted only when the corresponding capture exists or the harness copies that JSONL into the bundle (see optional paths/flags in [`create_evidence_bundle()`](https://github.com/$GITHUB_REPOSITORY/blob/main/testing_mcp/lib/evidence_utils.py#L1833)).

| File | Purpose |
|------|---------|
| **request_responses.jsonl** | Optional: MCP tool traffic (`tools/call`, etc.) when MCP capture is provided. |
| **llm_request_responses.jsonl** | Optional: LLM request/response stream (`type`: request/response) when LLM capture exists. |
| **http_request_responses.jsonl** | Optional: HTTP + SSE captures from the local app (e.g. `/interaction/stream`) when HTTP capture exists. |
| **gemini_http_request_responses.jsonl** | Optional: transport-level Gemini HTTP traces when Gemini capture exists. |

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
| **collection_log.txt** | Inventory of core files, top-level jsonl, `campaigns/`, other artifacts (reviewer aid). |
| **pre_restart_*.txt** | Optional cross-restart snapshots. |

## `campaigns/`

Exported campaign story + game state JSON (when local export runs). Supports persistence claims.

## Recordings and console

| File | Purpose |
|------|---------|
| **\*.cast** | asciinema session (often converted to hosted GIF/MP4 per canonical video rules). |
| **test_console_output.txt** | Driver stdout/stderr for the iteration. |

## Integrity

Every substantive file should have a sibling **`.sha256`** whose line uses the **local basename** (`sha256sum -c` from the iteration directory).

## Mental model

1. **metadata.json + run.json** → *what commit* and *what passed*.  
2. **JSONL captures** → *what happened on the wire*.  
3. **evidence.md** → *what you claim* and *where to look*.  
4. **artifacts/ + campaigns/** → *environment and persisted state*.  
5. **Hosted video URLs in PR** → *human-auditable proof* the bundle was produced honestly (see [SKILL.md](./SKILL.md)).
