---
name: integrate-completion-protocol
description: "Use after every /integrate invocation. Mandates /learn before reporting done; integrate without learn is incomplete execution."
---

# /integrate completion protocol — mandatory post-steps


After every `/integrate` invocation (branch creation), **always run `/learn` before reporting done**. These two steps are inseparable — `/integrate` without `/learn` is an incomplete execution. Do not report success until both steps are done.

@RTK.md
