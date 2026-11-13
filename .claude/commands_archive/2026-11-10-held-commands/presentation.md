---
description: /presentation
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Initial Outline Creation

**Action Steps:**
1. Create a presentation scratchpad: `roadmap/presentation_[timestamp].md`
2. Generate initial outline based on the topic
3. Structure with title, sections, and key points

### Phase 2: Interactive Q&A Refinement

**Action Steps:**
1. Present the initial outline to the user
2. Ask clarifying questions about:
   - Target audience
   - Presentation duration
   - Key messages to emphasize
   - Visual style preferences
   - Specific content requirements
3. Iterate on the outline based on feedback
4. Continue until user types "done", "proceed", or "looks good"

### Phase 3: Quality Review Chain

**Action Steps:**
Execute thinking commands in sequence:
1. **First**: Run `/thinku` on the refined outline
   - Analyze structure, flow, and completeness
   - Generate hypothesis about effectiveness
   - Verify logical consistency
2. **Then**: Run `/reviewdeep` for thorough analysis
   - Multi-perspective evaluation
   - Check for gaps or weaknesses
   - Suggest improvements
3. **Finally**: Critical review
   - Challenge assumptions
   - Identify potential issues
   - Ensure clarity and impact

### Phase 4: Presentation Generation

**Action Steps:**
1. Use python-pptx to create the PPTX file
2. Convert outline to slides with:
   - Professional formatting
   - Consistent styling
   - Appropriate layouts
   - Visual hierarchy
3. Save as `presentation_[topic]_[timestamp].pptx`

### Phase 5: Quality Assurance (/secondopinion)

**Action Steps:**
Comprehensive quality check:
1. **Devil's Advocate Review**
   - Challenge presentation logic
   - Question assumptions
   - Identify weaknesses
2. **Gemini MCP Feedback**
   - Get AI perspective on content quality
   - Check for clarity and coherence
   - Suggest improvements
3. **Web Search Validation**
   - Verify key facts and figures
   - Check current information
   - Validate claims
4. **Multi-Engine Validation**
   - Run `/perp` on key concepts using WebSearch, Perplexity, DuckDuckGo, Grok, and Gemini
   - Ensure accuracy and relevance
   - Surface additional insights or contradictions

### Phase 1: Create initial outline

**Action Steps:**
outline = create_initial_outline(topic)
save_to_scratchpad(outline)

### Phase 2: Interactive refinement

**Action Steps:**
while not user_satisfied:
    present_outline(outline)
    ask_clarifying_questions()
    outline = refine_based_on_feedback(outline)

### Phase 3: Quality review

**Action Steps:**
/thinku analyze presentation outline for completeness and flow
/reviewdeep evaluate presentation from multiple perspectives

### Phase 4: Generate presentation

**Action Steps:**
presentation = generate_pptx_from_outline(outline)

### Phase 5: Final quality assurance

**Action Steps:**
/secondopinion:
  1. Devil's advocate analysis
  2. Gemini MCP: "Review this presentation for clarity and impact"
  3. Web search key concepts for accuracy
  4. /perp validate core claims across Claude WebSearch, Perplexity, DuckDuckGo, Grok, and Gemini
```

## 📋 REFERENCE DOCUMENTATION

# /presentation

**Purpose**: Create professional presentations compatible with Google Slides through an interactive outline development process with multi-phase quality assurance.

**Aliases**: `/pres`, `/slide`

## Usage

```
/presentation [topic]
/pres "AI Safety in 2025"
/presentation /think "Climate Change Solutions"
```

## Protocol

### Current Date Awareness (macOS + Ubuntu)

Before validating facts or citing data, determine today's date so the presentation highlights recency and calls out outdated sources:

```sh
CURRENT_DATE=$(date "+%Y-%m-%d")
```

The POSIX `date` syntax above runs on both macOS and Ubuntu. If `date` is unavailable, use the following Python command instead:

```bash
python3 -c "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%d'))"
```

Incorporate `CURRENT_DATE` into research queries and explicitly note when statistics or references are older than today.

This command follows a structured multi-phase approach:

## Example Workflow

```python

# Critical review of assumptions and logic

## Key Characteristics

- **Interactive**: Develops outline through Q&A with user
- **Thorough**: Multi-phase quality review process
- **Compatible**: Generates PPTX files that work perfectly with Google Slides
- **Smart**: Uses AI thinking commands for quality assurance
- **Validated**: Cross-checks facts and claims

## Implementation Details

All logic is driven by this markdown file. The command:
1. Creates structured scratchpads for tracking
2. Uses inline Python code for generation (no external scripts)
3. Chains multiple commands for quality assurance
4. Leverages existing python-pptx installation
5. Follows explicit command sequences

## When to Use

- Creating professional presentations
- Need Google Slides compatibility
- Want thorough outline development
- Require fact-checked content
- Need multiple quality reviews

## Memory Enhancement

This command benefits from memory search to:
- Find previous presentation patterns
- Recall successful outline structures
- Apply learned best practices
- Avoid past mistakes

The command automatically searches memory for relevant presentation creation experiences.

## Command Composition

Can be combined with other commands:
- `/presentation /planexec` - Add planning phase
- `/presentation /think` - Extra deep analysis
- `/presentation /research` - Research-heavy topics
