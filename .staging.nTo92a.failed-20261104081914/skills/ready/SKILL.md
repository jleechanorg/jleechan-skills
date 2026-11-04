---
name: ready
description: Drive an authorized PR repair to current-head evidence, review, CI and comment readiness without assuming merge permission.
---

# Ready

Resolve the PR, exact head, repository gate policy and existing draft state. Preserve draft status while required evidence/reviews are pending; do not turn a nondraft PR back into a draft. Start independent reviews and cheap focused checks early with [parallelize-to-ceiling](../parallelize-to-ceiling/SKILL.md); final acceptance gates do not require serial execution of independent work.

At the current head verify: [evidence-standards](../evidence-standards/SKILL.md) coverage; [evidence-review](../evidence-review/SKILL.md) PASS; [advice](../advice/SKILL.md) two independent full-coverage approvals; newest required CI checks passing; mergeability without conflicts; actionable comments resolved or explicitly dispositioned. Follow stricter repository-specific gates where applicable.

Check open related regressions from concurrent tasks/trackers sharing a root cause or touched file. Surface their impact before declaring readiness; a different task owner does not make a regression nonblocking.

Fix authorized failures with focused validation. Diagnose real failures; retry infrastructure failures only with a recorded reason. A changed head requires fresh checks or a documented nonmaterial-delta reaffirmation preserving original evidence and quorum. Do not rewrite old capture SHAs.

Report READY only with exact head and all required gates proven; otherwise report missing/failed gates and next action. Evidence can stay in authorized private storage. External comments/publication and merge require current applicable authority; readiness alone does not grant either. Do not default to force-push or destructive conflict resolution.
