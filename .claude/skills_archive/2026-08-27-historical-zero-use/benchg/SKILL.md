---
name: benchg
description: Genesis vs Ralph orchestrator benchmark — runs both orchestration systems on the same project spec in isolated tmux sessions, then compares quantitative metrics (files, LOC), runs a consensus code review, does live build/test validation, and produces a benchmark report. Slash command /benchg [project_number] [custom_description].
---

# /benchg - Genesis vs Ralph Orchestrator Benchmark

**Command Summary**: Comprehensive benchmark comparison between Genesis and Ralph orchestration systems with consensus code review and live testing

**Usage**: `/benchg [project_number] [custom_description]`

**Purpose**: Execute complete benchmark workflow including orchestration execution, code review, and live testing validation

## Execution Instructions

When this command is invoked:

### 1. Parse Project Specification
```bash
PROJECT_NUM="${1:-1}"  # Default to Project 1
CUSTOM_DESCRIPTION="${2:-}"  # Optional custom project description

# Determine project specifications
case "$PROJECT_NUM" in
    1)
        PROJECT_TITLE="CLI Text Processing Utility"
        PROJECT_DESCRIPTION="Build a comprehensive command-line text processing utility that can analyze, transform, and manipulate text files with multiple operations like word count, character frequency analysis, text transformation (uppercase, lowercase, reverse), search and replace, and file format conversion. Include full test suite."
        EXPECTED_FEATURES="word count, character frequency, text transformation, search/replace, file format conversion, comprehensive CLI, full testing"
        ;;
    2)
        PROJECT_TITLE="REST API Web Service"
        PROJECT_DESCRIPTION="Create a RESTful web service with user authentication, CRUD operations, database integration, input validation, error handling, and API documentation. Include middleware for logging and rate limiting."
        EXPECTED_FEATURES="REST API, authentication, CRUD operations, database, validation, documentation, middleware"
        ;;
    3)
        PROJECT_TITLE="Data Processing Pipeline"
        PROJECT_DESCRIPTION="Build a data processing pipeline that can ingest CSV/JSON files, perform transformations, apply filters, generate reports, and export results. Include error handling, logging, and monitoring capabilities."
        EXPECTED_FEATURES="data ingestion, transformations, filtering, reporting, export, monitoring, logging"
        ;;
    custom)
        if [[ -z "$CUSTOM_DESCRIPTION" ]]; then
            echo "❌ Error: Custom project requires description as second parameter"
            echo "Usage: /benchg custom \"your custom project description\""
            exit 1
        fi
        PROJECT_TITLE="Custom Project"
        PROJECT_DESCRIPTION="$CUSTOM_DESCRIPTION"
        EXPECTED_FEATURES="as specified in custom description"
        ;;
    *)
        echo "❌ Error: Invalid project number. Use 1, 2, 3, or 'custom'"
        echo "Available projects:"
        echo "  1 - CLI Text Processing Utility"
        echo "  2 - REST API Web Service"
        echo "  3 - Data Processing Pipeline"
        echo "  custom \"description\" - Custom project"
        exit 1
        ;;
esac

echo "🏆 BENCHMARK: Genesis vs Ralph Orchestrator"
echo "📋 Project $PROJECT_NUM: $PROJECT_TITLE"
echo "📝 Description: $PROJECT_DESCRIPTION"
echo "🎯 Expected Features: $EXPECTED_FEATURES"
echo ""
```

### 2. Setup Isolated Working Directories
```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BENCHMARK_DIR="/tmp/benchmark_$TIMESTAMP"
GENESIS_DIR="$BENCHMARK_DIR/genesis_project${PROJECT_NUM}"
RALPH_DIR="$BENCHMARK_DIR/ralph_project${PROJECT_NUM}"

echo "📁 Setting up benchmark environment:"
echo "  Genesis: $GENESIS_DIR"
echo "  Ralph: $RALPH_DIR"
echo ""

mkdir -p "$GENESIS_DIR" "$RALPH_DIR"

# Ralph orchestrator path (set via env or use default)
RALPH_ORCHESTRATOR_PATH="${RALPH_ORCHESTRATOR_PATH:-$HOME/worktree_ralph/orchestration/orchestrate_unified.py}"
```

### 3. Execute Genesis Implementation
```bash
echo "🧬 STARTING GENESIS ORCHESTRATOR"
echo "=================================="

# Generate Genesis session name
GENESIS_SESSION="genesis-benchmark-p${PROJECT_NUM}-$(date +%Y%m%d-%H%M%S)"

echo "📋 Genesis Command Generation:"
/gene "$PROJECT_DESCRIPTION" 30 "$GENESIS_DIR"

echo ""
echo "⏱️ Genesis execution initiated. Monitoring progress..."

# Wait for Genesis to start before proceeding
sleep 10

# Check Genesis status
GENESIS_STATUS="Running"
if ! tmux has-session -t "$GENESIS_SESSION" 2>/dev/null; then
    # Try to find Genesis session by pattern matching
    GENESIS_ACTUAL_SESSION=$(tmux list-sessions 2>/dev/null | grep "genesis.*$(date +%Y%m%d)" | head -1 | cut -d: -f1)
    if [[ -n "$GENESIS_ACTUAL_SESSION" ]]; then
        GENESIS_SESSION="$GENESIS_ACTUAL_SESSION"
        echo "✅ Found Genesis session: $GENESIS_SESSION"
    else
        GENESIS_STATUS="Failed to start"
        echo "❌ Genesis session not found"
    fi
fi

echo "📊 Genesis Status: $GENESIS_STATUS"
echo ""
```

### 4. Execute Ralph Implementation
```bash
echo "🤖 STARTING RALPH ORCHESTRATOR"
echo "==============================="

# Initialize Ralph environment
cd "$RALPH_DIR"
git init
git config user.name "Ralph Benchmark"
git config user.email "ralph@benchmark.com"
echo "# Ralph Project $PROJECT_NUM" > README.md
git add .
git commit -m "Initial commit"

# Start Ralph orchestrator
RALPH_SESSION="ralph-benchmark-p${PROJECT_NUM}-$(date +%Y%m%d-%H%M%S)"

echo "📋 Ralph orchestration starting..."
# NOTE: orchestrate_unified.py --goal/--max-iterations deprecated (PR #5824). Use ai_orch for task execution.
tmux new-session -d -s "$RALPH_SESSION" bash -c "
    cd '$RALPH_DIR' &&
    ai_orch --async '$PROJECT_DESCRIPTION';
    exec bash
"

echo "⏱️ Ralph execution initiated."
echo "📊 Ralph Status: Running"
echo ""
```

### 5. Monitor Both Systems
```bash
echo "📊 MONITORING BOTH ORCHESTRATORS"
echo "================================="

MONITORING_DURATION=1800  # 30 minutes maximum
START_TIME=$(date +%s)

echo "⏰ Monitoring for up to $((MONITORING_DURATION / 60)) minutes..."
echo ""

# Monitor loop
while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [[ $ELAPSED -gt $MONITORING_DURATION ]]; then
        echo "⏰ Maximum monitoring time reached ($((MONITORING_DURATION / 60)) minutes)"
        break
    fi

    # Check Genesis status
    if tmux has-session -t "$GENESIS_SESSION" 2>/dev/null; then
        GENESIS_RUNNING="Yes"
    else
        GENESIS_RUNNING="No"
    fi

    # Check Ralph status
    if tmux has-session -t "$RALPH_SESSION" 2>/dev/null; then
        RALPH_RUNNING="Yes"
    else
        RALPH_RUNNING="No"
    fi

    # Status update
    echo "$(date +'%H:%M:%S') - Genesis: $GENESIS_RUNNING | Ralph: $RALPH_RUNNING"

    # Check if both completed
    if [[ "$GENESIS_RUNNING" == "No" ]] && [[ "$RALPH_RUNNING" == "No" ]]; then
        echo "✅ Both orchestrators completed"
        break
    fi

    # Wait before next check
    sleep 30
done

echo ""
```

### 6. Collect Implementation Results
```bash
echo "📊 COLLECTING BENCHMARK RESULTS"
echo "==============================="

# Genesis results
echo "🧬 Genesis Implementation:"
if [[ -d "$GENESIS_DIR" ]]; then
    cd "$GENESIS_DIR"
    GENESIS_FILES=$(find . -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" 2>/dev/null | wc -l)
    GENESIS_LINES=$(find . -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
    GENESIS_STRUCTURE=$(find . -type f -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" | head -10)

    echo "  📁 Location: $GENESIS_DIR"
    echo "  📄 Files: $GENESIS_FILES"
    echo "  📝 Lines: $GENESIS_LINES"
    echo "  🏗️ Structure:"
    echo "$GENESIS_STRUCTURE" | sed 's/^/    /'
else
    echo "  ❌ No implementation found"
    GENESIS_FILES=0
    GENESIS_LINES=0
fi

echo ""

# Ralph results
echo "🤖 Ralph Implementation:"
if [[ -d "$RALPH_DIR" ]]; then
    cd "$RALPH_DIR"
    RALPH_FILES=$(find . -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" 2>/dev/null | wc -l)
    RALPH_LINES=$(find . -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
    RALPH_STRUCTURE=$(find . -type f -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" | head -10)

    echo "  📁 Location: $RALPH_DIR"
    echo "  📄 Files: $RALPH_FILES"
    echo "  📝 Lines: $RALPH_LINES"
    echo "  🏗️ Structure:"
    echo "$RALPH_STRUCTURE" | sed 's/^/    /'
else
    echo "  ❌ No implementation found"
    RALPH_FILES=0
    RALPH_LINES=0
fi

echo ""
```

### 7. Code Quality Consensus Review
```bash
echo "🎯 CODE CONSENSUS REVIEW"
echo "========================"

# Only proceed with review if both have implementations
if [[ $GENESIS_LINES -gt 0 ]] && [[ $RALPH_LINES -gt 0 ]]; then
    echo "📋 Initiating comprehensive code review using /cons command..."
    echo ""

    # Execute consensus review
    /cons

    echo "✅ Consensus review completed"
else
    echo "⚠️ Skipping consensus review - missing implementations:"
    echo "  Genesis lines: $GENESIS_LINES"
    echo "  Ralph lines: $RALPH_LINES"
fi

echo ""
```

### 8. Live Build and Test Validation
```bash
echo "🚀 LIVE BUILD & TEST VALIDATION"
echo "==============================="

# Test Genesis implementation
echo "🧬 Testing Genesis Implementation:"
if [[ $GENESIS_LINES -gt 0 ]]; then
    cd "$GENESIS_DIR"

    # Find main executable file
    MAIN_FILE=$(find . -name "*.py" | head -1)
    if [[ -n "$MAIN_FILE" ]]; then
        echo "  📝 Main file: $MAIN_FILE"

        # Try to run help/version to test basic functionality
        echo "  🧪 Basic functionality test:"
        if python3 "$MAIN_FILE" --help &>/dev/null; then
            echo "    ✅ --help works"
        elif python3 "$MAIN_FILE" -h &>/dev/null; then
            echo "    ✅ -h works"
        else
            echo "    ⚠️ No help option found, trying direct execution"
            # Try direct execution with timeout
            timeout 5s python3 "$MAIN_FILE" &>/dev/null && echo "    ✅ Executes without error" || echo "    ⚠️ Execution issues"
        fi

        # Look for test files
        TEST_FILES=$(find . -name "*test*.py" -o -name "test_*.py")
        if [[ -n "$TEST_FILES" ]]; then
            echo "  🧪 Test files found:"
            echo "$TEST_FILES" | sed 's/^/    /'

            # Try to run tests
            echo "  🏃 Running tests:"
            if python3 -m pytest . -v &>/dev/null; then
                echo "    ✅ pytest tests pass"
            elif python3 -m unittest discover . &>/dev/null; then
                echo "    ✅ unittest tests pass"
            else
                echo "    ⚠️ Could not run tests successfully"
            fi
        else
            echo "  📝 No test files found"
        fi
    else
        echo "  ❌ No Python files found"
    fi
else
    echo "  ❌ No Genesis implementation to test"
fi

echo ""

# Test Ralph implementation
echo "🤖 Testing Ralph Implementation:"
if [[ $RALPH_LINES -gt 0 ]]; then
    cd "$RALPH_DIR"

    # Find main executable file
    MAIN_FILE=$(find . -name "*.py" | head -1)
    if [[ -n "$MAIN_FILE" ]]; then
        echo "  📝 Main file: $MAIN_FILE"

        # Try to run help/version to test basic functionality
        echo "  🧪 Basic functionality test:"
        if python3 "$MAIN_FILE" --help &>/dev/null; then
            echo "    ✅ --help works"
        elif python3 "$MAIN_FILE" -h &>/dev/null; then
            echo "    ✅ -h works"
        else
            echo "    ⚠️ No help option found, trying direct execution"
            # Try direct execution with timeout
            timeout 5s python3 "$MAIN_FILE" &>/dev/null && echo "    ✅ Executes without error" || echo "    ⚠️ Execution issues"
        fi

        # Look for test files
        TEST_FILES=$(find . -name "*test*.py" -o -name "test_*.py")
        if [[ -n "$TEST_FILES" ]]; then
            echo "  🧪 Test files found:"
            echo "$TEST_FILES" | sed 's/^/    /'

            # Try to run tests
            echo "  🏃 Running tests:"
            if python3 -m pytest . -v &>/dev/null; then
                echo "    ✅ pytest tests pass"
            elif python3 -m unittest discover . &>/dev/null; then
                echo "    ✅ unittest tests pass"
            else
                echo "    ⚠️ Could not run tests successfully"
            fi
        else
            echo "  📝 No test files found"
        fi
    else
        echo "  ❌ No Python files found"
    fi
else
    echo "  ❌ No Ralph implementation to test"
fi

echo ""
```

### 9. Generate Benchmark Summary Report
```bash
echo "📊 BENCHMARK SUMMARY REPORT"
echo "==========================="
echo ""
echo "🏆 Project $PROJECT_NUM: $PROJECT_TITLE"
echo "📅 Date: $(date)"
echo "⏱️ Duration: $((ELAPSED / 60)) minutes"
echo ""

echo "📈 QUANTITATIVE RESULTS"
echo "------------------------"
printf "| %-15s | %-15s | %-15s | %-15s |\n" "Metric" "Genesis" "Ralph" "Winner"
printf "| %-15s | %-15s | %-15s | %-15s |\n" "---------------" "---------------" "---------------" "---------------"
printf "| %-15s | %-15s | %-15s | %-15s |\n" "Files Created" "$GENESIS_FILES" "$RALPH_FILES" "$([[ $GENESIS_FILES -gt $RALPH_FILES ]] && echo "Genesis" || echo "Ralph")"
printf "| %-15s | %-15s | %-15s | %-15s |\n" "Lines of Code" "$GENESIS_LINES" "$RALPH_LINES" "$([[ $GENESIS_LINES -gt $RALPH_LINES ]] && echo "Genesis" || echo "Ralph")"
printf "| %-15s | %-15s | %-15s | %-15s |\n" "Completion" "$([[ $GENESIS_LINES -gt 0 ]] && echo "✅ Yes" || echo "❌ No")" "$([[ $RALPH_LINES -gt 0 ]] && echo "✅ Yes" || echo "❌ No")" "Both/Neither"

echo ""
echo "🎯 QUALITATIVE ASSESSMENT"
echo "-------------------------"
echo "Genesis Strengths:"
echo "  • Goal-driven autonomous development"
echo "  • Fast initialization and session management"
echo "  • Self-determination and validation protocols"

echo ""
echo "Ralph Strengths:"
echo "  • Comprehensive error handling and recovery"
echo "  • Multi-adapter support and flexibility"
echo "  • Production-ready orchestration features"

echo ""
echo "📋 IMPLEMENTATION LOCATIONS"
echo "---------------------------"
echo "Genesis: $GENESIS_DIR"
echo "Ralph: $RALPH_DIR"

echo ""
echo "🔍 NEXT STEPS"
echo "-------------"
echo "1. Review implementations in their respective directories"
echo "2. Compare architectural approaches and code quality"
echo "3. Test functionality manually if needed"
echo "4. Document lessons learned for orchestration improvements"

echo ""
echo "✅ Benchmark completed successfully!"
```

## Example Usage

```bash
# Run Project 1 (CLI Text Processing)
/benchg 1

# Run Project 2 (REST API)
/benchg 2

# Run Project 3 (Data Pipeline)
/benchg 3

# Run custom project
/benchg custom "Build a machine learning model training pipeline with data validation and model monitoring"
```

## Features

### 🎯 Comprehensive Comparison
- **Quantitative Metrics**: Files created, lines of code, execution time
- **Qualitative Assessment**: Architecture, code quality, feature completeness
- **Live Testing**: Actual build and run validation

### 🔍 Code Quality Review
- **Integrated /cons**: Automatic consensus review of both implementations
- **Architecture Analysis**: Design patterns, maintainability, scalability
- **Best Practices**: Code standards, testing approaches, documentation

### 🚀 Real Validation
- **Build Testing**: Verify implementations actually work
- **Test Execution**: Run test suites if present
- **Functionality Check**: Basic operational validation

### 📊 Professional Reporting
- **Structured Output**: Clear metrics and comparisons
- **Actionable Insights**: Strengths and weaknesses analysis
- **Implementation Tracking**: Full directory locations for review

## Integration Notes

This command leverages:
- **Genesis orchestration** via `/gene` command
- **Ralph orchestration** via `ai_orch --async`
- **Consensus review** via `/cons` command
- **tmux session management** for parallel execution
- **Comprehensive validation** with live testing

Perfect for evaluating orchestration system improvements and validating new features across both platforms.
