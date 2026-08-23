# Slash Command Recognition Research

## Research Findings: Why Claude Fails to Recognize Slash Commands

### Primary Failure Pattern
Claude sometimes responds "I don't recognize command X" without verifying if the command actually exists in `.claude/commands/`.

### Root Causes Identified

#### 1. Memory-Based Response Pattern
- **Issue**: Claude relies on cached/trained knowledge instead of checking filesystem
- **Example**: `/nb` command exists as alias in `newbranch.md` but Claude claimed it didn't exist
- **Solution**: ALWAYS check `.claude/commands/` directory before responding

#### 2. Alias Blindness
- **Issue**: Commands can have aliases defined in other .md files
- **Common aliases**:
  - `/nb` → `/newbranch` (defined in newbranch.md)
  - `/e` → `/execute` (defined in e.md)
  - `/debugp` → `/debug-protocol` (defined in debugp.md)
- **Solution**: Check for both direct command files AND search for aliases

#### 3. System Default Override
- **Issue**: Built-in behaviors may override custom commands
- **Research finding**: AI assistants prioritize system defaults over user-defined commands
- **Solution**: Explicit filesystem check overrides default assumptions

#### 4. Configuration/Cache Issues
- **Issue**: Stale or cached command knowledge
- **Pattern**: Commands appear missing until configuration reset
- **Solution**: Real-time filesystem verification bypasses cache

#### 5. Path Validation Flaws
- **Issue**: Simple prefix matching can fail with similar names
- **Example**: `/nb` might not match if only looking for exact `nb.md`
- **Solution**: Search content of all .md files for command definitions

### Research Sources
- Perplexity analysis of AI command recognition failures
- GitHub issues #4450, #1212 from Claude Code repository
- Analysis of actual failure case with `/nb reactr_continued`

### Prevention Protocol (Added to CLAUDE.md)

```markdown
🚨 **SLASH COMMAND VERIFICATION PROTOCOL**: ⚠️ MANDATORY
- ❌ **NEVER say "I don't recognize command X"** without checking `.claude/commands/` FIRST
- ✅ **ALWAYS check for aliases**: Commands may exist in other .md files
- ✅ **Filesystem is truth**: Check files, don't rely on memory
- ✅ **Pattern**: User types /command → Check filesystem → Execute or explain
```

### Key Learning
**Filesystem is the source of truth, not Claude's memory.** Every slash command claim must be verified against actual files.

## Implementation Checklist
- [x] Added verification protocol to CLAUDE.md
- [x] Documented common aliases
- [x] Created memory entity for pattern recognition
- [x] Researched external sources for failure patterns
- [x] Documented findings in this file

## Future Improvements
1. Create a command index file listing all aliases
2. Implement automatic alias discovery script
3. Add pre-execution validation step to all slash commands