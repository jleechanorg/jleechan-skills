---
name: preflight-capability-smoke
description: "Use when a task is large or its host capabilities are uncertain, on any Mac or Linux host. Reuses recent exact receipts where they still apply and probes only the missing capabilities, classifying each result as verified, limited, uncertain, untested, denied, unavailable or capacity, and never creating dummy remote writes, provider charges or credential changes to test permission."
---

# /preflight-capability-smoke — capability probe before a large or uncertain task

Use this when a task is **large or its host capabilities are uncertain** — multi-hour, multi-lane, multi-agent, first run on a host or runtime, or a first run in a **new repository or account**. It is a **capability probe, not a test suite**, and it must not create side effects.

**Reuse first, with invalidation.** If a needed capability already has a recent, exact receipt for the **same host, same repository, same account, and same head**, cite that receipt and probe nothing. A changed repository, account, credential identity, or head **invalidates the old receipt** even on the same host — re-probe the changed capability only.

## Procedure

**Step 0 — shallow dependency, authority, cost and hold scan comes first.** Before any expensive probe, read the cheap external signals: the named dependency owner, the authority/approval a write would need, whether the task carries cost or quota, and whether a runtime hold, stop order or device lock is in force. A held lane does not block unrelated work: continue the unblocked lanes and report the hold on the affected one. Only then run the probes below.

Every command below is scoped to the same explicitly quoted repo path, and every exit code is preserved. Never pipe a git command into another command in a way that hides its failure.

1. **Read** — prove the repo you will edit:
   ```bash
   REPO='/absolute/repo/path'
   git -C "$REPO" remote get-url origin; echo "exit=$?"
   git -C "$REPO" rev-parse --abbrev-ref HEAD; echo "exit=$?"
   git -C "$REPO" rev-parse HEAD; echo "exit=$?"
   git -C "$REPO" status --porcelain > /tmp/preflight-status.$$; echo "exit=$?"
   wc -l < /tmp/preflight-status.$$
   ```
   Capture each `exit=` value: a non-zero git exit is a failure, not an empty result. Compare the head against the head you were told to work at. A stale checkout or a wrong working directory is a finding, not a working copy.

2. **Write and execute** — prefer an existing scratch worktree; create one only if you will actually need it. Run **one real, already-existing focused test** in that repo and record the command, exit code, and outcome. A **read-only task needs no artificial commit, upload, or published artifact**: if the task will not write, do not manufacture a write to "prove" one.

3. **Publish path** — if the task will push, prove it with a real branch push. A **dry-run is a `limited` result, never `verified`**: it can pass locally while a remote receive hook, branch protection, or credential scope rejects the actual write. Record the denial text when that happens.

4. **Evidence path** — identify where artifacts will land and say whether that path is verified or only expected. One small real artifact is enough, and only when the task truly needs it.

   **If the response is lost or times out, the outcome is `uncertain`, not failed.** Write/upload requests can succeed server-side after the response is lost. **Read back first** (list the destination, fetch the object, check the PR comment). Retry **only** when the readback shows nothing landed **and** the failure is transient transport, within whatever call, spend or retry authority the task already has — this sets no count and adds no new cap. **Never** retry an access denial, a policy refusal, or an explicit stop; report those instead.

5. **Auth state** — state whether an authenticated session exists. An unauthenticated `401` has an **unknown cause** until verified: missing token, invalid or expired token, or a token for the wrong audience. An **expired token alongside a valid browser session** is a real combination, so a `401` never proves "no session exists" and a valid session never proves a token works.

6. **Gates** — name the next one or two dependency gates: approvals, credentials, device locks, or temporary slot limits. Identify gates **before** publishing anything. A held lane does not block unrelated work: continue the unblocked lanes and report the hold on the affected one.

## Result classification

| Class | Meaning |
|---|---|
| `verified` | The command executed, exited as expected, and its postcondition was confirmed; record command, exit and the observed postcondition |
| `limited` | Partial evidence: a dry-run, a probe against a stub, or a postcondition that was not confirmed |
| `uncertain` | A write or upload whose response was lost or timed out — **read back before retrying** |
| `untested` | Not exercised; say so instead of implying success |
| `denied` | Authorization refusal — quote the exact denial text |
| `unavailable` | Tool, binary, or credential is missing |
| `capacity` | Temporary limit (slots, quota, busy pane), not a permission denial |

Keep three failure kinds distinct:

- **Ordinary test failure** — the code ran and an assertion failed. This is a product or test defect.
- **Permission or authorization failure** — denied by policy, hook, branch protection, or credential scope. Quote the denial.
- **Tool or capacity failure** — missing binary, missing credential, quota, or busy resource. This is not a denial and not a product defect.

A failed executed command is never `verified`.

## Boundaries

- Never create dummy remote writes, provider charges, or credential/security changes merely to test permission.
- Never infer a capability from a config file, a sync-only receipt, or another host's result.
- A probe that produces a lasting artifact — a commit, a published file, a comment — is allowed only when the task needs that artifact anyway.
- An explicit stop, runtime hold, or safety floor **outranks** this probe: skip the affected step and report the hold instead of working around it.

## Output

One row per capability with command, exit and postcondition behind every `verified` row, the classified state for the rest, and the failure kind where something failed.
