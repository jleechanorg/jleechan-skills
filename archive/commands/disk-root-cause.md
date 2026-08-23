---
name: di[REDACTED_OPENAI_KEY]
description: Run the di[REDACTED_OPENAI_KEY] forensic skill to explain disk growth — min/floor deltas, attributable buckets, safe cleanup recommendations (no destructive commands without explicit OK).
metadata:
  type: command
  runtime: claude
---

# /di[REDACTED_OPENAI_KEY]

Thin slash command that delegates to the `di[REDACTED_OPENAI_KEY]` skill. Same effects as invoking the skill directly; this command exists so users get a single namespace entry point.

## Behavior

When the user types `/di[REDACTED_OPENAI_KEY] <optional question>`, this command:

1. Loads the skill at `skills/di[REDACTED_OPENAI_KEY]/SKILL.md`.
2. Falls back to the canonical skill invocation if the local copy is missing.
3. Returns whatever the skill returns.

## Examples

```text
/di[REDACTED_OPENAI_KEY]
/di[REDACTED_OPENAI_KEY] why is my disk filling up
/di[REDACTED_OPENAI_KEY] what grew in the last week
/di[REDACTED_OPENAI_KEY] find the min disk used last month and show delta vs now
/di[REDACTED_OPENAI_KEY] how much can I safely reclaim
```

## Notes

- This command is intentionally read-only. Safe cleanup commands appear in the skill's readout as recommendations, not auto-ran.
- Whenever the skill needs real-time evidence, the skill points the operator at `./disk_magician.sh snapshot` (which is itself safe and idempotent).
- See `skills/di[REDACTED_OPENAI_KEY]/SKILL.md` for the full procedure.
