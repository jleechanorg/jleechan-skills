---
title: "Read a Gemini / ChatGPT / Google-Doc share link as the user"
type: reference
date: 2026-07-20
verified_against: Gemini Flash share `Td7fA4pzuvMs` ("God of Murder Campaign Design")
status: HARDENED 2026-08-09 — guarded lifecycle, no fixed /tmp paths, no screenshots, EXIT-trap cleanup. Background only; the canonical lifecycle is in `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md` and MUST NOT be overridden by the snippets below.
---

# Reading auth-gated AI share links as the user

> **Background reference only.** The canonical guarded lifecycle for /browser is in `~/.claude/commands/browser.md` (the **Auth-gated share links** section) and `~/.claude/skills/browser-control/SKILL.md` (**Authorized credential reuse**). The snippets below MUST NOT override that canonical lifecycle — they exist to document the verified end-to-end pattern, not to be copy-pasted as a competing instruction set.

When the user gives you a `share.gemini.google/...`, `chatgpt.com/share/...`, or "anyone with the link" Google Doc URL and asks you to read the content, anonymous fetch (`curl`, `web_extract`, even headless `browser_navigate`) returns a **sign-in shell** with the conversation body loaded client-side only after Google / vendor auth.

The wrong move is to declare the task blocked and ask the user to paste the content. The right move is to read the page *as the user* by decrypting their Chrome cookies and injecting them into a headless Chromium session, using the **canonical guarded lifecycle** referenced above. Key invariants the lifecycle enforces:

- Cookie JSON + page text live only in **mktemp-generated private temp files** (`TMP_COOKIES`, `TMP_PAGE`), `chmod 600`, removed by EXIT trap on both success and failure. **No fixed predictable temp paths** — every credential-bearing write is a fresh `mktemp` file.
- **No `--screenshot`** is written by default. Screenshots are only allowed when the user explicitly requested visual evidence AND the page is known not to display secrets.
- **No HAR** is ever produced (the `browserclaw capture`/`learn`/`reverse` subcommands are banned for credential flows).
- The decrypt, inject, and Python scripts propagate nonzero exit via `set -euo pipefail`; cleanup runs even on failure.

This is what "use /browser or /browserclaw headless next time without asking" means — reach for the auth-aware recipe on the **first refusal**, not after being told.

## Verified recipe (background — see canonical lifecycle above)

The canonical 5-step guarded lifecycle is in `~/.claude/commands/browser.md` § **Auth-gated share links** (the `# 1.` through `# 6.` blocks ending in `cleanup_browser_share`). It uses `$TMP_COOKIES` / `$TMP_PAGE` from `mktemp -t browserclaw-XXXXXX.json` and `mktemp -t browserclaw-page-XXXXXX.txt`, `chmod 600` them, traps `cleanup_browser_share EXIT`, and removes both on both success and failure. **Do not substitute the older fixed-path snippets that previously lived in this file.**

The historical snippets in earlier versions of this file (using predictable cookie / page-text / screenshot paths) are RETIRED. If you see those fixed-path snippets anywhere else in the repo or in your own notes, replace them with the canonical guarded lifecycle — fixed predictable paths leak credentials across processes and survive long after the script exits.

## Why headless Chromium (not `channel=chrome`)

`channel=chrome` spawns the system Chrome binary which:
1. Briefly opens a visible window before transitioning to headless.
2. Can pollute the user's existing Chrome session with new tabs.

`channel=chromium` (bundled Chromium-for-Testing) is always headless, never opens a visible window, and is the right default for this workflow. **Verified 2026-07-18 multi-portal tax drive**: `channel=chrome --headless` opened a visible window despite the flag, so the user's #1 complaint ("use headless browser, stop doing normal browser") applies here.

## Truncation pitfall — scroll-to-bottom re-extraction

Gemini's share UI lazy-loads conversation history as the user scrolls. The canonical lifecycle's `--print-text 100000` captures the visible viewport but can **truncate mid-sentence** for long conversations (verified 2026-07-20: v7 truncated at "replaced by somethi").

**Fix:** re-extract with Playwright's scroll-to-bottom pattern, but write the result to a fresh `mktemp -t browserclaw-full-XXXXXX.txt` path, `chmod 600`, and trap-cleanup on EXIT. Use the orch-venv Python (has Playwright + browsers installed): `$HOME/.local/orch-venv/bin/python`. The system `python3` does NOT have Playwright browsers cached and will fail with `Executable doesn't exist at $HOME/Library/Caches/ms-playwright/chromium_headless_shell-1208/...`.

## Multi-turn conversation recovery (THE FINAL THING)

Gemini share pages render the full back-and-forth between the user and Gemini as `You said` / response pairs. When the user asks "make sure the final thing didn't miss anything I asked," the **last `You said` block** is what they want captured — not any of the intermediate drafts.

Detection recipe (write to a fresh mktemp path, not a fixed /tmp file):

```bash
TMP_FULL="$(mktemp -t browserclaw-full-XXXXXX.txt)"
chmod 600 "$TMP_FULL"
cleanup_browser_share_full() { rm -f "$TMP_FULL"; }
trap cleanup_browser_share_full EXIT INT TERM
grep -nE "^You said|^REVISED|^Campaign Design|^System:" "$TMP_FULL"
```

This prints every revision boundary. The final content to save is whatever comes **after the last `You said`** block in the file. Preserve intermediate drafts at `$TMP_FULL` for archival; only the final state lands in the user's artifact (wiki, world_reference, etc.). Cleanup runs on EXIT.

## What this works for (verified or expected to work)

| Source | Auth domain | Notes |
|---|---|---|
| Gemini share links | `%.google.com%` | Verified 2026-07-20 — 79 cookies, 169KB page text |
| ChatGPT shared chats | `%.openai.com%` | Same pattern; inject against `chatgpt.com/share/...` |
| Google Docs (with your account added, share-on) | `%.google.com%` | Same Google cookies; export via `gog docs export` instead if you just need the text |
| Notion shared pages | `%.notion.so%` + `%.notion.com%` | Decrypt both filters; Notion auth spans subdomains |
| Figma shared files | `%.figma.com%` | Same pattern; `figma.com/file/...` requires Figma session cookie |
| Linear shared issues | `%.linear.app%` | Same pattern; Linear session cookie is the auth |

## What this DOES NOT bypass

- **2FA / WebAuthn / passkey-only accounts** — the cookies decrypt, but the session might require re-prompt after N hours idle. Fix: user must have logged in within the cookie's lifetime.
- **Cloudflare Turnstile / DataDome / fingerprint challenges** — these check JS-side fingerprint, not cookies. Sites that reject headless Chromium's fingerprint (LinkedIn, X/Twitter, Facebook — observed 2026-07-05) will still bounce even with valid session cookies. **For fingerprint-sensitive targets, the browser-control skill's Aside-only exception overrides this entire recipe** — post a ONE-LINE display blocker, do not run the lifecycle at all.
- **MFA-gated Google accounts with no Chrome session** — if the user has never logged into Google in Chrome, there are no cookies to decrypt. Fall back to `gog`/`gws` CLI auth (separate Google OAuth flow) or ask the user to log into Chrome once.
- **Secret-bearing pages** (API-key creation/rotation, token pages, password/banking/recovery-code pages) — the canonical lifecycle's secret-bearing branch applies: NO `--print-text`, NO screenshots, NO HAR, NO persisted DOM. Use a bare Playwright script that emits only a boolean/status result and persists nothing.

## Anti-pattern: declaring blocked and asking the user to paste

The failure mode this recipe prevents:

> User: "Read this campaign and make a PR to save it in world_reference: https://share.gemini.google/Td7fA4pzuvMs"
> Agent (wrong): "Stopped at a blocker. The Gemini share link redirects to a sign-in page... Please paste the text."
> User: "use /browser or /browserclaw headless next time without asking"

`web_extract` returns "DDGS is a search-only backend and cannot extract URL content" (verified 2026-07-10, current behavior). `curl` returns the empty sign-in shell. `browser_navigate` returns the same. None of these are blockers — they're signals that the auth-aware recipe applies.

## Related

- Parent skill: `~/.hermes/skills/browserclaw/SKILL.md` (cookies decrypt + inject + CDP v20 bypass recipes)
- Sibling policy: `~/.hermes/skills/browser-headless-default/SKILL.md` (headless-only mandate; this recipe is the canonical "headless + auth" answer)
- Canonical guarded lifecycle: `~/.claude/commands/browser.md` § **Auth-gated share links** and `~/.claude/skills/browser-control/SKILL.md` § **Authorized credential reuse** — these are authoritative.
- `~/.claude/skills/google-credentials-fallback/SKILL.md` (fallback to `gog`/`gws` for Google Docs when the user has no Chrome session)
- SOUL.md `## COMMIT: finish-the-job` — declaring blocked without trying the auth-aware recipe is a finish-the-job violation