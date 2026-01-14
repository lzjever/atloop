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
- `discover.py` - Analyze workspace, build context
- `plan.py` - Generate execution plan via LLM
- `act.py` - Execute tools
- `verify.py` - Run tests, validate results

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
- `filesystem/` - File operations (read, write, edit, glob)
- `system/` - Command execution (run, shell scripts, Python scripts)
- `search/` - Regex search with context
- `interaction/` - Todo operations, skill loading

**LLM (`atloop/llm/`)**
- `schema.py` - ActionJSON schema for tool execution
- `placeholder_patterns.py` - Dynamic placeholder replacement in actions
- `prompts/` - System prompts for LLM (multilingual: en, zh)

**Config (`atloop/config/`)**
- Uses varlord for configuration management
- `models.py` - TaskSpec, Budget, and other data models
- Configuration file: `~/.atloop/config/atloop.yaml`

**Runtime (`atloop/runtime/`)**
- `sandbox_adapter.py` - Isolated execution environment interface
- `tool_runtime.py` - Tool execution in sandbox

### Workflow Execution

1. **DISCOVER**: Build context pack (goal + project profile + relevant files + memory)
2. **PLAN**: LLM generates ActionJSON with tool calls and placeholders
3. **ACT**: Execute tools in sandbox, update memory and state
4. **VERIFY**: Run verification (tests), check if task is complete
5. Repeat from DISCOVER until task complete or budget exhausted

### State Persistence

All state is persisted to `runs/{task_id}/agent_state.json` after each step:
- AgentState (step, phase, last_error, memory, artifacts, budget_used)
- Memory (facts, long-term data, debug-only data)
- Artifacts (current_diff, test_results, verification_success)

State is fully resumable - interrupted tasks can be continued.

### Memory Management

Memory is formatted via `MemoryFormatter` into sections:
- Critical warnings
- Task overview
- Execution plan
- Important context
- Recent activity
- Tool execution results
- Modified files content
- Current state
- Next steps guidance

Compression triggers when size exceeds threshold:
1. Rule-based: compress attempts, decisions, trim long-term memory
2. LLM-based: summarize old data, deduplicate

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

### Error Handling
- Error classification: Recoverable vs Fatal
- Recoverable errors → transition to PLAN phase for LLM recovery
- Fatal errors → transition to FAIL phase and terminate
- Loop detection → automatic intervention after repeated failures

## Important Constraints

### Budget Management
Always set appropriate budgets for tasks:
```python
Budget(
    max_llm_calls=50,      # LLM API call limit
    max_tool_calls=200,    # Tool execution limit
    max_wall_time_sec=600, # Time limit in seconds
)
```

### Task Types
- `bugfix`: Fix bugs, ensure tests pass
- `feature`: Implement new features with tests
- `refactor`: Improve code structure, maintain behavior

### Sandbox Isolation
All tool execution happens in sandbox - no direct file system access. Changes are synchronized between sandbox and workspace.

## Extension Points

### Adding New Tools
1. Inherit from `BaseTool` in `atloop/tools/base.py`
2. Implement `execute()` method returning `ToolResult`
3. Register in `ToolRegistry` (auto-discovery or manual)
4. Update tool schema in `atloop/llm/schema.py` if needed

### Adding New Phases
1. Inherit from `BasePhase` in `atloop/orchestrator/phases/base.py`
2. Implement `execute()` method
3. Add to `Phase` enum
4. Update state machine transitions in `Workflow`

### Custom Memory Formatting
1. Extend `MemoryFormatter` in `atloop/memory/memory_manager.py`
2. Override `format()` method
3. Use custom formatter in `Memory.get_formatted_context()`

## Documentation

- `README.md` - Project overview and quick start
- `ARCHITECTURE_DOCUMENTATION.md` - Detailed architecture with mermaid diagrams
- `tests/README_E2E_TESTING.md` - End-to-end testing guide
- `e2e_test/README.md` - E2E test documentation

## Dependencies (Agentsmith Ecosystem)

atloop is part of the Agentsmith open-source ecosystem:
- varlord - Configuration management
- lexilux - LLM communication
- noxrunner - Sandbox execution backend
- atloop - Autonomous task automation (this project)

These projects work together - changes in one may affect others.
