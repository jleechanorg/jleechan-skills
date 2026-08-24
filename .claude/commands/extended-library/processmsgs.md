---
description: /processmsgs - Intelligent Agent Message Processing with MCP Agent Mail
type: llm-orchestration
execution_mode: guided
---
## ⚡ EXECUTION WORKFLOW FOR CLAUDE

**🚨 CRITICAL DIRECTIVE: You are an autonomous task executor.**

**YOUR COMPLETE WORKFLOW:**
1. **Fetch messages** (metadata only, max 20)
2. **Classify by priority** (urgent, action, info, low)
3. **Send acknowledgment replies** for urgent/action items
4. **Mark messages as read**
5. **Report what you're working on**
6. **START WORKING** - Actually execute the tasks described in URGENT/ACTION messages

**🚨 MANDATORY ACTIONS FOR URGENT/ACTION MESSAGES:**
- ✅ Acknowledge the message with brief reply
- ✅ **IMMEDIATELY START WORKING** on the task described
- ✅ Search for files, check issue trackers, investigate code as needed
- ✅ Use all necessary tools (Read, Grep, Glob, Beads, GitHub, etc.)
- ✅ Complete the work fully before moving to next message
- ✅ Report results back via reply when done

**AUTONOMOUS EXECUTION WORKFLOW:**
1. **Fetch**: `fetch_inbox(include_bodies=false, limit=20)` - metadata scan
2. **Classify**: Categorize by subject/sender (urgent > action > info > low)
3. **Acknowledge**: Reply: "Acknowledged - starting work now"
4. **Execute**: **DO THE ACTUAL WORK** - investigate, code, test, fix
5. **Complete**: Reply with results when done
6. **Repeat**: Process next URGENT/ACTION message

**PERFORMANCE GUIDELINES:**
- Process urgent/action messages one at a time (sequential execution)
- Use all necessary tools to complete each task fully
- Report progress and results for each task
- Don't skip investigation steps - be thorough

**IMPORTANT:** This processes inter-agent messages from MCP Agent Mail. Your job is to acknowledge AND EXECUTE the work described in messages autonomously.

## 🚨 AUTONOMOUS EXECUTION WORKFLOW (6 STEPS)

### Step 1: 📥 Fetch Message Metadata

**Action:**
- `fetch_inbox(include_bodies=false, limit=20)` - Get subject, sender, date, importance

**Output:** List of message IDs with metadata for quick scanning

### Step 2: 🏷️ Classify Messages

**Classification Rules (metadata only):**
- **URGENT**: `importance="urgent"` OR subject contains "urgent", "blocker", "asap"
- **ACTION**: `ack_required=true` OR subject has "?", "please", "review"
- **INFO**: Status updates, progress reports
- **LOW**: Automated notifications

**Output:** Prioritized list (URGENT/ACTION first)

### Step 3: ✉️ Acknowledge First URGENT/ACTION Message

**For first URGENT/ACTION message:**
- `reply_message(body_md="Acknowledged - starting work on this now")`
- `mark_message_read(message_id=...)`

### Step 4: 🚀 Execute the Task

**🚨 CRITICAL: DO THE ACTUAL WORK**
- Search for files mentioned (Glob, Grep)
- Check issue trackers (Beads, GitHub MCP)
- Read code files (Read tool)
- Investigate requirements fully
- Write code, fix bugs, implement features
- Test your changes
- Use ALL tools needed to complete the task

**Output:** Completed work (code changes, bug fixes, implementations)

### Step 5: 📝 Report Results

**After completing work:**
- `reply_message(body_md="Completed [task summary]. [Details of what was done]")`
- Include file paths, changes made, test results

### Step 6: 🔄 Repeat or Summary

**If more URGENT/ACTION messages remain:**
- Go to Step 3 for next message

**If all urgent work complete:**
- Output final summary of all work completed

## 📋 REFERENCE DOCUMENTATION

# /processmsgs Command - Intelligent Agent Message Processing

**Usage**: `/processmsgs [options]`

**Purpose**: Automated agent message processing that reads inter-agent communications, analyzes content, and takes intelligent actions

## 🛠️ Prerequisites

- MCP Agent Mail server configured and running
- Agent registered in the project (use `register_agent` first)
- Project initialized with `ensure_project`

## 📚 Command Options

```bash
/processmsgs                    # Process all unread agent messages
/processmsgs urgent             # Process only urgent/flagged messages
/processmsgs sender:BlueLake    # Process messages from specific agent
```

## 🎯 What This Command Does

**Core Actions - FULL AUTONOMOUS EXECUTION:**
1. **Reads** unread agent messages using MCP Agent Mail tools
2. **Analyzes** content for action items, urgency, importance
3. **Classifies** messages into categories (URGENT, ACTION, INFO, LOW)
4. **Acknowledges** urgent/action messages
5. **EXECUTES** the work described in urgent/action messages autonomously
6. **Completes** tasks fully (investigates, codes, tests, fixes)
7. **Reports** results back to sender when done
8. **Marks** messages as read

**Autonomous Execution Pattern:**
- ✅ Fetch and classify messages
- ✅ Acknowledge urgent/action items immediately
- ✅ **ACTUALLY DO THE WORK** - don't just report, execute
- ✅ Use all necessary tools to complete tasks
- ✅ Report completion with results
- ✅ Move to next urgent/action message and repeat

## ⚡ Performance & Execution Strategy

**Autonomous Task Processing:**
- **20 message limit**: Fetches max 20 messages per run for classification
- **Metadata-first**: Quick classification using metadata (subject/sender/importance)
- **Sequential execution**: Process URGENT/ACTION messages one at a time
- **Full completion**: Complete each task before moving to next
- **Thorough investigation**: Use all tools needed (no shortcuts)

**Typical Performance:**
- Inbox fetch: ~2 seconds (metadata only)
- Classification: Instant (pure analysis)
- Task execution: Variable (depends on complexity)
  - Simple fixes: 1-3 minutes
  - Feature implementation: 5-15 minutes
  - Complex investigations: 15-30 minutes
- Report & reply: ~5 seconds

**Note:** This command prioritizes completion quality over speed - tasks are fully executed, not just acknowledged.

## 🚀 Workflow Integration

**Typical Use Cases:**
- **Project Coordination**: Process messages from other agents working on same project
- **Task Assignment**: Receive and acknowledge task assignments from coordinator
- **Status Updates**: Process progress reports from collaborating agents
- **Question/Answer**: Respond to questions from other agents

## 🔐 Security & Privacy

**Safe Automation Model:**
- Messages are project-scoped (no cross-project access)
- Full audit trail via Git repository
- No external API calls beyond MCP Agent Mail server
- All actions are reversible

## 📊 Success Metrics

**Processing Results Include:**
- Total messages processed
- Categories breakdown (urgent: 2, action: 5, status: 10, etc.)
- Actions taken (replies: 3, tasks extracted: 5, marked read: 15)
- Urgent items requiring immediate attention

## 🔄 Continuous Improvement

**Learning Mechanism:**
- Track which message types require action
- Improve classification accuracy over time
- Adapt to agent communication patterns
- Suggest better collaboration strategies

## 🛡️ Error Handling

**Graceful Failures:**
- MCP server unavailable → Report status, suggest troubleshooting
- Agent not registered → Provide registration instructions
- Project not initialized → Suggest running `ensure_project`
- Network issues → Retry with exponential backoff

## 🚨 CRITICAL: Classification-First Accountability

**Every message MUST be classified and reported. Actions are required when appropriate:**
- **URGENT** and **ACTION_REQUIRED** messages demand concrete follow-up (reply, task extraction, etc.)
- **STATUS_UPDATE** and **INFORMATION** messages may simply be summarized and marked read if no action is needed
- Always explain what was processed and why each item was handled that way

**NEVER output**: "I've read 10 messages" without detailing the disposition of each message.

## 📖 Related Skills

See `.claude/skills/mcp-agent-mail.md` for detailed MCP Agent Mail server setup and usage instructions.

## 🎓 Examples

### Autonomous Task Execution
```bash
/processmsgs
```
**Output:**
```
📬 Processed: 13 messages

├─ URGENT (1): Message #754 from mv - Fix multi-agent manual test serialization
├─ ACTION (0): None
├─ INFO (12): Completed work threads, status updates

🚀 Starting work on URGENT task: mcp_agent_mail-uo7

[Agent proceeds to work autonomously:]

1. ✅ Acknowledged message #754
2. 🔍 Checked Beads issue tracker (mcp_agent_mail-uo7 assigned to me)
3. 🔍 Located test file: testing_llm/MULTI_AGENT_MESSAGING_TEST.md
4. 📝 Identified issue: FastMCP Root objects not JSON serializable
5. 🔧 Applied fix: Convert results with .model_dump() before json.dump()
6. ✅ Verified fix works
7. 💬 Replied to mv with completion report

📊 Summary:
- Messages processed: 13
- Urgent tasks completed: 1
- Files modified: testing_llm/MULTI_AGENT_MESSAGING_TEST.md
- Status: All urgent work complete
```

**What happened:**
1. Fetched 13 message metadata
2. Classified #754 as URGENT (new assignment from mv)
3. Sent acknowledgment: "Acknowledged - starting work now"
4. **ACTUALLY DID THE WORK**: Searched files, checked Beads, investigated code, applied fix
5. Tested the fix to verify it works
6. Replied to mv with completion report including file changes
7. Marked #754 as read

### When Everything is Info
```bash
/processmsgs
```
**Output:**
```
📬 Processed: 8 messages

├─ URGENT (0): None
├─ ACTION (0): None
├─ INFO (8): All status updates from completed work

✅ No urgent/action items requiring work
📊 Summary: All messages are informational status updates

Performance: 1 tool call, ~3s
```

## 🔗 Integration Points

- **Project Coordination**: Multi-agent workflows via message passing
- **Task Management**: Task extraction integrates with project tracking
- **Status Reporting**: Progress updates to coordinator agents
- **Collaboration**: Inter-agent question/answer workflows

## ⚙️ Configuration

**MCP Agent Mail Setup**: See `.claude/skills/mcp-agent-mail.md` for:
- Server configuration
- Agent registration
- Project initialization
- Message sending/receiving patterns

## 🎯 Success Criteria

Command considered successful when:
1. ✅ All retrieved messages classified
2. ✅ Appropriate actions taken for each category (mandatory for URGENT/ACTION_REQUIRED)
3. ✅ Summary report generated
4. ✅ Urgent items clearly highlighted
5. ✅ User can act on provided information immediately
