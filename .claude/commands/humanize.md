---
description: Humanize text — strip AI-writing tells and add real voice. Loads the humanizer skill and applies it to the provided text, file, or your own draft.
---

Load `${CLAUDE_HOME:-$HOME/.claude}/skills/humanizer/SKILL.md` (or `../skills/humanizer/SKILL.md` relative to this commands dir) and apply it to: $ARGUMENTS

If no text was supplied, ask which file or paste to humanize. If a file path was supplied, read it first, then rewrite the affected sections and show the diff.