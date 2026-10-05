---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs). Platform-aware backend: headless Chrome or Aside browser with dynamic multi-account routing.
---

# /dot

Talk to the user's ChatGPT dot assistant using `scripts/dot.sh`. Platform-aware architecture:
- **Dynamic Multi-Account Support:** Target any ChatGPT dot account via `--account <name>` or `DOT_ACCOUNT=<name>`.
- **Machine-Local Configuration:** Configured in `~/.config/dot/config.json` mapping accounts to URLs, backends, and profile match selectors.
- **Headless Chrome Backend:** Runs headless Google Chrome against dedicated persistent profiles (`~/.config/dot-headless-chrome-<account_slug>`) on Linux and macOS with automatic process lifecycle and lock cleanup.
- **Aside Backend:** Uses Aside browser when configured or running on macOS.
- **Transparent Cross-Host Forwarding:** Automatically bridges between Linux and macOS hosts when specialized backends (e.g. Aside on macOS or headless Chrome on Linux) are required.

## Machine Configuration (`~/.config/dot/config.json`)

Accounts, target dot URLs, and preferred backends can be declared per-machine in `~/.config/dot/config.json` without hardcoding personal data into the repository:

```json
{
  "default_account": "primary",
  "accounts": {
    "primary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "profile_match": "work-domain.com"
    },
    "aside_account": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "aside",
      "profile_match": "Default"
    }
  },
  "aliases": {
    "work": "primary"
  }
}
```

## Default: delegate, then monitor

The dot runs its own coders. When /dot is used for work, hand the work to the dot instead of coding it yourself: send a scoped request (goal, PR/branch, acceptance criteria, constraints such as merge gates), then monitor rather than block.

- Poll the dot with exponential backoff while it has work in flight: first poll 1 minute after the send, then 2 minutes later, then 5 minutes later, then every 10 minutes. Give up 4 hours after the first send if the dot has not started or done the work, and report that to the user with the last reply seen. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim. Any reply from the dot that shows real progress (a claimed lane, branch or PR) restarts the backoff at 1 minute and the 4-hour clock.
  - **Set a `/goal` for the wait** (via `/cmux-goal`): condition "the dot's deliverable exists and is verified at the source (PR open, RED then GREEN re-run by me, CI green), or 4 hours have passed since the first send". The goal keeps the session polling; do not rely on remembering to poll.
  - **Claude Code:** one-shot `ScheduleWakeup` calls at the backoff delays (60s, 120s, 300s), then a 600s wakeup repeated every 10 minutes; or a durable `CronCreate` `*/10 * * * *` after the first three polls. Record the first-send time (absolute, with timezone) in the poll prompt so each tick can compute the 4-hour deadline.
  - **Codex (no `/loop`):** the same `/goal`; each turn runs the same poll, then waits the next backoff interval (`sleep 60`, `sleep 120`, `sleep 300`, then `sleep 600` in a backgrounded or bounded command).
  - Stop polling when the deliverable is done, blocked on the user, or the 4-hour limit passes.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

## Actions

- Read: `dot.sh [--account <name>] [--url <url>] read [chars]` prints the tail of the page text (default 5000). While the dot is working the tail ends with `dot` / `Thinking` / `Working`.
- Send: write the message to a `mktemp` file, then `dot.sh [--account <name>] [--url <url>] send <file>`. Prefix every message with the sender identity, e.g. `From Claude (<model>, <worktree>): ...`. Never interpolate raw text into JS; the script JSON-encodes the file.
- Single send attempt: `dot.sh [--account <name>] [--url <url>] send-once <file>`.
- To ask and get an answer: send, then poll `dot.sh read 3000` (separate calls, each under 60s) until the tail no longer ends in `Thinking` or `Working`.
- Run the script with a Bash timeout of at least 150s.

## Concurrency & Safety Rules

- Other agent sessions share this composer. ChatGPT restores a saved draft lazily on focus, so `send` focuses first, then inspects.
- **Stale draft:** A draft is only cleared if:
  1. It matches our own message from an interrupted prior attempt, OR
  2. The text already appears in a previously submitted user message (`[data-message-author-role=user]`) (with relaxed substring matching tolerant of read-receipt timestamps like 'Read 1:15 AM'), OR
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
- **Limit Detection:** Watch for limit signatures in read output, error banners, or send failures:
  - "Your dot is on a break" / "hit our abuse prevention limit" / "Check back in a bit"
  - "You've reached your usage limit" / "usage limit reached"
  - "Too many requests in 1 hour" / "rate limit exceeded"
- **Mandatory Rotation:** When an account hits a limit or cooldown, immediately rotate to the next configured account (e.g. `primary` -> `secondary` -> `tertiary` -> ...) using `--account <next>`.
- **Never Stall on Cooldown:** Do not wait idle or block execution when an account is on a break if other accounts are available. Continue driving work across the remaining active accounts.
- **Automatic Script Support:** `dot.sh` implements automatic account rotation (`DOT_ROTATE_ON_LIMIT=1` by default) using the `rotation` sequence declared in `~/.config/dot/config.json`.

## Backends & Persistent Profiles

- **Headless Chrome (`scripts/dot_chrome.mjs`):** Default backend for custom and multi-account configurations.
  - Dynamically auto-detects profile configuration from system Google Chrome's `Local State` matching `user_name`, `email`, `name`, or `hosted_domain`.
  - Uses dedicated persistent profiles (`~/.config/dot-headless-chrome-<account_slug>`).
  - Profiles are persistent across calls — never recreated afresh or re-seeded on subsequent invocations.
  - Automatically clears stale `SingletonLock` and terminates orphaned headless Chrome processes for that specific profile directory without interfering with user desktop Chrome.
  - Tolerates appended read-receipt timestamps (`Read 1:15 AM`) to prevent false draft conflicts.
- **Aside (macOS only):** Fast (8-10s), zero-copy, handles concurrent multi-agent traffic without profile locks.

## Configuration & Environment Variables

- `DOT_ACCOUNT`: Account identifier (matched against `~/.config/dot/config.json` or local Chrome profiles). Can also be passed via `--account <name>`.
- `DOT_URL`: Target ChatGPT dot assistant URL. Can also be passed via `--url <url>`.
- `DOT_BACKEND`: Force backend (`chrome`, `aside`, or `auto`).
- `DOT_CONFIG_FILE`: Custom path to dot JSON configuration (defaults to `~/.config/dot/config.json`).
- `DOT_REMOTE_HOST`: SSH host for Linux-to-Mac forwarding when using Aside (probes `macbook`, `macbook-ts`).
- `DOT_REMOTE_LINUX`: SSH host for Mac-to-Linux forwarding when using Chrome backend (probes `jeff-ubuntu`, `jeff-ubuntu-ts`).
- `DOT_CHROME_USER_DATA`: Explicit Chrome user data directory (defaults to account-specific persistent dir `~/.config/dot-headless-chrome-<account_slug>`).
- `DOT_CLEAR_DRAFT`: When set to `1`, forces clearing any existing draft in the composer before typing and sending.
- `DOT_DRY_RUN`: When `1` (Chrome backend), types, verifies exact match, clears composer, and prints `DOT_DRYRUN_OK` without sending.
