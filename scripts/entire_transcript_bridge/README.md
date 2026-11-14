# Entire transcript bridge

This repository uses the pinned Entire Go SDK to normalize Codex and Claude Code native JSONL transcripts for the human-nudge metrics workflow. The executable reads one complete native transcript from stdin and writes canonical Entire Transcript Format v1 JSONL to stdout.

## Build

Requirements: Go 1.27.4 or newer, and access to the Go module proxy or a populated module cache. From the repository root:

```sh
go -C scripts/entire_transcript_bridge build -o "${TMPDIR:-/tmp}/entire-transcript-bridge" .
```

The module pins `github.com/entireio/cli` at `v0.13.4`, corresponding to upstream commit `95eabf579d7aa6e5dbe994a6956c8e3fb44d4465`. The SDK is distributed under the MIT License; see the upstream [`LICENSE`](https://github.com/entireio/cli/blob/v0.13.4/LICENSE).

## Caller

The actual caller is [`scripts/native_usage_collector.py`](../native_usage_collector.py). Run it from the repository root and supply the history root, cutoff, and output path:

```sh
HISTORY_ROOT=/path/to/native-history
CUTOFF=2026-10-01T00:00:00Z
OUTPUT=/path/to/normalized-history.jsonl
BRIDGE="${TMPDIR:-/tmp}/entire-transcript-bridge"

python3 scripts/native_usage_collector.py \
  --history-root "$HISTORY_ROOT" \
  --cutoff "$CUTOFF" \
  --output "$OUTPUT" \
  --entire-parser "$BRIDGE" \
  --entire-agent codex
```

For Claude Code, set `--entire-agent claude-code`. The collector invokes the executable with `--agent`, sends the full native transcript on stdin, and reads only ETF v1 JSONL from stdout. The bridge supports `codex` and `claude-code`; it does not guess the format or invent missing event IDs.

To request a private adjudication packet, add `--nudge-packets "$NUDGE_PACKETS"` to the collector command, then use the linked [`scripts/human_nudge_adjudication.py`](../human_nudge_adjudication.py) with a caller-selected model command:

```sh
NUDGE_PACKETS=/private/path/human-nudge-packet.json
ANNOTATIONS=/private/path/human-nudge-annotations.jsonl
JUDGE_COMMAND='your-caller-selected-model-command'

python3 scripts/human_nudge_adjudication.py \
  --input "$NUDGE_PACKETS" \
  --judge-command "$JUDGE_COMMAND" \
  --output "$ANNOTATIONS"
```

The adjudication CLI owns the prompt, annotation schema, and invocation details; this bridge only normalizes native transcript input.

The SDK may omit or merge native events. The collector reports `entire_source_coverage=UNVERIFIED` and overall `PARTIAL` coverage when this adapter is selected, even after successful conversion. Emitted candidate counts describe converted events, not a complete native-event denominator.

## Privacy

Transcript content can include private user and assistant text. The bridge processes bytes locally and does not make network requests or persist input. Successful stdout is the normalized transcript and may still contain source text; callers must handle it as private data. Errors and diagnostics contain no transcript values. Do not send bridge output to public destinations. Private adjudication packets are created only by the explicitly requested collector workflow and must remain private. The ordinary metrics export excludes raw transcript text.

## Version and checks

`entire-transcript-bridge --version` prints JSON containing the tool and pinned SDK versions. Run the focused Go tests from this directory with `go test ./...`.
