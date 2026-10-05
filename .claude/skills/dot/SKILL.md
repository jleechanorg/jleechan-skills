---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs). Platform-aware backend: headless Chrome (jleechan@worldarchitect.ai default) or Aside browser (u0 default).
---

# /dot

Talk to the user's ChatGPT dot assistant using `scripts/dot.sh`. Platform-aware architecture:
- **Default Account (`jleechan@worldarchitect.ai`):** Runs headless Google Chrome against a dedicated persistent profile (`~/.config/dot-headless-chrome-worldarchitect`) on Linux and macOS (`https://chatgpt.com/dots/01a1032f-aa98-7703-91bf-a35b1f95f01c`).
- **Account `u0` (`jleechan@gmail.com`):** Uses Aside browser on macOS, or transparent SSH bridge from Linux (`https://chatgpt.com/dots/01a0f819-a779-775c-9d48-8c6035034033`).
- **Account `test` (`jleechantest@gmail.com`):** Runs headless Google Chrome against a dedicated persistent profile (`~/.config/dot-headless-chrome-test`) on Linux and macOS (`https://chatgpt.com/dots/01a0fead-2ea7-71c9-9e87-ac4af984601c`).
- **Dynamic Multi-Account Support:** Specify any account via `--account <name>` or `DOT_ACCOUNT=<name>`. The engine auto-detects matching profiles from Chrome's `Local State` by matching `user_name`, `email`, `name`, or `hosted_domain`, and manages a dedicated persistent profile directory (`~/.config/dot-headless-chrome-<account_slug>`). Custom dot URLs can be supplied via `--url <url>` or `DOT_URL=<url>`.

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

## Backends & Persistent Profiles

- **Headless Chrome (`scripts/dot_chrome.mjs`):** Default backend for `jleechan@worldarchitect.ai` and custom accounts.
  - Dynamically auto-detects profile configuration from system Google Chrome's `Local State` (`~/.config/google-chrome/Local State` on Linux, `~/Library/Application Support/Google/Chrome/Local State` on macOS) matching `user_name`, `email`, `name`, or `hosted_domain`.
  - Uses dedicated persistent profiles (`~/.config/dot-headless-chrome-<account_slug>`, e.g. `~/.config/dot-headless-chrome-worldarchitect`).
  - Profiles are persistent across calls — never recreated afresh or re-seeded on subsequent invocations.
  - Automatically clears stale `SingletonLock` and terminates orphaned headless Chrome processes for that specific profile directory without interfering with user desktop Chrome.
  - Tolerates appended read-receipt timestamps (`Read 1:15 AM`) to prevent false draft conflicts.
- **Aside (macOS only):** Used for account `u0` (`jleechan@gmail.com`). Fast (8-10s), zero-copy, handles concurrent multi-agent traffic without profile locks.

## Configuration & Environment Variables

- `DOT_ACCOUNT`: Account identifier (`jleechan@worldarchitect.ai` by default, or `u0`, `test`, `worldarchitect`, or custom email/profile name). Can also be passed via `--account <name>`.
- `DOT_URL`: Target ChatGPT dot assistant URL (automatically defaults based on selected account or custom). Can also be passed via `--url <url>`.
- `DOT_BACKEND`: Force backend (`chrome`, `aside`, or `auto`).
- `DOT_REMOTE_HOST`: SSH host for Linux-to-Mac forwarding when using Aside (probes `macbook`, `macbook-ts`).
- `DOT_CHROME_USER_DATA`: Explicit Chrome user data directory (defaults to account-specific persistent dir `~/.config/dot-headless-chrome-<account_slug>`).
- `DOT_CLEAR_DRAFT`: When set to `1`, forces clearing any existing draft in the composer before typing and sending.
- `DOT_DRY_RUN`: When `1` (Chrome backend), types, verifies exact match, clears composer, and prints `DOT_DRYRUN_OK` without sending.
