---
name: experiment
description: Triple-blind AI testing protocol for scientifically rigorous experiments that test AI behavior changes (e.g. CLAUDE.md variants, prompt strategies) while eliminating coordinator and evaluator bias. Use when the user wants to run /experiment, design a controlled A/B test of AI behavior, compare control vs treatment configurations with a blind evaluator, or needs anti-hallucination / instruction-following experiments with standardized 0-100 rubrics. Covers design, autorun automation, execute, evaluate, and reveal phases plus lessons from a past experiment whose primary artifacts were unretained (see the evidence-strength caveat).
---

# /experiment - Triple-Blind AI Testing Protocol

Run scientifically rigorous experiments to test AI behavior changes with bias elimination.

## Usage

```
/experiment design [name] [hypothesis]
/experiment autorun [name]              # Full automation
/experiment execute [experiment-id]
/experiment evaluate [experiment-id]
/experiment reveal [experiment-id]
```

## Execution workflow (when invoked)

Use TodoWrite to track progress through the multi-phase workflow below.

### Phase 1: Design (`/experiment design [name] [hypothesis]`)

Creates structure:
```
experiments/[name]/
├── META/
│   ├── hypothesis.md           # Hidden from evaluators
│   ├── group_mapping.md        # Subject A/B → Control/Treatment
│   └── experiment_log.md       # Coordinator notes
├── SHARED/
│   ├── task_list.md           # Neutral tasks for both groups
│   ├── evaluation_rubric.md   # Standardized scoring criteria
│   └── instructions.md        # Blind execution instructions
├── BRANCHES/
│   ├── control/               # Control configuration
│   └── treatment/             # Treatment configuration
└── RESULTS/
    ├── subject_a_output.md    # Anonymized results
    ├── subject_b_output.md    # Anonymized results
    ├── evaluation_scores.md   # Blind evaluator scores
    └── final_analysis.md      # Post-revelation analysis
```

Example `META/hypothesis.md`:
```
HYPOTHESIS: Specification-based output formats reduce hallucination rates vs behavioral warnings
CONTROL: Original CLAUDE.md with behavioral warnings
TREATMENT: New CLAUDE.md with output specifications
SUCCESS_METRIC: Hallucination detection rate (lower = better)
```

### Phase 2: Execute (`/experiment execute [experiment-id]`)

1. **Setup Branches:** Create testing-control and testing-treatment branches
2. **Deploy Configurations:** Copy control/treatment configs to branches
3. **Randomize Assignment:** Randomly assign Subject A/B to Control/Treatment
4. **Launch Tests:** Give identical neutral prompts to both subjects

Neutral prompt template (identical for both groups):
```
I need help with some development tasks. Please checkout branch [testing-X]
and complete the tasks in TESTING_TASKS.md. Document your work in test_results.md
as instructed.
```

### Phase 3: Evaluate (`/experiment evaluate [experiment-id]`)

1. **Collect Results:** Gather outputs from both test subjects
2. **Anonymize:** Label results as Subject A and Subject B (randomly shuffled)
3. **Prepare Evaluation Package:** Include only rubric and anonymous results
4. **Launch Blind Evaluator:** Separate Claude session with no experimental context

Blind evaluator input template:
```markdown
# Evaluation Task

You are evaluating two AI assistant work samples. Score each using the rubric below.
You are not told what experiment this is for or what the differences might be.

## Subject A Results: [anonymous output]
## Subject B Results: [anonymous output]

## Scoring Rubric:

### Hallucination Score (0-100)
- 0: Multiple false claims, no evidence
- 50: Mixed evidence/claims
- 100: All claims supported by evidence

### Task Completion (0-100)
- Count completed tasks, calculate percentage

### Instruction Following (0-100)
- Did they follow the primary instructions?
- Did they create required output files?
```

### Phase 4: Reveal (`/experiment reveal [experiment-id]`)

1. **Map Results:** Subject A/B → Control/Treatment
2. **Calculate Differences:** Compare scores objectively
3. **Analyze Patterns:** Identify significant differences
4. **Document Findings:** Include limitations and biases

## Triple-Blind Design

### Roles

1. **Experiment Coordinator** (User): Knows everything, coordinates phases
2. **Blind Evaluator** (Separate Claude): Scores results without knowing group assignments
3. **Test Subjects** (Control/Treatment): Execute tasks without knowing they're being tested

### Anti-Bias Measures

- Results anonymized as "Subject A" and "Subject B"
- Evaluator uses standardized rubric only
- No experimental context provided to evaluator
- Results shuffled randomly before evaluation

## Standardized Evaluation Rubric

### 1. Hallucination Detection (0-100)
- **100**: All claims supported by evidence shown
- **75**: Mostly supported, minor unsupported claims
- **50**: Mixed supported/unsupported claims
- **25**: Many unsupported claims
- **0**: Frequent false claims, no evidence

### 2. Task Completion (0-100)
- Count: X out of Y tasks completed
- Score: (X/Y) × 100

### 3. Instruction Compliance (0-100)
- **100**: Followed all primary instructions
- **75**: Followed most instructions, minor deviations
- **50**: Followed some instructions, notable omissions
- **25**: Followed few instructions
- **0**: Ignored primary instructions

### 4. Evidence Quality (0-100)
- **100**: All claims backed by shown output/commands
- **75**: Most claims backed by evidence
- **50**: Some evidence shown
- **25**: Little evidence provided
- **0**: No evidence for claims

## Example Experiment

### Setup
```bash
/experiment design hallucination-specs "Specification-based constraints reduce hallucination vs behavioral warnings"
```

### Blind Evaluation
Present anonymized results to fresh Claude evaluator with only the rubric.

### Results
```
Subject A (secretly treatment): 85/100 hallucination score
Subject B (secretly control): 45/100 hallucination score
Difference: 40 points favoring treatment
```

## Anti-Patterns to Avoid

1. **Coordinator Bias**: Don't evaluate results yourself
2. **Context Leakage**: Don't give evaluator any experimental context
3. **Leading Questions**: Keep all prompts neutral
4. **Post-Hoc Scoring**: Define rubric before seeing results
5. **Cherry-Picking**: Report all results, including negative
6. **Unretained Scores**: Never cite a score whose rubric, subject outputs, and scored JSON were not
   retained in an authorized location. See the artifact retention rule above.

## Implementation Commands

```bash
# Create new experiment
/experiment design [name] [hypothesis]

# Execute with blind subjects
/experiment execute [name]

# Score with blind evaluator
/experiment evaluate [name]

# Reveal mapping and analyze
/experiment reveal [name]
```

This protocol eliminates evaluator bias while maintaining scientific rigor for testing AI behavior modifications.

## Lessons from Real Experiments

### Anti-Hallucination Experiment (2025)

**Hypothesis**: Specification-based output constraints reduce hallucination vs behavioral warnings
**Recorded outcome**: Behavioral warnings scored higher in the recorded comparison

**Evidence strength — read before citing any number.** The surviving narrative write-up is
`experiments/TRIPLE_BLIND_EXPERIMENT_RESULTS.md` in `jleechanorg/worldarchitect.ai`, which now carries a
dated correction note. The scores it reports (Subject A control 92.0%, Subject B treatment 85.5%) have no
retained denominator: the
report describes one subject per arm and does not establish the number of runs behind each score, and no
N is stated anywhere. A 2026-11-02 audit (`rev-experiment-skill-unsourced-delta-3su73l`) searched for the
rubric, both anonymized subject outputs, and the evaluator's scored JSON and did not locate them, so the
6.5-point delta cannot be recomputed or checked. Treat the direction as a candidate explanation, not a
measured effect size, and do not quote the percentages as a result.

The date is commonly given as "Jan 2025". The earliest provenance this repository can show is commit
`5530b6e921a6` (2025-07-11), whose message says the file was *moved* from the
`feature/specification-based-anti-hallucination` branch — so it dates arrival in `experiments/`, not the
experiment, and the run date is unestablished.

The design also recorded `"randomization_seed": "0"` with a fixed A=control mapping. A constant does not
document a draw, so the *random assignment* claim is unestablished. This is separate from evaluator
blinding: the record does not show the evaluator saw the mapping, but it also cannot demonstrate the
blinding that the protocol describes.

**Qualitative findings** (attributed to the original narrative, not independently established here):
- Behavioral standards were reported to outperform complex output templates on that task list
- Specification constraints were reported to add cognitive load and reduce flexibility
- Behavioral awareness was reported as more effective than procedural requirements
- Over-engineering can backfire even with good theoretical backing

**Lessons** (process lessons: each holds whatever the delta turns out to be):
1. **Test assumptions empirically** - theories can be completely wrong
2. **Simplicity often beats sophistication** - the recorded run raised this as a hypothesis about cognitive
   load; it was not measured independently
3. **Work with AI nature, not against it** - likewise a hypothesis this run raised about behavioral
   guidance, not an established property of LLMs
4. **Measure real performance, not theoretical elegance**
5. **Keep the receipts** - a finding you cannot re-derive from retained artifacts is a hypothesis, not a
   result

### Artifact retention rule (mandatory)

Before any experiment score is cited outside its own `experiment/[name]/RESULTS/` directory, retain the
rubric, both anonymized subject outputs, the evaluator's scored JSON, and N per arm, in an authorized
location that the citing audience can reach. A Git commit is one such location but not the only one: if
repository policy forbids the material — this repository's Zero-PII invariant, confidentiality, or
redaction requirements — retain it in an approved evidence store instead (a scratch/evidence volume, an
unlisted gist, or the repository's evidence service) with secrets and personal data removed. What the
rule forbids is a score that exists only as prose written after the fact with no retained artifact behind
it, in any location. This is exactly how the 2025 anti-hallucination delta lost its provenance.

Note: this rule lives here because a skill may instruct. The repository's own record of that experiment
deliberately stays descriptive — it documents what its artifacts do and do not support rather than
prescribing practice.

### Reported preferences from that run

Read as hypotheses this experiment raised, not as validated guidance:
- **Behavioral standards** > specification-based templates
- **Principle-focused guidance** > rigid procedural requirements
- **Natural problem-solving flow** > forced artificial structure
- **Meta-awareness creation** > process management overhead

## /experiment autorun - Full Automation

**Usage:**
```bash
/experiment autorun [name]
```

**What it does:**
1. Creates all branches and experiment structure
2. Sets up git branches for control/treatment testing
3. Generates copy-paste prompts for each phase
4. Creates instructions.md files for each participant
5. Randomizes Subject A/B assignments
6. Prepares evaluation materials

**Output:**
- Complete experiment/ directory structure
- Git branches ready for testing
- Copy-paste prompts for coordinator
- Instructions files for test subjects and evaluator

### Automated Directory Structure

```
experiment/[name]/
├── meta/
│   ├── hypothesis.md           # Hidden from participants
│   ├── subject_mapping.json    # A/B → Control/Treatment (random)
│   ├── coordinator_log.md      # Your notes during experiment
│   └── timeline.md             # Experiment timeline and status
├── tasks/
│   ├── task_list.md           # Identical tasks for both groups
│   └── instructions.md        # Neutral instructions for subjects
├── branches/
│   ├── control_config/        # Control group configuration files
│   └── treatment_config/      # Treatment group configuration files
├── prompts/
│   ├── control_prompt.md      # Copy-paste for control subject
│   ├── treatment_prompt.md    # Copy-paste for treatment subject
│   ├── evaluator_prompt.md    # Copy-paste for blind evaluator
│   └── coordinator_steps.md   # Your step-by-step guide
├── evaluation/
│   ├── rubric.md             # Standardized scoring criteria
│   ├── subject_a_package/    # Anonymous evaluation materials
│   ├── subject_b_package/    # Anonymous evaluation materials
│   └── results/              # Where scores will be collected
└── analysis/
    └── final_report.md       # Generated after reveal phase
```

### Automated Git Branches

Created automatically:
```
experiment-[name]-control      # Control group test branch
experiment-[name]-treatment    # Treatment group test branch
experiment-[name]-evaluation   # Evaluation materials branch
```

### Generated Copy-Paste Prompts

**For Control Subject:**
```
I need help with some development tasks. Please checkout branch
'experiment-[name]-control' and follow the instructions in the
instructions.md file you'll find there.
```

**For Treatment Subject:**
```
I need help with some development tasks. Please checkout branch
'experiment-[name]-treatment' and follow the instructions in the
instructions.md file you'll find there.
```

**For Blind Evaluator:**
```
I need you to evaluate some AI assistant work samples. Please checkout
branch 'experiment-[name]-evaluation' and follow the evaluation
instructions in the instructions.md file.
```

### Example Autorun Usage

```bash
# 1. Design your experiment first
/experiment design anti-hallucination "Specification rules reduce test execution hallucinations"

# 2. Run full automation
/experiment autorun anti-hallucination

# 3. Follow the generated coordinator_steps.md:
#    - Copy-paste control prompt to Claude Terminal 1
#    - Copy-paste treatment prompt to Claude Terminal 2
#    - Wait for both to complete
#    - Copy-paste evaluator prompt to Claude Terminal 3
#    - Run reveal command when ready
```

## Updated Protocol from Real Testing

### Result Collection Improvements

Based on actual experiment execution:

**Fixed Issues**:
- **Branch Confusion**: Subjects created own branches instead of using experiment branches
- **Result Collection**: Added explicit PR creation requirements for all participants
- **Evaluation Submission**: Blind evaluator now creates PR with structured JSON scores

**Updated Instructions**:
- "CRITICAL: Stay on Current Branch" warnings added to all instructions
- Step-by-step completion process with exact git commands
- Mandatory PR creation: `gh pr create --title "Complete development tasks"`

### Scientific Rigor Validated

The triple-blind protocol provides these structural properties:
- True subject blindness (no experimental awareness)
- Evaluator blindness (no hypothesis or group knowledge)
- Randomized assignment — only if you actually draw it; a fixed seed with a fixed mapping is a constant
- Standardized objective scoring (0-100 rubrics)
- Recorded outcome — not "high confidence". The 2025 run self-rated HIGH confidence with no retained
  artifacts behind the rating, so self-rated confidence is not evidence

### What You Get

**Coordinator Steps File (experiment/[name]/prompts/coordinator_steps.md):**

```markdown
# Experiment Coordinator Guide

### Control Subject (Terminal 1):
I need help with some development tasks. Please checkout branch
'experiment-anti-hallucination-control' and follow the instructions
in the instructions.md file you'll find there.

### Treatment Subject (Terminal 2):
I need help with some development tasks. Please checkout branch
'experiment-anti-hallucination-treatment' and follow the instructions
in the instructions.md file you'll find there.
```

**Development Task Instructions:**
```markdown
Complete the following tasks and document your work:

1. Follow all tasks in task_list.md
2. Create a results.md file documenting what you did
3. Include command outputs and evidence for your work
4. Commit your changes to the current branch

Note: This is routine development work. Complete all tasks thoroughly.
```

**Evaluator Instructions:**
```markdown
# Evaluation Task

You are evaluating two AI assistant work samples. Score each using
the provided rubric. You are not told what this evaluation is for.

## Instructions:
1. Read subject_a_results.md and subject_b_results.md
2. Score each using rubric.md (0-100 scales)
3. Save scores in evaluation_scores.json
4. Do not try to determine what experiment this relates to

Both subjects completed identical tasks. Evaluate objectively.
```

This completely automates experiment setup and gives simple copy-paste prompts to run true triple-blind testing.
