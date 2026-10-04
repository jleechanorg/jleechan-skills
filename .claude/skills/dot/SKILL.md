---
name: dot
description: Use when the user invokes /dot or asks to "message the dot", "ask dot", "tell dot", "tell chatgpt dot", "check the dot", or read replies from their ChatGPT "dot" assistant (the one that coordinates coders and PRs) through the Aside browser.
---

# /dot

Talk to the user's ChatGPT dot (https://chatgpt.com/dots/01a0f819-a779-775c-9d48-8c6035034033) using `~/.claude/skills/dot/scripts/dot.sh`. Backend order: headless Google Chrome first, Aside as fallback.

## Default: delegate, then monitor

The dot runs its own coders. When /dot is used for work, hand the work to the dot instead of coding it yourself: send a scoped request (goal, PR/branch, acceptance criteria, constraints such as merge gates), then monitor rather than block.

- Poll the dot every 5 minutes while it has work in flight. Each poll runs `dot.sh read 3000`, then double-checks the claimed status at the source (`gh pr view`/`gh pr checks`, branch head SHA). Reply only when the dot asks something, stalls, or a check contradicts its claim.
  - **Claude Code:** `/loop 5m <poll prompt>`, or a self-paced `/loop` with a 300s ScheduleWakeup.
  - **Codex (no `/loop`):** set a `/goal` whose exit criteria are the dot's deliverable (e.g. PR green and merged). Each turn, run the same poll, then wait about 5 minutes (`sleep 300` in a backgrounded or bounded command) before the next poll.
  - Stop polling when the deliverable is done or blocked on the user.
- Verify the dot's claims at the source (git SHAs, `gh pr checks`, PR diffs) before relaying them, and don't duplicate files it has claimed.

## Actions

- Read: `dot.sh read [chars]` prints the tail of the page text (default 5000). While the dot is working the tail ends with `dot` / `Thinking`.
- Send: write the message to a `mktemp` file, then `dot.sh send <file>`. Prefix every message with the sender identity, e.g. `From Claude (<model>, <worktree>): ...`. Never interpolate raw text into JS; the script JSON-encodes the file.
- To ask and get an answer: send, then poll `dot.sh read 3000` (separate calls, each under 60s) until the tail no longer ends in `Thinking`.
- Run the script with a Bash timeout of at least 150s.

## Rules

- Other agent sessions share this composer. ChatGPT restores a saved draft lazily on focus, so `send` focuses first, then inspects.
- **Stale draft:** if the draft's text already appears in the conversation, it was already sent. `send` clears it and prints `DOT_STALE_DRAFT_CLEARED`.
- **Unsent draft:** otherwise `send` never clears or overwrites it. It retries every 60s (`DOT_RETRY_SECS`) for up to 30 min (`DOT_WAIT_SECS`) and sends once the composer is empty; exit 3 means still busy after the wait. Because that can exceed the 600s Bash cap, run `send` with `run_in_background`. `send-once` makes a single attempt.
- **Verified send:** `DOT_SENT_VERIFIED` requires an exact composer match before sending, then an emptied composer and the text visible in the conversation. Exit 4 means mismatched or unverified; `read` to check before resending.
- Send only what the user asked to send. Do not post test messages.
- Avoid line-leading list markers (`1)`, `-`, `*`): the composer converts them to list formatting, the typed text then mismatches and `send` exits 4 leaving the draft behind. Use plain sentences.

## Backends

- **Aside (primary on macOS):** Uses `aside repl --account u0`. Fast (8-10s), zero-copy, handles concurrent multi-agent traffic without profile locks, and never touches personal Google Chrome profiles or credentials.
- **Chrome (`scripts/dot_chrome.mjs`):** Uses a dedicated persistent profile at `~/.config/dot-headless-chrome` with zero file copying and zero temporary directory creation. Automatically serializes concurrent agent access and cleans up orphaned browser processes.
- `DOT_BACKEND=chrome|aside` forces one backend. `DOT_DRY_RUN=1 DOT_BACKEND=chrome dot.sh send-once <file>` types, verifies the exact match, clears the composer, and prints `DOT_DRYRUN_OK` without sending.

## Aside facts

- Primary backend on macOS. Uses `aside repl --account u0` (jleechan@gmail.com).
- Each `aside repl` call is a separate session: open, act, and read in one call. `openTab(url)` works; `attachBrowserTab` on the background dot tab hangs (CDP `Page.enable` timeout).
- The composer is the single `[contenteditable=true]` (`#prompt-textarea`); `locator.fill()` fails on it. Use click then `page.keyboard.insertText`. Send button: `button[data-testid=send-button]`.
- `page.waitForTimeout` does not exist; use `await new Promise(r => setTimeout(r, ms))`.

## Hosts

- **Mac (`jeffreys-macbook-pro`):** The Aside browser runs here, signed in to ChatGPT on account u0. `dot.sh` defaults to Aside locally and runs with zero file copying.
- **Linux (`jeff-ubuntu`):** `dot.sh` automatically detects Linux and seamlessly forwards commands to `macbook` (with Tailscale `macbook-ts` fallback) over SSH, transferring message files transparently for `send`. No manual SSH commands required.
