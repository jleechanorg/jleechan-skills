---
description: Repository Scaffolding Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execution Instructions

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 2: Post-Scaffolding Checklist

**Action Steps:**
After scaffolding is complete, the LLM should guide the user through:

1. **Script Verification**: Test that all copied scripts work correctly
2. **Permission Setup**: Ensure all scripts have proper executable permissions
3. **Integration Testing**: Run a few scripts to verify they work with the project
4. **Documentation**: Update project README or docs to reference the new scripts
5. **CI/CD Integration**: If applicable, integrate scripts into existing CI pipelines
6. **Team Communication**: If working in a team, communicate the new tooling setup

## 📋 REFERENCE DOCUMENTATION

# Repository Scaffolding Command

## Overview

This command scaffolds essential development scripts from the claude-commands repository into any target repository and provides intelligent adaptation instructions to the LLM.

## Command Logic

1. **Copy Core Scripts**: Copy the following scripts from claude-commands to the target repository:

   ### Root Level Scripts:
   - `create_worktree.sh` → Copy to project root
   - `integrate.sh` → Copy to project root
   - `schedule_branch_work.sh` → Copy to project root

   ### Scripts Directory:
   - `claude_mcp.sh` → Copy to `scripts/`
   - `claude_start.sh` → Copy to `scripts/`
   - `codebase_loc.sh` → Copy to `scripts/`
   - `coverage.sh` → Copy to `scripts/`
   - `create_snapshot.sh` → Copy to `scripts/`
   - `loc.sh` → Copy to `scripts/`
   - `loc_simple.sh` → Copy to `scripts/`
   - `push.sh` → Copy to `scripts/`
   - `resolve_conflicts.sh` → Copy to `scripts/`
   - `run_lint.sh` → Copy to `scripts/`
   - `run_tests_with_coverage.sh` → Copy to `scripts/`
   - `setup-github-runner.sh` → Copy to `scripts/`
   - `setup_email.sh` → Copy to `scripts/`
   - `sync_branch.sh` → Copy to `scripts/`

## Repository Location

The source scripts live in the [`jleechanorg/claude-commands`](https://github.com/jleechanorg/claude-commands) repository.
Clone that repository locally and set `CLAUDE_COMMANDS_PATH` to the absolute path of the clone (for example,
`~/workspace/claude-commands`). The slash command assumes that location unless you override the variable.

When this command is run:

```bash

# 1. Create scripts directory if it doesn't exist

mkdir -p scripts

# 2. Copy all specified scripts from claude-commands repository

# Note: CLAUDE_COMMANDS_PATH must point at your local claude-commands clone

cp "$CLAUDE_COMMANDS_PATH/create_worktree.sh" ./
cp "$CLAUDE_COMMANDS_PATH/integrate.sh" ./
cp "$CLAUDE_COMMANDS_PATH/schedule_branch_work.sh" ./

cp "$CLAUDE_COMMANDS_PATH/scripts/claude_mcp.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/claude_start.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/codebase_loc.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/coverage.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/create_snapshot.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/loc.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/loc_simple.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/push.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/resolve_conflicts.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/run_lint.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/run_tests_with_coverage.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/setup-github-runner.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/setup_email.sh" ./scripts/
cp "$CLAUDE_COMMANDS_PATH/scripts/sync_branch.sh" ./scripts/

# 3. Make all scripts executable

chmod +x *.sh scripts/*.sh
```

## LLM Adaptation Instructions

After copying the scripts, the LLM should analyze the target repository and adapt the scripts according to these guidelines:

### 1. **Technology Stack Detection**

- Examine `package.json`, `Cargo.toml`, `requirements.txt`, `go.mod`, etc.
- Identify the primary programming language and framework
- Detect testing frameworks (Jest, pytest, Go test, etc.)
- Identify linting tools (ESLint, pylint, golangci-lint, etc.)

### 2. **Script Adaptations Required**

#### `run_lint.sh` adaptations:

- **Node.js/TypeScript**: Update to use `npm run lint` or `npx eslint`
- **Python**: Update to use `flake8`, `black`, `ruff`, or `pylint`
- **Go**: Update to use `golangci-lint run`
- **Rust**: Update to use `cargo clippy`
- **Java**: Update to use `checkstyle` or `spotbugs`

#### `run_tests_with_coverage.sh` adaptations:

- **Node.js/TypeScript**: Update to use `npm test` with `jest --coverage` or `nyc`
- **Python**: Update to use `pytest --cov=.` or `coverage run -m pytest`
- **Go**: Update to use `go test -coverprofile=coverage.out ./...`
- **Rust**: Update to use `cargo test` with `cargo tarpaulin`
- **Java**: Update to use Maven/Gradle with JaCoCo

#### `coverage.sh` adaptations:

- Update coverage report generation commands based on detected tools
- Update coverage report paths and formats
- Configure coverage thresholds appropriate for the project

### 3. **Repository-Specific Customizations**

#### CI/CD Integration:

- If `.github/workflows/` exists, suggest integrating scripts into GitHub Actions
- If `.gitlab-ci.yml` exists, suggest GitLab CI integration
- If other CI systems detected, provide appropriate integration suggestions

#### Git Hooks:

- Suggest setting up pre-commit hooks using `setup-github-runner.sh` as a template
- Adapt hook scripts to run the repository's specific linting and testing commands

#### Documentation Updates:

- If `README.md` exists, suggest adding a "Development Scripts" section
- Document how to run each script and what it does
- Provide examples of common development workflows

### 4. **Configuration File Updates**

#### Package Manager Scripts:

- **Node.js**: Add script shortcuts to `package.json` scripts section
- **Python**: Suggest adding scripts to `pyproject.toml` or `setup.py`
- **Rust**: Add script shortcuts to `Cargo.toml`

#### Example `package.json` additions:

```json
{
  "scripts": {
    "scaffold:lint": "./scripts/run_lint.sh",
    "scaffold:test": "./scripts/run_tests_with_coverage.sh",
    "scaffold:coverage": "./scripts/coverage.sh",
    "scaffold:loc": "./scripts/loc.sh"
  }
}
```

## Usage Example

```bash

# User runs the scaffold command

/scaffold

# The LLM will:

# 1. Copy all specified scripts to the current repository

# 2. Analyze the project structure (package.json, requirements.txt, etc.)

# 3. Provide specific adaptation instructions for the detected stack

# 4. Suggest integration points and next steps

# 5. Update relevant configuration files if requested

```

## Benefits

- **Consistency**: All repositories get the same base set of development tools
- **Rapid Setup**: New projects can be scaffolded with essential scripts in minutes
- **Technology Adaptation**: Scripts are intelligently adapted to the specific tech stack
- **Standardization**: Teams can maintain consistent development workflows
- **Time Savings**: Avoids manual setup of common development infrastructure
- **Best Practices**: Scripts embody established development and deployment patterns

## Notes

- The LLM should ask for confirmation before making any file modifications
- Always preserve existing scripts - rename or backup before replacing
- Provide clear documentation about what each script does
- Consider the specific needs and conventions of the target repository
- Test adapted scripts in a safe environment before recommending their use
