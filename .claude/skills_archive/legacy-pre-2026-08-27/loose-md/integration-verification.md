# Integration Verification Protocol

**Purpose**: When claiming ANY integration works, you MUST provide the Three Evidence Rule to prove automatic behavior, not just manual testing.

## Three Evidence Rule (MANDATORY)

For ANY integration claim, provide ALL THREE:

| Evidence Type | What It Proves | Example |
|---------------|----------------|---------|
| **Configuration Evidence** | Feature is enabled | Config file entry, env var, feature flag |
| **Trigger Evidence** | Automatic activation | Hook registration, event listener, cron entry |
| **Log Evidence** | Actually executed | Timestamped logs from automatic (not manual) run |

## Evidence Template

```markdown
### Integration Claim: <what you're claiming works>

#### 1. Configuration Evidence
```
<actual config file content or env var showing feature enabled>
```
File: <path to config>

#### 2. Trigger Evidence
```
<code or config showing automatic trigger mechanism>
```
Mechanism: <how it triggers automatically>

#### 3. Log Evidence
```
<timestamped log output from automatic execution>
```
Timestamp: <when it ran>
Triggered by: <what caused it to run>
```

## Common Integration Claims That Require This Protocol

- "The hook is working"
- "The webhook fires automatically"
- "CI runs this on push"
- "The cron job executes"
- "The event listener handles this"
- "The middleware intercepts requests"

## Examples

### Good Evidence (Complete)

```markdown
### Integration Claim: Pre-commit hook runs fake code detection

#### 1. Configuration Evidence
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: fake-code-check
        name: Fake Code Detection
        entry: python scripts/fake_detector.py
        language: python
        types: [python]
```
File: .pre-commit-config.yaml (line 12-18)

#### 2. Trigger Evidence
```bash
$ git config --get core.hooksPath
.git/hooks
$ ls -la .git/hooks/pre-commit
-rwxr-xr-x 1 user user 478 Jan 15 10:00 .git/hooks/pre-commit
```
Mechanism: Git pre-commit hook installed via pre-commit framework

#### 3. Log Evidence
```
2025-01-15T10:05:23 [pre-commit] Running fake-code-check...
2025-01-15T10:05:24 [fake_detector] Scanning 3 files...
2025-01-15T10:05:25 [fake_detector] No fake code detected
2025-01-15T10:05:25 [pre-commit] Passed fake-code-check
```
Timestamp: 2025-01-15T10:05:23
Triggered by: `git commit -m "Add feature"` (automatic, not manual script run)
```

### Bad Evidence (Incomplete)

```markdown
### Integration Claim: Pre-commit hook runs fake code detection

"I ran the script and it worked."  <-- NO CONFIG EVIDENCE
"The config file has the hook."     <-- NO TRIGGER EVIDENCE
"Here's manual test output."        <-- NO AUTOMATIC LOG EVIDENCE
```

## Manual vs Automatic Evidence

| Evidence Type | Valid | Invalid |
|---------------|-------|---------|
| Script run manually | No | "python script.py" output |
| Script triggered by hook | Yes | Log shows hook invocation |
| Curl request sent manually | No | Manual API testing |
| Webhook received from external | Yes | Log shows webhook payload |

## Agent Verification Protocol

When verifying work done by another agent or automated process:

1. **File existence check**: `ls -la <expected files>`
2. **Git diff verification**: `git diff --stat` to see actual changes
3. **Git status check**: `git status` for uncommitted work
4. **Specific file content**: Read exact lines claimed to be modified

Never trust "it's done" without verification evidence.

## Quick Reference

Before claiming integration works:
1. Show me the CONFIG that enables it
2. Show me the TRIGGER that runs it automatically
3. Show me the LOGS from an automatic (not manual) execution

**If you cannot provide all three, the integration is NOT verified.**
