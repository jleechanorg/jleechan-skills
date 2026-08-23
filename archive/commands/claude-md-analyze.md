---
description: Claude-MD-Analyze Command - Comprehensive Directory Analysis for CLAUDE.md Deployment
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### 📋 WORKFLOW PHASES

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 1: Directory Discovery and Filtering

**Action Steps:**
**Discovery Process**:
```bash

### Phase 2: File Count and Type Analysis

**Action Steps:**
**File Analysis Protocol**:
```bash

### Phase 3: Git Activity Analysis

**Action Steps:**
**Developer Interaction Metrics**:
```bash

### Phase 4: Complexity Assessment

**Action Steps:**
**Structure Depth Analysis**:
```bash

### Phase 5: CLAUDE.md Integration Assessment

**Action Steps:**
**Existing CLAUDE.md Detection**:
```bash

### Phase 7: 🛠️ IMPLEMENTATION WORKFLOW

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

## 📋 REFERENCE DOCUMENTATION

# Claude-MD-Analyze Command - Comprehensive Directory Analysis for CLAUDE.md Deployment

**Purpose**: Automated analysis of directories to identify high-value targets for CLAUDE.md deployment using systematic scoring criteria and developer interaction analysis.

**Usage**: `/claude-md-analyze [directory] [options]` - Analyzes target directory for CLAUDE.md deployment viability

**Type**: Pure LLM-orchestrated command with JSON output for deployment pipeline integration

## 🚨 COMMAND OVERVIEW

The `/claude-md-analyze` command provides comprehensive directory analysis to identify optimal CLAUDE.md deployment targets through:
1. **Directory Discovery**: Recursive scanning with intelligent filtering
2. **Scoring Analysis**: Multi-factor complexity and value assessment  
3. **Git Analysis**: Developer interaction frequency and patterns
4. **Exclusion Filtering**: Archive, backup, and generated content detection
5. **JSON Output**: Structured data for deployment decision automation
6. **Quality Integration**: `/fake3` validation compatibility checks

## 🎯 ANALYSIS CRITERIA

### Core Threshold Requirements

- **Minimum File Count**: ≥5 files (configurable via `--min-files` parameter)
- **Developer Activity**: Git log analysis for interaction frequency
- **Directory Complexity**: Structure depth, file type diversity, and development patterns
- **Exclusion Patterns**: Automated filtering of non-development directories

### Scoring Matrix (0-100 scale)

**File Count Score (0-25 points)**:
- 5-10 files: 5 points
- 11-25 files: 10 points  
- 26-50 files: 15 points
- 51-100 files: 20 points
- 100+ files: 25 points

**Developer Activity Score (0-30 points)**:
- No commits: 0 points
- 1-10 commits (last 6 months): 5 points
- 11-25 commits: 10 points
- 26-50 commits: 15 points
- 51-100 commits: 20 points
- 100+ commits: 30 points

**Complexity Score (0-30 points)**:
- Single file type: 5 points
- 2-3 file types: 10 points
- 4-6 file types: 15 points
- Mixed development (code + config + docs): 20 points
- Complex development (tests + multiple languages): 25 points
- Enterprise complexity (CI/CD + docs + tests + multi-lang): 30 points

**Structure Depth Score (0-15 points)**:
- 1 level: 3 points
- 2-3 levels: 6 points
- 4-5 levels: 9 points
- 6-7 levels: 12 points
- 8+ levels: 15 points

# Core directory scanning with intelligent filtering

find [target_directory] -type d \
  -not -path "*/.*" \
  -not -path "*/node_modules/*" \
  -not -path "*/venv/*" \
  -not -path "*/build/*" \
  -not -path "*/dist/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/target/*" \
  -not -path "*/cache/*" \
  -not -path "*/temp/*" \
  -not -path "*/tmp/*" | \
head -1000  # Prevent excessive output
```

**Exclusion Pattern Detection**:
- **Archive Indicators**: `.zip`, `.tar.gz`, `backup`, `archive`, `old` in path
- **Generated Content**: `build/`, `dist/`, `generated/`, `auto/`, `compiled/`  
- **Version Control**: `.git/`, `.svn/`, `.hg/` directories
- **Dependencies**: `node_modules/`, `vendor/`, `venv/`, `virtualenv/`
- **IDE/Tool Files**: `.vscode/`, `.idea/`, `.vs/`, `.settings/`
- **Binary/Media**: Directories with >80% binary files

# Count files by type with development relevance scoring

find [directory] -type f | grep -E '\.(py|js|ts|jsx|tsx|java|cpp|c|h|go|rs|rb|php|cs|sql|yaml|yml|json|xml|md|rst|txt|sh|bat|ps1|dockerfile|makefile)$' | wc -l

# Development file type diversity analysis

find [directory] -type f -name "*.*" | sed 's/.*\.//' | sort | uniq -c | sort -nr
```

**File Type Classification**:
- **Core Code**: `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.go`, `.rs`, `.rb`, `.php`, `.cs`
- **Web Frontend**: `.jsx`, `.tsx`, `.vue`, `.html`, `.css`, `.scss`, `.less`
- **Configuration**: `.json`, `.yaml`, `.yml`, `.xml`, `.ini`, `.cfg`, `.conf`
- **Documentation**: `.md`, `.rst`, `.txt`, `.adoc`, `.tex`
- **Scripts**: `.sh`, `.bat`, `.ps1`, `.makefile`, `Dockerfile`
- **Data**: `.sql`, `.csv`, `.json`, `.xml`

# Commit frequency analysis (last 6 months)

git log --since="6 months ago" --oneline [directory] | wc -l

# Author diversity and collaboration patterns  

git log --since="6 months ago" --format="%an" [directory] | sort | uniq -c | sort -nr

# File modification frequency

git log --since="6 months ago" --name-only --oneline [directory] | grep -v "^[a-f0-9]" | sort | uniq -c | sort -nr

# Recent activity recency (last commit)

git log -1 --format="%ar" [directory]
```

**Activity Scoring Factors**:
- **Commit Frequency**: Raw commit count with recency weighting
- **Author Diversity**: Multiple contributors indicate team development
- **File Modification Patterns**: Consistent updates vs sporadic changes
- **Recency Factor**: Recent activity weighted higher than historical

# Directory depth calculation

find [directory] -type d | awk -F'/' '{print NF-1}' | sort -nr | head -1

# Subdirectory organization patterns

find [directory] -mindepth 1 -maxdepth 3 -type d | wc -l
```

**Development Pattern Recognition**:
- **Test Presence**: Detection of `test/`, `tests/`, `spec/`, `__tests__/` directories
- **Documentation**: `docs/`, `documentation/`, `README.md` presence
- **Configuration Management**: Multiple config files and environments
- **CI/CD Integration**: `.github/`, `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml`
- **Package Management**: `package.json`, `requirements.txt`, `Cargo.toml`, `pom.xml`

# Check for existing CLAUDE.md files in directory tree

find [directory] -name "CLAUDE.md" -o -name "claude.md" -o -name ".claude*"

# Analyze existing file content for conflicts/compatibility

```

**Integration Complexity Factors**:
- **Existing Documentation**: Presence of README.md, docs/ directory
- **Development Workflows**: Evidence of established processes
- **Tool Integration**: Existing CI/CD, linting, testing infrastructure
- **Team Size**: Git author analysis for collaboration scale

## 📊 JSON OUTPUT SCHEMA

```json
{
  "analysis_metadata": {
    "timestamp": "2025-01-15T10:30:00Z",
    "analyzer_version": "1.0.0",
    "target_directory": "/path/to/analyzed/directory",
    "analysis_duration_ms": 2500,
    "parameters": {
      "min_files": 5,
      "depth_limit": 10,
      "exclude_patterns": ["node_modules", "build", "dist"],
      "include_hidden": false
    }
  },
  "summary": {
    "total_directories_scanned": 156,
    "eligible_directories": 23,
    "high_value_targets": 8,
    "deployment_recommended": true,
    "overall_score": 78.5
  },
  "directory_rankings": [
    {
      "path": "/project/src/core",
      "rank": 1,
      "overall_score": 92.0,
      "deployment_priority": "HIGH",
      "scores": {
        "file_count": 25,
        "developer_activity": 28,
        "complexity": 26,
        "structure_depth": 13
      },
      "metrics": {
        "file_count": 87,
        "file_types": 8,
        "commits_6mo": 156,
        "unique_authors": 6,
        "max_depth": 5,
        "last_commit": "2 days ago"
      },
      "analysis_details": {
        "file_type_distribution": {
          "py": 45,
          "ts": 23,
          "json": 12,
          "md": 5,
          "yaml": 2
        },
        "development_indicators": {
          "has_tests": true,
          "has_docs": true,
          "has_ci_cd": true,
          "has_config": true,
          "package_management": "requirements.txt"
        },
        "git_activity": {
          "total_commits": 156,
          "unique_contributors": ["alice", "bob", "charlie", "diana", "eve", "frank"],
          "avg_commits_per_month": 26,
          "modification_frequency": "high",
          "collaboration_score": 0.85
        },
        "complexity_factors": {
          "subdirectory_count": 12,
          "config_files": 8,
          "documentation_coverage": "extensive",
          "testing_infrastructure": "comprehensive",
          "ci_cd_integration": "github_actions"
        }
      },
      "deployment_assessment": {
        "claude_md_exists": false,
        "integration_complexity": "medium",
        "potential_conflicts": [],
        "recommended_approach": "full_deployment",
        "estimated_setup_time": "15_minutes",
        "maintenance_effort": "low"
      },
      "fake3_compatibility": {
        "supported": true,
        "estimated_scan_time": "3_minutes",
        "expected_issues": "moderate",
        "automation_potential": "high"
      }
    }
  ],
  "excluded_directories": [
    {
      "path": "/project/node_modules",
      "exclusion_reason": "dependency_directory",
      "pattern_matched": "node_modules"
    },
    {
      "path": "/project/build",
      "exclusion_reason": "generated_content",
      "pattern_matched": "build"
    }
  ],
  "recommendations": {
    "deployment_strategy": "phased_rollout",
    "priority_order": [
      "/project/src/core",
      "/project/services/api", 
      "/project/tests/integration"
    ],
    "resource_requirements": {
      "estimated_total_setup_time": "45_minutes",
      "maintenance_overhead": "low",
      "training_requirements": "minimal"
    },
    "risk_assessment": {
      "deployment_risk": "low",
      "integration_challenges": ["existing_workflows"],
      "mitigation_strategies": ["gradual_adoption", "team_training"]
    }
  },
  "quality_metrics": {
    "analysis_confidence": 0.92,
    "data_completeness": 0.88,
    "git_availability": true,
    "permission_issues": false,
    "scan_limitations": []
  }
}
```

## 🚀 PARAMETER OPTIONS

### Basic Parameters

- `--directory` or `-d`: Target directory to analyze (default: current directory)
- `--min-files`: Minimum file count threshold (default: 5)
- `--max-depth`: Maximum directory depth to scan (default: 10)
- `--output`: Output file path for JSON results (default: stdout)

### Filtering Options

- `--include-hidden`: Include hidden directories/files (default: false)
- `--exclude-patterns`: Additional exclusion patterns (comma-separated)
- `--include-patterns`: Force inclusion patterns despite exclusions
- `--file-types`: Limit analysis to specific file types

### Analysis Options

- `--git-months`: Git analysis timeframe in months (default: 6)
- `--complexity-weights`: Custom scoring weights (format: file:25,activity:30,complexity:30,depth:15)
- `--quick-scan`: Skip detailed git analysis for faster results
- `--verbose`: Include detailed analysis steps in output

### Quality Integration

- `--fake3-check`: Include fake code pattern analysis compatibility
- `--deployment-simulation`: Simulate CLAUDE.md deployment process
- `--conflict-detection`: Check for potential integration conflicts

### LLM Command Composition

The command works through intelligent orchestration of existing tools:

1. **Directory Traversal**: Uses `find` and `ls` commands for filesystem analysis
2. **Git Analysis**: Uses `git log`, `git diff`, and `git blame` for activity metrics
3. **File Analysis**: Uses `grep`, `awk`, and `sed` for content pattern recognition
4. **JSON Generation**: Uses structured data assembly via LLM reasoning
5. **Quality Assessment**: Integrates with `/fake3` validation patterns

### LLM Orchestration Process

1. **Parameter Validation**: Parse and validate input parameters using natural language understanding
2. **Discovery Phase**: Execute filesystem scanning with intelligent filtering
3. **Analysis Phase**: Perform multi-factor scoring using systematic criteria
4. **Git Integration**: Extract developer activity patterns and collaboration metrics
5. **Scoring Calculation**: Apply weighted scoring model for deployment prioritization
6. **JSON Assembly**: Structure all findings into comprehensive output format
7. **Quality Validation**: Verify data completeness and analysis confidence

### Analysis Strategies

**High-Value Target Identification**:
- **Active Development**: Recent commits with multiple contributors
- **Complex Structure**: Multiple file types, testing, documentation
- **Strategic Importance**: Core functionality or frequently modified areas
- **Integration Readiness**: Existing development workflows and tooling

**Risk Assessment**:
- **Deployment Complexity**: Existing documentation and workflow conflicts
- **Team Adoption**: Collaboration patterns and development practices
- **Maintenance Overhead**: Required ongoing support and updates
- **Technical Debt**: Code quality and organizational maturity

### Safety Measures

- **Permission Handling**: Graceful handling of inaccessible directories
- **Performance Limits**: Configurable scan limits to prevent excessive resource usage
- **Error Recovery**: Continued analysis despite individual directory failures
- **Data Validation**: Confidence scoring and completeness metrics

## 🔍 EXAMPLE EXECUTION

```console
/claude-md-analyze /project/src --min-files 10 --output analysis.json --verbose

🚀 Starting /claude-md-analyze - CLAUDE.md Deployment Analysis
📍 Target: /project/src
⚙️ Parameters: min-files=10, max-depth=10, git-months=6

[Phase 1 - Directory Discovery]
🔍 Scanning filesystem structure...
📁 Found 156 directories, 847 files
🚫 Excluded 23 directories (dependencies, build artifacts)
✅ 45 directories meet minimum file threshold

[Phase 2 - File Analysis] 
📊 Analyzing file types and development patterns...
💻 Core development files: 234 (67%)
🧪 Test files: 45 (13%) 
📚 Documentation: 31 (9%)
⚙️ Configuration: 38 (11%)

[Phase 3 - Git Activity Analysis]
📈 Analyzing developer interaction patterns...
👥 6 unique contributors in last 6 months
📝 156 commits across analyzed directories
🕐 Most recent activity: 2 days ago
🔥 High activity directories: 8 identified

[Phase 4 - Complexity Assessment]
🏗️ Evaluating directory complexity...
📏 Average depth: 3.2 levels
🎯 Enterprise patterns detected: 12 directories
🧩 Integration complexity: Medium

[Phase 5 - CLAUDE.md Integration Assessment]
🔍 Checking existing CLAUDE.md presence...
📋 No conflicts detected
✅ Clean integration path available
⏱️ Estimated setup time: 45 minutes total

📊 Analysis Results:
🏆 Top Priority: /project/src/core (Score: 92.0)
🥈 Second Priority: /project/services/api (Score: 87.5)
🥉 Third Priority: /project/tests/integration (Score: 81.2)

📁 High-value targets identified: 8
✅ Deployment recommended: YES
📋 Full results written to: analysis.json

Ready for CLAUDE.md deployment pipeline!
```

## 🎯 SUCCESS CRITERIA

**Command succeeds when**:
- Complete directory analysis with confidence score ≥0.80
- JSON output generated with all required fields populated
- At least one high-value deployment target identified (score ≥70)
- Git analysis completed successfully (if repository available)
- Performance within reasonable time limits (<5 minutes for typical projects)

**Command provides warnings for**:
- Limited git history or no version control
- Permissions issues preventing full analysis
- Unusual directory structures or patterns
- Low confidence scores (<0.70) requiring manual review

**Command stops early if**:
- Target directory doesn't exist or inaccessible
- No directories meet minimum file threshold
- Excessive scan time (>10 minutes) without completion
- Critical filesystem errors

## 📚 INTEGRATION WITH OTHER COMMANDS

**Enhances**:
- `/fake3` - Provides deployment target analysis for code quality automation
- `/execute` - Enables automated CLAUDE.md deployment workflows
- `/planexec` - Informs deployment planning with systematic analysis

**Uses**:
- Standard filesystem tools (`find`, `ls`, `grep`)
- Git analysis commands (`git log`, `git diff`)
- JSON processing and structured output generation

**Compatible with**:
- `/orchestrate` - Supports batch analysis across multiple directories
- `/pr` - Provides deployment recommendations for pull request workflows
- CI/CD integration - JSON output suitable for automated deployment decisions

## 🔧 CONFIGURATION

### Default Behavior

- **Scan Depth**: 10 levels maximum (prevents excessive recursion)
- **File Threshold**: 5 files minimum (configurable)
- **Git Timeframe**: 6 months activity analysis
- **Output Format**: JSON to stdout (redirectable to file)
- **Exclusion Patterns**: Standard development exclusions (node_modules, build, etc.)

### LLM Decision Points

The LLM makes intelligent decisions about:
- **Scoring Weight Distribution**: Adaptive based on project characteristics
- **Exclusion Pattern Application**: Context-aware filtering beyond default patterns
- **Complexity Assessment**: Holistic evaluation of development maturity
- **Deployment Risk Evaluation**: Integration complexity and potential conflicts
- **Priority Ranking**: Strategic value assessment for deployment ordering

## 🚨 IMPORTANT NOTES

1. **Performance Considerations**: Large repositories may require `--quick-scan` mode
2. **Permission Requirements**: Read access needed for all analyzed directories
3. **Git Dependency**: Enhanced analysis requires git repository, graceful degradation otherwise
4. **JSON Validation**: Output structure verified for downstream automation compatibility
5. **Privacy Awareness**: No sensitive data included in analysis output
6. **Incremental Analysis**: Supports re-analysis with caching for large projects

This command embodies the principle: "Systematic analysis enables data-driven deployment decisions while providing comprehensive insights for CLAUDE.md integration success."
