---
description: /memory Command - Memory MCP Interaction with Query Optimization
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: 🎯 Actions

**Action Steps:**
1. **search** [query] - Perform optimized Memory MCP search with query transformation
2. **learn** [content] - Create entities and relationships from provided content
3. **recall** [topic] - Retrieve specific knowledge by topic
4. **graph** - Display knowledge network overview
5. **optimize** [query] - Test query optimization without executing search

### Phase 2: 🔍 SEARCH Action

**Action Steps:**
1. **Query Optimization**: Use the configured Memory MCP optimization workflow instead of referencing a repo-local optimizer script
2. **Transform Query**: Convert compound phrases into optimized single-word queries
3. **Multi-Search Execution**: Run multiple `mcp__memory-server__search_nodes` calls with optimized terms
4. **Result Merging**: Combine and deduplicate results from all searches
5. **Relevance Scoring**: Score results by relevance to original query
6. **Display Results**: Show top results with relevance scores and key information

### Phase 3: 📚 LEARN Action

**Action Steps:**
1. **Content Analysis**: Parse user content for entities and relationships
2. **Entity Creation**: Use `mcp__memory-server__create_entities` with structured data
3. **Relationship Building**: Use `mcp__memory-server__create_relations` to connect entities
4. **Confirmation**: Report successful creations and any failures

### Phase 4: 🧠 RECALL Action

**Action Steps:**
1. **Direct Search**: Use `mcp__memory-server__search_nodes` with topic
2. **Knowledge Retrieval**: Display entities related to the topic
3. **Context Display**: Show key observations and relationships

### Phase 5: 🌐 GRAPH Action

**Action Steps:**
1. **Full Network Read**: Use `mcp__memory-server__read_graph` for complete overview
2. **Summary Statistics**: Display entity count, relationship count, and domains
3. **Network Overview**: Show key patterns and coverage areas

### Phase 6: 🔬 OPTIMIZE Action

**Action Steps:**
1. **Query Analysis**: Load MemoryMCPOptimizer system
2. **Transformation Test**: Show original vs optimized query terms
3. **Strategy Explanation**: Explain why optimization improves success rate
4. **No Execution**: Test optimization without actually searching

## 📋 REFERENCE DOCUMENTATION

# /memory Command - Memory MCP Interaction with Query Optimization

**Usage**: `/memory [action] [query/params]`

**Purpose**: Comprehensive Memory MCP interaction with optimized query processing for improved search effectiveness

## 📚 Examples

```bash
/memory search "decision influence patterns"
/memory learn "Query optimization improves Memory MCP search success from 30% to 70%+"
/memory recall investigation
/memory graph
/memory optimize "compound query transformation effectiveness"
```

## 🚀 Implementation

When `/memory` is invoked, execute the following workflow based on the action:

## 🛠️ Query Optimization Integration

**Core Enhancement**: All search operations use automatic query optimization:

- **Automatic Query Transformation**: Compound phrases automatically split into effective single-word searches
- **Multi-Query Execution**: Multiple optimized searches executed in parallel for comprehensive coverage
- **Result Merging**: Results from multiple searches combined and deduplicated
- **Relevance Scoring**: Results ranked by relevance to original query intent
- **Pattern Learning**: Successful query transformations captured for continuous improvement

**Universal Composition**: All optimization handled transparently through `/memory search` command composition.

## 📊 Performance Features

- **Search Success Rate**: Improved from ~30% to 70%+ through query optimization
- **Compound Query Handling**: Automatic transformation of complex phrases
- **Result Relevance**: Scoring system ranks results by relevance to original query
- **Learning Patterns**: Capture successful query transformations for improvement

## 🚨 Error Handling

- **Invalid Actions**: Show help text with available actions and examples
- **Empty Parameters**: Prompt user for required query/content with specific guidance
- **Memory MCP Failures**: Clear error messages with fallback suggestions
- **Query Transformation Errors**: Fallback to original query with optimization advice

## 🔗 Integration Points

**Command Composition**: Works with existing Memory MCP infrastructure:
- **Optimizer System**: The configured Memory MCP search workflow for query enhancement
- **Memory MCP Tools**: All standard `mcp__memory-server__*` tools
- **Learning Integration**: Compatible with `/learn` command workflows
- **Guidelines System**: Enhances `/guidelines` Memory MCP consultations

## 💡 Usage Tips

**For Best Results**:
- Use natural language queries - optimization will handle compound phrases
- Include specific technical terms when learning new content
- Use recall for quick knowledge retrieval on familiar topics
- Run optimize first to understand how queries will be transformed

**Example Workflow**:
```bash
/memory optimize "memory mcp search effectiveness patterns"

# See optimization strategy, then run actual search:

/memory search "memory mcp search effectiveness patterns"

# Learn from results:

/memory learn "Single-word queries outperform compound phrases 70% vs 30%"
```

## 🎯 Expected Outcomes

- **Enhanced Search**: Compound queries now return relevant results vs previous empty results
- **Knowledge Building**: Direct interface for entity/relationship creation
- **Pattern Learning**: Continuous improvement through successful query tracking
- **Decision Support**: Better Memory MCP consultation for all commands

---

**Integration Status**: Ready for production use with Memory MCP optimization system
