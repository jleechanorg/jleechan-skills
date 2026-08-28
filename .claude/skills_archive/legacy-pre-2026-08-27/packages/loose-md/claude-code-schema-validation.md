# Claude Code Schema Validation & Testing

**Purpose**: Comprehensive guide for validating Claude Code settings.json and agent files using official and community tools.

## 🎯 Official JSON Schema Support (RESOLVED - Sept 2025)

As of **September 29, 2025**, Anthropic provides official JSON Schema validation for Claude Code settings.

### Official Schema URL
```
https://json.schemastore.org/claude-code-settings.json
```

**Source**: GitHub Issue #2783 - Closed as completed

## ✅ Using Official Schema Validation

### Step 1: Add Schema Reference to settings.json

Add the `$schema` field at the top of your settings.json:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
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
        "hooks": [...]
      }
    ]
  }
}
```

### Step 2: Enable IDE Validation

Once the `$schema` field is added, your IDE will automatically:
- ✅ Validate settings structure
- ✅ Show errors for invalid fields
- ✅ Provide autocomplete for available options
- ✅ Display documentation on hover

**Supported IDEs**:
- VS Code
- IntelliJ IDEA
- WebStorm
- Any editor with JSON Schema support

## 🧪 Unit Testing Framework

### Option 1: Official Schema Validation (Recommended)

Use the official schema with standard JSON validation tools:

**Using Python (jsonschema)**:
```python
#!/usr/bin/env python3
"""Test Claude Code settings.json validation"""

import json
import requests
from jsonschema import validate, ValidationError

def test_settings_validation():
    """Validate settings.json against official schema"""

    # Fetch official schema
    schema_url = "https://json.schemastore.org/claude-code-settings.json"
    schema = requests.get(schema_url).json()

    # Load settings file
    with open('.claude/settings.json', 'r') as f:
        settings = json.load(f)

    # Validate
    try:
        validate(instance=settings, schema=schema)
        print("✅ settings.json is valid")
        return True
    except ValidationError as e:
        print(f"❌ Validation error: {e.message}")
        print(f"   Path: {' -> '.join(str(p) for p in e.path)}")
        return False

if __name__ == "__main__":
    success = test_settings_validation()
    exit(0 if success else 1)
```

**Using Node.js (ajv)**:
```javascript
#!/usr/bin/env node
const Ajv = require('ajv');
const fs = require('fs');
const https = require('https');

async function testSettingsValidation() {
  // Fetch official schema
  const schemaUrl = 'https://json.schemastore.org/claude-code-settings.json';
  const schema = await new Promise((resolve, reject) => {
    https.get(schemaUrl, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject);
  });

  // Load settings
  const settings = JSON.parse(fs.readFileSync('.claude/settings.json', 'utf8'));

  // Validate
  const ajv = new Ajv();
  const valid = ajv.validate(schema, settings);

  if (valid) {
    console.log('✅ settings.json is valid');
    return true;
  } else {
    console.error('❌ Validation errors:');
    ajv.errors.forEach(err => {
      console.error(`  - ${err.instancePath}: ${err.message}`);
    });
    return false;
  }
}

testSettingsValidation().then(success => process.exit(success ? 0 : 1));
```

### Option 2: Community Tools

**A. claude-code-settings-schema (npm)**

Generates local schema file for offline validation:

```bash
# Generate schema file
npx claude-code-settings-schema

# Your settings.json will reference local schema
{
  "$schema": "./claude-code-settings.schema.json",
  ...
}
```

**Benefits**:
- Offline validation
- IDE autocomplete and IntelliSense
- Based on official Anthropic documentation

**B. claude-json-validator (Python CLI)**

Standalone validator for settings files:

```bash
# Clone repository
git clone https://github.com/trial123Zel/claude-json-validator
cd claude-json-validator

# Setup
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Validate
python claude-json-validator.py ~/.claude/settings.json
python claude-json-validator.py .claude/settings.json --verbose
python claude-json-validator.py settings.json --strict
```

**Exit Codes**:
- `0`: Valid (warnings allowed unless `--strict`)
- `1`: Errors found

## 🔧 Pre-Commit Hook Integration

### Method 1: Using Official Schema (Python)

**File**: `.claude/hooks/validate_settings.py`

```python
#!/usr/bin/env python3
"""Pre-commit hook to validate settings.json"""

import json
import sys
from pathlib import Path

try:
    import requests
    from jsonschema import validate, ValidationError
except ImportError:
    print("⚠️  jsonschema not installed, skipping validation")
    print("   Install with: pip install jsonschema requests")
    sys.exit(0)

def validate_settings():
    """Validate all settings.json files in the project"""

    schema_url = "https://json.schemastore.org/claude-code-settings.json"

    # Find settings files
    settings_files = [
        Path.home() / '.claude' / 'settings.json',
        Path('.claude') / 'settings.json',
    ]

    errors = []

    for settings_file in settings_files:
        if not settings_file.exists():
            continue

        print(f"🔍 Validating {settings_file}...")

        try:
            # Load schema
            schema = requests.get(schema_url, timeout=5).json()

            # Load settings
            with open(settings_file, 'r') as f:
                settings = json.load(f)

            # Validate
            validate(instance=settings, schema=schema)
            print(f"   ✅ Valid")

        except ValidationError as e:
            print(f"   ❌ Validation error: {e.message}")
            print(f"      Path: {' -> '.join(str(p) for p in e.path)}")
            errors.append((settings_file, e))
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON: {e}")
            errors.append((settings_file, e))
        except Exception as e:
            print(f"   ⚠️  Error validating: {e}")

    if errors:
        print(f"\n❌ Found {len(errors)} validation error(s)")
        return False

    print(f"\n✅ All settings files valid")
    return True

if __name__ == "__main__":
    success = validate_settings()
    sys.exit(0 if success else 1)
```

**Register in .claude/settings.json**:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'if [[ \"$CLAUDE_TOOL_INPUT\" == *\"settings.json\"* ]]; then python3 .claude/hooks/validate_settings.py; fi'",
            "description": "Validate settings.json before writing"
          }
        ]
      }
    ]
  }
}
```

### Method 2: Using /doctor Command

The simplest validation method:

```bash
# Run validation
/doctor
```

**Advantages**:
- Built into Claude Code
- No external dependencies
- Validates settings, agents, hooks
- Fast and reliable

**Pre-commit hook**:

```bash
#!/bin/bash
# .claude/hooks/pre_commit_validation.sh

echo "🔍 Running Claude Code validation..."

# Run /doctor (requires claude CLI)
if command -v claude >/dev/null 2>&1; then
    claude /doctor --quiet || {
        echo "❌ /doctor validation failed"
        exit 1
    }
    echo "✅ /doctor validation passed"
else
    echo "⚠️  claude CLI not found, skipping /doctor validation"
fi

exit 0
```

## 🧪 Agent Frontmatter Validation

### Validation Script for Agent Files

**File**: `.claude/hooks/validate_agents.py`

```python
#!/usr/bin/env python3
"""Validate Claude Code agent frontmatter"""

import re
import sys
from pathlib import Path

def validate_agent_frontmatter(agent_file):
    """Validate agent file frontmatter"""

    with open(agent_file, 'r') as f:
        content = f.read()

    # Check for frontmatter
    if not content.startswith('---\n'):
        return False, "Missing frontmatter opening '---'"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter structure"

    frontmatter = match.group(1)

    # Check required fields
    required_fields = ['name', 'description']
    missing_fields = []

    for field in required_fields:
        pattern = f'^{field}:\\s*.+$'
        if not re.search(pattern, frontmatter, re.MULTILINE):
            missing_fields.append(field)

    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    # Check for quoted values (should be unquoted)
    quoted_pattern = r'^(name|description):\s*["\']'
    if re.search(quoted_pattern, frontmatter, re.MULTILINE):
        return False, "Frontmatter values should be unquoted (remove quotes)"

    return True, "Valid"

def validate_all_agents():
    """Validate all agent files"""

    agent_dirs = [
        Path('.claude') / 'agents',
        Path.home() / '.claude' / 'agents',
    ]

    errors = []

    for agent_dir in agent_dirs:
        if not agent_dir.exists():
            continue

        for agent_file in agent_dir.glob('*.md'):
            print(f"🔍 Validating {agent_file.name}...")

            valid, message = validate_agent_frontmatter(agent_file)

            if valid:
                print(f"   ✅ {message}")
            else:
                print(f"   ❌ {message}")
                errors.append((agent_file, message))

    if errors:
        print(f"\n❌ Found {len(errors)} agent validation error(s)")
        return False

    print(f"\n✅ All agents valid")
    return True

if __name__ == "__main__":
    success = validate_all_agents()
    sys.exit(0 if success else 1)
```

## 🚀 CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/validate-claude-config.yml`

```yaml
name: Validate Claude Code Configuration

on:
  pull_request:
    paths:
      - '.claude/**'
  push:
    branches: [main]
    paths:
      - '.claude/**'

jobs:
  validate:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install jsonschema requests pyyaml

      - name: Validate settings.json
        run: |
          python3 .claude/hooks/validate_settings.py

      - name: Validate agent frontmatter
        run: |
          python3 .claude/hooks/validate_agents.py

      - name: Check JSON syntax
        run: |
          for file in $(find .claude -name "*.json"); do
            echo "Checking $file..."
            python3 -m json.tool "$file" > /dev/null
          done
```

### Pre-commit Framework Integration

**File**: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: validate-claude-settings
        name: Validate Claude Code settings
        entry: python3 .claude/hooks/validate_settings.py
        language: system
        pass_filenames: false
        files: '\.claude/settings\.json$'

      - id: validate-claude-agents
        name: Validate Claude Code agents
        entry: python3 .claude/hooks/validate_agents.py
        language: system
        pass_filenames: false
        files: '\.claude/agents/.*\.md$'

      - id: check-claude-json
        name: Check Claude Code JSON syntax
        entry: python3 -m json.tool
        language: system
        files: '\.claude/.*\.json$'
```

## 📊 Complete Test Suite Example

**File**: `tests/test_claude_config.py`

```python
#!/usr/bin/env python3
"""Complete test suite for Claude Code configuration"""

import json
import unittest
from pathlib import Path
import requests
from jsonschema import validate, ValidationError

class TestClaudeCodeConfig(unittest.TestCase):
    """Test Claude Code configuration files"""

    @classmethod
    def setUpClass(cls):
        """Load schema once for all tests"""
        schema_url = "https://json.schemastore.org/claude-code-settings.json"
        cls.schema = requests.get(schema_url).json()

    def test_project_settings_valid(self):
        """Test project settings.json is valid"""
        settings_file = Path('.claude/settings.json')
        self.assertTrue(settings_file.exists(), "settings.json not found")

        with open(settings_file, 'r') as f:
            settings = json.load(f)

        # Should not raise ValidationError
        validate(instance=settings, schema=self.schema)

    def test_settings_has_schema_reference(self):
        """Test settings.json includes $schema field"""
        with open('.claude/settings.json', 'r') as f:
            settings = json.load(f)

        self.assertIn('$schema', settings, "$schema field missing")
        self.assertIn('json.schemastore.org', settings['$schema'])

    def test_hooks_use_string_matchers(self):
        """Test all hooks use string matchers (not objects)"""
        with open('.claude/settings.json', 'r') as f:
            settings = json.load(f)

        if 'hooks' not in settings:
            return  # No hooks to test

        for hook_type, hooks_list in settings['hooks'].items():
            for i, hook_entry in enumerate(hooks_list):
                if 'matcher' in hook_entry:
                    self.assertIsInstance(
                        hook_entry['matcher'],
                        str,
                        f"{hook_type}[{i}] matcher should be string, not object"
                    )

    def test_agent_frontmatter(self):
        """Test all agents have valid frontmatter"""
        agents_dir = Path('.claude/agents')
        if not agents_dir.exists():
            self.skipTest("No agents directory")

        for agent_file in agents_dir.glob('*.md'):
            with self.subTest(agent=agent_file.name):
                with open(agent_file, 'r') as f:
                    content = f.read()

                # Check frontmatter exists
                self.assertTrue(
                    content.startswith('---\n'),
                    f"{agent_file.name}: Missing frontmatter"
                )

                # Extract frontmatter
                import re
                match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
                self.assertIsNotNone(match, f"{agent_file.name}: Invalid frontmatter")

                frontmatter = match.group(1)

                # Check required fields
                self.assertRegex(
                    frontmatter,
                    r'^name:\s*.+$',
                    f"{agent_file.name}: Missing name field",
                    flags=re.MULTILINE
                )
                self.assertRegex(
                    frontmatter,
                    r'^description:\s*.+$',
                    f"{agent_file.name}: Missing description field",
                    flags=re.MULTILINE
                )

                # Check values are unquoted
                self.assertNotRegex(
                    frontmatter,
                    r'^(name|description):\s*["\']',
                    f"{agent_file.name}: Values should be unquoted",
                    flags=re.MULTILINE
                )

if __name__ == '__main__':
    unittest.main()
```

**Run tests**:
```bash
# Run all tests
python3 tests/test_claude_config.py

# Run specific test
python3 tests/test_claude_config.py TestClaudeCodeConfig.test_hooks_use_string_matchers

# Verbose output
python3 tests/test_claude_config.py -v
```

## 🎯 Best Practices

### 1. Always Use Official Schema

Add `$schema` field to all settings.json files:
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  ...
}
```

### 2. Enable IDE Validation

Configure your IDE to use JSON Schema validation:
- **VS Code**: Automatic with `$schema` field
- **IntelliJ**: Enable JSON Schema support
- **Vim/Neovim**: Use CoC with json plugin

### 3. Run /doctor Regularly

```bash
# Before commits
/doctor

# In CI/CD
claude /doctor --quiet
```

### 4. Validate in Pre-commit Hooks

Add validation to prevent invalid configs:
```bash
#!/bin/bash
python3 .claude/hooks/validate_settings.py || exit 1
python3 .claude/hooks/validate_agents.py || exit 1
```

### 5. Test in CI/CD

Add validation to your CI pipeline:
```yaml
- name: Validate Claude Config
  run: |
    python3 tests/test_claude_config.py
```

## 🔍 Troubleshooting

### Schema Validation Fails

**Problem**: `jsonschema` validation errors

**Solution**:
1. Check official schema is accessible: `curl https://json.schemastore.org/claude-code-settings.json`
2. Verify JSON syntax: `python3 -m json.tool settings.json`
3. Run `/doctor` for official validation
4. Check schema version matches Claude Code version

### IDE Not Showing Validation

**Problem**: No autocomplete or error highlighting

**Solution**:
1. Ensure `$schema` field is present
2. Reload IDE window/restart
3. Check JSON Schema plugin is installed
4. Verify settings.json is recognized as JSON file

### Agent Frontmatter Errors

**Problem**: Agent parse errors in `/doctor`

**Solution**:
1. Run validation script: `python3 .claude/hooks/validate_agents.py`
2. Check frontmatter uses unquoted values
3. Verify both `name` and `description` fields present
4. Ensure frontmatter structure: `---\nfields\n---`

## 📚 Additional Resources

- **Official Schema**: https://json.schemastore.org/claude-code-settings.json
- **GitHub Issue #2783**: Settings schema discussion (resolved)
- **Community Tool**: https://github.com/spences10/claude-code-settings-schema
- **Python Validator**: https://github.com/trial123Zel/claude-json-validator
- **JSON Schema Docs**: https://json-schema.org/

---

**Last Updated**: 2025-11-17
**Schema Version**: As of September 29, 2025
**Applies To**: Claude Code 2.0+
