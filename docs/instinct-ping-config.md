# Instinct ping configuration

The launchd job reads its persistent configuration from
`~/.config/instinct-ping/config.json`. Create the file with values for your own
machine before installing the job:

```json
{
  "contact": "<your configured iMessage handle>",
  "task": "<short task title>",
  "repo": "/absolute/path/to/the/repository",
  "pr": "<pull request number>",
  "ask": "<bounded review request>"
}
```

Replace every placeholder. The repository value must be a reachable local Git
checkout with a current branch and commit. Restrict the file to its owner, for
example with `chmod 600 ~/.config/instinct-ping/config.json`.

The installer checks that the file is valid before it creates or replaces the
launchd wrapper or plist. Direct wrapper runs may override individual config
values with the existing `INSTINCT_IMSG_CONTACT`, `INSTINCT_PING_TASK`,
`INSTINCT_PING_REPO`, `INSTINCT_PING_PR`, and `INSTINCT_PING_ASK` environment
variables. These overrides do not change the persistent file.
