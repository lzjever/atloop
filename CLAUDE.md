# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

atloop is an autonomous AI agent system for automated code task execution in sandbox environments. It executes coding tasks through a structured 4-phase workflow: DISCOVER → PLAN → ACT → VERIFY.

**Key technologies:**
- Python 3.8+ (main language)
- varlord (configuration management)
- lexilux (LLM communication client)
- noxrunner (sandbox execution backend)
- rich (console output)

**Core architecture:**
- Orchestrator layer: AgentLoop, Workflow, WorkflowCoordinator
- Phase system: BasePhase with DiscoverPhase, PlanPhase, ActPhase, VerifyPhase
- Memory system: Intelligent context management with compression
- Tool registry: Auto-discovered tools for execution
- State management: Persistent state (JSON) after each step
- **Placeholder system: ALL file/script content must use placeholders** (critical!)

## Development Commands

### Setup
```bash
make dev-install        # Install package with dev dependencies (recommended)
make setup-venv         # Create venv with dependencies only (no package)
```

### Testing
```bash
make test               # Run unit tests
make test-cov           # Run tests with coverage
make test-integration   # Run integration tests (requires external services)
```

### Code Quality
```bash
make lint               # Run ruff linting
make format             # Format code with ruff
make format-check       # Check formatting
make check              # Run all checks (lint + format + test)
```

### Build & Release
```bash
make build              # Build distributions
make check-package      # Check package before uploading
```

### Running Tests
- Single test: `pytest tests/path/to/test.py::test_function -v`
- Marked tests: `pytest -m integration` (integration tests)

## Critical: Placeholder System

**⚠️ ALL file/script content MUST use placeholders - this is mandatory, not optional!**

The placeholder system separates ActionJSON from large content to avoid JSON parsing issues and token limits.

### Placeholder Format

Content is provided AFTER the JSON, delimited by special markers:

```
---((TYPE_descriptive-name))---
<actual content here>
```

### Required Placeholder Types

| Tool | Placeholder Type | Field | Format Example |
|------|-----------------|-------|----------------|
| `write_file` | `WRITE_FILE_CONTENT_<desc>` | `content` | `---((WRITE_FILE_CONTENT_main-py))---` |
| `edit_file` | `EDIT_FILE_CONTENT_<desc>` | `content` | `---((EDIT_FILE_CONTENT_fix-bug))---` |
| `append_file` | `APPEND_FILE_CONTENT_<desc>` | `content` | `---((APPEND_FILE_CONTENT_log))---` |
| `run` | `SHELL_COMMAND_<desc>` | `cmd` | `---((SHELL_COMMAND_ls-la))---` |
| `run_python_script_string` | `PYTHON_SCRIPT_<desc>` | `script` | `---((PYTHON_SCRIPT_test))---` |
| `run_shell_script_string` | `SHELL_SCRIPT_<desc>` | `script` | `---((SHELL_SCRIPT_setup))---` |

### Critical Rules

1. **ALL content must use placeholders** - even small content, no exceptions
2. **Each placeholder must be unique** within the same response
3. **Use descriptive names** (e.g., `WRITE_FILE_CONTENT_main-py` not just `WRITE_FILE_CONTENT_#1`)
4. **Placeholders are extracted after JSON** parsing via `PlaceholderReplacer` service
5. **Content follows the JSON** - not embedded within it

### Example Usage

```json
{
  "tool": "write_file",
  "args": {
    "path": "main.py",
    "content": "WRITE_FILE_CONTENT_main-py"
  }
}
---((WRITE_FILE_CONTENT_main-py))---
def main():
    print("Hello, World!")
```

### Implementation Details

**Location**: `atloop/llm/placeholder_patterns.py`

- `PLACEHOLDER_DELIMITER_REGEX` - Matches placeholder delimiters
- `PLACEHOLDER_SECTION_REGEX` - Removes placeholder sections from JSON
- `_extract_file_contents()` in schema.py - Extracts content from placeholders
- `PlaceholderReplacer` in phases/placeholder_replacer.py - Replaces placeholders with actual content

## Available Tools

All tools are auto-discovered and registered in `ToolRegistry`. Tool definitions in `atloop/llm/schema.py:70-83`.

### Filesystem Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `read_file` | Read sandbox files | path, offset, limit |
| `write_file` | Create/overwrite files | path, content (uses placeholder), max 6KB |
| `edit_file` | Modify file sections | path, content (old/new format with placeholder) |
| `multi_edit_file` | Batch edit multiple files | edits array (transactional) |
| `append_file` | Append to files | path, content (uses placeholder) |
| `glob` | Find files by pattern | pattern, max_results |
| `read_skill_file` | Read local skill files | path, skill_name |

### System Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `run` | Execute shell commands | cmd (uses placeholder), timeout_sec |
| `run_python_script_string` | Execute Python code | script (uses placeholder) |
| `run_shell_script_string` | Execute shell scripts | script (uses placeholder) |

### Search Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `search` | Regex search with context | query, glob, output_mode, -A, -B, -C, -i |

### Interaction Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `todo_write` | Create/update todo list | todos array (content, activeForm, status) |
| `todo_read` | Read todo list | (no parameters) |
| `load_skill` | Load skill metadata | name (skill name) |
| `load_skill_resource` | Load skill resource | skill_name, resource_type, resource_name |

## Architecture Overview

The system follows a **phase-based state machine** architecture:

```
Entry Points (CLI/API) → Orchestrator → Phases → Core Services
                                      ↓
              DISCOVER → PLAN → ACT → VERIFY (repeat)
```

### Key Components

**Orchestrator (`atloop/orchestrator/`)**
- `AgentLoop` - Main orchestration entry point
- `Workflow` - Workflow execution and state machine
- `WorkflowCoordinator` - Manages phases and state
- `state/manager.py` - Persistent state management (JSON serialization)
- `budget.py` - Resource limits (LLM calls, tool calls, time)
- `loop_detector.py` - Detects and intervenes in infinite loops

**Phases (`atloop/orchestrator/phases/`)**
- `base.py` - BasePhase abstract class
- `discover.py` - Analyze workspace, build context pack
- `plan.py` - Generate execution plan via LLM (with placeholders)
- `act.py` - Execute tools (replace placeholders first)
- `verify.py` - Run tests, validate results
- `placeholder_replacer.py` - Replace placeholders with actual content

**Memory System (`atloop/memory/`)**
- `state.py` - Memory data model (AgentState, Memory, Artifacts)
- `memory_manager.py` - Context formatting and compression
- `compressor.py` - Rule-based and LLM-powered compression
- `plan.py` - Execution plan tracking

**Retrieval (`atloop/retrieval/`)**
- `indexer.py` - Workspace indexing and search
- `context_pack.py` - Build context prompts for LLM
- `project_profile.py` - Project type detection (language, package manager, test commands)

**Tools (`atloop/tools/`)**
- `base.py` - BaseTool abstract class
- `registry.py` - Tool registration and execution
- `auto_discovery.py` - Auto-discovers tools from modules
- `filesystem/` - File operations (read, write, edit, glob)
- `system/` - Command execution (run, shell scripts, Python scripts)
- `search/` - Regex search with context
- `interaction/` - Todo operations, skill loading

**LLM (`atloop/llm/`)**
- `schema.py` - ActionJSON schema for tool execution + placeholder extraction
- `placeholder_patterns.py` - Placeholder regex patterns
- `prompts/` - System prompts for LLM (multilingual: en, zh)

**Config (`atloop/config/`)**
- Uses varlord for configuration management
- `models.py` - TaskSpec, Budget, and other data models
- Configuration file: `~/.atloop/config/atloop.yaml`

**Runtime (`atloop/runtime/`)**
- `sandbox_adapter.py` - Isolated execution environment interface
- `tool_runtime.py` - Tool execution in sandbox

## Phase Workflow Details

### 1. DISCOVER Phase
**Location**: `atloop/orchestrator/phases/discover.py`

**Purpose**: Build context pack for LLM

**Steps**:
1. Format memory using `MemoryFormatter`
2. Extract keywords from goal and recent errors
3. Search workspace for relevant files using `WorkspaceIndexer`
4. Build context pack with:
   - Goal and task summary
   - Project profile (language, package manager, test commands)
   - Relevant files (with snippets)
   - Recent error (if any)
   - Current diff (if any)
   - Test results (if any)
   - Memory summary

**Output**: `context_pack` stored in `job_state` for PLAN phase

### 2. PLAN Phase
**Location**: `atloop/orchestrator/phases/plan.py`

**Purpose**: Generate actions using LLM

**Steps**:
1. Get formatted memory from `MemoryFormatter`
2. Get context pack from DISCOVER phase
3. Build LLM prompt with:
   - System prompt (from `atloop/llm/prompts/`)
   - Context pack
   - Memory summary
   - Budget status
   - Current step
4. Call LLM to generate ActionJSON
5. **Extract placeholders** from response (content follows JSON)
6. Validate ActionJSON:
   - Check tool names are valid
   - Validate arguments
   - **CRITICAL**: Validate placeholder uniqueness
   - **CRITICAL**: Validate placeholder types match tool expectations
7. Store `placeholder_info` in job_state for ACT phase

**Output**: ActionJSON with placeholder references

**Error Handling**: If LLM output contains placeholders in text (not extracted), transition to PLAN again

### 3. ACT Phase
**Location**: `atloop/orchestrator/phases/act.py`

**Purpose**: Execute tools and update state

**Steps**:
1. Get ActionJSON from PLAN phase
2. **Replace placeholders** using `PlaceholderReplacer`:
   - Match placeholder names from PLAN to extracted content
   - Replace placeholder strings with actual content
   - Validate all placeholders were replaced
3. Execute tools in sequence:
   - Validate tool exists in registry
   - Validate tool arguments
   - Execute tool in sandbox
   - Capture results (stdout, stderr, exit_code)
4. Process results using `ActResultProcessor`:
   - Track file changes
   - Format errors
   - Update memory
5. Update state:
   - Add to `tool_results_history`
   - Update `modified_files_content`
   - Track created files
6. Check for stop reasons (done, fail, budget exhausted)

**Output**: Updated memory and state

### 4. VERIFY Phase
**Location**: `atloop/orchestrator/phases/verify.py`

**Purpose**: Verify task completion

**Steps**:
1. Check if verification configured
2. Run tests (if configured)
3. Check `verification_success`
4. Determine next action:
   - If task complete → transition to DONE
   - If task incomplete → transition to DISCOVER
   - If errors → transition to PLAN for recovery

**Output**: Verification status

## Memory Management

**Location**: `atloop/memory/`

### Memory Structure

Memory is categorized into three sections:

1. **FACTS** (fed to LLM):
   - `created_files` - Files created during task
   - `attempts` - Action attempts with results
   - `tool_results_history` - Tool execution results
   - `modified_files_content` - Content of modified files
   - `key_files` - Important files discovered

2. **LONG-TERM** (fed to LLM):
   - `plan` - Execution plan
   - `task_summary` - Task summary
   - `important_decisions` - Key decisions made
   - `milestones` - Milestones achieved
   - `learnings` - Learnings from execution

3. **DEBUG-ONLY** (NOT fed to LLM):
   - `decisions` - All decisions (filtered in production)
   - `llm_responses` - Raw LLM responses

### Memory Formatting

**Formatter**: `MemoryFormatter` in `atloop/memory/memory_manager.py`

Memory is formatted into sections:
1. Critical warnings
2. Task overview
3. Execution plan
4. Important context
5. Recent activity
6. Tool execution results
7. Modified files content
8. Current state
9. Next steps guidance

### Memory Compression

**Location**: `atloop/memory/compressor.py`

**Compression Triggers**:
- When memory size exceeds threshold (configurable)

**Compression Strategy**:
1. **Rule-based compression**:
   - Keep recent N items in each category
   - Compress old `attempts` to summary
   - Compress old `decisions` to summary
   - Trim long-term memory

2. **LLM-based compression** (if enabled):
   - Summarize old data
   - Deduplicate similar items
   - Extract key insights

## Error Handling

**Location**: `atloop/orchestrator/error_handler.py`

### Error Classification

**RECOVERABLE** (transition to PLAN for LLM recovery):
- Timeouts
- Network issues
- File not found
- Parsing errors
- Most execution errors

**FATAL** (transition to FAIL and terminate):
- Configuration errors
- State machine failures
- Critical system errors

### Error Classification Logic

**Patterns**: Defined in `ErrorHandler`
- `RECOVERABLE_PATTERNS` - Patterns that indicate recoverable errors
- `FATAL_PATTERNS` - Patterns that indicate fatal errors
- Type-based classification (e.g., `ConfigurationError` → FATAL)

**Default**: RECOVERABLE (give LLM a chance to recover)

### Error Recovery Flow

1. Error occurs during phase execution
2. `ErrorHandler.classify()` determines error category
3. If RECOVERABLE:
   - Format error for LLM consumption
   - Set `last_error` in state
   - Transition to PLAN phase
   - LLM generates recovery actions
4. If FATAL:
   - Log fatal error
   - Transition to FAIL phase
   - Terminate task

## Budget Management

**Location**: `atloop/orchestrator/budget.py`

### Budget Types

```python
Budget(
    max_llm_calls=50,      # LLM API call limit
    max_tool_calls=200,    # Tool execution limit
    max_wall_time_sec=600, # Time limit in seconds
)
```

### BudgetManager

**Methods**:
- `check_budget(state)` - Check if within budget
- `update_budget_used(state)` - Update budget usage

**Returns**: `(within_budget, error_message)` tuple

**Budget Checks**:
- Before each phase execution
- Before each tool execution
- Tracks cumulative usage

### Budget Exhaustion

When budget is exhausted:
- Set appropriate error message
- Transition to FAIL phase
- Terminate task gracefully

## State Persistence

**Location**: `atloop/orchestrator/state/manager.py`

### State File

**Path**: `runs/{task_id}/agent_state.json`

**Contents**:
```json
{
  "step": 1,
  "phase": "PLAN",
  "last_error": {...},
  "memory": {...},
  "artifacts": {...},
  "budget_used": {...}
}
```

### StateManager

**Responsibilities**:
- Single source of truth for agent state
- Auto-syncs to job_state
- Handles load/save operations
- `update()` method auto-saves after changes

### Resumability

State is fully resumable:
- Interrupted tasks can be continued
- All context preserved in agent_state.json
- Workflow resumes from last phase

## Sandbox Isolation

**Location**: `atloop/runtime/sandbox_adapter.py`

### SandboxAdapter (noxrunner)

**Purpose**: Creates isolated execution environment

**Methods**:
- `exec_shell(command, workdir, timeout_seconds)` - Execute shell command (returns sh exit code)
- `exec(command, workdir, timeout_seconds)` - Execute command directly (returns command exit code)
- `initialize_git()` - Set up git repository in sandbox

### Execution Flow

1. Upload workspace to sandbox `/workspace`
2. Execute commands in isolated environment
3. Capture results (stdout, stderr, exit_code)
4. Download results back to local workspace
5. Clean up sandbox session

### Safety Features

- **File synchronization**: Automatic sync between sandbox and workspace
- **Timeout protection**: All commands have timeout limits
- **Environment isolation**: No access to host system

## Code Conventions

### Style
- Line length: 100 characters (ruff)
- Type hints: Python 3.8+ compatible
- Quote style: double quotes

### Patterns
- **Base classes**: BasePhase, BaseTool for extensibility
- **State serialization**: All state objects have `to_dict()` and `from_dict()`
- **Tool auto-discovery**: Tools registered automatically via inheritance/convention
- **Phase transitions**: Explicit state machine with valid transitions only
- **Placeholder requirement**: ALL file/script content must use placeholders

### Error Handling
- Error classification: Recoverable vs Fatal
- Recoverable errors → transition to PLAN phase for LLM recovery
- Fatal errors → transition to FAIL phase and terminate
- Loop detection → automatic intervention after repeated failures

### Placeholder Usage (MANDATORY)
- **ALL file content** in write_file/edit_file/append_file must use placeholders
- **ALL commands** in run must use placeholders
- **ALL scripts** in run_python_script_string/run_shell_script_string must use placeholders
- Format: `---((TYPE_descriptive-name))---` followed by content
- Each placeholder must be unique within response

## Important Constraints

### Budget Management
Always set appropriate budgets for tasks:
```python
# Small fixes
Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=300)

# Medium tasks
Budget(max_llm_calls=30, max_tool_calls=150, max_wall_time_sec=900)

# Large features
Budget(max_llm_calls=80, max_tool_calls=300, max_wall_time_sec=1800)
```

### Task Types
- `bugfix`: Fix bugs, ensure tests pass
- `feature`: Implement new features with tests
- `refactor`: Improve code structure, maintain behavior

### Sandbox Isolation
All tool execution happens in sandbox - no direct file system access. Changes are synchronized between sandbox and workspace.

### File Size Limits
- `write_file`: Maximum 6,000 characters per turn
- Use `append_file` to continue writing large files
- Use `read_file` with offset/limit for reading large files

## Extension Points

### Adding New Tools
1. Inherit from `BaseTool` in `atloop/tools/base.py`
2. Implement `execute()` method returning `ToolResult`
3. Implement `validate_args()` for argument validation
4. Set `name` and `description` properties
5. Add to `VALID_TOOLS` in `atloop/llm/schema.py`
6. If tool uses placeholders, add placeholder type to `PLACEHOLDER_TYPES` in `atloop/llm/placeholder_patterns.py`

### Adding New Phases
1. Inherit from `BasePhase` in `atloop/orchestrator/phases/base.py`
2. Implement `execute()` method
3. Add to `Phase` enum
4. Update state machine transitions in `Workflow`
5. Update coordinator to handle new phase

### Custom Memory Formatting
1. Extend `MemoryFormatter` in `atloop/memory/memory_manager.py`
2. Override `format()` method
3. Use custom formatter in `Memory.get_formatted_context()`

## Common Issues and Troubleshooting

### Placeholder-Related Issues

**Symptom**: "Missing placeholder content" error
**Cause**: LLM didn't provide content blocks after JSON
**Solution**: Check LLM response format, ensure placeholders are properly delimited

**Symptom**: "Duplicate placeholder" error
**Cause**: Multiple placeholders with same name in response
**Solution**: Use unique descriptive names for each placeholder

**Symptom**: "Invalid placeholder type" error
**Cause**: Tool expects different placeholder type
**Solution**: Check tool documentation for correct placeholder type

### Memory Issues

**Symptom**: Context too large
**Cause**: Memory exceeded threshold without compression
**Solution**: Check compression policy settings, reduce memory retention

**Symptom**: Missing important context
**Cause**: Memory compression removed critical information
**Solution**: Adjust compression thresholds, review long-term memory settings

### Tool Execution Issues

**Symptom**: Tool not found
**Cause**: Tool not registered or wrong tool name
**Solution**: Check `VALID_TOOLS` in schema.py, verify tool auto-discovery

**Symptom**: Tool validation failed
**Cause**: Invalid arguments or missing required fields
**Solution**: Check tool documentation, verify argument structure

## Documentation

- `README.md` - Project overview and quick start
- `ARCHITECTURE_DOCUMENTATION.md` - Detailed architecture with mermaid diagrams
- `tests/README_E2E_TESTING.md` - End-to-end testing guide
- `e2e_test/README.md` - E2E test documentation
- `atloop/llm/prompts/en/developer.txt` - System prompt for LLM (tool usage, placeholder rules)

## Dependencies (Agentsmith Ecosystem)

atloop is part of the Agentsmith open-source ecosystem:
- varlord - Configuration management
- lexilux - LLM communication
- noxrunner - Sandbox execution backend
- atloop - Autonomous task automation (this project)

These projects work together - changes in one may affect others.
