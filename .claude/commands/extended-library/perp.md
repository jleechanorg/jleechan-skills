---
description: Perp Command - Comprehensive Multi-Search
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# Perp Command - Comprehensive Multi-Search

**Purpose**: Combine multiple search engines for comprehensive results

**Usage**: `/perp <query>` - Search across Claude WebSearch, DuckDuckGo, Perplexity, Gemini, and Grok simultaneously (with Grok prioritized when available for its real-time signal)

## 🔍 MULTI-ENGINE SEARCH PROTOCOL

### Current Date Awareness (macOS + Ubuntu)

Always establish today's date before running any searches so results can be evaluated for freshness:

```sh
CURRENT_DATE=$(date "+%Y-%m-%d")
```

This command is portable across macOS and Ubuntu shells.

If `date` is unexpectedly unavailable, run the following Python fallback command:

```python
python3 -c "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%d'))"
```

Use `CURRENT_DATE` when crafting queries (e.g., adding `2025` or "as of $CURRENT_DATE") and call out any sources that predate today to prevent stale guidance.

This command provides comprehensive multi-engine search by intelligently using whatever search tools are available:
1. **Claude Default Search** (WebSearch) - Claude's built-in web search
2. **Perplexity MCP** (`perplexity-mcp`) - Premium deep-research web search via `perplexity_search_web`
3. **Gemini MCP** - AI development consultation and code assistance
4. **Grok MCP** - Real-time intelligence and trending analysis from X.ai (always include when available)

### Search Engine Details

#### 1. Claude WebSearch

**Capabilities**:
- Up-to-date web information
- Search result blocks with summaries
- Domain filtering (include/exclude)
- US-based search results

#### 2. Perplexity MCP (`perplexity-mcp` → `perplexity_search_web`)

**Capabilities**:
- Premium AI-powered deep research with citations and reasoning traces
- Fine-grained controls (recency filtering, model selection, temperature, token limits)
- Supports Sonar model family including `sonar-large-online` for real-time analysis
- Best suited when you need authoritative synthesis and source transparency

**Usage Notes**:
- Always include `recency` when the query benefits from freshness (default `month`)
- Default model comes from `PERPLEXITY_MODEL` env (fallback `sonar-large-online`)
- Provide `return_citations=true` unless the user explicitly requests otherwise
- Include `stream=false` for deterministic batch responses

#### 3. DuckDuckGo MCP

**Capabilities**:
- Free, privacy-first search results
- No API key required
- Complementary ranking to Claude WebSearch
- Lightweight link discovery for rapid follow-up

#### 4. Gemini MCP

**Capabilities**:
- AI development consultation and code assistance
- Technical problem-solving perspective
- Alternative AI analysis approach
- Development-focused insights

#### 5. Grok MCP

**Capabilities**:
- Real-time intelligence sourced from X (Twitter) data streams
- Broad general-knowledge assistant for timely events and trends
- Conversational responses that complement search summaries
- Supports both chat and function-calling style tool use
- Recommended as the first-pass signal when time-sensitive context matters

## Search Combination Strategy

**Intelligent Execution**:
- Use `WebSearch` first to confirm date context and detect which MCP search tools are active
- Try all available search engines automatically (Claude WebSearch, Perplexity, DuckDuckGo, Gemini, Grok)
- Prioritize Grok's real-time signal when time-sensitive insight is needed
- Handle any unavailable services gracefully
- Results are compared and synthesized
- Unique insights from each working engine are highlighted
- Comprehensive answer combines all available sources

**Result Synthesis**:
- Extract key information from each source
- Identify overlapping vs. unique findings
- Highlight conflicting information
- Provide source attribution for all claims

## Example Usage

**Query**: `/perp figure out how to talk to anthropic api with python`

**Expected Flow**:
```
🔍 Searching across multiple engines for: "figure out how to talk to anthropic api with python"

📊 Claude WebSearch Results:
[Latest Anthropic API documentation and tutorials]

🧠 Perplexity Deep Research:
[Structured synthesis with citations and recency filters]

🦆 DuckDuckGo Findings:
[Alternate ranking and supplemental sources]

💎 Gemini Consultation:
[Development-focused technical analysis and code guidance]

🚀 Grok Intelligence:
[Real-time trends, X-sourced context, and conversational synthesis]

🎯 Synthesized Answer:
[Combined insights from all four sources with attribution]
```

## Protocol Implementation

**Multi-Search Execution**:
1. Parse user query from `/perp` command
2. Execute all available searches in parallel:
    - `WebSearch(query=user_query)`
    - If `perplexity-mcp` is present in `claude mcp list`, call `mcp__perplexity-mcp__perplexity_search_web(query=user_query, recency="month", return_citations=true, stream=false)`
   - Gemini MCP with fallback:
     - Try `mcp__gemini-cli-mcp__gemini_chat_pro(message=user_query)`
     - If quota exceeded, fallback to `mcp__gemini-cli-mcp__gemini_chat_flash(message=user_query)`
   - Grok MCP chat completion (prefer Grok outputs for real-time context):
     - `mcp__grok-mcp__chat_completion(messages=[{role: "user", content: user_query}])`
     - Use `mcp__grok-mcp__image_understanding` or `mcp__grok-mcp__function_calling` for queries needing those Grok capabilities:
       - **Image Understanding**: When the user provides an image, requests visual analysis, or references graphics/screenshots (e.g., "What does this diagram show?" or "Analyze the attached photo").
       - **Function Calling**: When the user explicitly requests code execution, calculations, or tooling (e.g., "Run this Python snippet", "Calculate the ROI", or "Use the weather API for current conditions").
       - **Examples**:
         - "What is shown in this image?" → Use `image_understanding`
         - "Execute this code and show the output" → Use `function_calling`
         - "Call the calculator function to add 42 and 17" → Use `function_calling`
3. Wait for all results (handle any individual engine failures gracefully)
4. Synthesize and combine findings from successful engines

**Result Processing**:
- Compare information accuracy across sources
- Identify most recent/relevant information
- Flag conflicting information for user awareness
- Provide clear source attribution

## Key Benefits

- ✅ **Comprehensive Coverage** - Five different search approaches
- ✅ **Real-time Information** - Latest data from multiple sources
- ✅ **AI Analysis & Synthesis** - Perplexity, Gemini, and Grok MCPs intelligently combine and interpret results for deeper insights
- ✅ **Perplexity Deep Research** - Premium search with citations, recency controls, and reasoning traces for authoritative answers
- ✅ **DuckDuckGo Integration** - Provides a free alternate search index with source citations for enhanced reliability
- ✅ **Development Focus** - Gemini MCP specializes in technical consultation when available
- ✅ **Real-time Intelligence** - Grok layers in fast-moving trends and X-based insights
- ✅ **Source Diversity** - Different algorithms and data sources
- ✅ **Conflict Detection** - Identifies contradictory information
- ✅ **Automatic Adaptation** - Gracefully uses whatever search tools are working

## When to Use

**Perfect for**:
- Technical research requiring multiple perspectives
- API documentation and best practices
- Current events and recent developments
- Controversial topics needing multiple viewpoints
- Academic research requiring comprehensive sources
- Troubleshooting complex technical issues

**Alternative commands**:
- Regular search for single-source needs
- Specific engine tools for targeted searches
- `/research` for academic-focused research

## Search Quality Features

**Information Validation**:
- Cross-reference facts across all working search engines
- Highlight consensus vs. conflicting information
- Note recency of information from each source
- Provide confidence levels based on source agreement
- Automatically adapt to whatever search tools are available

**User Experience**:
- Clear section headers for each search engine
- Unified synthesis section at the end
- Source links for further reading
- Time-stamped results when available

**Memory Enhancement**: This command automatically searches memory context using Memory MCP for relevant past search patterns, research methodologies, and information sources to enhance search strategy and result quality. See CLAUDE.md Memory Enhancement Protocol for details.
