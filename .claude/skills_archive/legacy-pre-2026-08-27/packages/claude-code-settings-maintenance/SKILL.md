# Claude Code Settings & Configuration Maintenance

**Purpose**: Best practices for maintaining Claude Code settings.json and agent files to avoid validation errors and ensure proper configuration.

## 🚨 Critical: Always Consult Official Documentation

**MANDATORY PROTOCOL**: When uncertain about configuration format, ALWAYS web search official Claude Code documentation first.

### Documentation Search Strategy

1. **Use WebFetch tool** to retrieve latest official docs
2. **Primary documentation URLs**:
   - `https://code.claude.com/docs/en/` - Main documentation hub
   - `https://code.claude.com/docs/en/hooks` - Hooks documentation
   - `https://code.claude.com/docs/en/agents` - Agents documentation
   - `https://code.claude.com/docs/en/settings` - Settings reference

3. **Search pattern**:
   ```
   WebFetch(url="https://code.claude.com/docs/en/hooks",
            prompt="What is the correct format for hook matchers?")
   ```

## 📋 Hooks Configuration Format

### ✅ Correct Format (String Matchers)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Running pre-tool hook'",
            "description": "Example hook"
          }
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Before write operation'",
            "description": "Pre-write hook"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'After bash command'",
            "description": "Post-bash hook"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'User submitted prompt'",
            "description": "Prompt submission hook"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Session stopping'",
            "description": "Stop hook"
          }
        ]
      }
    ]
  }
}
```

### ❌ Incorrect Format (Object Matchers - OLD FORMAT)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": {"tools": ["*"]},  // ❌ WRONG - Object format
        "hooks": [...]
      },
      {
        "matcher": {"tools": ["Write"]},  // ❌ WRONG - Object format
        "hooks": [...]
      }
    ]
  }
}
```

### Matcher Types

| Matcher Pattern | Description | Example |
|----------------|-------------|---------|
| `"*"` | Match all tools | `"matcher": "*"` |
| `"Write"` | Match specific tool | `"matcher": "Write"` |
| `"Edit|Write"` | Match multiple tools (regex) | `"matcher": "Edit|Write"` |
| `"Bash(git:*)"` | Match specific bash commands | `"matcher": "Bash(git:*)"` |
| `""` | Empty matcher (for non-tool hooks) | `"matcher": ""` |

> **Note:** Matcher patterns accept raw regular expressions. Use the pipe (`|`) for alternation without escaping (e.g., `"Edit|Write"`).

### Hook Event Types

- **PreToolUse**: Runs before tool execution (requires matcher)
- **PostToolUse**: Runs after tool execution (requires matcher)
- **UserPromptSubmit**: Runs when user submits prompt (use empty matcher `""`)
- **SessionStart**: Runs at session start (use empty matcher `""`)
- **Stop**: Runs when session stops (use empty matcher `""`)

## 🤖 Agent File Frontmatter Format

### ✅ Correct Format (Unquoted Values)

```yaml
---
name: my-agent
description: A specialized agent for specific tasks with detailed expertise
---

# Agent Content
Your agent instructions here...
```

### ❌ Incorrect Format (Quoted Values)

```yaml
---
name: "my-agent"  # ❌ WRONG - Quoted
description: "A specialized agent..."  # ❌ WRONG - Quoted
---
```

### Required Frontmatter Fields

| Field | Required | Format | Example |
|-------|----------|--------|---------|
| `name` | ✅ Yes | Unquoted string | `name: code-review` |
| `description` | ✅ Yes | Unquoted string | `description: Expert code reviewer` |

### Agent Naming Best Practices

- **Use kebab-case**: `code-review`, `test-runner`, `security-audit`
- **Be descriptive**: Name should indicate agent's purpose
- **Avoid generic names**: Prefer `python-test-runner` over `tester`
- **No quotes**: YAML values should be unquoted

## 🔍 Validation Protocol

### 1. Use /doctor Command

**ALWAYS run `/doctor` after configuration changes**:

```bash
/doctor
```

Expected clean output:
```
✅ Diagnostics
 └ Currently running: npm-global (2.0.43)
 └ Settings: Valid
 └ Agents: All parsed successfully
 └ Hooks: All registered correctly
```

### 2. Common Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `matcher: Expected string, but received object` | Using `{"tools": [...]}` format | Change to string: `"*"` or `"Write"` |
| `Missing required "description" field` | Agent frontmatter missing description | Add `description: ...` to frontmatter |
| `Missing required "name" field` | Agent frontmatter missing name | Add `name: ...` to frontmatter |
| `Invalid frontmatter` | Quoted values in YAML | Remove quotes from name/description |

### 3. Pre-Commit Checklist

Before committing settings changes:

- [ ] Run `/doctor` to validate configuration
- [ ] Check hooks section uses string matchers
- [ ] Verify all agent files have required frontmatter
- [ ] Ensure agent frontmatter uses unquoted values
- [ ] Test hooks execute correctly (if applicable)

## 🛠️ Troubleshooting Workflow

### Issue: Hooks Not Working

1. **Check matcher format**: Ensure using string matchers, not objects
2. **Verify hook syntax**: Confirm JSON structure is valid
3. **Test command**: Run hook command manually to ensure it works
4. **Check permissions**: Ensure hook script files are executable

### Issue: Agent Parse Errors

1. **Check frontmatter**: Verify both `name` and `description` fields present
2. **Remove quotes**: Ensure values are unquoted (YAML format)
3. **Validate YAML**: Ensure frontmatter block starts/ends with `---`
4. **Check indentation**: YAML is indent-sensitive (use spaces, not tabs)

### Issue: Settings Not Loading

1. **Validate JSON**: Use `jq` or JSON validator to check syntax
2. **Check file location**: Ensure settings.json is in correct directory
   - Global: `~/.claude/settings.json`
   - Project: `<project>/.claude/settings.json`
3. **Restart Claude Code**: Configuration changes may require restart

## 📚 Documentation Reference Quick Links

| Topic | URL |
|-------|-----|
| Hooks | `https://code.claude.com/docs/en/hooks` |
| Agents | `https://code.claude.com/docs/en/agents` |
| Settings | `https://code.claude.com/docs/en/settings` |
| MCP Servers | `https://code.claude.com/docs/en/mcp` |
| Permissions | `https://code.claude.com/docs/en/permissions` |

## 🎯 Best Practices Summary

1. **Always consult official docs** when uncertain about format
2. **Use string matchers** for hooks (not object format)
3. **Use unquoted values** in agent frontmatter
4. **Run /doctor** after every configuration change
5. **Test hooks manually** before committing
6. **Keep settings.json valid** - use JSON validator
7. **Document custom configurations** in project README
8. **Version control** all .claude/ directory files
9. **Use descriptive names** for agents and hooks
10. **Follow principle of least privilege** for permissions

## ⚠️ Common Pitfalls to Avoid

| Pitfall | Impact | Prevention |
|---------|--------|------------|
| Using old object matcher format | Hooks fail validation | Always use string matchers |
| Quoting agent frontmatter values | Agent parse errors | Use unquoted YAML values |
| Missing description field | Agent not loaded | Always include name + description |
| Invalid JSON syntax | Settings not loaded | Validate JSON before commit |
| Not running /doctor | Deploy with broken config | Run /doctor before every commit |

## 🔄 Migration Guide: Old to New Hook Format

### Step 1: Identify Old Format

Search for object matchers:
```bash
grep -n '"matcher": {' .claude/settings.json
```

### Step 2: Convert to String Format

**Old**:
```json
"matcher": {"tools": ["*"]}
"matcher": {"tools": ["Write"]}
"matcher": {"tools": ["Bash(git:*)"]}
```

**New**:
```json
"matcher": "*"
"matcher": "Write"
"matcher": "Bash(git:*)"
```

### Step 3: Handle Non-Tool Hooks

For `UserPromptSubmit`, `Stop`, `SessionStart`:
```json
{
  "UserPromptSubmit": [
    {
      "matcher": "",  // Empty string for non-tool hooks
      "hooks": [...]
    }
  ]
}
```

### Step 4: Validate

```bash
/doctor
```

## 📝 Example: Complete Valid Configuration

```json
{
  "env": {
    "BASH_MAX_OUTPUT_LENGTH": "5000"
  },
  "permissions": {
    "allow": ["Bash(git:*)"]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Pre-tool execution'",
            "description": "Log before tool use"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'File written'",
            "description": "Log file writes"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Prompt submitted'",
            "description": "Log prompt submission"
          }
        ]
      }
    ]
  }
}
```

## 🚀 When to Web Search Official Docs

**ALWAYS search official docs when**:
- Unsure about configuration format
- Encountering validation errors
- Implementing new features
- Migrating from old formats
- Debugging hook execution issues
- Adding new agent types
- Configuring MCP servers
- Setting up permissions

**Search Example**:
```javascript
WebFetch({
  url: "https://code.claude.com/docs/en/hooks",
  prompt: "What is the correct format for hook matchers? Show examples."
})
```

## ✅ Success Criteria

Configuration is correct when:
- [ ] `/doctor` shows no errors
- [ ] All hooks execute as expected
- [ ] All agents parse successfully
- [ ] Settings.json is valid JSON
- [ ] Agent frontmatter is valid YAML
- [ ] Matchers use string format (not objects)
- [ ] Frontmatter values are unquoted

---

**Last Updated**: 2025-11-17
**Applies To**: Claude Code 2.0+
**Official Docs**: https://code.claude.com/docs/en/
