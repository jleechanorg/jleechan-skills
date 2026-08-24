---
description: Alias for /accept-adapt-reject. Triage feedback into Accept / Adapt / Reject buckets.
type: ai
execution_mode: immediate
---

# /aar

Shortcut alias for `/accept-adapt-reject`. See `~/.claude/commands/accept-adapt-reject.md` for the full command spec and behavior.

## Usage

```
/aar <feedback text or reference to a thread/PR/comments>
```

## Examples

```
/aar "Rename getData to fetchData. Also, add caching."
/aar PR #5678 review comments
/aar "Stop using const for everything"
```

The full AAR algorithm and output template live in the `accept-adapt-reject` skill:

```
~/.hermes/skills/accept-adapt-reject/SKILL.md
```

This command loads that skill and runs the triage.