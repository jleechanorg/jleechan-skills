# Runtime dependencies

The coordinator worker and its companion `dot` transport require Bash, Python 3, `flock`, and the `timeout` utility. The transport requires Node.js; Node 22 is the supported runtime in this host setup. Its Chrome backend also requires Google Chrome and the Node `playwright` package resolvable by `dot_chrome.mjs` (or a `DOT_PW_MODULES` path that exposes that package).

The repository contains the coordinator scripts and the portable `dot` skill scripts, not browser profiles, account configuration, cookies, or installed Node modules. Configure recipients and profile locations locally through `DOT_CONFIG_FILE` (default `~/.config/dot/config.json`) and keep browser profiles outside the repository. Cross-host forwarding is optional and additionally requires the configured SSH host.
