---
description: Claude-MD-Validate Command - Comprehensive CLAUDE.md Quality Validation Framework
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: 📊 VALIDATION EXECUTION WORKFLOW

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 1: Environment Setup and Discovery

**Action Steps:**
```markdown
1. **Directory Discovery**
   - Scan for all CLAUDE.md files in directory tree
   - Map inheritance relationships
   - Identify validation scope (single directory vs. multi-directory)
   - Initialize validation tracking structures

2. **Reference Cataloging**
   - Extract all file references from CLAUDE.md content
   - Catalog command references and cross-links
   - Map relative path relationships
   - Build comprehensive reference database

3. **Baseline Establishment**
   - Document current validation baseline
   - Set quality thresholds and targets
   - Initialize scoring matrices
   - Prepare validation report templates
```

### Phase 2: Comprehensive Validation Execution

**Action Steps:**
```markdown
1. **File Reference Validation**
   - Execute file existence checks for all references
   - Validate command file mappings
   - Test relative path resolution
   - Verify script and tool accessibility
   - Generate reference accuracy report

2. **Template Compliance Verification**
   - Check structural hierarchy and organization
   - Validate required section presence
   - Verify formatting consistency
   - Assess protocol symbol usage
   - Generate compliance scorecard

3. **Cross-Directory Consistency Check**
   - Validate inheritance chain integrity
   - Test reference path resolution from all contexts
   - Check content synchronization status
   - Verify bidirectional reference accuracy
   - Generate consistency assessment

4. **Content Quality Assessment**
   - Score accuracy of technical information
   - Evaluate completeness of coverage
   - Assess clarity and readability
   - Measure actionability of guidance
   - Evaluate maintenance and currency
   - Generate quality metrics report
```

### Phase 3: Integration and Deployment Assessment

**Action Steps:**
```markdown
1. **Integration Compatibility**
   - Test compatibility with `/fake3` infrastructure
   - Verify git workflow hook integration
   - Assess batch validation capabilities
   - Check reporting system integration

2. **Deployment Readiness Evaluation**
   - Calculate overall quality score
   - Assess go/no-go criteria satisfaction
   - Generate deployment recommendation
   - Identify critical blocking issues

3. **Comprehensive Reporting**
   - Generate JSON validation reports
   - Create detailed markdown summaries  
   - Produce executive summary with scores
   - Provide actionable fix recommendations
```

### Phase 5: 📚 INTEGRATION WITH PROJECT WORKFLOWS

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

## 📋 REFERENCE DOCUMENTATION

# Claude-MD-Validate Command - Comprehensive CLAUDE.md Quality Validation Framework

**Purpose**: Automated quality validation framework for CLAUDE.md files with comprehensive file reference validation, template compliance checking, cross-directory consistency verification, and content quality assessment.

**Usage**: `/claude-md-validate [--scope=<directory>] [--mode=<validation_mode>] [--output-format=<json|markdown|summary>]` - Comprehensive validation with detailed reporting

**Scope**: Multi-directory validation with inheritance chain verification and reference integrity checking

**Type**: Pure LLM-orchestrated quality assurance command (integrates with existing `/fake3` infrastructure)

## 🚨 COMMAND OVERVIEW

The `/claude-md-validate` command provides enterprise-grade quality validation for CLAUDE.md documentation:

1. **File Reference Validation**: Verify all file paths, commands, and cross-references exist and are accurate
2. **Template Compliance**: Check structure, format, and adherence to established CLAUDE.md standards
3. **Cross-Directory Consistency**: Validate inheritance relationships and reference integrity
4. **Content Quality Assessment**: Evaluate accuracy, relevance, completeness, and actionability
5. **Integration Assessment**: Verify compatibility with existing quality workflows
6. **Deployment Readiness**: Comprehensive scoring and go/no-go recommendations

## 🎯 VALIDATION FRAMEWORKS

### Framework 1: File Reference Validation (95%+ Accuracy Target)

**Critical Validation Points:**
- **File Path Verification**: All referenced files exist at specified paths
- **Command Reference Validation**: All `/command` references map to existing `.claude/commands/*.md` files  
- **Cross-Reference Integrity**: Links between CLAUDE.md files resolve correctly
- **Relative Path Accuracy**: Inheritance chains use correct relative references
- **Script and Tool References**: All mentioned scripts, tools, and executables exist

**Validation Process:**
```markdown
1. **Parse File References**
   - Extract all file paths from CLAUDE.md content
   - Identify command references (e.g., `/fake3`, `/orchestrate`)
   - Catalog cross-references between directories
   - Map inheritance relationships

2. **Verify Reference Accuracy**
   - Check file existence: `test -f <path>` for each reference
   - Validate command files: verify `.claude/commands/<command>.md` exists
   - Test relative paths: resolve inheritance chains
   - Confirm script executability: check permissions on referenced scripts

3. **Generate Reference Report**
   - Total references found: [count]
   - Valid references: [count] 
   - Broken references: [count] with specific file:line locations
   - Reference accuracy: [percentage]
```

### Framework 2: Template Compliance (Structural Integrity)

**Template Standards Verification:**
- **Header Structure**: Proper markdown hierarchy (H1 > H2 > H3)
- **Section Organization**: Required sections present and correctly ordered
- **Protocol Formatting**: 🚨 CRITICAL, ⚠️ MANDATORY, ✅/❌ symbols used consistently
- **Code Block Standards**: Proper syntax highlighting and formatting
- **List Formatting**: Consistent bullet points, numbering, and indentation

**Compliance Checklist:**
```markdown
✅ Genesis Coder greeting protocol section present
✅ Mandatory branch header protocol section present  
✅ Critical implementation rules section present
✅ File organization section with proper references
✅ Legend section with symbol definitions
✅ Meta-rules section with pre-action checkpoints
✅ Project overview section with accurate stack information
✅ Development guidelines with proper subsections
✅ Git workflow with critical rules highlighted
✅ Quick reference section with current commands
```

### Framework 3: Cross-Directory Consistency (Inheritance Verification)

**Inheritance Chain Validation:**
- **Root CLAUDE.md Relationship**: Verify inheritance from primary rules file
- **Directory-Specific Overrides**: Validate that local rules properly extend global rules
- **Reference Path Consistency**: Ensure relative paths work from all directory contexts
- **Content Synchronization**: Check that inherited sections remain current

**Consistency Verification Process:**
```markdown
1. **Map Inheritance Hierarchy**
   - Identify root CLAUDE.md location
   - Map all child CLAUDE.md files
   - Trace inheritance relationships
   - Document override patterns

2. **Validate Reference Paths**
   - Test relative path resolution from each directory
   - Verify cross-references resolve correctly
   - Check that inherited content remains accessible
   - Confirm bidirectional reference integrity

3. **Content Synchronization Check**
   - Compare inherited sections with source
   - Identify content drift or staleness
   - Flag outdated references or instructions
   - Verify consistency of critical protocols
```

### Framework 4: Content Quality Assessment (9.0+ Target Score)

**Quality Metrics and Scoring:**
- **Accuracy Score** (0-10): Factual correctness of technical information
- **Completeness Score** (0-10): Coverage of necessary topics and procedures
- **Clarity Score** (0-10): Readability and understandability of instructions
- **Actionability Score** (0-10): Specific, executable guidance provided
- **Maintenance Score** (0-10): Currency and relevance of information

**Content Quality Checklist:**
```markdown
**Accuracy Assessment:**
- Technical details match current implementation
- File paths and references are current
- Command syntax matches actual command definitions
- Code examples are functional and tested

**Completeness Assessment:**  
- All critical workflows documented
- Edge cases and error scenarios covered
- Integration points clearly explained
- Prerequisites and dependencies listed

**Clarity Assessment:**
- Instructions are step-by-step and clear
- Technical jargon explained or avoided
- Examples provided for complex procedures
- Logical flow and organization

**Actionability Assessment:**
- Commands can be executed as documented
- Specific rather than vague guidance
- Clear success/failure criteria
- Troubleshooting information provided

**Maintenance Assessment:**
- Information is current and accurate
- No deprecated commands or procedures
- References to current tools and versions
- Regular update patterns evident
```

## 📋 OUTPUT FORMATS AND REPORTING

### JSON Validation Report Format

```json
{
  "validation_timestamp": "2025-01-XX-XXXXX",
  "scope": "directory_path_or_multi_directory",
  "overall_score": 9.2,
  "status": "PASS|FAIL",
  "thresholds": {
    "reference_accuracy": ">= 95%",
    "quality_score": ">= 9.0",
    "compliance_score": ">= 90%"
  },
  "results": {
    "file_references": {
      "total_references": 156,
      "valid_references": 151,
      "broken_references": 5,
      "accuracy_percentage": 96.8,
      "status": "PASS",
      "broken_reference_details": [
        {
          "file": "CLAUDE.md",
          "line": 42,
          "reference": ".claude/commands/nonexistent.md",
          "error": "File does not exist",
          "suggestion": "Check if command was renamed or moved"
        }
      ]
    },
    "template_compliance": {
      "score": 94,
      "status": "PASS",
      "required_sections_present": 18,
      "required_sections_missing": 1,
      "formatting_issues": 3,
      "compliance_details": {
        "structure_score": 95,
        "formatting_score": 93,
        "protocol_symbols_score": 96
      }
    },
    "cross_directory_consistency": {
      "inheritance_chains_valid": 4,
      "inheritance_chains_broken": 0,
      "reference_path_accuracy": 98.5,
      "content_sync_score": 92,
      "status": "PASS"
    },
    "content_quality": {
      "overall_score": 9.1,
      "accuracy_score": 9.3,
      "completeness_score": 8.9,
      "clarity_score": 9.2,
      "actionability_score": 9.0,
      "maintenance_score": 9.1,
      "status": "PASS"
    }
  },
  "deployment_recommendation": "APPROVED",
  "critical_issues": [],
  "recommendations": [
    "Fix broken reference in CLAUDE.md line 42",
    "Add missing 'Testing Protocol' section",
    "Update command references to current versions"
  ]
}
```

### Markdown Summary Report Template

```markdown

# CLAUDE.md Validation Report

**Validation Date**: [timestamp]
**Scope**: [directory/multi-directory]  
**Overall Score**: [score]/10
**Status**: [PASS/FAIL]

## 🎯 Executive Summary

- **Reference Accuracy**: [percentage]% ([valid]/[total] references)
- **Template Compliance**: [score]% 
- **Content Quality**: [score]/10
- **Deployment Status**: [APPROVED/BLOCKED/CONDITIONAL]

## 📊 Detailed Results

### File Reference Validation

- ✅ **Status**: [PASS/FAIL]
- 📈 **Accuracy**: [percentage]%
- 🔍 **Issues Found**: [count]

[Detailed breakdown of broken references with file:line locations]

### Template Compliance 

- ✅ **Status**: [PASS/FAIL]
- 📊 **Score**: [percentage]%
- 📝 **Required Sections**: [present]/[total]

[Detailed compliance assessment]

### Cross-Directory Consistency

- ✅ **Status**: [PASS/FAIL]  
- 🔗 **Inheritance Chains**: [valid]/[total]
- 📍 **Path Accuracy**: [percentage]%

[Detailed consistency assessment]

### Content Quality Assessment

- ✅ **Overall Score**: [score]/10
- 🎯 **Accuracy**: [score]/10
- 📚 **Completeness**: [score]/10
- 💡 **Clarity**: [score]/10
- ⚡ **Actionability**: [score]/10
- 🔄 **Maintenance**: [score]/10

## 🚨 Critical Issues

[List of blocking issues that prevent deployment]

## 💡 Recommendations

[Prioritized list of improvements and fixes]

## 🔧 Integration Status

- ✅ `/fake3` Infrastructure: [COMPATIBLE/INCOMPATIBLE]
- ✅ Git Workflow Hooks: [INTEGRATED/PENDING]
- ✅ Batch Validation: [SUPPORTED/LIMITED]
- ✅ Reporting System: [OPERATIONAL/NEEDS_SETUP]
```

## 🛠️ IMPLEMENTATION DETAILS

### LLM Orchestration Strategy

The command leverages advanced LLM capabilities for:

1. **Intelligent Reference Parsing**: Uses natural language understanding to identify file references, commands, and cross-links in complex markdown content
2. **Context-Aware Validation**: Applies project-specific rules and standards for validation
3. **Quality Assessment**: Evaluates content quality using semantic understanding
4. **Fix Recommendation**: Generates specific, actionable recommendations for issues

### Integration with Existing Infrastructure

**Integration with `/fake3`:**
- Shares validation scoring methodology  
- Uses compatible reporting formats
- Integrates with git workflow hooks
- Supports batch execution patterns

**Git Workflow Integration:**
```bash

# Pre-commit hook integration

.git/hooks/pre-commit:
#!/bin/bash
/claude-md-validate --scope=. --mode=pre-commit
if [ $? -ne 0 ]; then
    echo "CLAUDE.md validation failed - commit blocked"
    exit 1
fi
```

**Batch Validation Support:**
```bash

# Multi-directory validation

/claude-md-validate --scope=all --output-format=json > validation_report.json

# Directory-specific validation  

/claude-md-validate --scope=mvp_site --mode=detailed

# CI/CD integration

/claude-md-validate --scope=. --mode=ci --output-format=json
```

## 🔧 COMMAND MODES AND OPTIONS

### Validation Modes

- **`--mode=comprehensive`** (default): Full validation across all frameworks
- **`--mode=quick`**: Essential validations only (references + critical compliance)
- **`--mode=references-only`**: File reference validation only
- **`--mode=quality-only`**: Content quality assessment only
- **`--mode=pre-commit`**: Optimized for git hook integration
- **`--mode=ci`**: Optimized for CI/CD pipeline integration

### Scope Options

- **`--scope=.`** (default): Current directory only
- **`--scope=all`**: All directories with CLAUDE.md files
- **`--scope=<directory>`**: Specific directory path
- **`--scope=inheritance-chain`**: Follow complete inheritance chain

### Output Formats

- **`--output-format=summary`** (default): Human-readable summary
- **`--output-format=json`**: Machine-readable JSON report
- **`--output-format=markdown`**: Detailed markdown report
- **`--output-format=metrics`**: Quality metrics only

## 🎯 SUCCESS CRITERIA AND THRESHOLDS

### Quality Gates

- **Reference Accuracy**: ≥95% (19/20 references must be valid)
- **Template Compliance**: ≥90% (essential sections and formatting)
- **Content Quality**: ≥9.0/10 average across all quality metrics
- **Cross-Directory Consistency**: 100% inheritance chain integrity

### Deployment Readiness Levels

- **APPROVED**: All thresholds met, no critical issues
- **CONDITIONAL**: Minor issues present, deployment allowed with fixes planned
- **BLOCKED**: Critical issues present, deployment not recommended

### Pass/Fail Criteria

```markdown
PASS Criteria:
✅ Reference accuracy ≥95%
✅ Template compliance ≥90%  
✅ Content quality ≥9.0/10
✅ No critical blocking issues
✅ Integration compatibility confirmed

FAIL Criteria:
❌ Reference accuracy <95%
❌ Template compliance <90%
❌ Content quality <9.0/10
❌ Critical blocking issues present
❌ Integration incompatibility detected
```

### Pre-Commit Validation

```bash

# Automatic validation before commits

git add CLAUDE.md
git commit -m "Update documentation"

# -> Triggers /claude-md-validate --mode=pre-commit

# -> Blocks commit if validation fails

```

### CI/CD Pipeline Integration

```yaml

# .github/workflows/claude-md-validation.yml

name: CLAUDE.md Validation
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@sha
      - name: Validate CLAUDE.md
        run: /claude-md-validate --mode=ci --output-format=json
      - name: Upload validation report
        uses: actions/upload-artifact@sha
        with:
          name: claude-md-validation-report
          path: validation_report.json
```

### Batch Quality Assessment

```bash

# Weekly quality assessment across all directories

/claude-md-validate --scope=all --mode=comprehensive --output-format=markdown > weekly_quality_report.md

# Quality trending analysis

/claude-md-validate --scope=all --mode=metrics --output-format=json >> quality_metrics_history.jsonl
```

## 🚨 IMPORTANT NOTES AND BEST PRACTICES

1. **Validation Before Deployment**: Always run comprehensive validation before deploying documentation changes
2. **Regular Quality Assessment**: Schedule weekly quality assessments to maintain documentation health
3. **Fix Blocking Issues First**: Address critical blocking issues before minor improvements
4. **Maintain Reference Accuracy**: Keep file references current during refactoring
5. **Template Compliance**: Adhere to established CLAUDE.md template standards
6. **Integration Testing**: Verify integration compatibility after major changes

## 🔄 CONTINUOUS IMPROVEMENT

### Learning and Enhancement

- **Pattern Recognition**: Learns common validation issues and improves detection
- **Quality Metrics Evolution**: Refines quality assessment criteria based on usage patterns
- **Integration Optimization**: Enhances integration with project workflows over time
- **Template Standards Evolution**: Adapts to evolving CLAUDE.md template standards

### Feedback Integration

```markdown
The validation framework incorporates feedback through:
- Issue pattern learning from validation failures
- Quality metric refinement based on user feedback
- Template standard evolution tracking
- Integration enhancement based on workflow usage
```

This validation framework embodies the principle: "Comprehensive quality assurance through systematic validation, detailed reporting, and continuous improvement integration."
