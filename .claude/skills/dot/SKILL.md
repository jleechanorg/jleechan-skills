---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs). Platform-aware backend: headless Chrome with dynamic multi-account routing.
---

# /dot

Talk to the user's ChatGPT dot assistant using `scripts/dot.sh`. Platform-aware architecture:
- **Dynamic Multi-Account Support:** Target any ChatGPT dot account via `--account <name>` or `DOT_ACCOUNT=<name>`.
- **Machine-Local Configuration:** Configured in `~/.config/dot/config.json` mapping accounts to URLs, backends, and profile match selectors.
- **Headless Chrome Backend:** Runs headless Google Chrome against dedicated persistent profiles (`~/.config/dot-headless-chrome-<account_slug>`) on Linux and macOS with unified profile resolution and non-destructive lock recovery.
- **Transparent Cross-Host Forwarding:** Automatically bridges between Linux and macOS hosts when local Chrome is unavailable (e.g. forward to a Mac with a signed-in Chrome profile).

## Machine Configuration (`~/.config/dot/config.json`)

Accounts, target dot URLs, and preferred backends can be declared per-machine in `~/.config/dot/config.json` without hardcoding personal data into the repository:

```json
{
  "default_account": "primary",
  "rotation": ["primary", "secondary"],
  "accounts": {
    "primary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "profile_match": "work-domain.com"
    },
    "secondary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "profile_match": "personal-email"
    }
  },
  "aliases": {
    "work": "primary",
    "personal": "secondary"
  }
}
```

`profile_match` selects which signed-in Chrome profile is used for that account by matching `user_name`, `email`, `name`, or `hosted_domain` against the system Chrome `Local State`. Chrome is the only supported backend; the aside backend was retired.

## Default: delegate, then monitor

The dot runs its own coders. When /dot is used for work, hand the work to the dot instead of coding it yourself: send a scoped request (goal, PR/branch, acceptance criteria, constraints such as merge gates), then monitor rather than block.

- **Priority check first (mandatory):** the first message of every handoff asks whether the task is in the dot's current top 6, and asks it to reply "not top 6" or give its rank and start time. If the reply is "not top 6", or the composer stays blocked, or the account is limited: do small work yourself, or send the same check to the next account in `rotation` with `--account <next>`. Hand off only to an account that ranks it in its top 6.

- Poll the dot with exponential backoff while it has work in flight: first poll 1 minute after the send, then 2 minutes later, then 5 minutes later, then every 10 minutes. Give up 4 hours after the first send if the dot has not started or done the work, and report that to the user with the last reply seen. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim. Any reply from the dot that shows real progress (a claimed lane, branch or PR) restarts the backoff at 1 minute and the 4-hour clock.
  - **Set a `/goal` for the wait** (via `/cmux-goal`): condition "the dot's deliverable exists and is verified at the source (PR open, RED then GREEN re-run by me, CI green), or 4 hours have passed since the first send". The goal keeps the session polling; do not rely on remembering to poll.
  - **Claude Code:** one-shot `ScheduleWakeup` calls at the backoff delays (60s, 120s, 300s), then a 600s wakeup repeated every 10 minutes; or a durable `CronCreate` `*/10 * * * *` after the first three polls. Record the first-send time (absolute, with timezone) in the poll prompt so each tick can compute the 4-hour deadline.
  - **Codex (no `/loop`):** the same `/goal`; each turn runs the same poll, then waits the next backoff interval (`sleep 60`, `sleep 120`, `sleep 300`, then `sleep 600` in a backgrounded or bounded command).
  - Stop polling when the deliverable is done, blocked on the user, or the 4-hour limit passes.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

## Actions

- Read: `dot.sh [--account <name>] [--url <url>] read [chars]` prints the tail of the page text (default 5000). While the dot is working the tail ends with `dot` / `Thinking` / `Working`.
- Send: write the message to a `mktemp` file, then `dot.sh [--account <name>] [--url <url>] send <file>`. Prefix every message with the sender identity, e.g. `From Claude (<model>, <worktree>): ...`. Never interpolate raw text into JS; the script JSON-encodes the file.
  - **Mandatory after any send that hands off or asks for work:** in the same turn, without asking, harden the wait condition with `/ironclad` (binary, verified at the source, 4-hour cap), then set it via `/cmux-goal` (or native `/goal` when cmux is unavailable) using the condition in "Default: delegate, then monitor". Run `send` in the background, since it can wait up to 30 min on a busy composer; it posts once and never resends. A send without a goal is an unfinished step.
- Single send attempt: `dot.sh [--account <name>] [--url <url>] send-once <file>`.
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
3. Once logged in and the ChatGPT chat/dot page loads, close the browser window. The session tokens and cookies are saved in that profile directory.
4. Re-test with `dot.sh --account <name> read 500`.

## Cloudflare & Session Verification

- The script directly evaluates ChatGPT's `/api/auth/session` endpoint within the authenticated page context.
- **Cloudflare Challenges / 403s:** If Cloudflare returns a challenge or 403 on the session endpoint, the script reports `DOT_CHROME_UNAVAILABLE: Cloudflare challenge` or `Cloudflare 403 on session endpoint`. This is a transient challenge condition — it is never treated as a logged-out state and never invalidates local cookies.
- **Genuine Logouts:** Only reported when `/api/auth/session` returns 200 with an empty user object or when explicit login action buttons are displayed.

## Concurrency & Safety Rules

- Other agent sessions share this composer. ChatGPT restores a saved draft lazily on focus, so `send` focuses first, then inspects.
- **Stale draft:** A draft is only cleared if:
  1. It matches our own message from an interrupted prior attempt, OR
  2. The text already appears in a previously submitted user message (`[data-message-author-role=user]`) matching the full normalized message content (never wiping on short prefix substrings), OR
  3. Forced via `DOT_CLEAR_DRAFT=1`.
  If cleared, `send` prints `DOT_STALE_DRAFT_CLEARED`.
- **Unsent draft:** If an unsubmitted draft belonging to another session is present, `send` NEVER clears or overwrites it. It retries every 60s (`DOT_RETRY_SECS`) up to 30 min (`DOT_WAIT_SECS`) and sends once the composer is empty; exit 3 means still busy after the wait.
- **Verified send:** `DOT_SENT_VERIFIED` requires:
  1. Exact composer match after typing,
  2. Emptied composer after clicking send,
  3. The submitted text appearing in the conversation message list (`[data-message-author-role=user]`).
  Exit 4 means mismatched or unverified.
- Send only what the user asked to send. Do not post test messages.
- Avoid line-leading list markers (`1)`, `-`, `*`): the composer converts them to list formatting, which can cause mismatch detection. Use plain sentences.

## Account Rotation on Limits (Mandatory)

Always rotate across configured accounts when hitting a rate limit, usage limit, abuse prevention cooldown, or message cap:
- **Limit Detection:** Detected directly from ChatGPT UI alert elements (`[role=alert]`, alert banners), emitting structured `DOT_USAGE_LIMIT_REACHED` events.
- **Mandatory Rotation:** When an account hits a limit or cooldown, immediately rotate to the next configured account in `rotation` using `--account <next>`.
- **Clean Profile Hand-off:** Rotation unsets both `DOT_CHROME_USER_DATA` and `DOT_URL` across the boundary so the next account automatically resolves its own dedicated profile directory and target URL.
- **Automatic Script Support:** `dot.sh` implements automatic account rotation (`DOT_ROTATE_ON_LIMIT=1` by default) using the `rotation` sequence declared in `~/.config/dot/config.json`.

## Backend & Persistent Profiles

- **Headless Chrome (`scripts/dot_chrome.mjs`):** The only supported backend.
  - Dynamically auto-detects profile configuration from system Google Chrome's `Local State` matching `user_name`, `email`, `name`, or `hosted_domain`.
  - Explicitly configured via `user_data_dir` in `~/.config/dot/config.json` (e.g. `~/.config/dot-headless-chrome-<name>`).
  - Initial seeding copies storage and cookies from matching system Chrome profile on first creation, then persists independently (never re-seeded if cookies or preferences exist).
  - Safely handles `SingletonLock`: verifies lock holder PID liveness, waiting politely if held by an active Chrome process, clearing only genuinely dead locks without killing peer processes.
  - Tolerates appended read-receipt timestamps (`Read 1:15 AM`) to prevent false draft conflicts.
- **Cross-host fallback:** When the local host has no Chrome (e.g. a Linux runner with no Chrome installed), `dot.sh` forwards the call via SSH to the configured `remote_host`. Set `DOT_REMOTE_HOST=<host>` to override, or `DOT_NO_REMOTE=1` to disable forwarding.

## Configuration & Environment Variables

- `DOT_ACCOUNT`: Account identifier (matched against `~/.config/dot/config.json` or local Chrome profiles). Can also be passed via `--account <name>`.
- `DOT_URL`: Target ChatGPT dot assistant URL. Can also be passed via `--url <url>`.
- `DOT_BACKEND`: Force backend (`chrome` or `auto`). The `aside` backend was retired; selecting it is a usage error.
- `DOT_CONFIG_FILE`: Custom path to dot JSON configuration (defaults to `~/.config/dot/config.json`).
- `DOT_REMOTE_HOST`: SSH host for Linux→Mac forwarding when local Chrome is unavailable (configured in `~/.config/dot/config.json` or environment).
- `DOT_ALLOW_REMOTE`: Set to 0 to disable remote SSH fallback (default: 1 on non-Darwin when local Chrome is unavailable and `remote_host` is configured). Set to 1 to attempt remote forwarding immediately before trying local Chrome.
- `DOT_NO_REMOTE`: Set to 1 to disable remote SSH forwarding.
- `DOT_CHROME_USER_DATA`: Explicit Chrome user data directory (defaults to account-specific persistent dir configured in `~/.config/dot/config.json`).
- `DOT_CLEAR_DRAFT`: When set to `1`, forces clearing any existing draft in the composer before typing and sending.
- `DOT_DRY_RUN`: When `1` (Chrome backend), types, verifies exact match, clears composer, and prints `DOT_DRYRUN_OK` without sending.