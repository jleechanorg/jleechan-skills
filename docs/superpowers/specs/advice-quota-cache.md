# Advice quota cache

## Outcome

Known provider-account quota windows are remembered in a private, short-lived `/tmp` record so `/advice` skips that seat until its reported reset time.

## Non-goals

The cache does not detect quota errors, infer reset times, store provider output or credentials, reserve reviewers, alter reviewer quorum, or block an otherwise authorized attempt when storage is unavailable.

## Acceptance

- Cache keys distinguish the provider and a SHA-256 digest of the account identity obtained from an existing verified seat binding, not just the model.
- Only an explicitly observed quota result with an explicit reset time is recorded; missing or already-passed reset times create no block.
- Quota and successful-probe events carry their actual observation time; stale delayed writes cannot override a newer event, and success wins an equal-time tie.
- A live, unexpired record returns `QUOTA_BLOCKED`; its reported reset makes the seat eligible and clears the record.
- Checking cached status makes no provider call. A fresh successful probe from the normal advice flow can explicitly clear an earlier record.
- Cache files and lock are owner-only, symlink-safe, atomically written and safe under concurrent calls. Held locks, unsafe paths and filesystem errors fail open immediately. Raw identities, errors and credentials never enter the cache.
- The advice skill checks the record before dispatching a seat and continues the normal fallback path when it is blocked.

## User story

When an advice provider says its account is limited until a stated time, a later `/advice` run skips only that account while the limit remains active and can use another eligible reviewer.

## Proof plan

Unit tests cover account/provider separation, reset expiry, successful-clear behavior, malformed cache recovery, symlink and concurrent directory operations, private permissions and absence of raw provider text. Run the advice contract tests and `git diff --check`.

## Mock exemption

Unit tests use a temporary directory and a fixed clock; the cache helper makes no provider or network calls.

## Risk

`/tmp` may be cleared on reboot, which only causes a provider to be attempted again. A fresh successful probe clears stale state. If the cache is unsafe or unavailable, the helper fails open and reports that fact; it cannot block authorized work.
