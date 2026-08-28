# check-team-worldai-workstreams

Check the status of the worldai-workstreams team agents and report on their progress.

## What it does

1. Check TaskList for all tasks (workstreams 1-5)
2. Report which agents are done, running, or stuck
3. Check if any new commits were pushed to your-project.com or llm_wiki
4. Check for any new beads created via sqlite3
5. Report to user with status update

## Run when
- The 30-minute cron loop fires
- User asks "how's the team doing?"
- Team agents report completion

## Status to report
- Per-workstream status (running, completed, blocked)
- Notable new findings
- Any new beads or wiki pages created
- Next actions needed
