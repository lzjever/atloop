# Prompt Template Variable Injection Analysis

## Overview

This document analyzes how template variables in `developer.txt` are populated and injected, how memory is used, and whether the current prompt design is sufficient for the system's needs.

## Template Variables and Their Sources

### Variables in `developer.txt` (lines 121-151)

| Variable | Source | Injection Point | Default Value |
|----------|--------|-----------------|---------------|
| `{GOAL}` | `task_spec.goal` | `PlanPhase.execute()` → `LLMClient.build_user_message()` | N/A (required) |
| `{CONSTRAINTS}` | `task_spec.constraints` | Same as above | "None" |
| `{MAX_LLM_CALLS}` | `task_spec.budget.max_llm_calls` | Same as above | 30 |
| `{MAX_TOOL_CALLS}` | `task_spec.budget.max_tool_calls` | Same as above | 200 |
| `{MAX_WALL_TIME_SEC}` | `task_spec.budget.max_wall_time_sec` | Same as above | 1800 |
| `{STATE_SUMMARY}` | `MemorySummarizer.summarize()` | `PlanPhase.execute()` → `LLMClient.build_user_message()` | "Initial state" |
| `{PROJECT_PROFILE}` | `ContextPackBuilder.build()` | `PlanPhase.execute()` → `ContextPackBuilder.build()` → `LLMClient.build_user_message()` | "Not identified" |
| `{RELEVANT_FILES}` | `ContextPackBuilder.build()` (via `WorkspaceIndexer.search()`) | Same as above | "None" |
| `{RECENT_ERROR}` | `state.last_error.summary` | `PlanPhase.execute()` → `ContextPackBuilder.build()` → `LLMClient.build_user_message()` | "None" |
| `{CURRENT_DIFF}` | `state.artifacts.current_diff` | Same as above | "No changes" |
| `{TEST_RESULTS}` | `state.artifacts.test_results` + `verification_success` | Same as above | "" (empty) |

## Data Flow

### Complete Injection Flow

```
1. PlanPhase.execute()
   │
   ├─→ MemorySummarizer.summarize(state, max_length, task_goal, tool_registry)
   │   └─→ Generates memory_summary (string)
   │
   ├─→ ContextPackBuilder.build(goal, constraints, recent_error, current_diff, 
   │                            test_results, verification_success, memory_summary, keywords)
   │   ├─→ ProjectProfile.to_dict() → project_profile (string)
   │   ├─→ WorkspaceIndexer.search(keywords) → relevant_files (string)
   │   └─→ Returns ContextPack object
   │
   └─→ LLMClient.build_user_message(goal, constraints, budget, state_summary, 
                                     project_profile, relevant_files, recent_error, 
                                     current_diff, test_results, verification_success)
       ├─→ Loads developer.txt template
       ├─→ Replaces all placeholders with actual values
       └─→ Returns complete user_message (string)
```

### Key Files

- **Template Loading**: `atloop/llm/client.py:179` - `self.load_prompt_template("developer")`
- **Variable Replacement**: `atloop/llm/client.py:213-232` - Dictionary-based replacement
- **Memory Generation**: `atloop/memory/summarizer.py:85-711` - `MemorySummarizer.summarize()`
- **Context Building**: `atloop/retrieval/context_pack.py:128-234` - `ContextPackBuilder.build()`
- **Orchestration**: `atloop/orchestrator/phases/plan.py:24-484` - `PlanPhase.execute()`

## Memory Injection and Usage

### Memory Summary Generation

**Location**: `atloop/memory/summarizer.py:MemorySummarizer.summarize()`

**What Memory Includes** (in order of appearance):

1. **Task Completion Status** (if applicable)
   - Checks if task goal matches created files
   - Provides completion recommendation

2. **Created Files Warning** (CRITICAL)
   - Lists all created files
   - Strong warning not to recreate them

3. **Task Overview** (Long-term Memory)
   - `state.memory.task_summary` - Persistent task summary

4. **Loaded Skills** (Complete Content)
   - Shows last 3 loaded skills with full content
   - Includes cached resources information
   - Guides LLM to use skill guidelines

5. **Current Execution Plan** (Long-term Memory)
   - `state.memory.plan` - Dynamic plan with progress tracking

6. **Important Decisions** (Long-term Memory)
   - Top 5 important decisions (scored by importance)
   - From `state.memory.important_decisions`

7. **Achieved Milestones** (Long-term Memory)
   - Top 5 milestones (scored by importance)
   - From `state.memory.milestones`

8. **Important Learnings** (Long-term Memory)
   - Top 3 learnings (scored by importance)
   - From `state.memory.learnings`

9. **Recent Steps** (Facts Only)
   - Last 3 steps with factual information only
   - Shows: step number, action count, tools used, stop_reason
   - **Intentionally excludes**: `current_step_thoughts`, `plan`, `llm_output` (to prevent feedback loops)

10. **Recent Attempts** (Detailed Tool Results)
    - Last 3 attempts with full tool execution details
    - Includes stdout/stderr with smart truncation
    - Uses `OutputLimitStrategy` for tool-specific limits

11. **Modified Files Content** (if applicable)
    - Recent file modifications for context

12. **Progress Metrics** (added in PlanPhase)
    - Files created/modified counts
    - Unique actions ratio
    - View/Modify ratio
    - Consecutive same pattern detection

### Memory Size Management

- **Default Max Length**: 64,000 characters (configurable via `memory.summary_max_length`)
- **Dynamic Reduction**: If LLM returns 400 Bad Request, reduces by 20% (minimum: 16,000 chars)
- **Compression Strategy**: Uses importance scoring to prioritize content

### Memory Storage

**Location**: `atloop/memory/state.py:Memory` dataclass

**Key Fields**:
- `task_summary`: Long-term task overview
- `plan`: Current execution plan
- `decisions`: Recent step decisions (facts only, no LLM thoughts)
- `important_decisions`: Important decisions (scored)
- `milestones`: Achieved milestones
- `learnings`: Important learnings
- `attempts`: Recent attempts with tool results
- `created_files`: List of created files (critical for preventing recreation)
- `modified_files_content`: Recent file modifications
- `skill_cache`: Loaded skills with resources
- `llm_responses`: **NOT shown to LLM** (debugging only)

## Prompt Design Analysis

### Current Prompt Structure

The `developer.txt` prompt has two main sections:

1. **Static Instructions** (lines 1-120)
   - Response format (JSON)
   - Workflow (4-phase loop)
   - Tool selection guide
   - Placeholder system
   - Core principles
   - Environment info

2. **Dynamic Context** (lines 121-151)
   - Task context with all template variables
   - Memory summary (via `{STATE_SUMMARY}`)

### Strengths

✅ **Clear Separation**: Static instructions vs. dynamic context
✅ **Memory Integration**: Comprehensive memory summary via `{STATE_SUMMARY}`
✅ **Context Rich**: Multiple context sources (project profile, relevant files, errors, diffs, tests)
✅ **Feedback Loop Prevention**: Memory intentionally excludes LLM's own thoughts to prevent circular reasoning
✅ **Critical Warnings**: Created files warning is prominently placed in memory

### Potential Issues

⚠️ **Memory Placement**: Memory is injected as `{STATE_SUMMARY}` in the "Current State" section, but memory actually contains much more than just "current state" - it includes:
   - Long-term memory (task summary, plan, decisions, milestones, learnings)
   - Recent history (steps, attempts)
   - Critical warnings (created files)
   - Skills content

⚠️ **Section Naming Mismatch**: The section is labeled "### Current State" but contains comprehensive memory including long-term information. This might confuse the LLM about what is "current" vs. "historical".

⚠️ **Memory Size**: With default 64K character limit, memory can be very large. The prompt doesn't explicitly tell the LLM how to prioritize information within the memory.

⚠️ **Missing Guidance**: The prompt doesn't explicitly instruct the LLM to:
   - Check created files list before creating new files
   - Review important decisions when making similar choices
   - Use loaded skills when applicable
   - Consider milestones when assessing progress

### Recommendations

#### 1. Improve Section Structure

**Current**:
```markdown
### Current State
{STATE_SUMMARY}
```

**Suggested**:
```markdown
### Memory and Context
{STATE_SUMMARY}

**Important**: The above section contains:
- Long-term memory (task overview, plan, important decisions, milestones, learnings)
- Recent history (last 3 steps and attempts)
- Critical warnings (created files - DO NOT recreate!)
- Loaded skills (complete content - use these guidelines)

Review this section carefully before making decisions.
```

#### 2. Add Memory Usage Guidelines

Add to the static instructions section (around line 70-80):

```markdown
### Memory Usage Guidelines

- **Check Created Files**: Before using `write_file`, check the "Created Files" section in memory to avoid recreating existing files
- **Review Important Decisions**: When facing similar situations, review "Important Decisions" for past learnings
- **Use Loaded Skills**: If "Loaded Skills" section exists, follow those guidelines for relevant tasks
- **Consider Milestones**: Review "Achieved Milestones" to understand progress
- **Learn from Attempts**: Review "Recent Attempts" to understand what worked and what didn't
```

#### 3. Enhance Task Context Section

**Current structure is good**, but could add:

```markdown
### Task Context

### Goal
{GOAL}

### Constraints
{CONSTRAINTS}

### Budget
- Max LLM calls: {MAX_LLM_CALLS}
- Max tool calls: {MAX_TOOL_CALLS}
- Max execution time: {MAX_WALL_TIME_SEC} seconds

**Note**: Budget is tracked automatically. If limits are approached, prioritize completing the goal efficiently.

### Memory and Context
{STATE_SUMMARY}

**Memory Structure**:
- Top: Task completion status and critical warnings (created files)
- Middle: Long-term memory (task overview, plan, important decisions, milestones, learnings)
- Bottom: Recent history (steps, attempts with tool results)

### Project Information
{PROJECT_PROFILE}

**Use this to**: Understand project structure, language, package manager, and test commands.

### Relevant Files
{RELEVANT_FILES}

**Use this to**: Find files related to your current task. Use `read_file` to examine them.

### Recent Errors / Tool Results
{RECENT_ERROR}

**Use this to**: Understand what went wrong and avoid repeating mistakes.

### Current Diff
{CURRENT_DIFF}

**Use this to**: See what files have been modified recently.

### Test Results
{TEST_RESULTS}
```

#### 4. Add Memory Navigation Hints

Since memory can be large, add guidance on how to navigate it:

```markdown
**Memory Navigation Tips**:
1. Start with "Created Files" warning (if present) - critical to avoid recreation
2. Review "Task Overview" for high-level context
3. Check "Current Execution Plan" for progress
4. Scan "Recent Steps" for immediate context
5. Review "Recent Attempts" for tool execution details
6. Consult "Loaded Skills" when task matches skill description
```

## Conclusion

### Is the Current Prompt Sufficient?

**Partially Yes, but with room for improvement:**

✅ **What Works Well**:
- Comprehensive memory injection via `{STATE_SUMMARY}`
- Rich context from multiple sources
- Clear static instructions
- Feedback loop prevention (excludes LLM thoughts)

⚠️ **What Could Be Better**:
- Section naming ("Current State" is misleading for comprehensive memory)
- Missing explicit guidance on how to use memory sections
- No instructions on prioritizing memory content
- Could benefit from memory navigation hints

### Priority Improvements

1. **High Priority**: Rename "Current State" to "Memory and Context" and add brief explanation
2. **Medium Priority**: Add memory usage guidelines to static instructions
3. **Low Priority**: Add memory navigation hints for large memory summaries

### System Design Alignment

The current prompt design **aligns well** with the system's memory architecture:
- ✅ Memory summarizer provides comprehensive context
- ✅ Memory excludes LLM thoughts (prevents feedback loops)
- ✅ Multiple context sources are integrated
- ✅ Critical warnings (created files) are prominently placed

The main gap is **explicit guidance** on how the LLM should interpret and use the memory structure, which could improve decision-making quality.
