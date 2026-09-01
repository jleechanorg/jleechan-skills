---
title: "Multi-profile cookie scan — when the target site isn't in `Default`"
type: reference
date: 2026-07-14
status: HARDENED 2026-08-09 — guarded mktemp lifecycle, explicit authorization required, no fixed /tmp paths, EXIT-trap cleanup. Background only; the canonical lifecycle is in `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md`.
---

# Multi-profile cookie scan — when the target site isn't in `Default`

> **Background reference only.** The canonical guarded lifecycle for /browser is in `~/.claude/commands/browser.md` (the **Auth-gated share links** section) and `~/.claude/skills/browser-control/SKILL.md` (**Authorized credential reuse**). The snippets below MUST NOT override that canonical lifecycle — they document the verified multi-DB sweep pattern.

When `browserclaw cookies decrypt --domain-filter '%target.com%'` returns `Wrote 0 cookies` against `~/Library/Application Support/Google/Chrome/Default/Cookies`, **do not stop**. When explicitly authorized for the task, the user may have the site logged into a different Chrome profile, a different browser (Brave, Aside), or a different default browser entirely. Sweep all known profiles before concluding "no session exists." **Credential reuse requires explicit task authorization.**

## macOS cookie DB locations to sweep

| Browser / Profile | Path | Keychain service | Keychain account |
|---|---|---|---|
| Chrome Default | `~/Library/Application Support/Google/Chrome/Default/Cookies` | `Chrome Safe Storage` | `Chrome` |
| Chrome Profile 1 | `~/Library/Application Support/Google/Chrome/Profile 1/Cookies` | `Chrome Safe Storage` | `Chrome` (same — Chrome uses one keychain entry per OS user) |
| Chrome Profile N | `~/Library/Application Support/Google/Chrome/Profile N/Cookies` | `Chrome Safe Storage` | `Chrome` |
| Brave | `~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies` | `Brave Safe Storage` | `Brave` |
| Edge | `~/Library/Application Support/Microsoft Edge/Default/Cookies` | `Microsoft Edge Safe Storage` | `Microsoft Edge` |
| **Aside (2026-06-27+ default)** | `~/Library/Application Support/Aside/Default/Cookies` | `Aside Safe Storage` | `Aside` |
| Codex | `~/Library/Application Support/Codex/Default/Cookies` | `Codex Safe Storage` (or similar) | `Codex` |

## Discovery first — list actual profiles

Don't guess. Before the sweep loop, list what's actually installed:

```bash
ls -d ~/Library/Application\ Support/Google/Chrome/Profile*/Cookies \
       ~/Library/Application\ Support/Google/Chrome/Default/Cookies \
       ~/Library/Application\ Support/BraveSoftware/Brave-Browser/Default/Cookies \
       ~/Library/Application\ Support/Microsoft\ Edge/Default/Cookies \
       ~/Library/Application\ Support/Aside/Default/Cookies \
       ~/Library/Application\ Support/Codex/Default/Cookies 2>/dev/null
```

## Sweep loop (background — see canonical lifecycle above)

The canonical lifecycle uses `mktemp -t browserclaw-XXXXXX.json`, `chmod 600`, and `trap ... EXIT INT TERM` cleanup. **Do not use fixed `/tmp/<name>-cookies.json` paths** — those leak credentials across processes and survive long after the script exits. The hardened sweep loop is:

```bash
TARGET='venmo.com'   # or whatever domain you're hunting

# One mktemp cookie file reused for the entire sweep; deleted before exit.
set -euo pipefail
umask 077
TMP_COOKIES="$(mktemp -t browserclaw-sweep-XXXXXX.json)"
chmod 600 "$TMP_COOKIES"
trap 'rm -f "$TMP_COOKIES"' EXIT INT TERM HUP

# Iterate every Chromium-style profile you might have. Aside is
# listed first because its signed-in session is the operator's
# most common source of cookies. Each entry expands to
# `<label>:<db-path>:<keychain-service>:<keychain-account>`.
match_profile() {
  local label="$1" db="$2" svc="$3" acct="$4"
  [ -f "$db" ] || return 0
  local summary_file
  summary_file="$(mktemp -t browserclaw-sweep-sum-XXXXXX.txt)"
  chmod 600 "$summary_file"
  env -i HOME="$HOME" \
    PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    browserclaw cookies decrypt --db "$db" \
      --output "$TMP_COOKIES" \
      ${svc:+--keychain-service "$svc"} ${acct:+--keychain-account "$acct"} \
      --domain-filter "%${TARGET}%" --summary >"$summary_file" 2>&1 || true
  local count=0
  if [ -s "$TMP_COOKIES" ]; then
    count="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
  fi
  if [ "$count" -gt 0 ]; then
    chmod 600 "$TMP_COOKIES"
    echo "MATCH: $label (${count} cookies) — stopping sweep"
    rm -f "$summary_file"
    return 1
  fi
  echo "=== $label === Wrote 0 cookies"
  if [ -s "$summary_file" ]; then
    head -n 5 "$summary_file"
  fi
  rm -f "$summary_file"
  return 0
}

# Chrome profiles — sweep in the order Aside-first then Chrome
# Default, Profile 1, Profile 2, Profile 3. Aside is a real launchd
# daemon and is the primary signed-in browser per the browser-control
# skill, so it goes first.
for entry in \
  "Aside:$HOME/Library/Application Support/Aside/Default/Cookies:Aside Safe Storage:Aside" \
  "Chrome-Default:$HOME/Library/Application Support/Google/Chrome/Default/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile1:$HOME/Library/Application Support/Google/Chrome/Profile 1/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile2:$HOME/Library/Application Support/Google/Chrome/Profile 2/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile3:$HOME/Library/Application Support/Google/Chrome/Profile 3/Cookies:Chrome Safe Storage:Chrome" \
  "Brave:$HOME/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies:Brave Safe Storage:Brave" \
  "Edge:$HOME/Library/Application Support/Microsoft Edge/Default/Cookies:Microsoft Edge Safe Storage:Microsoft Edge"; do
  IFS=: read label db svc acct <<< "$entry"
  if ! match_profile "$label" "$db" "$svc" "$acct"; then
    break
  fi
done
```

**If ALL return `Wrote 0 cookies`:**
- The user is not logged in to that site on this Mac from any browser profile browserclaw can read
- STOP. Do not pretend a headless injection will work.
- Tell the user honestly: "I scanned N profiles + M browsers. No `<target>` cookies found. You're either logged in on your phone only, on Safari, or on a profile I can't see."
- Offer recovery paths: log-in-once-in-Chrome (then poll cron), manual download, vendor support, alt data source (see "Gmail-as-data-fallback" below).

**Why the env -i wrapper:** per SOUL.md `## COMMIT: bashrc-profile-xapp-drift-blocks-launchd`, `env -i` with explicit `HOME=` and `PATH=` avoids the GITHUB_TOKEN drift that breaks `gh` invocations. Same wrapper works for browserclaw because it also calls `security find-generic-password` which needs `HOME` to find the Login keychain.

## Gmail-as-data-fallback — the often-missed path

Before concluding "I can't get the data," check whether the target site's data is **already emailed to the user**. Many activity statements are sent as email attachments or inline tables.

```bash
gog gmail search --account $USER@gmail.com \
  "from:<sender-domain> OR subject:<keyword>" --max 10
```

If the search finds the data, fetch and parse:
```bash
gog gmail search "from:venmo.com subject:transaction history" --max 10
# Get full message body for a specific ID
gog gmail thread <thread_id> --select body
# Or download the attachment if it's a CSV (use a guarded mktemp path, not a fixed /tmp path).
VENMO_ATTACH="$(mktemp -t venmo-attach-XXXXXX.csv)"
chmod 600 "$VENMO_ATTACH"
gog gmail attachment <msg_id> --output "$VENMO_ATTACH"
trap 'rm -f "$VENMO_ATTACH"' EXIT INT TERM
```

The right order is:
1. Sweep cookie profiles (above) only if authorized
2. While that's running, run `gog gmail search` for the data
3. Decide based on results: inject cookies (path A) OR pull from Gmail (path B) OR fall back to vendor support (path C)

## Worked example — 2026-07-14, Venmo task

Jeffrey asked to use Venmo cookie to fetch Jan 2024 statements for an auditor. Sweep returned:

| Profile | Result |
|---|---|
| Chrome Default | `Wrote 0 cookies` |
| Chrome Profile 1 | `Wrote 0 cookies` |
| Chrome Profile 3 | `Wrote 0 cookies` |
| Aside | `Wrote 0 cookies` |

Gmail sweep:
| Search | Oldest hit |
|---|---|
| `venmo.com statement OR transaction history` | 2025-10-11 (16 months newer than the 2024-01 target) |

**Conclusion posted back to thread:** no Venmo session on this Mac, no Gmail history old enough → three recovery paths offered (Venmo support form, in-app download on phone, Chase bank statement lookup for the funding source).

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `browserclaw: Keychain lookup failed for service='Chrome Safe Storage' account='Chrome'` | User clicked Deny on a prior keychain prompt, or the entry was deleted | Open Keychain Access.app → search `Chrome Safe Storage` → ensure it exists; re-run and click Always Allow |
| `CookieDecryptError: Cookie DB not found` | Browser not installed, or path typo | Confirm with `ls "$HOME/Library/Application Support/Google/Chrome/Default/Cookies"` |
| `CookieDecryptError: is not a Chromium Cookies DB (no meta.version row)` | Wrong file — passing `Cookies-journal` or `Login Data` | Use the `Cookies` file (no suffix) |
| 0 cookies for a profile the user swears they use | Wrong profile — Chrome shows multiple via `chrome://version` | `ls ~/Library/Application\ Support/Google/Chrome/ | grep -i prof` to find the actual name |

## Cross-references

- Canonical guarded lifecycle: `~/.claude/commands/browser.md` and `~/.claude/skills/browser-control/SKILL.md` § **Authorized credential reuse** — these are authoritative.
- browserclaw SKILL.md "Edge cases / failure modes" — has the single-profile case; this file extends it for multi-profile
- browserclaw SKILL.md "Poll-until-cookies-appear pattern" — what to do AFTER finding a profile with 0 cookies: register a 5-min poll cron
- SOUL.md `## COMMIT: bashrc-profile-xapp-drift-blocks-launchd` — env -i wrapper rationale
- SOUL.md `## COMMIT: slack-cross-workspace-fallback-xoxp` — if you need to post the "no cookies found" status to Slack from a runtime where bot token is blocked
