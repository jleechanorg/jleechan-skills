---
description: Control live browser sessions, websites, settings, OAuth, and Slack app configuration through the current browser policy. Primary Aside (MCP then CLI), then browserclaw cookies decrypt + inject for headless auth, then Playwright headless. Auth-gated share links reuse the installed browserclaw skill's verified cookie-injection references after both Aside paths are exhausted.
type: skill
execution_mode: immediate
---

# /browser [task]

Route the task in this priority order. Advance only when the current route cannot complete the authenticated task; a single transport/tab error is not enough. Even if the browser-control skill is unavailable, missing, or fails to load, this command MUST still resolve to the right tool.

1. **Aside-MCP** if the active runtime exposes the Aside MCP tools. Use them. The user's existing signed-in tabs and session persist across calls.
2. **Aside CLI** (`aside repl` / `aside "<prompt>"` / `aside account list`) — drives the already-running `Aside.app` profile and reuses its signed-in session. It is a real browser session, not the headless fallback. Sandbox note: `aside` Bash calls require `dangerouslyDisableSandbox: true` (Aside CLI fails closed, not soft, when the Bash sandbox blocks its local IPC).
3. **`browserclaw cookies decrypt + inject`** for sites where the user is already authenticated but Aside is not signed-in, unavailable, or on a headless host. Decrypt the user's existing cookies from the local Chromium profile (Aside → Chrome Default → Profile 1 → Profile 2 → Brave → Edge), inject into Playwright Chromium headless (`--browser-channel chromium --headless`), navigate. ALWAYS use `--summary` when only a domain check is needed, write only to a private `/tmp` file, never log values, never commit cookie JSON, delete the file immediately after use. **Never** route credential-bearing flows through `browserclaw capture` / `learn` / `reverse` — those persist full HTTP traffic to a HAR file that can contain the new secret in plaintext.
4. **Playwright headless (no auth)** for unauthenticated/deterministic flows, scripted sweeps, or CI-style checks.
5. **Visible/headed browser** — only when the user explicitly opted in for it in the current thread.

**Fingerprint-sensitive sites (Aside-only exception):** LinkedIn, banks/brokerages (Chase, Fidelity, Vanguard, Schwab), and sites with active Cloudflare/Akamai bot-mitigation that flag the Chromium-for-Testing headless fingerprint. For these, drop the cookie-copy route and use the existing signed-in Aside profile directly. If the host is headless, post a ONE-LINE BLOCKER naming the missing display rather than retrying headless.

Then load the installed `browser-control` skill with normal skill discovery and execute the workflow for `$ARGUMENTS`. Use the installed `playwright-ui-testing` skill only when the task is deterministic UI testing, CI, isolated profiles, traces, video, or multi-browser coverage. The full contract for these routing rules lives in `browser-control/SKILL.md` and is enforced by the contract test `tests/test_browser_command_contract.py` in this repo, which fails if the routing order or the auth-gate recipe pointer ever changes.

## Auth-gated share links (Gemini / ChatGPT / Google Docs / Notion)

**If the task is "read / save / summarize / extract / ingest" the content of an auth-gated share URL** (`share.gemini.google/...`, `chatgpt.com/share/...`, `docs.google.com/document/d/.../edit` with restricted access, `notion.so/...` shared pages, vendor AI share dialogs) and an anonymous fetch returns the vendor's sign-in shell — **do NOT post an "unblock options" menu and do NOT ask the user to paste the content.** Continue the same global routing order: try the existing signed-in Aside session through MCP, then Aside CLI; only if neither can access the content, pivot to **`browserclaw` headless** and read the page as the user. The fingerprint-sensitive Aside-only exception still overrides this fallback.

Verified 5-step recipe (2026-07-20 on Gemini share `Td7fA4pzuvMs`, 79 Google cookies decrypted, full 169KB page text extracted). The safe recipe below is canonical; the multi-profile sweep is embedded inline so the canonical lifecycle does not depend on operator-executed fixed-path sweep snippets. The optional browserclaw reference files are background only and must not override this guarded lifecycle.

```bash
# Canonical guarded lifecycle for /browser auth-gated content.
# Fail-closed: any decrypt/inject/Playwright failure aborts before
# persisted credential state, and INT/TERM/HUP also trigger cleanup.
# One canonical cleanup trap removes BOTH the cookie file and the
# page text on every success, error, and signal. The secret branch
# runs INSIDE this trap, and the multi-profile sweep produces a
# cookie artifact the canonical recipe consumes before cleanup.
set -euo pipefail
# Restrict the process umask so any mktemp / redirect that does
# not respect an explicit chmod still ends up owner-only. The
# canonical recipe also re-applies chmod 600 after every sweep
# write because browserclaw's writer uses Path.write_text()
# which honors the process umask.
umask 077
TMP_COOKIES="$(mktemp -t browserclaw-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-page-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE"
# INT/TERM/HUP handlers MUST terminate nonzero after cleanup so
# a signal during a long decrypt/inject does not let bash
# continue past the trap and recreate credential files. We use
# the same trap as cleanup_browser_share and force an exit
# in the trap function itself.
cleanup_browser_share() {
  local rc=$?
  rm -f "$TMP_COOKIES" "$TMP_PAGE"
  return "$rc"
}
exit_on_signal() {
  local rc=$?
  cleanup_browser_share || true
  # Exit immediately with 128+signal so bash does NOT continue
  # past the trap. Re-raising via `kill -SIG $$` is unreliable
  # because bash defers re-entry of the same signal while the
  # handler is still running; a direct `exit` is the documented
  # and race-free way to terminate from a signal trap.
  if [ -n "${1:-}" ]; then
    case "${1}" in
      INT)  exit 130 ;;
      TERM) exit 143 ;;
      HUP)  exit 129 ;;
      *)    exit "$rc" ;;
    esac
  fi
  exit "$rc"
}
trap 'exit_on_signal TERM' TERM
trap 'exit_on_signal HUP' HUP
trap 'exit_on_signal INT' INT
trap cleanup_browser_share EXIT

# 1. Multi-profile sweep runs FIRST, Aside first — the canonical
#    recipe does NOT depend on Chrome Default being non-empty
#    before falling through to other profiles. The sweep writes
#    the first non-empty cookie JSON to $TMP_COOKIES and short-
#    circuits. Each browserclaw write is followed by chmod 600
#    because browserclaw's writer honors the process umask.
#
#    When multiple Aside accounts are signed in (`aside account
#    list` shows more than one), prefer the one the current
#    task asked for; if the task did not name one, run the
#    sweep with the default profile and let the gate decide.
#    Each browserclaw call uses `--keychain-account` to pin the
#    keychain entry that decrypts the corresponding cookies.db.
set +e
for entry in \
  "Aside:$HOME/Library/Application Support/Aside/Default/Cookies:Aside Safe Storage:Aside" \
  "Aside-Profile1:$HOME/Library/Application Support/Aside/Profile 1/Cookies:Aside Safe Storage:Aside-Profile1" \
  "Chrome-Default:$HOME/Library/Application Support/Google/Chrome/Default/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile1:$HOME/Library/Application Support/Google/Chrome/Profile 1/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile2:$HOME/Library/Application Support/Google/Chrome/Profile 2/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile3:$HOME/Library/Application Support/Google/Chrome/Profile 3/Cookies:Chrome Safe Storage:Chrome" \
  "Brave:$HOME/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies:Brave Safe Storage:Brave" \
  "Edge:$HOME/Library/Application Support/Microsoft Edge/Default/Cookies:Microsoft Edge Safe Storage:Microsoft Edge"; do
  IFS=: read label db svc acct <<< "$entry"
  [ -f "$db" ] || continue
  env -i HOME="$HOME" \
    PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    browserclaw cookies decrypt --db "$db" \
      --output "$TMP_COOKIES" \
      --keychain-service "$svc" --keychain-account "$acct" \
      --domain-filter '%<vendor-domain>%' --summary >/dev/null 2>&1 || true
  if [ -s "$TMP_COOKIES" ]; then
    count="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
    if [ "$count" -gt 0 ]; then
      # browserclaw's writer uses Path.write_text() and does not
      # enforce a restrictive mode. Re-apply 0600 so the cookie
      # file never ends up world- or group-readable even with a
      # permissive umask. The EXIT trap will remove the file
      # on any subsequent failure.
      chmod 600 "$TMP_COOKIES"
      echo "MATCH: $label (${count} cookies) — stopping sweep" >&2
      break
    fi
  fi
  rm -f "$TMP_COOKIES"
done
set -e

DECRYPT_COUNT="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
if [ "$DECRYPT_COUNT" -le 0 ]; then
  echo "BLOCKER: no <vendor-domain> cookies in any profile. Ask the user to log in once." >&2
  exit 11
fi

# 2. We now have a valid cookie artifact. Inject.

# 3. Inject + navigate headless Chromium; keep private body text temporary.
env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  browserclaw cookies inject \
    --cookies "$TMP_COOKIES" \
    --goto "<full-share-url-with-skid-if-present>" \
    --browser-channel chromium \
    --headless \
    --wait-after-load 12 \
    --print-text 100000 > "$TMP_PAGE"

# 4. If --print-text truncates mid-sentence, scroll to the bottom with a bare
#    headless Playwright script that reads `$TMP_COOKIES` and overwrites
#    `$TMP_PAGE`; preserve the same trap and never use fixed output paths.

# 5. Read only the captured fields needed for the task. Verify the expected
#    first-user message appears, not the sign-in shell.

# 6. Cleanup is owned by the EXIT/INT/TERM/HUP trap (cleanup_browser_share),
#    which is armed throughout the recipe. There is no disarm line —
#    keeping the trap armed is the fail-closed contract: any signal
#    arriving after step 5 still removes both files. The trap's
#    `rm -f` is idempotent, so a normal exit that fires the EXIT
#    trap is the same as an explicit cleanup call.
```

**Why `--browser-channel chromium` (not `chrome`):** `channel=chrome` briefly opens a visible Chrome window before transitioning to headless — verified bug 2026-07-18. The bundled Chromium-for-Testing is always headless and never pollutes the user's existing Chrome session.

This pattern is enforced by the contract test `tests/test_browser_command_contract.py` in this repo, which fails if the routing order or the auth-gate recipe pointer ever changes.
