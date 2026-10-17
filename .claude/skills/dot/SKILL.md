---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs). Each account uses its own local persistent Chrome session.
---

# /dot

Talk to the user's ChatGPT dot assistant using `scripts/dot.sh`. The scripts are a thin mechanical pointer (type, read, submit, clear, verify — see `GUARDRAIL.md`); every judgment call lives in this file, read top-down: how to work through the dot first, then transport actions and the peer-draft policy, then operational reference.

## Default: delegate, then monitor

### Small fixes stay local (do NOT delegate)

**Never send the dot a request you can finish yourself in one edit.** Delegation has a real round-trip cost (transport, polling, backoff, source re-verification), and it consumes a shared composer. If the fix is small, do it locally and only report it.

A fix is **small** (do it yourself) when all hold:
- it touches one or two files;
- it changes no more than roughly 30 lines;
- it needs no new design decision, API, dependency, or provider call;
- it can be verified with a command you can run right now (lint, compile, or a focused test).

Delegate instead when the work is **not small**: multiple files or subsystems, a design or contract decision, an unfamiliar area needing investigation, long-running builds/tests, or anything requiring capabilities or access you do not have.

When unsure, prefer doing it locally and reporting the result; escalating is cheap only after you have tried. If you catch yourself writing a dot message to describe a one-file edit, stop and just make the edit.

The dot runs its own coders. When /dot is used for work, hand the work to the dot instead of coding it yourself: send a scoped request (goal, PR/branch, acceptance criteria, constraints such as merge gates), then monitor rather than block.

- **Active work check first (mandatory):** before declining an authorized task, ask the Dot to inventory current work in progress and count only distinct tasks demonstrably executing now. Require a receipt for each claimed active task: item/goal, owner, live run/session or worktree/PR, the exact action happening now, and a fresh artifact or command result. Assignment, rank, "busy", or start time alone is not proof. Idle, stalled, finished, queued, and waiting-for-review tasks are not active. Capacity is a valid refusal only with evidence for at least six distinct active tasks, each showing its exact present action and fresh receipt; include those receipts in the reply. Do not gate acceptance on rank or ask the user to prioritize the task. If fewer than six active tasks are proven, take the authorized task and fill open capacity with safe work. Keep genuine permission/approval holds and measured resource limits separate from a full-capacity refusal: state the evidence and exact blocked action, preserve the approval boundary, and continue work that remains feasible. If the composer stays blocked or the account is limited, send the same request to the next account in `rotation` with `--account <next>`.

### Coordinator recovery checkbacks

For a user-requested coordinator recovery cycle, this contract overrides the generic polling and /goal defaults below. It is owner guidance, not a new scheduler or a change to the fixed reminder transport body.

- Start only after an exact transport receipt for the initial reminder in the intended chat. Inter-check delays in seconds: `60, 120, 300, 300, 300, 300, 300, 300, 300, 300`. Measure each delay from the previous completed observation (first delay from the verified send). Record actual observations and source receipts in the existing checkpoint. New reminders and partial progress never reset the count.
- Increment once per completed observation attempt, including a recorded timeout or read failure; resume an interrupted attempt under the same count. Later re-observation consumes the next scheduled count: no check eleven or disguised in-check re-observation.
- Preserve the cycle checkpoint and the intended chat.
- Direct user messages take priority: respond promptly, apply changed scope/cancellations before further action, and preserve the cycle checkpoint. Use the existing supported interruptible wait/wake mechanism. Do not create jobs, daemons, senders or competing coordinators. Do not change providers, credentials or installed schedules. If timing is unsupported, name the exact capability gap; do not claim planned checks ran.
- Resume unfinished authorized work with its existing owner; recover checkpoints, acceptance gaps and older commitments. Verify owner state before any separately authorized reassignment. A publication hold need not block authorized safe tests or design. Attempt a concrete permitted unblock route for each blocker and continue independent work within evidenced capacity, rather than repeating inventories.
- At each check require fresh original task artifacts against the requested acceptance criteria and a disposition for every unfinished request. Daemon health, delivery success, Working, timestamps, HEARTBEAT_OK, assignments and chat claims do not prove task execution or completion. Empty/failed reads remain unverified. Passing tests do not prove unperformed activation or publication.
- End early only when all requested outcomes are source-verified complete, the user cancels this cycle, or all remaining necessary observations are blocked after permitted alternatives are exhausted. One blocked lane must not stop other feasible lanes. Ten checks end the bounded observation cycle, not task ownership: report remaining gaps, keep checkpoints and next triggers, and continue feasible authorized work; otherwise wait quietly on precise blockers.

### Other delegated work

- For other delegated work only, poll the dot with exponential backoff while it has work in flight: first poll 1 minute after the send, then 2 minutes later, then 5 minutes later, then every 10 minutes. Give up 4 hours after the first send if the dot has not started or done the work, and report that to the user with the last reply seen. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim. Any reply from the dot that shows real progress (a claimed lane, branch or PR) restarts the backoff at 1 minute and the 4-hour clock.
  - **Set a `/goal` for the wait** (via `/cmux-goal`): condition "the dot's deliverable exists and is verified at the source (PR open, RED then GREEN re-run by me, CI green), or 4 hours have passed since the first send". The goal keeps the session polling; do not rely on remembering to poll.
  - **Claude Code:** one-shot `ScheduleWakeup` calls at the backoff delays (60s, 120s, 300s), then a 600s wakeup repeated every 10 minutes; or a durable `CronCreate` `*/10 * * * *` after the first three polls. Record the first-send time (absolute, with timezone) in the poll prompt so each tick can compute the 4-hour deadline.
  - **Codex (no `/loop`):** the same `/goal`; each turn runs the same poll, then waits the next backoff interval (`sleep 60`, `sleep 120`, `sleep 300`, then `sleep 600` in a backgrounded or bounded command).
  - Stop polling when the deliverable is done, blocked on the user, or the 4-hour limit passes.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

### Cloud-computer capability gaps

When Dot cannot perform a requested cloud-computer task (for example, a test,
build, browser flow, deployment, or provider operation), handle the gap before
calling the task blocked:

1. Identify the exact missing capability and capture the command, working
   directory or worktree, target PR/branch, and the relevant error or output.
2. Ask Dot to inspect and attempt safe, authorized setup: install a repository-
   declared dependency with the approved package manager, complete the
   repository setup, use the canonical provider or browser login flow, or
   request the needed account or workspace permission through its approved
   mechanism. Never ask for, copy, or store secrets; never bypass security,
   disable a guardrail, reuse another account's session, or claim that a
   request was granted when it was only submitted.
3. Re-run the exact blocked command after setup and verify the resulting
   artifact or source state. If the capability remains unavailable, keep
   independent authorized work moving and report the precise unblock rather
   than waiting or claiming completion.
4. Report the unresolved gap in the current chat, Slack, and email. Slack text
   uses `mcp__slack__conversations_add_message` to the already verified
   operator DM or channel (resolve the configured target; do not guess one).
   For email, use the available `/opt/homebrew/bin/gog gmail send` command with
   an authorized recipient and a `mktemp` body file; do not invent an email
   tool, recipient, or credential. If an approved sender or recipient is not
   available, state `email unavailable` explicitly in the chat and Slack
   reports. Each report must include the exact blocked command or artifact,
   setup/install/login/permission attempts and their results, the distinction
   between requested and granted access, and the concrete unblock needed.

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
1. **Check back within 5 minutes**: sleep up to 300s, then `dot.sh read` (or re-attempt `send-once`) to see if the peer sent it themselves or the draft changed.
2. **If the draft is still stuck, decide by reading it:**
   - **Sensible message** (complete sentences, a real instruction/question for the dot) → **prefer sending it**: `dot.sh submit-draft` (prints `DOT_DRAFT_SUBMITTED`). The peer's intent reaches the dot; then send your own message.
   - **Weird half-typed text** (mid-word cutoffs, command fragments, pasted garbage) → **clear it**: `dot.sh clear-draft` (prints `DOT_DRAFT_CLEARED`), then send your own message.
3. Never force-clear a draft while a peer session is provably actively typing (draft text changing between reads). `DOT_CLEAR_DRAFT=1` on `send` remains the forced-clear escape hatch; own-leftover and already-sent drafts are always safe-cleared automatically.

**Verified send:** `DOT_SENT_VERIFIED` requires exact composer match after typing, emptied composer after sending, and the submitted text appearing in the conversation message list (`[data-message-author-role=user]`). Exit 4 means mismatched or unverified.
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
- **NEVER launch any browser binary other than system Google Chrome (with `--password-store=keychain`) against a live dot profile** (`~/.config/dot-headless-chrome-*`). This includes Playwright/Puppeteer (`launchPersistentContext`) and any bundled Chromium: Playwright defaults to its own Chromium with `--use-mock-keychain`, which cannot decrypt the Keychain-encrypted cookie store, so Chrome treats the session cookies as corrupt and EVICTS them — the account stays signed in server-side, but the profile is wiped. On 2026-10-11 this destroyed the `jleechan` (jeffrey) and `worldarchitect` profiles 26 seconds apart during a single ad-hoc inspection sweep.
- **To check login/session status, use `dot.sh --account <name> read` or `dot.sh --account <name> probe`** — they launch the correct binary with the correct flags. Never open the profile with a foreign browser; if a custom script must inspect the profile internals, copy the profile directory first (e.g. `cp -R ~/.config/dot-headless-chrome-X /tmp/probe-copy`) and run against the copy, or use read-only SQLite (`sqlite3 "file:.../Cookies?mode=ro"`, or `sqlite3 <db> ".backup /tmp/c.sqlite"` for a live store) without launching any browser. **Never `immutable=1` on a database Chrome may be writing** — it ignores the WAL and can mislead on a live store.
- **Session-loss forensics (read-only, before any recovery):** a wiped profile shows a rebuilt anonymous cookie store (fresh `oai-did`/csrf cookies, zero `session-token` rows) while the account itself is fine server-side. `dot.sh` now classifies this automatically: a not-signed-in read/send also emits `DOT_STORE_REBUILD: ...` when the store shows the rebuild signature. Recover ONLY via `dot.sh login`. Never treat profile logout as an account logout.
- **Machine checks now built into dot.sh (do not weaken them):** per-profile exclusive lock (a kernel `flock` on a hashed path under `$TMPDIR/dot-profile-locks/`, held by a holder process that dies with its parent — auto-released on ANY exit including kill -9, no stale-lock logic. The lock deliberately lives OUTSIDE the profile directory: a probe contract asserts launches leave the profile dir untouched, and a lock path inside the profile makes process scans that substring-match the profile dir treat it as in use); disk-space floor (`DOT_MIN_FREE_MB`, default 512 — a full disk corrupts the SQLite cookie store); OPT-IN foreign-binary enforcement (`DOT_ENFORCE_SYSTEM_CHROME=1`, honoured on login, headless and send-prepared): refuses a non-system binary unless `DOT_ALLOW_FOREIGN_BINARY=1`, because `DOT_CHROME_BIN` is a supported override for tests and alternate Chrome channels — the real 2026-10-11 wipe came from an ad-hoc script that bypassed `dot.sh` entirely; login launches with the same `--password-store` flags as headless; `login` holds the coordinator STOP marker for the whole window and removes it only if it created it; process-group teardown even when the node wrapper exits before the browser.
- **Session snapshots (own-profile, no coupling):** every authenticated read/send/probe keeps `Cookies.snapshot` next to the live store (SQLite online backup; `DOT_SNAPSHOT=0` disables). `dot.sh restore-session` restores it — only with Chrome fully stopped, keeping a `.pre-restore` copy. Restoration is opportunistic: server-side token rotation may make a snapshot stale, in which case the probe reports logged out and the canonical `dot.sh --account <name> login` path still applies. Never resync cookies from another browser profile.
- **Login-window hygiene:** while a `dot.sh login` window is open, the profile is process-locked (dot commands return `profile directory locked by active process`); set the coordinator STOP marker (`~/.local/state/ai.gemini.agy-dot-coordinator/STOP`) before launching and remove it after the window closes; after closing a login window manually, remove stale `SingletonLock`/`SingletonCookie`/`SingletonSocket` in the profile dir if a probe reports a stale lock.

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
- `DOT_CLEAR_DRAFT`: When set to `1`, forces clearing any existing draft or edit state in the composer before typing and sending. Peer-draft decisions otherwise follow the SKILL.md policy (check back within 5 min, then `submit-draft` or `clear-draft`).
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

Each `user_data_dir` must be dedicated to that Dot account and must not point inside the system Google Chrome profile. If `user_data_dir` is omitted, Dot derives a separate local directory from the account key. `profile_directory` is optional: it selects a named Chrome subprofile and defaults to `Default` when absent. The value must be one safe directory name, such as `Profile 1`; path separators, `.` and `..`, and control characters are rejected. `DOT_PROFILE_DIRECTORY` may temporarily override the configured subprofile for one invocation, subject to the same validation. Chrome is the only backend. Multi-account targeting uses `--account <name>` / `DOT_ACCOUNT`, with independent headless-Chrome sessions per host/account pair and unified profile resolution with non-destructive lock recovery.
