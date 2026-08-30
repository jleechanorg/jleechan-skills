---
description: "Review or revise prose documents (roadmap docs, reports, status docs, handoffs, Google Docs, HTML) — dispatches to the document-standards skill which runs the five-lane workflow (truth, economy, readability, thermo-style audit, output)."
type: quality
execution_mode: immediate
revision_marker: DOCUMENT_STANDARDS_COMMAND_V1
---

# /document-standards [target]

Thin dispatcher. Loads and follows the canonical skill body:

```shell
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
TARGET="${1:-}"
```

Read `$CLAUDE_HOME/skills/document-standards/SKILL.md` and execute the full
five-lane workflow against `<target>` — a doc path, Google Doc URL, HTML file,
or prose diff — or the doc most recently touched in this session if no target
is given.

The `CLAUDE_HOME` substitution lets the same command work in a user's live
`~/.claude`, in an isolated test install
(`CLAUDE_HOME=/tmp/jleechan-skills.test/claude`), and on `/linux` after
`install-claude-commands.sh --backup`.

## Flags

- `smoke-test` — load-only check; reports command/skill paths and the revision
  marker without running lanes or editing files.

## Examples

```shell
/document-standards
/document-standards ./docs/status-report.md
/document-standards https://docs.google.com/document/d/<id>/edit
/document-standards smoke-test
```
