# TITAN Features

## Overview

TITAN is an AI-powered task automation system designed to execute coding tasks autonomously. It provides both CLI and API interfaces for task execution.

## Core Features

### 1. Unified Workflow

TITAN uses a single, unified workflow: **DISCOVER → PLAN → ACT → VERIFY**

- **DISCOVER**: Analyze workspace, understand task requirements
- **PLAN**: Generate execution plan
- **ACT**: Execute tool calls
- **VERIFY**: Verify results, run tests

This unified approach eliminates confusion and provides predictable behavior.

### 2. Task Types

TITAN supports three task types:

- **bugfix**: Fix bugs in code
- **feature**: Implement new features
- **refactor**: Refactor existing code

### 3. Configuration Management

#### Type-Safe Configuration
- Uses **varlord** for type-safe configuration
- Centralized models in `titan/config/models.py`
- Multi-source loading: YAML files, environment variables, .env files

#### Configuration Sources (Priority Order)
1. Environment variables (`TITAN__*`)
2. `.env` file (in current directory)
3. Project config (`./.titan/config/titan.yaml`)
4. User config (`~/.titan/config/titan.yaml`)

#### Key Configuration Models
- `TitanConfig`: Main configuration
- `TaskSpec`: Task specification
- `Budget`: Execution budget (LLM calls, tool calls, wall time)
- `SandboxConfig`: Sandbox configuration
- `MemoryConfig`: Memory management settings

### 4. Budget Management

TITAN tracks and enforces execution budgets:

- **LLM calls**: Maximum number of LLM API calls
- **Tool calls**: Maximum number of tool executions
- **Wall time**: Maximum execution time

Budget is enforced at runtime, preventing runaway executions.

### 5. State Management

#### State Persistence
- Job state is persisted to disk
- Can recover from failures
- Supports resuming interrupted tasks

#### State Components
- `AgentState`: Current agent state
- `JobState`: Job execution state
- `StateManager`: Manages state persistence

### 6. Memory Management

#### Automatic Compression
- History compression when context exceeds threshold
- Memory summarization for long-running tasks
- Intelligent retention of important information

#### Memory Components
- `MemoryManager`: Manages agent memory
- `Summarizer`: Compresses history
- `Scorer`: Scores memory items for retention

### 7. Tool System

#### Built-in Tools
- **Filesystem**: File operations (read, write, list, etc.)
- **Interaction**: User interaction (ask, confirm)
- **Search**: Code search (grep, find)
- **System**: System operations (run commands)

#### Tool Features
- Auto-discovery of tool implementations
- Tool registry for tool management
- Error handling and output formatting

### 8. Skills System

#### Built-in Skills
- **best-practices**: Coding best practices
- **error-handling**: Error handling patterns
- **tool-usage**: Tool usage guidelines

#### Custom Skills
- Load skills from custom directories
- Skills provide context and guidance to the agent

### 9. Event Logging

#### Comprehensive Logging
- All events are logged
- Event replay for debugging
- Report generation

#### Log Components
- `EventLogger`: Logs events
- `EventReplay`: Replays events
- `ReportGenerator`: Generates reports

### 10. Code Retrieval

#### Workspace Indexing
- Automatic workspace indexing
- Project profile detection
- Context pack building

#### Retrieval Components
- `Indexer`: Indexes workspace
- `ProjectProfile`: Analyzes project structure
- `ContextPack`: Builds context for LLM

## CLI Features

### Commands

#### `titan init`
Initialize TITAN configuration.

```bash
titan init [--titan-dir DIR]
```

#### `titan execute`
Execute a task.

```bash
titan execute \
  --workspace /path/to/workspace \
  --prompt "Fix the bug in calculator.py" \
  [--prompt-file /path/to/prompt.txt] \
  [--sandbox-url http://127.0.0.1:8080] \
  [--local-test] \
  [--session SESSION_ID] \
  [--titan-dir DIR]
```

#### `titan config`
Show current configuration.

```bash
titan config [--titan-dir DIR]
```

### CLI Design
- **Minimal**: 71 lines (92.6% reduction from original)
- **Uses varlord**: For CLI argument parsing
- **Single responsibility**: Read parameters, provide user interaction

## API Features

### TaskRunner

The `TaskRunner` class provides a programmatic interface for task execution.

#### Initialization

```python
from titan.api import TaskRunner

runner = TaskRunner(titan_dir="/path/to/.titan")  # Optional
```

#### Execution

```python
result = runner.execute(
    task_config={
        "goal": "Fix the bug in calculator.py",
        "workspace_root": "/path/to/workspace",
        "task_type": "bugfix",
        "constraints": ["Don't change the API"],
        "budget": {
            "max_llm_calls": 50,
            "max_tool_calls": 100,
            "max_wall_time_sec": 3600,
        },
        "sandbox": {  # Optional override
            "base_url": "http://127.0.0.1:8080",
            "local_test": False,
        },
    },
    console=False,  # Optional: show console output
)

if result["success"]:
    print(f"Task completed: {result['status']}")
    print(f"Report: {result['report']}")
else:
    print(f"Task failed: {result.get('error')}")
```

### API Design
- **Single method**: `execute()` - the only way to run tasks
- **Type-safe**: Uses varlord for configuration
- **Simple**: Minimal interface, clear behavior

## Configuration Examples

### Basic Configuration (`~/.titan/config/titan.yaml`)

```yaml
ai:
  completion:
    model: "gpt-4"
    api_base: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
  performance:
    max_tokens_input: 128000
    max_tokens_output: 8000

sandbox:
  base_url: "http://127.0.0.1:8080"
  local_test: false

default_budget:
  max_llm_calls: 80
  max_tool_calls: 200
  max_wall_time_sec: 3600

memory:
  max_items: 100
  compression_threshold: 0.7
```

### Environment Variable Overrides

```bash
export TITAN__AI__COMPLETION__MODEL="gpt-4-turbo"
export TITAN__AI__COMPLETION__API_BASE="https://api.openai.com/v1"
export TITAN__DEFAULT_BUDGET__MAX_LLM_CALLS=100
```

## Usage Examples

### Example 1: Bug Fix

```bash
titan execute \
  --workspace /path/to/project \
  --prompt "Fix the division by zero error in calculator.py"
```

### Example 2: Feature Implementation

```bash
titan execute \
  --workspace /path/to/project \
  --prompt "Add a square root function to calculator.py" \
  --prompt-file /path/to/requirements.txt
```

### Example 3: Refactoring

```bash
titan execute \
  --workspace /path/to/project \
  --prompt "Refactor calculator.py to use a class-based design" \
  --task-type refactor
```

### Example 4: API Usage

```python
from titan.api import TaskRunner

runner = TaskRunner()

result = runner.execute({
    "goal": "Add error handling to all functions",
    "workspace_root": "/path/to/project",
    "task_type": "refactor",
    "constraints": [
        "Maintain backward compatibility",
        "Add unit tests for error cases",
    ],
})

print(f"Success: {result['success']}")
print(f"Status: {result['status']}")
```

## Error Handling

### Budget Exhaustion
- Task stops when budget is exhausted
- Returns failure status with reason

### Tool Errors
- Tool errors are captured and included in context
- Agent can retry with different approach

### State Recovery
- State is persisted after each phase
- Can resume from last successful phase

## Performance

### Token Management
- Automatic context window management
- History compression when needed
- Memory summarization for long tasks

### Execution Limits
- Configurable via `Budget` model
- Enforced at runtime
- Prevents runaway executions

## Internationalization

- **Code**: All in English
- **Logs**: All in English
- **Prompts**: English templates (with support for other languages)
- **Template system**: `PromptLoader` enables language switching

## Testing

TITAN includes comprehensive tests:

- **Unit tests**: 29 tests
- **Integration tests**: 32 tests
- **E2E tests**: 21 tests
- **Validation tests**: 19 tests
- **Total**: 100+ tests, 100% pass rate

## Limitations

### Current Limitations
- Code coverage: 39% (target: >80%)
- Some modules lack unit tests
- Performance tests not yet implemented

### Known Issues
- Large codebases may require more memory
- Complex refactorings may exceed budget
- Some edge cases in error handling

## Future Enhancements

### Planned Features
- Performance tests
- Stress tests
- Additional unit tests for all modules
- Improved error messages
- Better state recovery

### Under Consideration
- Parallel tool execution
- Incremental workspace indexing
- Advanced memory compression strategies
- Custom tool development framework
