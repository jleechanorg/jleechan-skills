## Actions

- `restore-session` — restore this profile's last own-session snapshot (Chrome must be stopped; verify with read/probe afterward). This is opportunistic recovery; token rotation can invalidate the snapshot.

- Read: `dot.sh [--account <name>] [--url <url>] read [chars]` prints the tail of the page text (default 5000). While the dot is working the tail ends with `dot` / `Thinking` / `Working`.
- Probe: `dot.sh [--account <name>] probe <expected-email-sha256>` checks the existing profile against the frozen account identity and returns a typed `DOT_SESSION_PROBE` result. Hash the exact UTF-8 email bytes with lowercase SHA-256 hex; do not normalize the address. The result includes identity/endpoint/probe status, composer availability, opaque profile slot, probe ID, timestamp, and cleanup state, never the email or digest. It uses the existing profile only, does not inspect or change composer text, send messages, read/copy cookies, or remove locks. Cleanup state is Playwright lifecycle evidence, not an OS-level no-residual-process audit; see `scripts/dot_chrome.mjs` for exact lifecycle fields. `logged_out` requires HTTP 200 JSON with no user and no composer; 403/challenge is `challenge`, indeterminate is `unknown`, and launch/profile failure is `unavailable`.
- Send: write the message to a `mktemp` file, then `dot.sh [--account <name>] [--url <url>] send <file>`. Prefix every message with the sender identity, e.g. `From Claude (<model>, <worktree>): ...`. Never interpolate raw text into JS; the script JSON-encodes the file.
  - **Mandatory after any send that hands off or asks for work:** in the same turn, without asking, harden the wait condition with `/ironclad` (binary, verified at the source; use the coordinator recovery checkback condition when applicable, otherwise the generic 4-hour cap), then set it via `/cmux-goal` (or native `/goal` when cmux is unavailable) using the condition in "Default: delegate, then monitor". Run `send` in the background, since it can wait up to 30 min on a busy composer; it posts once and never resends. A send without a goal is an unfinished step.
- Single send attempt: `dot.sh [--account <name>] [--url <url>] send-once <file>`.
- Submit the existing draft: `dot.sh [--account <name>] submit-draft` sends whatever draft/edit state the composer already holds (prints `DOT_DRAFT_SUBMITTED: <text>`), or `DOT_SUBMIT_NOTHING_TO_SEND` when empty.
- Clear the existing draft: `dot.sh [--account <name>] clear-draft` discards whatever the composer holds (prints `DOT_DRAFT_CLEARED`), escaping any edit state first.

### Peer-draft policy (decision lives HERE, not in code)

Other agent sessions share this composer; ChatGPT restores a saved draft lazily on focus, so `send` focuses first, then inspects. When `send`/`send-once` reports `DOT_DRAFT_PRESENT` (exit 3), do NOT immediately clear or keep blind-retrying:
1. **Wait 30 seconds, then submit if unchanged.** Sleep up to 30s and re-read the composer. Ignore an appended read-receipt timestamp when comparing text. If the draft text is **otherwise identical after 30s** (nobody is actively typing), just submit it: `dot.sh submit-draft` (prints `DOT_DRAFT_SUBMITTED`). Do not wait 5 minutes; do not clear a stable draft. Then send your own message.
2. **If the text is still changing** (a peer is provably actively typing between reads), do not submit or clear yet — wait one more 30s cycle, or route your message to the next account in `rotation`.
3. **Clear only genuine garbage** (mid-word cutoffs, command fragments, pasted junk) with `dot.sh clear-draft` (prints `DOT_DRAFT_CLEARED`), then send your own message.
4. `DOT_CLEAR_DRAFT=1` on `send` remains the forced-clear escape hatch; own-leftover and already-sent drafts are always safe-cleared automatically.

**After sending:** Confirm the intended message is present in the intended
conversation before treating the handoff as complete. If the transport cannot
verify the send, inspect the intended conversation before retrying. Consult
`scripts/dot_chrome.mjs` for the installed transport's current verification
behavior; this skill gives the operator's decision rule.
- Send only what the user asked to send. Do not post test messages.
- Avoid line-leading list markers (`1)`, `-`, `*`): the composer converts them to list formatting, which can cause mismatch detection. Use plain sentences.
- Interactive login / auth: `dot.sh [--account <name>] login` launches visible Chrome attached to that account's profile directory.
- To ask and get an answer: send, then poll `dot.sh read 3000` (separate calls, each under 60s) until the tail no longer ends in `Thinking` or `Working`.
- Run the script with a Bash timeout of at least 150s.

### Exit codes

- `0`: Success (read produced output, send verified, or dry-run verified).
- `2`: Usage error, missing argument/message file, or unrecoverable error.
- `3`: Composer busy with peer draft after retry deadline (`DOT_WAIT_SECS`).
- `4`: Send could not be verified in page text.
- `5`: ChatGPT usage limit, rate limit, or abuse prevention reached (rotation exhausted or unrotatable).

## Invocation banner (account + backend + profile directory)

Every `dot.sh` invocation prints a one-line banner to stderr identifying the resolved account, backend, target host, and profile directory before doing anything else:

```
dot.sh: account=<name> backend=<chrome|auto> url=<host> dir=<path>
```

Profile directory resolution is unified between `dot.sh` and `scripts/dot_chrome.mjs resolve-profile`, guaranteeing that the banner, interactive `login`, and headless runs always operate on the identical profile directory.

## Interactive Login & Session Recovery

If an account returns `DOT_CHROME_UNAVAILABLE: not signed in`:
1. Use `restore-session` only when Chrome for that profile is stopped, then verify with `read` and the account's expected-identity `probe`. A missing or expired snapshot does not authorize a browser fallback.
2. If recovery does not restore the session, do not open the personal/default Chrome profile, transfer cookies, or route the live Dot profile through another browser or the bundled-browser fallback. Report the scoped authentication blocker unless both conditions in step 3 are met.
3. Run visible `login` only when the current thread explicitly requests it and the resolved profile is independently verified as a separate, task-owned Dot profile, distinct from personal/default Chrome. Check the `dot.sh` account/backend/profile banner and verify the profile's task ownership before opening the window; stop if either condition cannot be established. Then run `login` on that exact account:
   ```bash
   scripts/dot.sh --account <name> login
   ```
   This launches a visible Google Chrome window attached to the exact resolved profile directory for that account.
4. Sign in to ChatGPT manually in the browser window.
5. Once logged in and the ChatGPT chat/dot page loads, close the browser window. The session is saved in that host/account's dedicated profile directory. Repeat login independently for each account on each host.
6. Re-test with `dot.sh --account <name> read 500` and the expected-identity `probe`.

## Cloudflare & Session Verification

- The script directly evaluates ChatGPT's `/api/auth/session` endpoint within the authenticated page context.
- **Cloudflare Challenges / 403s:** If Cloudflare returns a challenge or 403 on the session endpoint, the script reports `DOT_CHROME_UNAVAILABLE: Cloudflare challenge` or `Cloudflare 403 on session endpoint`. This is a transient challenge condition — it is never treated as a logged-out state and never invalidates local cookies.
- **Genuine Logouts:** Only reported when `/api/auth/session` returns 200 with an empty user object or when explicit login action buttons are displayed.

## Concurrency & Safety Rules

- **MANDATORY: every dot profile owns an INDEPENDENT session.** For session creation and recovery, follow [Interactive Login & Session Recovery](#interactive-login--session-recovery); its restore-first sequence and visible-login gate are authoritative.
- **BANNED: cookie-store resync from desktop/other profiles**, in either direction. A session shared between live browsers can be invalidated by server-side token rotation. If recovery is needed, follow the sequence above.
- **Never launch a browser other than system Google Chrome against a live Dot
  profile.** Use `dot.sh` for profile operations; it selects the host-specific
  password store: macOS `--password-store=keychain`; Linux uses
  `--password-store=gnome-libsecret` for headless Chrome when `DISPLAY` or
  `DBUS_SESSION_BUS_ADDRESS` is set, and for login. Playwright/Puppeteer and bundled Chromium may use an incompatible keychain backend and damage session cookies.
- **To check login/session status, use `dot.sh --account <name> read` or `dot.sh --account <name> probe`** — they launch the correct binary with the correct flags. Never open the profile with a foreign browser; if a custom script must inspect the profile internals, copy the profile directory first (e.g. `cp -R ~/.config/dot-headless-chrome-X /tmp/probe-copy`) and run against the copy, or use read-only SQLite (`sqlite3 "file:.../Cookies?mode=ro"`, or `sqlite3 <db> ".backup /tmp/c.sqlite"` for a live store) without launching any browser. **Never `immutable=1` on a database Chrome may be writing** — it ignores the WAL and can mislead on a live store.
- **Session-loss forensics (read-only, before any recovery):** a wiped profile shows a rebuilt anonymous cookie store (fresh `oai-did`/csrf cookies, zero `session-token` rows) while the account itself is fine server-side. `dot.sh` now classifies this automatically: a not-signed-in read/send also emits `DOT_STORE_REBUILD: ...` when the store shows the rebuild signature. After diagnosis, follow [Interactive Login & Session Recovery](#interactive-login--session-recovery); visible login remains subject to its step 3. Never treat profile logout as an account logout.
- **Machine checks now built into dot.sh (do not weaken them):** disk-space floor (`DOT_MIN_FREE_MB`, default 512 — a full disk corrupts the SQLite cookie store); OPT-IN foreign-binary enforcement (`DOT_ENFORCE_SYSTEM_CHROME=1`, honoured on login, headless and send-prepared): refuses a non-system binary unless `DOT_ALLOW_FOREIGN_BINARY=1`, because `DOT_CHROME_BIN` is a supported override for tests and alternate Chrome channels — the real 2026-10-11 wipe came from an ad-hoc script that bypassed `dot.sh` entirely; login launches with the same `--password-store` flags as headless; process-group teardown even when the node wrapper exits before the browser. The per-profile kernel flock and the coordinator STOP marker were deleted on 2026-10-20 at the operator's request: dot.sh no longer serializes concurrent invocations on one profile and `DOT_PROFILE_LOCKED` no longer exists, so concurrent launches against the same profile are the caller's own risk.
- **Session snapshots (own-profile, no coupling):** authenticated read/send/probe keeps `Cookies.snapshot` beside the live store (`DOT_SNAPSHOT=0` disables); `restore-session` requires Chrome fully stopped and keeps a `.pre-restore` copy. A snapshot can be stale after token rotation; verify with the recovery sequence above.
- `.dot-profile.lock.ready.*` files are legacy scratch and carry no authority.
**Directory exclusivity.** A dot `user_data_dir` is owned by dot alone: no other tool, MCP server, or browser may
be configured to use it. **Lock-holder probe (run whenever `dot.sh` exits with
`profile directory locked by active process PID`):** the singleton target embeds only `<hostname>-<pid>`, so resolve
the parent in two steps:

```bash
PID=$(readlink "$dir/SingletonLock" | sed 's/.*-//')
PPID_=$([ -n "$PID" ] && ps -o ppid= -p "$PID" | tr -d ' ' || true)
[ -n "$PID" ] && ps -o pid=,ppid=,stat=,command= -p "${PID}${PPID_:+,$PPID_}"
```

**Dot's own lineages:** `dot.sh -> dot_chrome.mjs -> Chrome` (headless `read`/`send`/`probe`) and
`dot.sh -> Chrome` (interactive `login`). Only a parent outside both is another tool: report that parent's pid and
command and stop.

**Liveness for cleanup:** the holder is dead only when `ps -o stat= -p "$PID"` is empty or starts with `Z`. Remove
singleton files only for a dead holder; never unlink a lock a live process holds, or one whose live parent is
unidentified. Do not use `! kill -0` alone - it succeeds on `EPERM` for a live cross-UID process.

**Thin-pointer invariant:** `dot.sh`/`dot_chrome.mjs` are mechanical transport only (type, read, submit, clear, verify). All judgment — what to send, when to submit vs clear a peer draft, how to phrase coordination — belongs in this skill’s instructions and the calling agent, never hardcoded in the scripts. See `GUARDRAIL.md` for the enforced LOC budget.

## Account Rotation on Limits (Mandatory)

Resolve eligible accounts and work restrictions from [Machine Configuration](configuration.md#machine-configuration-configdotconfigjson--reference).
Route new work to `default_account`, then the next eligible account in `rotation` when it is limited or its
composer remains blocked. Do not exclude an account merely because an agent originated the request. Explicit
account/target bindings and [coordinator recovery checkbacks](delegation.md#coordinator-recovery-checkbacks) keep their
existing reassignment rules. Read back uncertain sends before dispatching the same task elsewhere.

Before selection, inspect the configured account roster, applicable account policy, known in-flight work and
existing identity/health receipts. Use the supported `probe` action with the verified expected identity when a
fresh check is needed. It checks the session/composer without sending a message; it does not establish model
quota or task completion. Do not send test pings to every Dot. Read-only probes may run concurrently only on
distinct profiles within measured resources; serialize callers of the same Dot profile. Instinct uses its own profile.

Independent authorized tasks may use different eligible accounts concurrently. For one task, use backups on
verified failure or unavailability, preserving ownership and attempt deadlines. For advice, follow its
[candidate checks and fallback](../advice/SKILL.md#candidate-checks-fan-out-and-fallback): all Dot accounts
collectively supply at most one vote, and runtime dispatch limits still apply. The caller owns interactive
routing and receipts; `dot-coordinator` remains a single-account scheduled reminder.

Before the required closing receipt or verdict, include every configured account's disclosure-safe alias, health evidence/time,
actual send attempted (yes/no), outcome or concrete skip reason, receipt and next action. For example:
“A attempted: quota refusal (receipt); B attempted: delivered (receipt); C not attempted: task already delivered
to B.” Delivery is not completion. Missing evidence means UNKNOWN or attempt UNVERIFIED, never guessed quota.
A skipped account needs a reason such as task already delivered, account policy, verified quota window, existing
ownership, profile contention or deadline. Keep private account identifiers out of published receipts.

`dot.sh` supports automatic rotation (`DOT_ROTATE_ON_LIMIT=1` by default), clearing `DOT_CHROME_USER_DATA`,
`DOT_URL` and `DOT_PROFILE_DIRECTORY` so the next account resolves its own profile and target. Attribute every
automatic attempt from transport output; if the visited accounts cannot be verified, report that gap rather
than claiming the roster was exhausted. Advice and bound recovery callers retain `DOT_ROTATE_ON_LIMIT=0`.
