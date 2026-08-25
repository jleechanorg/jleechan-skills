---
description: Control live browser sessions, websites, settings, OAuth, and Slack app configuration through the current browser policy. For auth-gated share links (Gemini / ChatGPT / Google Docs / Notion), use `browserclaw cookies decrypt + inject` — verified recipe at ~/.hermes/skills/browserclaw/references/gemini-share-link-as-user.md.
type: skill
execution_mode: immediate
---

# /browser [task]

Read `~/.claude/skills/browser-control/SKILL.md` and execute the workflow for `$ARGUMENTS`.

Use `~/.claude/skills/playwright-ui-testing/SKILL.md` only when the task is deterministic UI testing, CI, isolated profiles, traces, video, or multi-browser coverage.

## Auth-gated share links (Gemini / ChatGPT / Google Docs / Notion)

Use the cookie-transfer recipe only when the user has explicitly authorized access to the requested authenticated content. Keep cookies local and task-scoped, never expose their values, and continue to follow the canonical skill's credential-handling limits.

**If the task is "read / save / summarize / extract / ingest" the content of an auth-gated share URL** (`share.gemini.google/...`, `chatgpt.com/share/...`, `docs.google.com/document/d/.../edit` with restricted access, `notion.so/...` shared pages, vendor AI share dialogs) and an anonymous fetch returns the vendor's sign-in shell — **do NOT post an "unblock options" menu and do NOT ask the user to paste the content.** On the first refusal, pivot to **`browserclaw` headless** and read the page AS the user.

Verified 5-step recipe (2026-07-20 on Gemini share `Td7fA4pzuvMs`, 79 Google cookies decrypted, full 169KB page text extracted, campaign module saved via PR $GITHUB_REPOSITORY#8483):

```bash
# 1. Decrypt Chrome Default cookies for the vendor auth domain
env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  browserclaw cookies decrypt \
    --db "$HOME/Library/Application Support/Google/Chrome/Default/Cookies" \
    --output /tmp/<vendor>-cookies.json \
    --domain-filter '%<vendor-domain>%' --summary

# 2. If 0 cookies returned, sweep Profile 1 / Aside / Brave per
#    ~/.hermes/skills/browserclaw/references/multi-profile-cookie-scan.md.
#    If still 0, post ONE-LINE BLOCKER naming the missing-cookie domain.

# 3. Inject + navigate headless Chromium + dump page text
env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  browserclaw cookies inject \
    --cookies /tmp/<vendor>-cookies.json \
    --goto "<full-share-url-with-skid-if-present>" \
    --browser-channel chromium \
    --headless \
    --wait-after-load 12 \
    --screenshot /tmp/<vendor>_authed.png \
    --print-text 100000 > /tmp/<vendor>_page.txt

# 4. If --print-text truncates mid-sentence (Gemini share pages lazy-load
#    sections), re-extract with Playwright + scroll-to-bottom. See
#    ~/.hermes/skills/browserclaw/references/gemini-share-link-as-user.md
#    for the verified Python script.

# 5. Read the captured text end-to-end. Verify the expected first-user
#    message appears (NOT the vendor sign-in form). Proceed with the user's
#    actual ask against the captured content.
```

**Why `--browser-channel chromium` (not `chrome`):** `channel=chrome` briefly opens a visible Chrome window before transitioning to headless — verified bug 2026-07-18. The bundled Chromium-for-Testing is always headless and never pollutes the user's existing Chrome session.

This pattern is enforced by SOUL.md `## COMMIT: read-auth-gated-share-links-with-browserclaw` (verified 2026-07-20). The contract test `tests/test_browser_command_mentions_browserclaw.py` in `~/jleechanclaw` fails if this file ever drops the `browserclaw` reference or the auth-gate recipe pointer.
