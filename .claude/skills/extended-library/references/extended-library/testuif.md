---
description: Intelligent Regression Testing with Playwright MCP
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Automatic Thinking & Planning

**Action Steps:**
**🧠 ALWAYS START WITH `/think`:**
Execute `/think` to analyze:
1. Current PR context and changed files
2. Git diff analysis against main branch
3. Frontend vs backend changes identification
4. Risk assessment for functionality impacts
5. Test strategy prioritization

### Phase 2: Plan Adaptation

**Action Steps:**
**🎯 IF USER PROVIDED INSTRUCTIONS:**
Adapt the plan based on user input after `/testuif`:
1. Parse user requirements and constraints
2. Modify testing scope and priorities accordingly
3. Integrate user-specific test scenarios
4. Adjust comparison strategy as requested

**📋 DEFAULT COMPARISON STRATEGY:**
When no specific instructions given:
5. Test ALL functionality from Flask frontend in React V2
6. Ensure feature parity between old and new sites
7. Validate critical user journeys work identically
8. Document any missing or broken functionality

### Phase 3: Systematic Execution

**Action Steps:**
**⚡ ALWAYS USE `/execute`:**
Use `/execute` with comprehensive testing plan:

```
/execute
1. MANDATORY: Generate complete field interaction matrix (Campaign Type × Character × Setting × AI Options)
2. Apply smart matrix testing strategy (pairwise combinations + high-risk prioritization)
3. Set up browser automation environment (Playwright MCP with headless=true)
4. Execute Phase 1: High-risk matrix combinations (25 critical tests)
5. Execute Phase 2: Feature coverage matrix (35 comprehensive tests)
6. Execute Phase 3: Edge case matrix (20 boundary tests)
7. Test Flask frontend functionality (baseline) - ALL matrix paths
8. Test React V2 equivalent functionality - ALL matrix paths with dynamic placeholder verification
9. Compare feature parity with matrix cell-by-cell evidence
10. Document matrix findings with clickable screenshot links
11. Perform adversarial testing on previously failing matrix cells
12. Generate matrix coverage report with bug pattern analysis
13. Post comprehensive matrix results to PR documentation
```

### Phase 4: Enhanced PR Documentation with Claude Vision Analysis

**Action Steps:**
**📸 ENHANCED SCREENSHOT POSTING PROTOCOL:**
Always post screenshots to PR using structured directory with Claude vision analysis:

```
docs/pr[NUMBER]/
├── flask_baseline/
│   ├── 01_landing_page.png
│   ├── 02_campaign_list.png
│   ├── 03_campaign_creation.png
│   └── ...
├── react_v2_comparison/
│   ├── 01_landing_page.png
│   ├── 02_campaign_list.png
│   ├── 03_campaign_creation.png
│   └── ...
├── claude_vision_analysis/
│   ├── flask_vs_react_comparison.md
│   ├── hardcoded_values_detection.md
│   ├── ui_consistency_analysis.md
│   ├── functionality_gaps_identified.md
│   └── visual_regression_findings.md
├── accessibility_validation/
│   ├── flask_accessibility_tree.json
│   ├── react_accessibility_tree.json
│   ├── accessibility_comparison.md
│   └── wcag_compliance_check.md
├── technical_verification/
│   ├── dom_inspector_output.txt
│   ├── css_properties_extracted.json
│   ├── network_requests_log.json
│   ├── console_errors_warnings.txt
│   └── verification_evidence.md
├── issues_found/
│   ├── broken_functionality.png
│   ├── missing_features.png
│   ├── claude_vision_detected_issues.png
│   └── ...
└── testing_report.md
```

**🔍 CLAUDE VISION INTEGRATION WORKFLOW:**
```bash

## 📋 REFERENCE DOCUMENTATION

# Intelligent Regression Testing with Playwright MCP

**Purpose**: Perform comprehensive regression testing using `/think` and `/execute`, comparing old Flask site to new React V2 site with full functionality validation

**Action**: Always use `/think` to analyze context, then `/execute` for systematic testing. Adapts plan based on user input after command.

**Usage**:
- `/testuif` (automatic analysis and testing)
- `/testuif [specific instructions]` (adapts plan to user requirements)

## Execution Protocol

## 🚨 MANDATORY QUALITY ASSURANCE INTEGRATION

**Quality Assurance Protocol**: See [CLAUDE.md §Mandatory QA Protocol](/CLAUDE.md#-mandatory-quality-assurance-protocol). All browser testing MUST comply.

### 📋 Pre-Testing Requirements (⚠️ MANDATORY)

- **Matrix Testing**: Apply full matrix methodology per canonical protocol
- **Evidence Collection**: Screenshot every test matrix cell with path labels
- **Completion Validation**: All validation gates from QA protocol required
- **Code Scanning**: Search for hardcoded values and patterns systematically
- **Adversarial Testing**: Attempt to break claimed fixes and verify related patterns
```

**🚨 MANDATORY HEADLESS CONFIGURATION:**
```bash

# Environment variables for headless enforcement

export PLAYWRIGHT_HEADLESS=1
export BROWSER_HEADLESS=true

# Playwright MCP configuration with explicit headless flag

mcp__playwright-mcp__browser_navigate --headless=true --url="http://localhost:8081"
mcp__playwright-mcp__browser_take_screenshot --headless=true --filename="baseline.png"
```

## 🔍 Enhanced Screenshot Validation Protocol (2025)

**INTEGRATION**: Based on latest AI testing research, use advanced validation methods:

### **Method 1: Claude Vision Direct Analysis (Primary)**

```bash

# Capture screenshots to filesystem for Claude vision analysis

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
VALIDATION_DIR="/tmp/testuif_validation/$TIMESTAMP"
mkdir -p "$VALIDATION_DIR"

# Flask baseline screenshots

mcp__playwright-mcp__browser_take_screenshot --name="flask_dashboard" --path="$VALIDATION_DIR/flask_dashboard.png"
mcp__playwright-mcp__browser_take_screenshot --name="flask_campaign_creation" --path="$VALIDATION_DIR/flask_campaign_creation.png"

# React V2 comparison screenshots

mcp__playwright-mcp__browser_take_screenshot --name="react_dashboard" --path="$VALIDATION_DIR/react_dashboard.png"
mcp__playwright-mcp__browser_take_screenshot --name="react_campaign_creation" --path="$VALIDATION_DIR/react_campaign_creation.png"

# Claude analyzes screenshots directly using Read tool

echo "Screenshots saved to $VALIDATION_DIR for Claude vision analysis"
```

### **Method 2: Accessibility Tree + Visual Hybrid**

```bash

# Get structured accessibility data alongside screenshots

mcp__playwright-mcp__browser_snapshot > "$VALIDATION_DIR/flask_accessibility.json"
mcp__playwright-mcp__browser_snapshot > "$VALIDATION_DIR/react_accessibility.json"

# Cross-validate structured data with visual confirmation

# Claude can read both JSON accessibility data AND screenshot images

```

### **Method 3: Progressive Baseline Comparison**

```bash

# Create baselines if they don't exist

if [ ! -d "/tmp/testuif_baselines" ]; then
    mkdir -p /tmp/testuif_baselines
    echo "Creating baseline screenshots for future comparisons"
    mcp__playwright-mcp__browser_take_screenshot --path="/tmp/testuif_baselines/flask_baseline.png"
fi

# Compare current state against established baselines

# Use Claude vision to analyze differences between baseline and current screenshots

```

**🚨 FAILURE-EXIT SEMANTICS:**
```bash

# Exit codes for parity check failures

PARITY_CHECK_PASSED=0    # All functionality matches
PARITY_CHECK_FAILED=1    # Feature parity failures detected
CRITICAL_ERROR=2         # Browser automation or system errors

# Bail-on-failure implementation

set -e  # Exit immediately on any command failure
set -o pipefail  # Fail on any pipe command failure

# Example parity validation with non-zero exit

validate_feature_parity() {
    local flask_result="$1"
    local react_result="$2"

    if [ "$flask_result" != "$react_result" ]; then
        echo "❌ PARITY FAILURE: Feature mismatch detected"
        echo "Flask: $flask_result"
        echo "React: $react_result"
        exit $PARITY_CHECK_FAILED
    fi

    echo "✅ PARITY VERIFIED: Feature behavior matches"
    return 0
}
```

**🔄 FULL FUNCTIONALITY COMPARISON TESTING:**

**Flask Frontend (Baseline) - Test ALL of:**
- Landing page and authentication flows
- Campaign list, creation, and management
- Campaign gameplay and story continuation
- Settings, profile, and user preferences
- Navigation, routing, and deep linking
- Asset loading, performance, and errors

**React V2 Frontend (New) - Validate SAME functionality:**
- Identical user journeys and workflows
- Feature-complete comparison to Flask
- Performance and user experience validation
- Integration with Flask backend APIs
- Authentication and session management
- Error handling and edge cases

# After capturing screenshots, perform Claude vision analysis

for screenshot in "$VALIDATION_DIR"/*.png; do
    echo "Analyzing $(basename $screenshot) with Claude vision..."
    # Claude reads and analyzes each screenshot for:
    # - Hardcoded values detection ("Ser Arion", "Loading campaign details...")
    # - UI consistency verification
    # - Feature parity validation
    # - Visual regression detection
done

# Generate structured analysis reports

echo "Screenshots ready for Claude vision analysis at: $VALIDATION_DIR"
echo "Use Read tool to analyze each screenshot with specific validation prompts"
```

**📊 AUTO-GENERATE ENHANCED PR COMMENT:**
Create structured comment on PR with Claude vision analysis integration:
- **Executive Summary**: Testing results with Claude vision insights
- **Claude Vision Analysis Summary**:
  - Hardcoded values detection results
  - UI consistency findings
  - Visual regression analysis
  - Feature parity visual verification
- **Technical Verification Summary:** DOM state, CSS properties, network requests, console logs
- **Accessibility Analysis:** Tree comparison and WCAG compliance
- Feature parity analysis (✅ Working, ❌ Broken, ⚠️ Different, 🔍 Claude Vision Detected)
- **Evidence-Based Confidence Score:** Percentage based on technical + visual verification completeness
- Performance comparison between frontends
- **Claude Vision Critical Issues:** Issues detected through AI screenshot analysis
- Links to all screenshot, accessibility, AND Claude vision analysis evidence
- **Anti-bias verification:** What was tested that should NOT work
- **Visual Regression Score:** Pixel-level difference analysis
- Recommendations for deployment readiness with visual confidence metrics

## Example Execution Flows

### Basic Usage with Enhanced Validation

```
User: /testuif
Claude: /think [analyzes PR context and creates testing strategy with Claude vision integration]
Claude: /execute [comprehensive Flask vs React V2 comparison with enhanced screenshot validation]
Claude: [Posts results to docs/pr1118/ with Claude vision analysis, accessibility trees, and visual regression findings]
```

### Adapted Usage with Claude Vision Focus

```
User: /testuif and make sure you compare old site to the new site and all functionality in the old site fully tested in new site
Claude: /think [incorporates specific comparison requirements + Claude vision hardcoded value detection]
Claude: /execute [focused on complete feature parity with AI-powered visual validation]
Claude: [Detailed functionality mapping with Claude vision analysis of hardcoded "Ser Arion" and placeholder text]
```

### Custom Focus with Visual Regression

```
User: /testuif focus on campaign creation workflow and authentication only
Claude: /think [narrows scope to specified areas + progressive baseline comparison]
Claude: /execute [deep dive testing with accessibility tree + screenshot hybrid validation]
Claude: [Targeted testing report with Claude vision analysis of specific UI components]
```

### Enhanced Validation Prompt Templates

```markdown

## Claude Vision Analysis Prompts for /testuif

### Hardcoded Values Detection

"Read [screenshot] and check for:
1. Any hardcoded 'Ser Arion' character names
2. 'Loading campaign details...' placeholder text
3. Static 'intermediate • fantasy' labels
4. Non-functional button placeholders
Format as: ✅ PASS / ❌ FAIL with exact locations"

### Feature Parity Visual Verification

"Compare [flask_screenshot] with [react_screenshot]:
1. Identical UI layout and positioning
2. Same data displayed in both versions
3. Consistent button placement and functionality
4. Visual elements match expected design
Report differences with pixel-level precision"

### Visual Regression Analysis

"Analyze [current_screenshot] vs [baseline_screenshot]:
1. Layout shifts or element displacement
2. Color changes or styling differences
3. Missing or added UI elements
4. Text content modifications
Provide regression score (0-100%) with change summary"
```

## Critical Requirements

**🧠 MANDATORY SLASH COMMAND USAGE:**
- ALWAYS start with `/think` for analysis and planning
- ALWAYS use `/execute` for actual test implementation
- NEVER execute testing directly without proper slash command orchestration

**🔄 COMPLETE FUNCTIONALITY VALIDATION:**
- Test EVERY feature available in Flask frontend
- Ensure React V2 has equivalent functionality
- Document any gaps, differences, or improvements
- Validate identical user workflows and outcomes

**📸 COMPREHENSIVE VISUAL DOCUMENTATION:**
- Screenshot every major functionality in both frontends
- Organize by PR number in structured directories
- Generate comparative analysis with visual evidence
- Post complete testing report as PR comment

**🚨 ENHANCED BROWSER AUTOMATION WITH AI VALIDATION:**
- Use Playwright MCP (preferred) with Claude vision integration
- Real API calls with Firebase and Gemini (costs money!)
- **MANDATORY HEADLESS**: `PLAYWRIGHT_HEADLESS=1` environment variable enforced
- **FAILURE SEMANTICS**: Non-zero exit codes bubble up parity failures (`exit 1`)
- **AI-POWERED VALIDATION**: Claude vision analyzes screenshots for hardcoded values
- **ACCESSIBILITY TREE INTEGRATION**: Structured data + visual confirmation
- **PROGRESSIVE BASELINES**: Compare against established visual baselines
- Actual browser interactions, never HTTP simulation
- **CLI Contract**: `--headless=true --bail` flags prevent silent partial passes
- **SCREENSHOT VALIDATION**: Save to filesystem for Claude Read tool analysis

**✅ ENHANCED DEPLOYMENT READINESS ASSESSMENT:**
Final output always includes:
- Go/No-Go recommendation for React V2 deployment with Claude vision confidence
- **Claude Vision Critical Issues**: AI-detected hardcoded values and UI inconsistencies
- **Visual Regression Score**: Pixel-level difference analysis vs baselines
- Feature parity score (% complete) with visual verification
- **Accessibility Compliance Score**: WCAG validation with tree analysis
- Performance impact analysis with visual load time comparison
- **AI Validation Confidence**: Percentage based on Claude vision analysis completeness
- Risk assessment and mitigation steps with visual evidence
- **Screenshot Evidence Library**: Complete visual documentation for manual review

## Enhanced Intelligence Features (2025)

**🎯 AI-POWERED CONTEXTUAL ADAPTATION:**
- Automatically adjusts testing scope based on PR changes + Claude vision analysis
- Recognizes frontend vs backend modifications with visual impact assessment
- Prioritizes testing based on risk, impact, and AI-detected visual regressions
- Incorporates user feedback into execution plan with enhanced validation methods

**🔍 ADVANCED ISSUE DETECTION:**
- **Claude Vision Detection**: Hardcoded values, placeholder text, UI inconsistencies
- **Accessibility Analysis**: WCAG compliance through tree structure validation
- **Visual Regression**: Pixel-level difference detection vs established baselines
- MIME type errors and asset loading failures
- Authentication and session management problems
- API integration and data persistence issues
- UI/UX differences and regression bugs with visual evidence
- Performance degradation with visual load time comparison

**📋 AI-ENHANCED ACTIONABLE REPORTING:**
- **Claude Vision Findings**: Specific UI issues with exact screenshot locations
- **Visual Evidence**: Every issue backed by screenshot analysis
- **Accessibility Recommendations**: Tree-based compliance improvement suggestions
- Specific steps to fix AI-detected issues with visual context
- Priority ranking based on visual impact analysis
- Feature gap analysis with screenshot comparison evidence
- Performance optimization with visual metrics
- User experience improvements backed by AI visual analysis

**🚀 2025 AI Testing Innovation:**
- **Self-Healing Visual Baselines**: Automatically adapt to acceptable UI changes
- **Intelligent Screenshot Comparison**: AI understands meaningful vs cosmetic differences
- **Cross-Browser Visual Validation**: Multi-engine screenshot consistency checking
- **Progressive Enhancement Detection**: AI identifies improved vs broken functionality

This command provides intelligent, comprehensive regression testing that ensures your React V2 frontend is deployment-ready with full feature parity to the existing Flask frontend.
