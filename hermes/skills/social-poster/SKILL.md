---
name: social-poster
version: 0.1.0
description: |
  Draft social-media posts for LinkedIn, Hacker News, Twitter/X, Reddit, Threads,
  Facebook, Instagram, Mastodon, Bluesky, and Dev.to. Each draft is staged in an
  Aside browser tab (signed-in persistent session), screenshotted, and surfaced
  for human review. Posts ONLY go live after the user types "POST APPROVED"
  (per-platform allowed: "POST APPROVED linkedin,hackernews"). Pure draft mode by
  default — no LLM augmentation, no auto-post, no exceptions.
when_to_use: |
  Use when the user asks to draft a post for any social platform, share a project
  on LinkedIn/HN/Twitter, post to Reddit, prepare a Show HN, draft an Instagram
  caption, or any "draft a post" / "post to <platform>" / "share on social" /
  "/social <intent>" request. Also fires on "/social <intent>" slash command.
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
  - Grep
triggers:
  - "draft a social post"
  - "draft a post"
  - "post to social"
  - "post to linkedin"
  - "post to hacker news"
  - "post to reddit"
  - "post to twitter"
  - "post to threads"
  - "post to facebook"
  - "post to instagram"
  - "draft linkedin post"
  - "draft hacker news post"
  - "draft reddit post"
  - "draft tweet"
  - "draft twitter thread"
  - "draft instagram caption"
  - "draft threads post"
  - "show hn"
  - "social poster"
  - "/social"
context: inline
---

# Social Poster — Draft-Only, POST APPROVED Gated

## Twitter/X browser workflow

This section takes precedence over generic staging/auth recipes for Twitter/X.
Draft and stage requests remain unpublished. An explicit publish or crosspost
request selects the publishing workflow; it does not remove the mandatory
`POST APPROVED` confirmation or platform allowlist. Ask for any missing required
confirmation after the exact text, account, and media are reviewable. Never turn
this into standing permission for future posts.

1. Reuse a supported browser session and inspect the signed-in handle before
   drafting or staging. If signed out, prefer the normal **Continue with Google**
   flow when offered, select the intended existing Google account, and verify
   the resulting X handle. A Google email alone does not prove the X identity.
2. For a normal login failure, try one supported recovery (return to the official
   login page or select the intended existing account), then report the exact
   blocker. Stop for human-only challenges or denied actions. Never extract or
   decrypt cookies, tokens, passwords, or browser credential stores; never bypass
   access denial or switch to a hidden API to work around a blocked UI.
3. Read the source post and retain its original text and original photo/video
   when requested. Verify the uploaded media preview; do not silently replace
   the original asset with a screenshot or omit it. Report inaccessible media.
4. Inspect the verified account's recent posts for the source link and matching
   text/media before submission. If a matching post exists, return its permalink
   rather than creating a duplicate. If history cannot be checked, resolve that
   uncertainty before posting. Recheck after any timeout or uncertain submission
   before retrying; a timeout is not proof that posting failed.
5. Before shortening text or building a thread, check the current account's
   composer for supported long posts. When the full source fits, prefer one post
   with the original media unless the user requested a thread. If it does not
   fit, prepare a faithful shorter draft or thread for review. Do not assume a
   subscription or a fixed limit from an old template; verify the full text
   remains in the composer with no truncation or limit warning.
6. Verify the exact visible text, intended handle, and media before the gated
   publish action. Submit once. Then open the resulting permalink and verify
   the author handle, visible full text (expand when needed), and original media.
   Return the permalink with the verification result. A cleared composer or
   success toast alone is not proof; report an uncertain outcome without retrying
   until the profile/history check establishes whether the post exists.

## Contract

1. **Draft, never post** — default mode produces text files + browser-staged tabs + screenshots. No network mutation without explicit `POST APPROVED`.
2. **Persistent browser session** — uses `aside` CLI (signed into $USER@gmail.com) to keep one session across multiple platform tabs; never spawns a fresh Playwright Chromium per platform.
3. **Per-platform conformance** — character limits, title rules, hashtag placement, threading, self-promo ratios checked at draft time (no "fix it after posting").
4. **Reddit 10/90 + per-sub rules** — every Reddit draft is checked against the live-verified rules in `references/subreddit-rules.md` (r/LocalLLaMA, r/Rag, r/OpenAI verified via Aside probe 2026-07-05).
5. **POST APPROVED token** — `scripts/post_approved.py` checks for literal `POST APPROVED` (or per-platform like `POST APPROVED linkedin,hackernews`) before clicking any submit button. Without the token, exits code 2 with "BLOCKED — no POST APPROVED token".
6. **No LLM augmentation by default** — pure templating. To enable LLM refinement, pass `--use-llm` (which routes through your existing `~/.hermes/config.yaml` auxiliary provider; never hardcodes API keys).
7. **Auto-stage on /social** — when invoked as `/social <intent>`, run Phase 1 + Phase 2 back-to-back without asking. The user invoked the command → staging is implied. (Jeffrey preference, 2026-07-17: "stage it and next time stage without asking".) Skip staging ONLY if Aside extension bridge is down or all drafts are intentionally login-wall / load_only / no_recipe.

## Supported Platforms

| Platform | Template | Has web compose? | Notes |
|----------|----------|------------------|-------|
| LinkedIn | `templates/linkedin.md` | ✅ | long-form + 300-char short variant |
| Hacker News | `templates/hackernews.md` | ✅ | "Show HN:" prefix when self-promo; title ≤80 chars |
| Twitter/X | `templates/twitter.md` | ✅ | single tweet + thread; hashtags at end of last tweet only |
| Reddit | `templates/reddit.md` | ✅ | one file per subreddit; text-post preferred over link-post |
| Threads | `templates/threads.md` | ✅ | ≤500 chars, casual |
| Facebook | `templates/facebook.md` | ✅ | medium-length, link-friendly |
| Instagram | `templates/instagram.md` | ⚠️ no web compose | caption + 30-hashtag block; surfaces mobile instructions |
| Mastodon | `templates/mastodon.md` | ✅ | 500-char default; configurable instance |
| Dev.to | `templates/devto.md` | ✅ | markdown article format |

## Phases

### Phase 1 — Draft (deterministic, no browser)

Run `scripts/draft_social_post.py` with intent + key-points + link + platforms. Produces per-platform files in `--out <dir>`. Character-limit hard-rejects; spam-rule soft-warns.

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/draft_social_post.py
python3 "$PY" \
  --intent "announce jleechanclaw open-source release" \
  --key-points "AI agent orchestration, hermes deploy pipeline, skill framework" \
  --link "https://github.com/jleechanorg/jleechanclaw" \
  --platforms linkedin,hackernews,twitter,reddit,threads,facebook,instagram,mastodon,devto \
  --reddit-subs "LocalLLaMA,Rag,OpenAI" \
  --image "" \
  --out /tmp/drafts/social-2026-07-06/
```

Output: one `.md` file per platform (or per subreddit for Reddit). Filename-safe slugs.

### Phase 2 — Stage in Aside (browser, no auto-post)

**Prefer the MCP path (`stage_in_aside_mcp.py`) when available.** The `aside repl` CLI silently no-ops on programmatic paste (lesson #11; verified 2026-07-17 across 9/11 platforms failed despite "compose-ready" status). The HTTP MCP at 127.0.0.1:8013/mcp with `openTab()` + Playwright `locator().fill()` reliably pastes when the session is healthy.

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/stage_in_aside_mcp.py
python3 "$PY" --drafts /tmp/drafts/social-2026-07-17/
# allowlist sub-stage, e.g. only HN + Twitter for retry runs:
python3 "$PY" --drafts /tmp/drafts/social-2026-07-17/ --only hackernews,twitter
```

Falls back to the legacy `aside repl` script when MCP is unreachable:

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/stage_in_aside.py
python3 "$PY" --drafts /tmp/drafts/social-2026-07-17/
```

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/stage_in_aside.py
python3 "$PY" --drafts /tmp/drafts/social-2026-07-06/
```

**Contract (v3, 2026-07-11):** The script now enforces paste-and-verify. For each platform:

1. Opens a new Aside tab on the platform's compose URL.
2. Optional trigger click (LinkedIn "Start a post", Facebook "What's on your mind").
3. Pastes the draft into the relevant field via per-platform paste function:
   - `react_textarea` — vanilla `<textarea>` / `<input>` (Reddit, HN, Mastodon, Dev.to)
   - `exec_command` — contentEditable (Twitter, LinkedIn, Facebook, Threads); uses `document.execCommand('insertText', false, text)` after `el.focus()` — the only reliable pattern for React-controlled contentEditable fields.
4. **Reads the field back** with `verify_text(selector)` and compares against expected draft length (≥70% threshold to allow for trailing whitespace stripping).
5. Captures post-paste screenshot → `/tmp/drafts/social-2026-07-06/screenshots/<platform>.png`.
6. Sets status:
   - `"staged"` — paste verified, screenshot saved
   - `"paste_failed"` — compose form loaded but text didn't persist (user must paste manually)
   - `"login_wall"` — page is a sign-in screen, no paste attempted
   - `"load_only"` — Instagram (no web compose)
   - `"failed"` — Aside subprocess error (e.g. extension bridge dead)

The script will NOT claim a platform is "ready" unless the draft text was verified inside the field. Vision-verify at least one screenshot per platform after staging for a final cross-check.

**Aside recipes** for each platform's compose URL live in `references/aside-recipes.md`.

### Phase 3 — Surface to user

Print all draft file paths + screenshot paths. Attach screenshots via Slack `MEDIA:/path` (per `evidence-attach-to-slack` skill). Ask: *"POST APPROVED?"*

### Phase 4 — Post (gated)

ONLY after the user types `POST APPROVED` (literal, case-insensitive, optionally with comma-separated platform allowlist), run:

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/post_approved.py
python3 "$PY" \
  --drafts /tmp/drafts/social-2026-07-06/ \
  --approval-token "POST APPROVED" \
  [--platforms linkedin,hackernews]  # if omitted, posts all staged
```

Behavior per platform:
- LinkedIn / HN / Twitter / Reddit / Threads / Facebook / Mastodon / Dev.to → click submit, capture post-URL.
- Instagram → surface draft caption as text + print mobile instructions (no web compose). Manual copy-paste from phone.

Posting log written to `--drafts/posted.json` with timestamps + captured URLs.

## Safety Gates

1. **`POST APPROVED` required** — see `scripts/post_approved.py` `check_approval()` function. Hard exit 2 if missing.
2. **`--dry-run`** — default behavior of `post_approved.py` if invoked without an approval token. Prints staged tabs and exits.
3. **Per-platform allowlist** — `POST APPROVED linkedin` only posts LinkedIn. Comma-separated = OR. Default = all staged platforms.
4. **No silent failures** — any platform that fails to post writes to `posted.json` with `{"status": "failed", "error": "..."}`. User is notified.
5. **Audit log** — every draft run writes `--out/manifest.json` with timestamp, intent, platforms, character counts, spam-rule warnings.

## Subreddit Selection (verified 2026-07-05)

| Content type | Primary | Secondary | Tertiary |
|---|---|---|---|
| Open-source / local AI tool | r/LocalLLaMA | r/OpenSourceAI | r/singularity (opinion-only) |
| RAG / retrieval / vector DB | r/Rag | r/LocalLLaMA | — |
| Coding agent / dev tool | r/OpenAI (text post) | r/LocalLLaMA | — |
| General AI news / opinion | r/OpenAI | r/LocalLLaMA | r/ClaudeAI (Claude-specific) |

**Banned / avoid:**
- r/AItools, r/AutoGen, r/LMStudio → banned subs.
- r/singularity, r/AGI, r/Futurism, r/MachineLearning → zero self-promo.
- r/philosophy, r/ProgrammerHumor → AI content banned outright.

## Anti-Patterns

- ❌ Auto-posting without `POST APPROVED` (bypasses the safety gate)
- ❌ Using `mcp__playwright-mcp__*` for localhost testing — use `aside` (signed-in session)
- ❌ Calling `aside show_browser` / headed mode without explicit opt-in (headless-only default)
- ❌ Hardcoding API keys in `draft_social_post.py` (LLM augmentation must route through `~/.hermes/config.yaml`)
- ❌ Stripping 10/90 framing from Reddit drafts ("I built this, here's the link") — guarantees removal
- ❌ Posting the same draft verbatim across Reddit subs (each sub has different norms; per-sub files required)
- ❌ Posting link-only to r/OpenAI — requires text post + context (verified rule)
- ❌ Clicking submit in Phase 2 (stage-only)
- ❌ **Treating `draft_social_post.py` output as final without reading it** — the templater hallucinates key-points into the wrong slots when the intent is a commentary/opinion piece rather than a project announcement (e.g. "Fable AI oneshot a 2D game" gets turned into "jleechanclaw does X"). **Always read every generated `.md` file before staging.** If templating misfires, hand-author the drafts directly (write `.md` files in `--out`) and re-run staging on the hand-authored files. Worked example: `references/fable-2d-game-2026-07-11.md`.
- ❌ **Trusting `stage_in_aside.py`'s "compose-ready" DOM verdict without vision-verification.** The script's DOM-detector only checks for selectors like `input[name="title"]`; it does NOT verify that the text was actually pasted into the field. Programmatic paste via React setter / contentEditable frequently fails silently on Twitter, LinkedIn, HN, and Reddit modals. After every staging run, vision-verify AT LEAST ONE screenshot per platform (`vision_analyze("Is the draft text visible in the compose field, or is it empty?")`). If empty, the compose form is loaded but paste didn't stick — user must paste manually from the `.md` files.
- ❌ **Trusting `listBrowserTabs()` as proof the platform is signed in** — it proves the *tab* is signed in, but `openTab(compose-url)` may still hit a session-revalidation redirect to a login wall (LinkedIn, Facebook, Dev.to, Mastodon, Threads all did this on 2026-07-11). The source-of-truth check is: vision-verify the staged screenshot shows a compose form with user avatar/handle visible, NOT a login wall.
- ❌ **Staging a Twitter draft that exceeds 280 chars (verified 2026-07-17).** The compose modal accepts arbitrary input but disables the Post button (red highlight + "-666" counter visible) once the limit is exceeded. The drafter must keep single-tweet drafts ≤280 chars; longer content needs a `--thread` flag that splits into N tweets. The default `templates/twitter.md` does NOT enforce this — check after drafting.
- ❌ **Splitting the staging workflow across multiple MCP `tools/call` invocations** (verified 2026-07-17). See lesson 19 — each `openTab` opens a fresh tab, so call 2's paste lands on a different form instance than call 1's open. Always bundle `(openTab → fill → verify → screenshot)` in ONE IIFE per platform.

## LinkedIn login-wall unblock signals (verified 2026-07-11)

When LinkedIn staging returns a "Welcome back" password screen, do NOT conclude LinkedIn is unreachable. Check for these one-click unblock signals in the screenshot before declaring the platform blocked:

1. **Google One-Tap prompt** (top-right overlay, dark gray box, "Sign in to LinkedIn with Google" + blue "Continue as Jeffrey" button) — one click unblocks the session.
2. **Continue with Google button** (white button below "Sign in" with Google G logo) — same OAuth flow, one click.
3. **Sign in with Apple button** — same UX as Google.

If any of these are visible AND the email shown matches `$USER@your-project.com`, the user can unblock LinkedIn in 1-2 clicks. Tell them which button to click.

If NO unblock signal is visible (just an empty password field), the session is fully expired and the user must type their password.

## Output Format

After Phase 3, the skill reply includes:

```
## social-poster draft ready

- Drafted: 9 platforms (linkedin, hackernews, twitter, reddit x3, threads, facebook, instagram, mastodon, devto)
- Staged: 9 Aside tabs open (URLs: …)
- Screenshots: /tmp/drafts/social-2026-07-06/screenshots/ (9 PNGs)
- Manifest: /tmp/drafts/social-2026-07-06/manifest.json

**To post:** reply with `POST APPROVED` (all) or `POST APPROVED <platforms>`.
**To revise:** tell me what to change and I'll re-draft + re-stage.
```

Screenshots attached via `MEDIA:/path/to/png` for inline Slack preview.

## Trigger → Action Map

| User says | Action |
|-----------|--------|
| `draft a post about X` | Phase 1 only |
| `draft + stage a post about X` | Phase 1 + Phase 2 |
| `POST APPROVED` | Phase 4 (all staged) |
| `POST APPROVED linkedin,twitter` | Phase 4 (only those two) |
| `revise the linkedin draft` | Re-run Phase 1 + Phase 2 for that platform only |
| `cancel drafts` | Close Aside tabs, keep files |
| `draft posts for <LinkedIn/Twitter URL>` | **Commentary-source path:** extract source body via `curl + og:description regex` (NOT `web_extract`), hand-author drafts (template misfires on commentary), see `references/fable-2d-game-2026-07-11.md` |

## Phase 3.5 — Posting the user-facing summary (Slack/Discord), MCP-down aware

The draft summary message to the user can land on Slack/Discord/chat. When the messaging MCP is available, use it. **When `mcp__slack__conversations_add_message` returns `not_in_channel` or the server reports "unreachable after N consecutive failures", fall back to the user's XOX-P (user token) via curl** (per SOUL.md `slack-cross-workspace-fallback-xoxp`):

```bash
TOKEN="$SLACK_USER_TOKEN"
curl -fsS -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary @<(jq -n --arg txt "$BODY" \
    '{channel: "<chan>", thread_ts: "<ts>", text: $txt}')
```

The XOX-P fallback posts as the user (not the Hermes bot identity). **Say so in the body if it might confuse the user.** Do NOT stall with "iteration budget exhausted" — the post still goes through. After the fallback, continue with the standard "POST APPROVED?" prompt.

For non-Slack chat (Discord/Telegram/Discord DM/etc.) the same fallback pattern applies: `curl` to the platform's REST endpoint with the user token rather than waiting for the MCP to recover.

## Files

- `scripts/draft_social_post.py` — deterministic drafter
- `scripts/stage_in_aside.py` — opens Aside tabs + screenshots (legacy `aside repl` path — silent paste failure mode)
- `scripts/stage_in_aside_mcp.py` — **preferred**: opens Aside tabs + pastes via HTTP MCP at 127.0.0.1:8013/mcp. One MCP call per platform bundles open + paste + verify + screenshot on a single `page` object (avoiding the "fresh tab = lost paste" failure). Verified selectors for HN, Twitter, Mastodon, Reddit ×3, Dev.to, LinkedIn, Facebook, Threads (2026-07-17).
- `scripts/cookie_inject_and_stage.py` — uses `browserclaw cookies decrypt` + Playwright Chrome with injected cookies to stage + paste drafts (for platforms where Aside is not signed in)
- `scripts/post_approved.py` — gated publisher
- `templates/*.md` — 9 platform templates
- `references/subreddit-rules.md` — live-verified per-sub rules
- `references/platform-character-limits.md` — hard limits + soft guidance
- `references/aside-recipes.md` — `aside repl` snippets per platform
- `references/platform-session-status.md` — per-platform cookie injection + anti-bot results (verified 2026-07-05). **Playwright Chrome only — see `aside-repl-session-state.md` for `aside repl`-based staging.**
- `references/blog-post-to-gdoc.md` — recipe for "draft a blog post in Google Docs" (canonical `gws docs` path + local-markdown fallback when gws OAuth is unauthenticated).
- `references/aside-repl-session-state.md` — verified auth state per platform for `aside repl` workflows (2026-07-06). Includes the `listBrowserTabs()` live-tab probe recipe, the `document` scope-doesn't-persist-across-REPL-calls pitfall, and per-platform paste workarounds for LinkedIn contentEditable / Facebook click-first / Twitter thread pagination.
- `references/aside-repl-playwright-pattern.md` — verified `openTab()` returns a Playwright `Page` object with `screenshot()` (Buffer→base64), `evaluate()`, `locator()`, `frameLocator()`. Includes 6 working paste/click/inspect idioms. Source of truth for the 2026-07-06 staging rewrite.
- `references/fable-2d-game-2026-07-11.md` — worked example for commentary/opinion drafts (NOT project announcements). Documents the Fable 2D-game run, the templater failure mode, the vision-verify matrix, and the recommended workflow for future commentary runs.
- `references/fable-quota-skill-2026-07-15.md` — worked example for **commentary/opinion about a third-party capability + a personal artifact (gist/skills)**. Documents lessons 15 (`require('fs')` is not in the REPL; capture screenshots via base64 stdout redirect), 16 (Mastodon URLs: `/compose` is 404, use `/publish`), and 17 (LinkedIn share-box trigger has obfuscated classes; programmatic click fails). Also documents the Phase 3.5 MCP-down fallback for posting the summary via XOX-P curl when `mcp__slack__conversations_add_message` is unreachable.
- `tests/test_*.py` — unit + integration tests
- `references/staged-vs-pasted-verification.md` — **CRITICAL**: how to verify drafts actually got pasted into compose forms (vs. just having the page loaded). Use the explicit "what text is in the field?" vision prompt + the verification snippet. The stage script's `staged: True` is not enough.
- `references/aside-mcp-cli-gmail-profile.md` — Aside automation via HTTP MCP at 127.0.0.1:8013/mcp with `mcp-session-id` header flow + gmail (u0) profile. Reusable Python client snippet. The most reliable automation path when the Chrome extension bridge is alive. **Includes the verified openTab + locator.fill() + screenshot pipeline, per-platform selector table for HN / Twitter / Mastodon / Reddit / Dev.to / LinkedIn / Facebook / Threads, and 7 stage pitfalls (MCP degradation, Reddit fragility, login walls, subprocess.run vs Popen) verified 2026-07-17.**

## Operator preferences (captured 2026-07-11)

Jeffrey's standing directives for this skill — embed these in any automation flow:

1. **Headless only.** Never open a visible browser window. Use `browserclaw cookies inject --headless` or headless Playwright (`p.chromium.launch(headless=True)`). If a step would spawn a GUI window (e.g. `open -a "Aside"` or `aside "Open X"` without headless mode), prefer the headless equivalent or surface the limitation rather than opening the GUI.
2. **Use `/browserclaw` to copy Chrome cookies as needed.** Cookies are the persistent auth substrate; decrypt them from the local Chrome / Aside cookie DB rather than asking the user to log in or paste tokens. If `browserclaw` CLI is broken (see browserclaw SKILL.md broken-editable-install pitfall), fall back to hand-loading the Playwright `storage_state` JSON written by a previous successful decrypt.
3. **`POST APPROVED` gating is mandatory.** No auto-post, no scheduled post, no background post. The literal token `POST APPROVED` (optionally `POST APPROVED <platforms>`) must appear in the current session before any submit/click-post action.
4. **Vision-verify, don't DOM-detect.** The script's DOM verdict and the actual field contents can disagree — programmatic paste via React setter / contentEditable frequently fails silently. After every staging run, vision-verify at least one screenshot per platform with the explicit question "What text is currently inside the compose field?" before claiming the platform is "ready".

## Critical lessons (from real sessions, not theoretical)

0. **`staged` ≠ `pasted`.** The stage_in_aside.py script labels every successfully-navigated compose form as "staged" even when the paste silently failed (React-controlled-field re-render ate the programmatic input). **Vision-verify the actual TEXT inside the title input + body textarea, not just the page state.** A logged-in compose form with empty fields looks identical to a logged-in compose form with empty fields — vision models will say "compose form ready" either way unless explicitly asked "what text is currently inside the field?" (lesson from 2026-07-11 Fable-2D-game run, user pushback: "all of those drafts are obviously wrong and just random login screens so youre not even close to working"). See `references/staged-vs-pasted-verification.md` for the verify-paste checklist + reusable paste verification snippet.

0a. **Use `--account u0` ($USER@gmail.com) for `aside repl` automation.** Default active is `u1` (your-project.com) and the extension bridge can be more brittle on that profile. Verified 2026-07-11 — user pushed "use $USER@gmail.com profile next time and use the mcp or cli its supposed dto work". See `references/aside-mcp-cli-gmail-profile.md`.

0b. **Aside HTTP MCP at 127.0.0.1:8013/mcp is the most reliable automation path** (when the extension bridge is alive). Tools surface: just `repl` (single tool wrapping the persistent JS REPL). MCP initialize handshake requires reading the `mcp-session-id` header from the response and sending it on subsequent calls + `notifications/initialized`. Top-level `await` is NOT allowed in the REPL — wrap in `(async () => { ... })();`. The REPL has persistent scope (vars persist across calls), `fs` module via `node:fs/promises`, `display()` for inline image preview, `sleep(ms)`, `fetch()` with user cookies. See `references/aside-mcp-cli-gmail-profile.md` for the full request flow + reusable client snippet.

1. **`aside account list` does NOT show per-platform auth state.** It only shows the active Google account ID. To gauge whether LinkedIn/Twitter/Facebook/etc. are actually signed in, run `aside repl "const tabs = await listBrowserTabs(); console.log(tabs.map(t => t.url).join(' | '))"`. A signed-in tab on the platform = the session is valid, even if a fresh `openTab(compose-url)` shows a login wall (compose-URL navigation may trigger session re-auth).

2. **`document` scope does NOT persist across `aside repl` calls.** Each call gets a fresh JS context. Multi-step workflows (open → click → paste → verify) must be bundled in ONE async IIFE in a single call. Screenshot via `annotatedScreenshot(pageObj)` returned from `openTab()`, not `annotatedScreenshot(null)`.

3. **Programmatic paste into LinkedIn/Twitter/Facebook compose modals is unreliable.** Twitter's textarea + React setter trick works in a single bundled call. LinkedIn's contentEditable div + `el.innerHTML = text` works but React state may not sync (manual paste is more reliable). Facebook requires click-first on "What's on your mind, [Name]?" before the modal opens. **Default workflow: stage + screenshot the empty compose area, let the user paste manually.** This avoids the React control gymnastics entirely and the user still gets visual proof the compose UI is loaded.

4. **`POST APPROVED` is mandatory for any submit/click-post action.** Drafts may be staged freely. Posting requires the literal `POST APPROVED` string (optionally with comma-separated platform allowlist). No exceptions, no "looks approved" heuristics. See `scripts/post_approved.py` `check_approval()` for the gate logic.

5. **`aside session` ≠ `account list` ≠ Chrome cookie DB.** The source of truth is `listBrowserTabs()`. If the user says "I'm signed in to LinkedIn", verify with that probe before declaring a platform unreachable.

6. **`openTab(url)` returns a Playwright `Page` object**, not a serializable tab descriptor. Use `p.screenshot()` directly (returns a Buffer that base64-encodes for stdout), or `p.locator(...)` / `p.evaluate(() => ...)` for DOM ops. `annotatedScreenshot(null)` throws `Cannot read properties of null (reading 'snapshot')`; `annotatedScreenshot(pageObj)` works but `p.screenshot()` is simpler. See `references/aside-repl-playwright-pattern.md` for the verified idioms.

7. **Reddit compose URL must end in `?selftext=true`.** `https://old.reddit.com/r/<sub>/submit` lands on the link-post form by default, which navigates through the "link vs text" tab UI and triggers a session re-auth redirect. The `?selftext=true` param lands directly on the text-post form with title (textarea[name="title"]) + body (textarea[name="text"]) fields visible. `stage_in_aside.py`'s compose URL for Reddit MUST include this param. Verified 2026-07-06 for r/LocalLLaMA, r/OpenAI, r/Rag — all three compose forms loaded immediately with no auth redirect when the `?selftext=true` suffix was used.

8. **Vision-verify compose-vs-login, don't DOM-detect.** A DOM-only check like `document.querySelector('input[name="title"]')` can give false negatives if the page is still loading. The deterministic check is `p.screenshot()` → save → `vision_analyze(image_url, "Is the compose form for posting to r/X visible, with title input and body textarea? Or is it a login wall?")`. The user said "Many of these screenshots are login screens I wanna find the draft post screen / Still not good enough" on 2026-07-06 — the lesson: ALWAYS confirm by vision, never trust URL or DOM-only state when the user wants visual proof.

9. **Aside daemon restart = sessions break.** If `aside repl` returns "fetch failed" and you `pkill -f AsideDaemon` to recover, all open tabs are lost. Subsequent `openTab()` calls hit login walls even though the underlying Chrome cookie DB still has valid sessions, because Aside's tab-object state is gone. `listBrowserTabs()` returns `TOTAL_TABS 1` (a single fresh tab) instead of the prior 17-tab state. **Fix:** instead of `pkill`, try `open -a "Aside"` first — sometimes the daemon recovers without losing tabs. If you must restart, plan for a sign-in re-pass on platforms that were "previously signed in."

10. **`draft_social_post.py` cannot tell a project announcement from a commentary/opinion piece.** When the source URL is a personal reaction to a third-party capability (e.g. "Fable AI oneshot a 2D game from my text sim"), the templater will hallucinate the user's open-source project as the subject and stuff every key-point into the wrong slot. **Always read every generated `.md` before staging.** If misfires, hand-author directly into the same files. Worked example: `references/fable-2d-game-2026-07-11.md`.

11. **Compose-ready ≠ paste-stuck (re-confirmed 2026-07-11).** Even when the compose form is loaded and vision-verified, programmatic paste via React setter / contentEditable frequently fails silently on Twitter, HN, Reddit, and LinkedIn. After staging, vision-verify ONE screenshot per platform with the question "What text is actually in the compose field? Empty or has content?" If empty, the form loaded but paste didn't stick — surface this to the user as "compose form ready, paste manually from the `.md` file." Do NOT claim the draft is staged-and-pasted when the field is empty.

12. **`web_extract` cannot fetch LinkedIn post bodies (re-confirmed 2026-07-11).** The `ddgs` backend returned `ddgs is a search-only backend and cannot extract URL content`. Workaround: `curl -A "Mozilla/5.0 ... Chrome/126.0.0.0 ..." <linkedin-url> -o /tmp/post.html`, then `python3 -c "import re; m = re.search(r'<meta[^>]+property=\"og:description\"[^>]+content=\"([^\"]+)\"', open('/tmp/post.html').read()); print(m.group(1) if m else 'NONE')"`. LinkedIn embeds the full post body in og:description.

13. **Aside MCP `repl` tool: SKIP `notifications/initialized` (verified 2026-07-11).** The MCP initialize handshake works, but if you send `notifications/initialized` after the initialize, subsequent `tools/call` requests return `Bad Request: No valid session ID provided` even though the session-id header is correctly attached. **The working pattern:** init → read `mcp-session-id` from response header → call `tools/call` immediately, skip `notifications/initialized`. Also: use top-level `await` directly in REPL code (the REPL is in module mode) — DO NOT wrap in `(async () => { ... })();` IIFEs because the IIFE swallows `console.log` output via the SSE stream. Top-level `console.log('HELLO')` works synchronously; `await fetch('https://api.ipify.org')` then `console.log(await r.text())` works async.

14. **`browserclaw` CLI broken if its editable worktree is deleted (verified 2026-07-11).** Symptom: `browserclaw --help` returns empty; running any `browserclaw cookies ...` command returns `ModuleNotFoundError: No module named 'browserclaw.cli'`. Diagnosis: `pip show browserclaw` shows `Editable project location: $HOME/.worktrees/browserclaw-cookies`; if that path no longer exists, the editable install in `.local/orch-venv/lib/python3.13/site-packages/_editable_impl_browserclaw.pth` points to a nonexistent directory and the module fails to import. Fix options: (a) `pip install -e /path/to/browserclaw/repo --force-reinstall --no-deps` to repoint the .pth, (b) `pip uninstall browserclaw && pip install browserclaw` to drop the editable install, (c) recreate the worktree at the original path. The Playwright + cookie inject pattern still works without browserclaw — see `headless_stage_paste.py` for a self-contained alternative.

15. **`require('fs')` is NOT available in the Aside REPL (verified 2026-07-15).** Trying `require('fs').writeFileSync(...)` inside `aside repl` returns `Error: External modules are not available in the REPL.` The screenshot Buffer from `p.screenshot()` cannot be saved directly from inside the REPL. **The verified pattern** — capture the base64 via `console.log` then grep+decode in the parent shell:

```bash
aside repl "
const p = await openTab('<url>');
await sleep(3000);
const ss = await p.screenshot();
console.log('SCREENSHOT_B64:' + ss.toString('base64'));
" > /tmp/out.txt 2>&1
grep '^SCREENSHOT_B64:' /tmp/out.txt | sed 's/^SCREENSHOT_B64://' | base64 --decode > /tmp/shot.png
```

This works because top-level `await` is allowed directly in the REPL (no IIFE wrapper needed — see lesson 13). For multi-platform staging loops, wrap in a Python `subprocess.run` loop that parses each `SCREENSHOT_B64:` line and decodes to disk.

16. **Mastodon URLs: `mastodon.social/compose` is a 404; use `mastodon.social/publish` (verified 2026-07-15).** Old docs and recipes reference `/compose`, but the modern Mastodon (v4.x) instance returns a 404 Not Found for that path. The compose preview lives at `/publish`. **Caveat:** `/publish` shows the compose form to unauthenticated users, but the "Post" button won't work until you sign in. Verify session state with vision ("Login / Create account buttons visible on the right?") before staging. Other instances (e.g. `mastodon.social/@user`) have different canonical paths; check the instance's help docs.

17. **LinkedIn share-box trigger uses obfuscated class names that defeat programmatic clicks (verified 2026-07-15).** `.locator('button[aria-label*="Start a post"]')` returns 0 matches. Click-by-text (`document.querySelectorAll('button').forEach(el => { if (el.textContent.includes('Start a post')) el.click() })`) also returns 0 — LinkedIn renders the "Start a post" box as a `<div>` with `role="button"` and randomized class names like `share-box-feed-entry__closed-share-box`. After 3 failed attempts (locator, click-by-text, click-by-placeholder), the recommended path is: **tell the user "click 'Start a post' manually, then paste from linkedin.md"**. Same fallback applies to Threads (sometimes), Facebook (modal requires click on "What's on your mind, [Name]?" first), and Instagram (no web compose at all).

18. **`aside repl` CLI silently no-ops on programmatic paste — use Aside HTTP MCP instead (verified 2026-07-17).** Switching the staging script from `aside repl "..."` to the HTTP MCP at `127.0.0.1:8013/mcp` is the difference between 9/11 platforms stuck at "compose-ready with empty fields" and 3/11 platforms actually having the draft text in the field. The `aside repl` path looks identical — every `await loc.fill(...)` returns without error — but the field stays empty because the underlying Chrome DevTools clipboard-write hook is silently disabled in that mode. Use `scripts/stage_in_aside_mcp.py` as the canonical staging entry point; treat `aside repl` paste as a known-broken path.

19. **Bundle open + paste + verify + screenshot in ONE MCP call per platform, never split (verified 2026-07-17).** Each `openTab(url)` opens a fresh tab. If the JS code is split across multiple MCP calls — call 1 opens the tab, call 2 types, call 3 verifies — the typed text is lost because call 2's `openTab` reopens a new tab on the same URL, which resets the compose form. The fix is one MCP `tools/call` per platform wrapping `(async () => { openTab → fill → verify → screenshot })()` in a single IIFE; the screenshot base64 emits on a separate `SHOT_<var>:` line so the companion `RESULT_<var>=<json>` line stays small enough to parse reliably.

20. **MCP server at 127.0.0.1:8013/mcp degrades after ~6-8 bundled calls (verified 2026-07-17).** Symptom: subsequent `tools/call` requests return 0 bytes (no SSE error, no console output, the curl process times out after 180s with empty body). Cause: Chrome / Aside daemon contention from too many open tabs / `playwright.Page` handles held across calls. Recovery: `pkill -9 -f aside` then `open -a "Aside"` and wait 10s; `aside account use u0`; `openTab <warmup-url>` once to confirm the window has focus; re-run. Or, if the same script that worked minutes ago now returns empty, restart Between MCP sessions — every fresh session starts healthy.

21. **Reddit's old.reddit.com form is fragile — fill sometimes hangs Chrome entirely (verified 2026-07-17).** Symptom: `locator.fill()` for `textarea[name='text']` on `/r/X/submit?selftext=true` triggers an indefinite Chrome hang (no MCP response after 60s+). The same code works for HN (`textarea[name='text']`) and Mastodon (`<textarea>`) — the difference is old.reddit's anti-spam heuristics. Workaround: run each Reddit subreddit in its own fresh MCP session, fill title first, then body in a separate call. If the body fill still hangs, surface the draft `.md` file to the user for manual paste.

22. **Login walls silently reappeared for LinkedIn / Facebook / Threads / Dev.to with Chrome profile u0 = $USER@gmail.com (verified 2026-07-17).** Earlier sessions (2026-07-11) reported these platforms as "signed in for the session via fresh `openTab`"; the cookies appear to have rotated or expired between sessions. Symptom: `openTab` on the compose URL redirects to the platform's sign-in form (Dev.to shows `input#user_email` + `input#user_password`; LinkedIn shows "Welcome back" page). Fix: one-time manual login in the Aside GUI, then re-run staging — u0 cookies refresh for the next 24-72h. Or fall back to headless Playwright + `browserclaw cookies inject` per `references/platform-session-status.md`.

23. **Use `subprocess.Popen + .communicate(timeout=...)`, NOT `subprocess.run(timeout=...)` for MCP `curl` calls (verified 2026-07-17).** `subprocess.run(..., timeout=180)` silently drops output if the curl process writes its SSE bytes between Python's timeout firing and the process exiting cleanly. `Popen` + `communicate(timeout=180)` captures the same data. Indistinguishable on a happy path; visible failure mode is `len(out) == 0` after a "successful" call.

24. **Always vision-verify the actual TEXT inside the field after staging (verified 2026-07-17 re-confirmation).** The HN stage reported `paste: ok=true, len=1131` via the verify step, but the saved screenshot showed only the last 2 sentences of a multi-paragraph body. Playwright's `locator.fill()` silently truncates on certain React-controlled textareas when the input exceeds ~1000 chars and the field has not been focused first. The fix is `await loc.click(); await sleep(300); await loc.fill(text)` (already in `stage_in_aside_mcp.py`), BUT vision-verify is the only reliable cross-check — the verify step reads `document.querySelector().value.length` which disagrees with what's actually visible after a re-render. Always end Phase 2 with one `vision_analyze` per platform asking "what text is currently in the field?" before declaring success.