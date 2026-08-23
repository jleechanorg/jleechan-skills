---
description: /spicy_remove — remove egregious safety-violating content from a campaign in Firestore while keeping general sex scenes intact
type: orchestration
execution_mode: immediate
---

# /spicy_remove

Read **`.claude/skills/spicy_remove.md`** and execute it according to `$ARGUMENTS`.

This command automates the sanitization of safety-triggering elements (egregious non-consensual themes, explicit slang) in a campaign's Firestore `current_state` and `story` documents to bypass model safety blocks.
