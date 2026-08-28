---
description: MCP Agent Mail - Inter-Agent Messaging and Coordination System
type: setup
scope: project
---

# MCP Agent Mail - Inter-Agent Messaging and Coordination

This skill provides comprehensive setup and usage documentation for enabling agent-to-agent messaging and coordination via the MCP Agent Mail server.

## 📋 Overview

**Purpose**: Enable AI agents to communicate with each other through a message-passing system for coordinated work, project collaboration, and multi-agent workflows.

**Core Capabilities:**
- Register agents with unique identities
- Send messages between agents
- Reply to messages with threading
- Fetch inbox messages
- Mark messages as read
- Project-scoped communication
- Message threading and replies
- Agent discovery (whois lookup)

## 🚀 Prerequisites

- Python 3.8+ installed
- MCP Agent Mail server configured
- Project workspace initialized

## 🛠️ MCP Agent Mail Server

### Features

- **Agent Registration**: Create unique agent identities within projects
- **Message Passing**: Send structured messages between agents
- **Threading**: Reply to messages with conversation threading
- **Inbox Management**: Fetch and manage incoming messages
- **Project Scoping**: Messages are scoped to specific projects
- **Agent Discovery**: Look up agent profiles and recent activity

### Configuration in `.claude/settings.json`

```json
{
  "mcpServers": {
    "mcp-agent-mail": {
      "command": "python3",
      "args": [
        "/path/to/mcp-agent-mail/server.py",
        "--stdio"
      ]
    }
  }
}
```

## 🎯 Key Concepts

### Agents

Agents are AI workers with unique identities registered in the system:
- **Name**: Unique identifier (e.g., "BlueLake", "GreenCastle")
- **Program**: Agent type (e.g., "codex-cli", "claude-code")
- **Model**: Underlying model (e.g., "opus-4.1", "gpt5-codex")
- **Task**: Current focus/responsibility

### Projects

Projects are workspaces that scope agent communication:
- **Project Key**: Unique identifier (e.g., "/abs/path/backend")
- **Agents**: Registered agents working on the project
- **Messages**: Project-scoped message history

### Messages

Structured communications between agents:
- **Subject**: Message topic
- **Body**: Markdown-formatted content
- **Recipients**: To/CC/BCC lists
- **Threading**: Reply chains with thread IDs
- **Metadata**: Sender, timestamp, importance

## 📚 Common Workflows

### 1. Register an Agent

```python
# Auto-generated name
register_agent(
    project_key="/abs/path/backend",
    program="claude-code",
    model="opus-4.1",
    task_description="Implementing auth system"
)

# Explicit name
register_agent(
    project_key="/abs/path/backend",
    program="codex-cli",
    model="gpt5-codex",
    name="BlueLake",
    task_description="Database migrations"
)
```

### 2. Send a Message

```python
send_message(
    project_key="/abs/path/backend",
    sender_name="GreenCastle",
    to=["BlueLake"],
    subject="Auth API design review",
    body_md="Please review the attached API design...",
    importance="high",
    ack_required=True
)
```

### 3. Fetch Inbox

```python
# Recent messages
messages = fetch_inbox(
    project_key="/abs/path/backend",
    agent_name="BlueLake",
    limit=20,
    include_bodies=True
)

# Urgent only
urgent = fetch_inbox(
    project_key="/abs/path/backend",
    agent_name="BlueLake",
    urgent_only=True
)

# Since last check
new_messages = fetch_inbox(
    project_key="/abs/path/backend",
    agent_name="BlueLake",
    since_ts="2025-10-23T00:00:00+00:00"
)
```

### 4. Reply to Message

```python
reply_message(
    project_key="/abs/path/backend",
    message_id=1234,
    sender_name="BlueLake",
    body_md="I've reviewed the design. Here are my thoughts..."
)
```

### 5. Look Up Agent

```python
agent_info = whois(
    project_key="/abs/path/backend",
    agent_name="BlueLake",
    include_recent_commits=True
)
```

## 🔄 Integration Patterns

### Multi-Agent Workflows

**Orchestrated Work:**
1. **Coordinator Agent** assigns tasks via messages
2. **Worker Agents** fetch inbox for assignments
3. **Workers** send progress updates
4. **Coordinator** aggregates results

**Peer Collaboration:**
1. **Agent A** sends question/request
2. **Agent B** fetches inbox, sees message
3. **Agent B** replies with answer/result
4. **Agent A** polls for reply

### Project Coordination

**Example: PR Review Workflow**
1. **PR Agent** analyzes pull request
2. **PR Agent** sends findings to **Security Agent** and **Test Agent**
3. **Security Agent** reviews security implications
4. **Test Agent** validates test coverage
5. Both reply with approvals/concerns
6. **PR Agent** aggregates feedback

## 🎯 `/processmsgs` Command Usage

The `/processmsgs` command processes agent messages (not emails):

```bash
# Process all unread agent messages
/processmsgs

# Process messages from specific sender
/processmsgs sender:BlueLake

# Process urgent messages only
/processmsgs urgent
```

**What it does:**
1. Fetches unread messages from agent inbox
2. Classifies messages by importance
3. Drafts replies for action-required messages
4. Marks messages as read
5. Reports summary of processed messages

## 🔐 Security & Privacy

**Access Control:**
- Agents can only send messages if registered in project
- Messages are scoped to projects
- No cross-project message access

**Data Handling:**
- Messages stored in project-local Git repository
- Full audit trail via Git history
- No external API calls

## 📊 Message Categories

**URGENT**: High-priority, time-sensitive communications
- Blocking issues
- Critical decisions needed
- Deadline approaching

**ACTION_REQUIRED**: Requires response or action
- Review requests
- Questions needing answers
- Task assignments

**INFORMATION**: Status updates, notifications
- Progress reports
- Completed work notifications
- General updates

## 🛡️ Error Handling

**Common Issues:**

**MCP server unavailable:**
- Verify server configuration in settings.json
- Check server process is running
- Review server logs

**Agent not registered:**
- Call `register_agent` first
- Verify project_key matches

**Message not found:**
- Check message_id is correct
- Verify agent has access to project

## 🎓 Examples

### Multi-Agent Code Review

**Agent 1 (Reviewer):**
```python
send_message(
    project_key="/abs/path/backend",
    sender_name="ReviewBot",
    to=["CodeBot", "SecurityBot"],
    subject="PR #123 Review Request",
    body_md="Please review PR #123 for security and code quality",
    importance="high"
)
```

**Agent 2 (Security):**
```python
# Fetch inbox
messages = fetch_inbox(project_key="/abs/path/backend", agent_name="SecurityBot")

# Reply
reply_message(
    project_key="/abs/path/backend",
    message_id=messages[0]['id'],
    sender_name="SecurityBot",
    body_md="✅ No security issues found"
)
```

### Task Coordination

**Coordinator:**
```python
send_message(
    project_key="/abs/path/backend",
    sender_name="Coordinator",
    to=["WorkerA", "WorkerB"],
    subject="Task Assignment: Database Migration",
    body_md="""
## Tasks
- WorkerA: Create migration scripts
- WorkerB: Test migration on staging
    """
)
```

**Worker:**
```python
# Check inbox
tasks = fetch_inbox(project_key="/abs/path/backend", agent_name="WorkerA")

# Complete work and report
reply_message(
    project_key="/abs/path/backend",
    message_id=tasks[0]['id'],
    sender_name="WorkerA",
    body_md="✅ Migration scripts created and tested"
)
```

## 🔗 Related Tools

- **ensure_project**: Initialize project for agent communication
- **register_agent**: Create agent identity
- **send_message**: Send message to other agents
- **reply_message**: Reply to message with threading
- **fetch_inbox**: Get incoming messages
- **whois**: Look up agent information
- **mark_message_read**: Mark message as processed

## ⚙️ Best Practices

**DO:**
- Register agents before sending messages
- Use descriptive agent names and task descriptions
- Include clear subjects in messages
- Reply to messages to maintain threading
- Use importance levels appropriately
- Poll inbox regularly for new messages

**DON'T:**
- Send messages before registering agent
- Use generic/unclear subjects
- Ignore thread context when replying
- Overuse urgent importance
- Forget to mark messages as read

## 🎯 Success Criteria

Effective agent communication when:
1. ✅ Agents registered in project
2. ✅ Messages clearly structured
3. ✅ Threading maintained for conversations
4. ✅ Inbox checked regularly
5. ✅ Replies sent in timely manner
6. ✅ Message status tracked (read/unread)
