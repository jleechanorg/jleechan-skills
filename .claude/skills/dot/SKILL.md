---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs). Each account uses its own local persistent Chrome session.
---

# /dot

Talk to the user's ChatGPT dot assistant using `scripts/dot.sh`. The scripts are a thin mechanical pointer (type, read, submit, clear, verify — see `GUARDRAIL.md`); every judgment call lives in this file, read top-down: how to work through the dot first, then transport actions and the peer-draft policy, then operational reference.

## Default: delegate non-small work, then monitor

### Explicit Dot requests take priority

When the user explicitly asks to use Dot or invokes `/dot` for work, send the
task to Dot even when it looks small. Send a scoped request with the goal,
branch or PR, acceptance criteria, and applicable constraints. Dot runs its own
coders; monitor its work and verify claims at the source.

Delegating a task does not expand its authorization. Preserve the user's scope
and all separate merge, destructive-action, credential, publication, and
permission boundaries. A reversible action is not automatically authorized
just because Dot requests it.

### Small fixes do not need Dot unless requested

When deciding whether to involve Dot without an explicit user request, do not
route a small fix to Dot. A fix is small when all are true:

- it touches one or two files;
- it changes no more than roughly 30 lines;
- it needs no new design decision, API, dependency, or provider call;
- it can be verified with a command available now.

Unfamiliarity alone does not make a fix non-small. Involve Dot when work spans
more files or subsystems, needs design or contract decisions, requires
investigation across the codebase, involves long-running checks, or needs
capabilities or access unavailable locally. When unsure, inspect enough of the
affected flow to classify it before deciding. Follow the active runtime's
normal implementation policy for work that is not assigned to Dot.

- **Active work check first (mandatory):** before declining an authorized task, ask the Dot to inventory current work in progress and count only distinct tasks demonstrably executing now. Require a receipt for each claimed active task: item/goal, owner, live run/session or worktree/PR, the exact action happening now, and a fresh artifact or command result. Assignment, rank, "busy", or start time alone is not proof. Idle, stalled, finished, queued, and waiting-for-review tasks are not active. Capacity is a valid refusal only with evidence for at least six distinct active tasks, each showing its exact present action and fresh receipt; include those receipts in the reply. Do not gate acceptance on rank or ask the user to prioritize the task. If fewer than six active tasks are proven, take the authorized task and fill open capacity with safe work. Keep genuine permission/approval holds and measured resource limits separate from a full-capacity refusal: state the evidence and exact blocked action, preserve the approval boundary, and continue work that remains feasible. If the composer stays blocked or the account is limited, send the same request to the next account in `rotation` with `--account <next>`.

### Coordinator recovery checkbacks

For a user-requested coordinator recovery cycle, this contract overrides the generic polling and /goal defaults below. It is owner guidance, not a new scheduler or a change to the fixed reminder transport body.

- Start only after an exact transport receipt for the initial reminder in the intended chat. Inter-check delays in seconds: `60, 120, 300, 300, 300, 300, 300, 300, 300, 300`. Measure each delay from the previous completed observation (first delay from the verified send). Record actual observations and source receipts in the existing checkpoint. New reminders and partial progress never reset the count.
- Increment once per completed observation attempt, including a recorded timeout or read failure; resume an interrupted attempt under the same count. Later re-observation consumes the next scheduled count: no check eleven or disguised in-check re-observation.
- This cycle also overrides the account-rotation rules: retain the verified account and intended chat. Set `DOT_ROTATE_ON_LIMIT=0` on each coordinator `dot.sh` invocation so automatic rotation cannot change its target. Do not rotate to another account or target on a busy composer or quota limit; report the exact transport blocker and preserve the checkpoint. A separately authorized reassignment requires a newly verified target and must not create duplicate ownership.
- Keep the intended destination explicit for every reminder and observation. If a transport reports `DOT_TARGET_MISMATCH`, do not send or retry blindly; inspect the current destination and establish whether it is the intended conversation before proceeding. Keep destination safeguards. If a guard rejects a route that resolves to the intended conversation, update it to check stable conversation identity rather than path strings alone.
- Direct user messages take priority: respond promptly, apply changed scope/cancellations before further action, and preserve the cycle checkpoint. Use the existing supported interruptible wait/wake mechanism. Do not create jobs, daemons, senders or competing coordinators. Do not change providers, credentials or installed schedules. If timing is unsupported, name the exact capability gap; do not claim planned checks ran.
- Resume unfinished authorized work with its existing owner; recover checkpoints, acceptance gaps and older commitments. Verify owner state before any separately authorized reassignment. A publication hold need not block authorized safe tests or design. Attempt a concrete permitted unblock route for each blocker and continue independent work within evidenced capacity, rather than repeating inventories.
- At each check require fresh original task artifacts against the requested acceptance criteria and a disposition for every unfinished request. Daemon health, delivery success, Working, timestamps, HEARTBEAT_OK, assignments and chat claims do not prove task execution or completion. Empty/failed reads remain unverified. Passing tests do not prove unperformed activation or publication.
- End early only when all requested outcomes are source-verified complete, the user cancels this cycle, or all remaining necessary observations are blocked after permitted alternatives are exhausted. One blocked lane must not stop other feasible lanes. Ten checks end the bounded observation cycle, not task ownership: report remaining gaps, keep checkpoints and next triggers, and continue feasible authorized work; otherwise wait quietly on precise blockers.

### Other delegated work

For PR/lifecycle review requests, including a requested `/dot` review, the
600-second end-to-end reviewer-attempt limit in `pr-lifecycle` § Reviewer timeout
and completion takes precedence over this section's generic four-hour wait and
polling schedule. Preserve the reviewer quorum and eligibility rules in
`pr-lifecycle`. Start the clock when the request is queued or sent; queueing/delivery,
setup, transport calls, polling/waits, review, result capture, receipt recording,
and cleanup all consume the same budget. Bound each transport timeout and wait
to the remaining time; a 150-second minimum transport setting never extends the
reviewer deadline. On timeout, record the attempt as non-approving and continue
to the next eligible independent reviewer, subject to verified cleanup of any
shared execution resource. Ordinary delegated work keeps its existing schedule.

- For other delegated work only, poll the dot with exponential backoff while it has work in flight: first poll 1 minute after the send, then 2 minutes later, then 5 minutes later, then every 10 minutes. Give up 4 hours after the first send if the dot has not started or done the work, and report that to the user with the last reply seen. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim. Any reply from the dot that shows real progress (a claimed lane, branch or PR) restarts the backoff at 1 minute and the 4-hour clock.
  - **Set a `/goal` for the wait** (via `/cmux-goal`): condition "the dot's deliverable exists and is verified at the source (PR open, RED then GREEN re-run by me, CI green), or 4 hours have passed since the first send". The goal keeps the session polling; do not rely on remembering to poll.
  - **Claude Code:** one-shot `ScheduleWakeup` calls at the backoff delays (60s, 120s, 300s), then a 600s wakeup repeated every 10 minutes; or a durable `CronCreate` `*/10 * * * *` after the first three polls. Record the first-send time (absolute, with timezone) in the poll prompt so each tick can compute the 4-hour deadline.
  - **Codex (no `/loop`):** the same `/goal`; each turn runs the same poll, then waits the next backoff interval (`sleep 60`, `sleep 120`, `sleep 300`, then `sleep 600` in a backgrounded or bounded command).
  - Stop polling when the deliverable is done, blocked on the user, or the 4-hour limit passes.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

### Cloud-computer capability gaps

When Dot cannot perform a requested cloud-computer task, confirm the exact gap
before calling the task blocked. Record the host, repository or worktree,
branch or SHA, command, exit status, missing capability, and expected artifact.
Ask Dot to attempt safe setup using repository-declared dependencies and
approved login or permission flows. Never copy credentials or browser
sessions, bypass a guard, or treat a permission request as granted. Re-run the
exact command and verify its output or artifact at the source. Keep independent
authorized work moving if the capability remains unavailable, and report the
precise blocker and required unblock in the current conversation. Notify other
channels only when that channel and recipient are authorized for the task.

## Actions

- `restore-session` — restore this profile's last own-session snapshot (Chrome must be stopped; verify with read/probe afterward; `login` remains the canonical recovery).

- Read: `dot.sh [--account <name>] [--url <url>] read [chars]` prints the tail of the page text (default 5000). While the dot is working the tail ends with `dot` / `Thinking` / `Working`.
- Probe: `dot.sh [--account <name>] probe <expected-email-sha256>` checks the current session with the existing profile and returns a typed `DOT_SESSION_PROBE` JSON result. Pass the frozen expected email's SHA-256 digest of its exact UTF-8 bytes, encoded as lowercase hex; do not trim or change the email's case before hashing. The output includes identity match, endpoint status, probe status, composer availability, an opaque profile slot, probe ID, and timestamp; it never includes the raw email or digest.
  The probe uses the existing-profile-only launch with the normal Chrome options plus a Playwright launch timeout. It awaits launch before starting the probe-local deadline, so a timed-out body/evaluate returns `unknown` without abandoning a pending launch. The installed SDK consumes that launch timeout and its startup-failure path performs bounded graceful-close/kill cleanup; a launch failure reports `cleanup_state: unresolved` because no context handle is returned for disconnect verification. Cleanup first awaits `context.close()`; if that hangs or fails, it uses the owned public `context.browser().close()` when available and verifies the public disconnected state/event. `cleanup_state` reports `not_started`, `context_closed`, `browser_disconnected`, or `unresolved`; unresolved cleanup is `unavailable`. This reports Playwright API lifecycle evidence and does not claim an OS-level no-residual-process audit. The probe does not scan desktop Chrome `Local State`, seed profiles, read or copy cookies, remove locks, inspect or change composer text, or send messages. A visible composer is reported separately and does not imply logout.
  `logged_out` requires a valid HTTP 200 JSON session with no user and no composer; a 403 or Cloudflare challenge title is `challenge`; indeterminate responses are `unknown`; launch/profile failures are `unavailable`.
- Send: write the message to a `mktemp` file, then `dot.sh [--account <name>] [--url <url>] send <file>`. Prefix every message with the sender identity, e.g. `From Claude (<model>, <worktree>): ...`. Never interpolate raw text into JS; the script JSON-encodes the file.
  - **Mandatory after any send that hands off or asks for work:** in the same turn, without asking, harden the wait condition with `/ironclad` (binary, verified at the source; use the coordinator recovery checkback condition when applicable, otherwise the generic 4-hour cap), then set it via `/cmux-goal` (or native `/goal` when cmux is unavailable) using the condition in "Default: delegate, then monitor". Run `send` in the background, since it can wait up to 30 min on a busy composer; it posts once and never resends. A send without a goal is an unfinished step.
- Single send attempt: `dot.sh [--account <name>] [--url <url>] send-once <file>`.
- Submit the existing draft: `dot.sh [--account <name>] submit-draft` sends whatever draft/edit state the composer already holds (prints `DOT_DRAFT_SUBMITTED: <text>`), or `DOT_SUBMIT_NOTHING_TO_SEND` when empty.
- Clear the existing draft: `dot.sh [--account <name>] clear-draft` discards whatever the composer holds (prints `DOT_DRAFT_CLEARED`), escaping any edit state first.

### Peer-draft policy (decision lives HERE, not in code)

Other agent sessions share this composer; ChatGPT restores a saved draft lazily on focus, so `send` focuses first, then inspects. When `send`/`send-once` reports `DOT_DRAFT_PRESENT` (exit 3), do NOT immediately clear or keep blind-retrying:
1. **Wait 30 seconds, then submit if unchanged.** Sleep up to 30s and re-read the composer. If the draft text is **identical after 30s** (nobody is actively typing), just submit it: `dot.sh submit-draft` (prints `DOT_DRAFT_SUBMITTED`). Do not wait 5 minutes; do not clear a stable draft. Then send your own message.
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
1. **Canonical Login Command:** Run `login` on that exact account:
   ```bash
   scripts/dot.sh --account <name> login
   ```
   This launches a visible Google Chrome window attached to the exact resolved profile directory for that account.
2. Sign in to ChatGPT manually in the browser window.
3. Once logged in and the ChatGPT chat/dot page loads, close the browser window. The session is saved in that host/account's dedicated profile directory. Repeat login independently for each account on each host.
4. Re-test with `dot.sh --account <name> read 500`.

## Cloudflare & Session Verification

- The script directly evaluates ChatGPT's `/api/auth/session` endpoint within the authenticated page context.
- **Cloudflare Challenges / 403s:** If Cloudflare returns a challenge or 403 on the session endpoint, the script reports `DOT_CHROME_UNAVAILABLE: Cloudflare challenge` or `Cloudflare 403 on session endpoint`. This is a transient challenge condition — it is never treated as a logged-out state and never invalidates local cookies.
- **Genuine Logouts:** Only reported when `/api/auth/session` returns 200 with an empty user object or when explicit login action buttons are displayed.

## Concurrency & Safety Rules

- **MANDATORY: every dot profile owns an INDEPENDENT session, created only via `dot.sh --account <name> login`** (a visible Chrome window the user signs into; the script itself never enters, stores, or extracts credentials). This is the one canonical recovery from `logged_out` and the only sanctioned way a dot profile ever gets a session. Do not "help" by sharing a session from any other browser — see the resync ban below.
- **BANNED: cookie-store resync from desktop/other profiles** (copying `Cookies` from a desktop Chrome profile into a dot profile, in either direction). A session shared between two live browsers is a rotation race: ChatGPT rotates the session token on activity, the rotation supersedes the old token server-side, and the browser that did not rotate renders logged out. On 2026-10-11 this logged the user's personal Chrome out of their own account after a resync-based restore. Sessions are cheap and independent — use `dot.sh login` instead.
- **Never launch a browser other than system Google Chrome against a live Dot
  profile.** Use `dot.sh` for profile operations; it selects the host-specific
  password store: macOS `--password-store=keychain`; Linux uses
  `--password-store=gnome-libsecret` for headless Chrome when `DISPLAY` or
  `DBUS_SESSION_BUS_ADDRESS` is set, and for login. Playwright/Puppeteer and bundled Chromium may use an incompatible keychain backend and damage session cookies.
- **To check login/session status, use `dot.sh --account <name> read` or `dot.sh --account <name> probe`** — they launch the correct binary with the correct flags. Never open the profile with a foreign browser; if a custom script must inspect the profile internals, copy the profile directory first (e.g. `cp -R ~/.config/dot-headless-chrome-X /tmp/probe-copy`) and run against the copy, or use read-only SQLite (`sqlite3 "file:.../Cookies?mode=ro"`, or `sqlite3 <db> ".backup /tmp/c.sqlite"` for a live store) without launching any browser. **Never `immutable=1` on a database Chrome may be writing** — it ignores the WAL and can mislead on a live store.
- **Session-loss forensics (read-only, before any recovery):** a wiped profile shows a rebuilt anonymous cookie store (fresh `oai-did`/csrf cookies, zero `session-token` rows) while the account itself is fine server-side. `dot.sh` now classifies this automatically: a not-signed-in read/send also emits `DOT_STORE_REBUILD: ...` when the store shows the rebuild signature. Recover ONLY via `dot.sh login`. Never treat profile logout as an account logout.
- **Machine checks now built into dot.sh (do not weaken them):** disk-space floor (`DOT_MIN_FREE_MB`, default 512 — a full disk corrupts the SQLite cookie store); OPT-IN foreign-binary enforcement (`DOT_ENFORCE_SYSTEM_CHROME=1`, honoured on login, headless and send-prepared): refuses a non-system binary unless `DOT_ALLOW_FOREIGN_BINARY=1`, because `DOT_CHROME_BIN` is a supported override for tests and alternate Chrome channels — the real 2026-10-11 wipe came from an ad-hoc script that bypassed `dot.sh` entirely; login launches with the same `--password-store` flags as headless; process-group teardown even when the node wrapper exits before the browser. The per-profile kernel flock and the coordinator STOP marker were deleted on 2026-10-20 at the operator's request: dot.sh no longer serializes concurrent invocations on one profile and `DOT_PROFILE_LOCKED` no longer exists, so concurrent launches against the same profile are the caller's own risk.
- **Session snapshots (own-profile, no coupling):** every authenticated read/send/probe keeps `Cookies.snapshot` next to the live store (SQLite online backup; `DOT_SNAPSHOT=0` disables). `dot.sh restore-session` restores it — only with Chrome fully stopped, keeping a `.pre-restore` copy. Restoration is opportunistic: server-side token rotation may make a snapshot stale, in which case the probe reports logged out and the canonical `dot.sh --account <name> login` path still applies. Never resync cookies from another browser profile.
- **Login-window hygiene:** there is no per-profile flock or coordinator STOP marker any more (removed 2026-10-20), so
  concurrent launches against the same profile remain the caller's own risk; `.dot-profile.lock.ready.*` files are
  legacy scratch and carry no authority.
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

**Thin-pointer invariant:** `dot.sh`/`dot_chrome.mjs` are mechanical transport only (type, read, submit, clear, verify). All judgment — what to send, when to submit vs clear a peer draft, how to phrase coordination — belongs in THIS SKILL.md and the calling agent, never hardcoded in the scripts. See `GUARDRAIL.md` for the enforced LOC budget.

## Account Rotation on Limits (Mandatory)

Always rotate across configured accounts when hitting a rate limit, usage limit, abuse prevention cooldown, or message cap:
- **Limit Detection:** Detected directly from ChatGPT UI alert elements (`[role=alert]`, alert banners), emitting structured `DOT_USAGE_LIMIT_REACHED` events.
- **Mandatory Rotation:** When an account hits a limit or cooldown, immediately rotate to the next configured account in `rotation` using `--account <next>`.
- **Clean Profile Hand-off:** Rotation unsets `DOT_CHROME_USER_DATA`, `DOT_URL`, and `DOT_PROFILE_DIRECTORY` across the boundary so the next account automatically resolves its own dedicated profile directory, target URL, and configured subprofile.
- **Automatic Script Support:** `dot.sh` implements automatic account rotation (`DOT_ROTATE_ON_LIMIT=1` by default) using the `rotation` sequence declared in `~/.config/dot/config.json`.

## Backend & Persistent Profiles

- **Headless Chrome (`scripts/dot_chrome.mjs`):** The only supported backend.
  - Resolves one persistent profile per account from `user_data_dir` in `~/.config/dot/config.json` or `~/.config/dot-headless-chrome-<account_slug>`.
  - Creates a blank profile; each host and account signs in on its own with `dot.sh --account <name> login`.
  - Rejects profile paths that overlap the system Google Chrome profile, including symlink aliases.
  - Safely handles `SingletonLock`: verifies lock holder PID liveness, waiting politely if held by an active Chrome process, clearing only genuinely dead locks without killing peer processes.
  - Tolerates appended read-receipt timestamps (`Read 1:15 AM`) to prevent false draft conflicts.
- **Local execution:** If Chrome is unavailable on a host, Dot reports that local prerequisite failure. It does not forward the request to another host, because doing so would reuse that host's signed-in session.

## Configuration & Environment Variables

- `DOT_ACCOUNT`: Account identifier in `~/.config/dot/config.json`. Can also be passed via `--account <name>`.
- `DOT_URL`: Target ChatGPT dot assistant URL. Can also be passed via `--url <url>`.
- `DOT_BACKEND`: Force backend (`chrome` or `auto`). Both values select Chrome.
- `DOT_CONFIG_FILE`: Custom path to dot JSON configuration (defaults to `~/.config/dot/config.json`).
- `DOT_CHROME_USER_DATA`: Explicit Chrome user data directory (defaults to account-specific persistent dir configured in `~/.config/dot/config.json`).
- `DOT_PROFILE_DIRECTORY`: Explicit named Chrome subprofile override (defaults to the account's `profile_directory`, or `Default` when absent); it must pass the same single-directory-name validation.
- `DOT_CLEAR_DRAFT`: When set to `1`, forces clearing any existing draft or edit state in the composer before typing and sending. Peer-draft decisions otherwise follow the SKILL.md policy (wait 30s, submit if unchanged, else route to the next rotation account).
- `DOT_DRY_RUN`: When `1` (Chrome backend), types, verifies exact match, clears composer, and prints `DOT_DRYRUN_OK` without sending.

## Machine Configuration (`~/.config/dot/config.json`) — reference

Accounts, target dot URLs, and preferred backends can be declared per-machine in `~/.config/dot/config.json` without hardcoding personal data into the repository:

```json
{
  "default_account": "primary",
  "rotation": ["primary", "secondary"],
  "accounts": {
    "primary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "user_data_dir": "~/.config/dot-headless-chrome-primary",
      "profile_directory": "Profile 1"
    },
    "secondary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "user_data_dir": "~/.config/dot-headless-chrome-secondary",
      "profile_directory": "Profile 2"
    }
  },
  "aliases": {
    "work": "primary",
    "personal": "secondary"
  }
}
```

Each `user_data_dir` must be dedicated to that Dot account and must not point inside the system Google Chrome profile. No other tool, MCP server, or browser may share a dot `user_data_dir`; exclusivity covers the directory, not only dot's own launches. If `user_data_dir` is omitted, Dot derives a separate local directory from the account key. `profile_directory` is optional: it selects a named Chrome subprofile and defaults to `Default` when absent. The value must be one safe directory name, such as `Profile 1`; path separators, `.` and `..`, and control characters are rejected. `DOT_PROFILE_DIRECTORY` may temporarily override the configured subprofile for one invocation, subject to the same validation. Chrome is the only backend. Multi-account targeting uses `--account <name>` / `DOT_ACCOUNT`, with independent headless-Chrome sessions per host/account pair and unified profile resolution with non-destructive lock recovery.
