---
name: grok
description: Alias for the canonical grokbot browser conversation workflow; /grok talks to the Grok bot the same way /dot talks to Dot.
---

Read and follow [grokbot](../grokbot/SKILL.md) completely and apply it to the request.

`/grok` is the short name for the same transport as `/grokbot`; it adds no sender,
account, schedule, storage or permissions. Retain the exact target and receipts.

Treat this alias as unlinked for now: do not add `/grok` as the default route from
other skills. `/dot` is the Dot transport and `/grok` is the Grok transport; they are
independent and neither delegates to the other.
