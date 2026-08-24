---
name: distributed-caching
description: Distributed system and caching architecture rules before adding any cache, memo, or in-memory store.
---

# Distributed System & Caching Architecture

**Use this skill BEFORE adding any cache, memo, or in-memory store to `$PROJECT_ROOT/**`.** It exists because an agent shipped an in-process embedding cache (PR #7758) without first reasoning about pod locality — it happened to be correct (global/immutable data), but nothing in the harness forced that check.

## The system is distributed — no session affinity

Your Project runs as **multiple load-balanced Cloud Run instances**. A given user's requests are **not** guaranteed to land on the same instance (pod) — Cloud Run has **no session affinity** by default, and consecutive turns from the same user routinely hit different pods.

**Topology source of truth: `scripts/shared_config.sh`** (consumed by `deploy.sh` and `.github/workflows/pr-preview.yml` to prevent drift). Read it for current values — do NOT hardcode them elsewhere. As of this writing:

| Setting | Var | Meaning |
|---|---|---|
| maxScale | `WORLDARCH_MAX_INSTANCES` | up to N parallel instances (sized via Little's law) |
| containerConcurrency | `WORLDARCH_CONCURRENCY` | requests per instance; spreads CPU-bound work across instances |
| gunicorn threads | `WORLDARCH_GUNICORN_THREADS` | threads per instance |
| minScale | `MIN_INSTANCES` (`deploy.sh`) | ≥1 for stable/dev, 0 for preview/ephemeral |

Because maxScale > 1 and minScale can be 0, **process-local memory is per-pod and ephemeral**: it does not survive scale-down, deploy, or a request landing on a cold/other pod.

## The rule: classify cache-data scope BEFORE choosing a backend

Before adding any cache, answer: **is the cached value the same for every user, or specific to a user/session?**

| Data scope | In-process (per-pod dict/LRU) | External store (Firestore) |
|---|---|---|
| **Global + immutable** — pure function of content; identical for all users (e.g. prompt-asset chunk embeddings keyed by `sha256(text)`, parsed static config) | ✅ **Correct.** Each pod warms its own copy of the same data. Worst case = a per-pod cold-start cost, never a correctness bug. | Optional (eliminates per-pod cold start; see precompute follow-up). |
| **Per-user / per-session / mutable** — game state, user settings, campaign data, rate-limit counters, anything keyed by `user_id`/`campaign_id`/`session` | ❌ **Bug.** The next request hits a different pod and misses (or, worse, reads stale per-pod state). Looks like it works in single-instance local/dev, fails in prod. | ✅ **Required.** Firestore is the cross-pod source of truth. |

**Heuristic:** if the cache key contains `user_id`, `campaign_id`, `session`, or any per-request identity → it must not be an in-process cache. If the key is a content hash of immutable bytes → in-process is fine.

## Why "it worked locally / in dev" is not proof

Dev runs `minScale=1` and low traffic, so most requests hit the **same** pod and a per-user in-process cache appears to work. Under prod load (concurrency saturates, autoscaler adds pods) the same code silently degrades: cache hit rate collapses and per-user state diverges per pod. **Never validate a cache only against single-instance local/dev.** Reason about the N-pod case explicitly.

## Worked example — PR #7758 (why the in-process cache was acceptable)

The RAG embedding cache (`$PROJECT_ROOT/prompt_rag.py`) memoizes FastEmbed results keyed by `sha256(chunk_text)`. The cached values are **prompt-asset chunk embeddings** — sliced from versioned, immutable asset bytes, a pure function of the text, **identical for every user** (no `user_id` in the key, query row never cached). So it is **global + immutable** → in-process is correct: each pod independently warms the same embeddings; there is no cross-pod correctness hazard, only a per-pod cold-start cost.

That per-pod cold-start cost is the residual limitation, which is why the **durable** follow-up is **precompute-and-persist** the embeddings to Firestore (bead `rev-gu8h4` / issue #7760): the serve path reads vectors from Firestore (shared across pods) and only embeds the per-turn query. That moves global-immutable data from "recomputed per pod" to "computed once, shared" — an optimization, not a correctness fix.

**Counter-example that would have been a bug:** caching a *user's* most-recent RAG result or a *campaign's* assembled prompt in the same process dict — the next turn on another pod would miss or serve another pod's stale copy. That belongs in Firestore.

## Checklist before adding a cache

1. State the cache key and what scope it represents (global-immutable vs per-user/session/mutable).
2. If per-user/session/mutable → external store (Firestore), not in-process. Stop.
3. If global-immutable → in-process is acceptable; note the per-pod cold-start cost and whether a shared store (Firestore precompute) is the better durable design.
4. Bound in-process caches (LRU + max size) — pods are long-lived; unbounded growth = OOM.
5. Do not validate only on single-instance dev; reason about the N-pod case.
