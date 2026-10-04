---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs). Platform-aware backend: Aside browser on macOS, headless Chrome secondary/fallback, transparent SSH bridge on Linux.
---

# /dot

Talk to the user's ChatGPT dot assistant using `scripts/dot.sh`. Platform-aware architecture:
- **macOS:** Aside browser (primary, account `u0` by default), headless Google Chrome secondary.
- **Linux:** Transparent SSH bridge to macOS host (`macbook` / `macbook-ts`), or local headless Chrome.

## Default: delegate, then monitor

The dot runs its own coders. When /dot is used for work, hand the work to the dot instead of coding it yourself: send a scoped request (goal, PR/branch, acceptance criteria, constraints such as merge gates), then monitor rather than block.

- Poll the dot every 5 minutes while it has work in flight. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim.
  - **Claude Code:** `/loop 5m <poll prompt>`, or a self-paced `/loop` with a 300s ScheduleWakeup.
  - **Codex (no `/loop`):** set a `/goal` whose exit criteria are the dot's deliverable (e.g. PR green and merged). Each turn, run the same poll, then wait about 5 minutes (`sleep 300` in a backgrounded or bounded command) before the next poll.
  - Stop polling when the deliverable is done or blocked on the user.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

## Actions

- Read: `dot.sh read [chars]` prints the tail of the page text (default 5000). While the dot is working the tail ends with `dot` / `Thinking` / `Working`.
- Send: write the message to a `mktemp` file, then `dot.sh send <file>`. Prefix every message with the sender identity, e.g. `From Claude (<model>, <worktree>): ...`. Never interpolate raw text into JS; the script JSON-encodes the file.
- To ask and get an answer: send, then poll `dot.sh read 3000` (separate calls, each under 60s) until the tail no longer ends in `Thinking` or `Working`.
- Run the script with a Bash timeout of at least 150s.

## Concurrency & Safety Rules

- Other agent sessions share this composer. ChatGPT restores a saved draft lazily on focus, so `send` focuses first, then inspects.
- **Stale draft:** A draft is only cleared if:
  1. It exactly matches our own message from an interrupted prior attempt, OR
  2. The exact text already appears in a previously submitted user message (`[data-message-author-role=user]`).
  If cleared, `send` prints `DOT_STALE_DRAFT_CLEARED`.
- **Unsent draft:** If an unsubmitted draft belonging to another session is present, `send` NEVER clears or overwrites it. It retries every 60s (`DOT_RETRY_SECS`) up to 30 min (`DOT_WAIT_SECS`) and sends once the composer is empty; exit 3 means still busy after the wait.
- **Verified send:** `DOT_SENT_VERIFIED` requires:
  1. Exact composer match after typing,
  2. Emptied composer after clicking send,
  3. The submitted text appearing in the conversation message list (`[data-message-author-role=user]`).
  Exit 4 means mismatched or unverified.
- Send only what the user asked to send. Do not post test messages.
- Avoid line-leading list markers (`1)`, `-`, `*`): the composer converts them to list formatting, which can cause mismatch detection. Use plain sentences.

## Backends

- **Aside (primary on macOS):** Uses `aside repl --account ${DOT_ACCOUNT:-u0}`. Fast (8-10s), zero-copy, handles concurrent multi-agent traffic without profile locks, and never touches personal Google Chrome profiles or credentials.
- **Chrome (`scripts/dot_chrome.mjs`):** Uses a dedicated persistent profile at `${DOT_CHROME_USER_DATA:-~/.config/dot-headless-chrome}` with zero file copying and zero temporary directory creation. Automatically detects `SingletonLock` held by orphaned Chrome processes targeting that specific user-data directory and cleans them safely.
  - *Initial Chrome Setup:* To populate the headless profile initially, launch Chrome once with `--user-data-dir=~/.config/dot-headless-chrome`, log into ChatGPT, and close it.

## Configuration & Environment Variables

- `DOT_URL`: Target ChatGPT dot assistant URL (defaults to user coordinator dot).
- `DOT_ACCOUNT`: Aside browser account identifier (defaults to `u0`).
- `DOT_BACKEND`: Force backend (`aside`, `chrome`, or `auto`).
- `DOT_REMOTE_HOST`: SSH host for Linux-to-Mac forwarding (probes `macbook`, `macbook-ts` by default).
- `DOT_CHROME_USER_DATA`: Custom Chrome user data directory (defaults to `~/.config/dot-headless-chrome`).
- `DOT_DRY_RUN`: When `1` (Chrome backend), types, verifies exact match, clears composer, and prints `DOT_DRYRUN_OK` without sending.
