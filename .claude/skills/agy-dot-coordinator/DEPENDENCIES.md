# Runtime dependencies

The coordinator requires Bash, Python 3, flock, and the timeout utility. The companion dot transport requires Node.js; Node 22 is the supported runtime for this host package. Its Chrome backend requires Google Chrome and the Node playwright package resolvable by dot_chrome.mjs, or exposed through DOT_PW_MODULES.

The repository contains portable scripts only. It excludes account configuration, SSH host configuration, browser profiles, cookies, and installed Node modules. Configure recipients and profile paths outside the repository through DOT_CONFIG_FILE (default ~/.config/dot/config.json). Cross-host forwarding is optional and requires the SSH host to be configured locally.

The optional AGY sender is rejected by this coordinator's delivery-receipt contract, so AGY is not a runtime prerequisite.
