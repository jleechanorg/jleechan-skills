## Backend & Persistent Profiles

Headless system Chrome is the only supported backend. Resolve the account's
dedicated profile using the Machine Configuration reference below; never share
it with another tool or host. Login and recovery follow [Interactive Login &
Session Recovery](transport.md#interactive-login--session-recovery).
If Chrome is unavailable locally, report that prerequisite gap; do not forward
the request to another host or reuse its signed-in session.

## Configuration & Environment Variables

- `DOT_ACCOUNT`: Account identifier in `~/.config/dot/config.json`. Can also be passed via `--account <name>`.
- `DOT_URL`: Target ChatGPT dot assistant URL. Can also be passed via `--url <url>`.
- `DOT_BACKEND`: Force backend (`chrome` or `auto`). Both values select Chrome.
- `DOT_CONFIG_FILE`: Custom path to dot JSON configuration (defaults to `~/.config/dot/config.json`).
- `DOT_CHROME_USER_DATA`: Explicit Chrome user data directory (defaults to account-specific persistent dir configured in `~/.config/dot/config.json`).
- `DOT_PROFILE_DIRECTORY`: Explicit named Chrome subprofile override (defaults to the account's `profile_directory`, or `Default` when absent); it must pass the same single-directory-name validation.
- `DOT_CLEAR_DRAFT`: When set to `1`, forces clearing any existing draft or edit state in the composer before typing and sending. Peer-draft decisions otherwise follow the SKILL.md policy (wait 30s, submit if unchanged, else route to the next rotation account).
- `DOT_DRY_RUN`: When `1` (Chrome backend), types, verifies exact match, clears composer, and prints `DOT_DRYRUN_OK` without sending.

## Machine Configuration (`~/.config/dot/config.json`) — reference

Accounts, target dot URLs, and preferred backends can be declared per-machine in `~/.config/dot/config.json` without hardcoding personal data into the repository:

Optionally designate a primary dot and miscellaneous dots using the existing account
keys: set `default_account` to the primary and list only accounts eligible for
automatic fallback in `rotation`, in preference order. Select a miscellaneous dot
explicitly with `--account` when appropriate. Names and roles are local choices;
without such preferences, existing selection and rotation behavior is unchanged.
If `rotation` is omitted, the transport falls back to all configured accounts, so
set it explicitly when any account must be excluded from automatic fallback.

A user may keep optional per-account work restrictions in a machine-local
`~/.config/dot/account-policy.md`, keyed by account name or alias. Before routing
new work, read that file if present and honor its applicable restrictions for the
resolved account, including on explicit `--account` selection and blocked-composer
fallback. For example, a user may reserve one account for human-requested work and
instruct it to decline new AI-originated requests and refer the requester to another
dot. Exclude such an account from `rotation` unless all automatic fallback work is
permitted there. These restrictions apply only to accounts the user names, not to
existing work or other accounts. The policy is agent guidance, not a transport
enforcement mechanism; the scripts do not read this file. Preserve fixed-target
coordinator rules and all existing authorization and capacity constraints.

```json
{
  "default_account": "primary",
  "rotation": ["primary", "secondary"],
  "accounts": {
    "primary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "user_data_dir": "~/.config/dot-headless-chrome-primary",
      "profile_directory": "Profile 1"
    },
    "secondary": {
      "url": "https://chatgpt.com/dots/<dot-id>",
      "backend": "chrome",
      "user_data_dir": "~/.config/dot-headless-chrome-secondary",
      "profile_directory": "Profile 2"
    }
  },
  "aliases": {
    "work": "primary",
    "personal": "secondary"
  }
}
```

Each `user_data_dir` must be dedicated to that Dot account and must not point inside the system Google Chrome profile. No other tool, MCP server, or browser may share a dot `user_data_dir`; exclusivity covers the directory, not only dot's own launches. If `user_data_dir` is omitted, Dot derives a separate local directory from the account key. `profile_directory` is optional: it selects a named Chrome subprofile and defaults to `Default` when absent. The value must be one safe directory name, such as `Profile 1`; path separators, `.` and `..`, and control characters are rejected. `DOT_PROFILE_DIRECTORY` may temporarily override the configured subprofile for one invocation, subject to the same validation. Chrome is the only backend. Multi-account targeting uses `--account <name>` / `DOT_ACCOUNT`, with independent headless-Chrome sessions per host/account pair and unified profile resolution with non-destructive lock recovery.
