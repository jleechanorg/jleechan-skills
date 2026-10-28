---
name: automation
description: Route pull-request automation actions through the package configured for the current environment.
---

# Pull Request Automation

Use this skill as the entry point to the PR-automation package installed for
the current environment. The package's own documentation defines its
supported interface, safety limits, and result artifacts; this shared skill
does not prescribe a package name, CLI binary, repository namespace, hook, or
schedule.

## Actions

- `/automation status` — report the package's current safety and run status.
- `/automation monitor [<owner>/<repository>]` — inspect the requested
  repository or the current repository when omitted.
- `/automation process <pr-number> --repo <owner>/<repository>` — process the
  specified PR using the package's documented safeguards.
- `/automation safety check` — read current safety limits and attempt counts.
- `/automation safety check-pr <pr-number> --repo <owner>/<repository>` — read
  the specific PR's safety status.
- `/automation safety clear` — clear safety history only when the user
  explicitly requests that destructive action.

Resolve an omitted repository from the current checkout with the GitHub CLI.
Do not infer a repository from a package name or hardcoded organization.

## Authentication and configuration

Use existing GitHub CLI authentication and check it with `gh auth status`. If
a stale `GITHUB_TOKEN` interferes with host authentication, unset it only in
the current shell and retry. Do not print or create tokens, add credentials to
shell profiles or `.env` files, or display credential values in status output.
Use only notification integrations already configured by their owner.

The installed package owns its safety limits, persistence, optional
notifications, and executable invocation. Follow its current documentation
for those details; do not copy installation, post-push hook, crontab, or
direct-CLI recipes into this catalog entry.
