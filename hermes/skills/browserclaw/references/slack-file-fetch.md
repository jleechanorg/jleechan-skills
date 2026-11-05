# Slack attachment access

Use the configured native Slack connector only for attachment metadata or content exposed through its existing authorized operations. If the connector is unavailable, lacks the needed method, or reports insufficient authorization, stop and report that access blocker. Do not read token files, extract credentials from shell configuration, or call Slack REST endpoints with a user token as a fallback.

For any browser-based access, follow `~/.claude/skills/browser-control/SKILL.md`. Personal browser profiles, cookies, and login state are off-limits; browser or cookie access must not bypass Slack authorization.

When the authorized connector returns an attachment, verify only the task-relevant result, such as the returned filename, declared type, and successful content availability. Keep attachment contents and identifiers private, and do not include them in reusable documentation or logs.
