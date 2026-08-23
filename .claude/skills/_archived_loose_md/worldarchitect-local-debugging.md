# Your Project Local Debugging Reference

## Log File Locations

**Flask server logs:**
```
/tmp/your-project.com/<branch-name>/flask-server.log
```

**MCP server logs:**
```
/tmp/your-project.com/<branch-name>/mcp-server.log
```

## Quick Log Commands

```bash
# Tail recent logs for current branch
tail -100 /tmp/your-project.com/codex_integrate-gemini-and-openrouter-apis-czdlzo/flask-server.log

# Search for errors
grep -i "error\|cerebras\|400\|500" /tmp/your-project.com/*/flask-server.log | tail -50

# Watch logs in real-time
tail -f /tmp/your-project.com/*/flask-server.log
```

## When Server Restart is Required

Python caches modules, so restart needed after changing:
- `constants.py` - any constant values
- Any `__init__.py` files
- Import structure changes
- New dependencies

**No restart needed for:**
- Template changes (Jinja reloads)
- Static files (CSS/JS)
- Most Flask route logic (with debug mode)

## Running Server

```bash
# From project root
./run_local_server.sh

# Server runs on port 8005-8007 (check output)
```

## Common Debug Patterns

```bash
# Find provider/model being used
grep "MODEL_INFO\|Using provider" /tmp/your-project.com/*/flask-server.log | tail -10

# Find token/context errors
grep "context_length\|token" /tmp/your-project.com/*/flask-server.log | tail -10

# Find API errors with response body
grep -A2 "API error" /tmp/your-project.com/*/flask-server.log | tail -20
```
