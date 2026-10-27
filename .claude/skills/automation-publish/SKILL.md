---
name: automation-publish
description: Automation Package Publishing Command - Publish both orchestration and automation packages to PyPI
---

## Command Summary
Publish `jleechanorg-orchestration` and `jleechanorg-pr-automation` to PyPI and verify the installed packages. Verify scheduled automation only when it is part of the requested outcome, using the selected job's current configuration.

## EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**

## CRITICAL: Both Packages Must Be Published

The `jleechanorg-pr-automation` package depends on `jleechanorg-orchestration`.
**You MUST publish BOTH packages** to ensure the CLI validation code is in sync.

## EXECUTION WORKFLOW

### Phase 1: Bump Orchestration Version

**Action Steps:**
1. Read current version from `orchestration/pyproject.toml`
2. Increment patch version (e.g., `0.1.32` → `0.1.33`)
3. Update version in `orchestration/pyproject.toml`

### Phase 2: Build and Publish Orchestration

**Action Steps:**
1. Navigate to `orchestration/` directory
2. Clean previous builds: `rm -rf dist/ build/ *.egg-info`
3. Build package: `python3 -m build`
4. Upload to PyPI: `python3 -m twine upload --repository pypi dist/jleechanorg_orchestration-*`
5. Wait 15-20 seconds for PyPI propagation

### Phase 3: Bump Automation Version

**Action Steps:**
1. Read current version from `automation/pyproject.toml`
2. Increment patch version (e.g., `0.2.112` → `0.2.113`)
3. Update version in `automation/pyproject.toml`

### Phase 4: Build and Publish Automation

**Action Steps:**
1. Navigate to `automation/` directory
2. Clean previous builds: `rm -rf dist/ build/ *.egg-info`
3. Build package: `python3 -m build`
4. Upload to PyPI: `python3 -m twine upload --repository pypi dist/jleechanorg_pr_automation-*`
5. Wait 15-20 seconds for PyPI propagation

### Phase 5: Install Both from PyPI (NOT editable)

**Action Steps:**
1. Uninstall any existing versions: `pip uninstall -y jleechanorg-orchestration jleechanorg-pr-automation`
2. Install BOTH from PyPI (specific versions):
   ```
   pip install jleechanorg-orchestration==X.Y.Z jleechanorg-pr-automation==A.B.C
   ```
3. **CRITICAL VERIFICATION** - Run from /tmp to avoid local package shadowing:
   ```
   cd /tmp && python3 -c "
   import orchestration
   import jleechanorg_pr_automation
   print('Orchestration from:', orchestration.__file__)
   print('Automation from:', jleechanorg_pr_automation.__file__)
   # Both MUST show site-packages, NOT local worktree paths
   assert 'site-packages' in orchestration.__file__, 'Orchestration not from PyPI!'
   assert 'site-packages' in jleechanorg_pr_automation.__file__, 'Automation not from PyPI!'
   print('SUCCESS: Both packages installed from PyPI')
   "
   ```
4. **CRITICAL VERIFICATION** - Verify CLI validation imports resolve from the installed packages (still from /tmp):
   ```
   cd /tmp && python3 -c "
   from orchestration import cli_validation
   from jleechanorg_pr_automation import jleechanorg_pr_monitor
   print('CLI validation module:', cli_validation.__file__)
   print('PR monitor module:', jleechanorg_pr_monitor.__file__)
   assert 'site-packages' in cli_validation.__file__, 'cli_validation not from PyPI!'
   assert 'site-packages' in jleechanorg_pr_monitor.__file__, 'pr_monitor not from PyPI!'
   print('SUCCESS: CLI validation and monitor resolve from PyPI')
   "
   ```

### Phase 6: Commit and Push

**Action Steps:**
1. Commit both version bumps:
   ```
   git add automation/pyproject.toml orchestration/pyproject.toml
   git commit -m "chore: Publish automation X.Y.Z and orchestration A.B.C to PyPI"
   ```
2. Push to remote: `git push origin <branch-name>`

### Phase 7: Verify a Requested Scheduled Job

Package publication does not authorize terminating scheduled processes or
launching every configured job. Inspect only the requested job and preserve all
existing schedule entries, especially credential-bearing `GITHUB_TOKEN` lines.

**Action Steps:**
1. Read the current scheduled-job definition through its credential-safe path; never print raw crontab lines.
2. Select only the requested job and preserve its configured environment without copying credential values into command arguments or logs.
3. If an existing task-owned process must be stopped, verify its exact PID, owner, and worktree, then follow that service's cleanup owner. Never use `pkill` or a process-name/port sweep.
4. Verify the selected job's actual output and exit status. A running process or a message that jobs were launched does not prove the job completed successfully.

## VERIFICATION CHECKLIST

After completion, verify:
- [ ] Both packages show `site-packages` path (not local worktree)
- [ ] CLI validation imports resolve from PyPI: verify module paths include `site-packages`
- [ ] `jleechanorg-pr-monitor --help` works
- [ ] Any requested scheduled job completed with its actual output and exit status verified

## REFERENCE DOCUMENTATION

### Purpose
Automate publishing BOTH `jleechanorg-orchestration` and `jleechanorg-pr-automation` packages:
1. Orchestration contains CLI validation code
2. Automation depends on orchestration
3. Both must be published together to stay in sync

### Why Both Packages?
- `jleechanorg-orchestration` contains `cli_validation.py` with quota detection
- `jleechanorg-pr-automation` imports from orchestration
- If only automation is published, the cron job may use stale orchestration code

### Common Failure Modes
1. **Editable install shadowing**: Local `orchestration/` directory shadows PyPI package
   - Fix: Run verification from `/tmp`, not from worktree directory
2. **PyPI propagation delay**: Package not available immediately after upload
   - Fix: Wait 15-20 seconds between upload and install
3. **Stale pip cache**: pip installs old cached version
   - Fix: Use explicit version pinning `==X.Y.Z`

### Prerequisites
- `python3` with `build` and `twine` packages installed
- PyPI credentials configured (via `PYPI_TOKEN` or `~/.pypirc`)
- Git repository with both `automation/pyproject.toml` and `orchestration/pyproject.toml`
