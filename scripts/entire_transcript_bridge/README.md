# Entire transcript bridge

This repository uses the pinned Entire Go SDK to normalize Codex and Claude Code native JSONL transcripts. The executable reads one complete native transcript from stdin and writes canonical Entire Transcript Format v1 JSONL to stdout.

## Build

Requirements: Go 1.27.4 or newer, and access to the Go module proxy or a populated module cache. From the repository root:

```sh
go -C scripts/entire_transcript_bridge build -o "${TMPDIR:-/tmp}/entire-transcript-bridge" .
```

The module pins `github.com/entireio/cli` at `v0.13.4`, corresponding to upstream commit `95eabf579d7aa6e5dbe994a6956c8e3fb44d4465`. The SDK is distributed under the MIT License; see the upstream [`LICENSE`](https://github.com/entireio/cli/blob/v0.13.4/LICENSE).

## Caller

The bridge is a standalone executable: pass `--agent codex` or `--agent claude-code` and pipe one native transcript on stdin. It reads only that transcript and emits ETF v1 JSONL on stdout; it does not guess the format or invent missing event IDs.

The SDK may omit or merge native events, so coverage of the native transcript is unverified. Emitted candidate counts describe converted events, not a complete native-event denominator.

## Privacy

Transcript content can include private user and assistant text. The bridge processes bytes locally and does not make network requests or persist input. Successful stdout is the normalized transcript and may still contain source text; callers must handle it as private data. Errors and diagnostics contain no transcript values. Do not send bridge output to public destinations. The ordinary metrics export excludes raw transcript text.

## Version and checks

`entire-transcript-bridge --version` prints JSON containing the tool and pinned SDK versions. Run the focused Go tests from this directory with `go test ./...`.
