---
description: Alias for /document-standards — dispatches to the document-standards skill.
type: quality
execution_mode: immediate
revision_marker: DOCUMENT_STANDARDS_COMMAND_V1
---

# /ds [target]

Shortcut alias for `/document-standards`.

```shell
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
```

Read `$CLAUDE_HOME/skills/document-standards/SKILL.md` and execute the full
five-lane workflow against `<target>`. Pass `smoke-test` as `<target>` for a
load-only diagnostic.
