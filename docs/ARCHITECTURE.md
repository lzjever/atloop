# TITAN Architecture

## Overview

TITAN is a task automation system that uses AI agents to execute coding tasks. The architecture follows a clean, layered design with clear separation of concerns.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  (titan/cli/) - Minimal, uses varlord for argument parsing  │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                        API Layer                             │
│  (titan/api/) - TaskRunner, single execution method         │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Core Library                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Orchestrator (titan/orchestrator/)                    │  │
│  │  - AgentLoop: Thin wrapper (39 lines)                │  │
│  │  - Workflow: DISCOVER → PLAN → ACT → VERIFY          │  │
│  │  - Coordinator: Manages state, budget, phases        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Runtime (titan/runtime/)                              │  │
│  │  - SandboxAdapter: Sandbox communication             │  │
│  │  - ToolRuntime: Tool execution                        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ LLM (titan/llm/)                                      │  │
│  │  - LLMClient: AI endpoint communication (lexilux)    │  │
│  │  - ActionJSON: Structured action parsing              │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Retrieval (titan/retrieval/)                          │  │
│  │  - Indexer: Workspace indexing                        │  │
│  │  - ProjectProfile: Project analysis                   │  │
│  │  - ContextPack: Context building                      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Memory (titan/memory/)                                │  │
│  │  - MemoryManager: State management                    │  │
│  │  - Summarizer: History compression                     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Tools (titan/tools/)                                  │  │
│  │  - Registry: Tool registration                        │  │
│  │  - Filesystem, Interaction, Search, System tools      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Config (titan/config/)                                │  │
│  │  - ConfigLoader: Uses varlord for type-safe config    │  │
│  │  - Models: TitanConfig, TaskSpec, Budget, etc.        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Simple
- **One function, one method**: Each class has a single, clear responsibility
- **Minimal interfaces**: APIs are as simple as possible
- **Few parameters**: Functions take only necessary parameters

### 2. Clear
- **One class, one responsibility**: Clear separation of concerns
- **Clear directory structure**: Logical module organization
- **Clear naming**: Self-documenting code

### 3. Explicit
- **Predictable behavior**: No hidden side effects
- **No ambiguity**: Clear error messages and behavior
- **Type safety**: varlord ensures configuration type safety

### 4. Unique
- **One thing, one way**: Single workflow implementation
- **No multiple choices**: Removed redundant implementations
- **Single execution method**: `TaskRunner.execute()` is the only way to run tasks

## Layer Responsibilities

### CLI Layer (`titan/cli/`)
- **Purpose**: User interaction entry point
- **Responsibilities**:
  - Parse command-line arguments (uses varlord)
  - Read user input (prompt text or file)
  - Display results
- **Size**: 71 lines (92.6% reduction from original)
- **Dependencies**: varlord (for CLI argument parsing)

### API Layer (`titan/api/`)
- **Purpose**: Programmatic interface
- **Responsibilities**:
  - Provide `TaskRunner` class
  - Single `execute()` method
  - Configuration management (uses varlord via ConfigLoader)
- **Dependencies**: varlord (via ConfigLoader)

### Core Library
- **Purpose**: Core functionality
- **No varlord dependency**: Pure business logic
- **Dependencies**: lexilux (for LLM), noxrunner (for sandbox)

## Workflow

### Unified Workflow: DISCOVER → PLAN → ACT → VERIFY

```
┌──────────┐
│ DISCOVER │  Analyze workspace, understand task
└────┬─────┘
     │
┌────▼─────┐
│  PLAN    │  Generate execution plan
└────┬─────┘
     │
┌────▼─────┐
│   ACT    │  Execute tool calls
└────┬─────┘
     │
┌────▼─────┐
│ VERIFY   │  Verify results, run tests
└────┬─────┘
     │
     ├─── Success → Complete
     └─── Failure → Retry or Report
```

### Phase Details

1. **DISCOVER** (`titan/orchestrator/phases/discover.py`)
   - Index workspace
   - Analyze project structure
   - Understand task requirements

2. **PLAN** (`titan/orchestrator/phases/plan.py`)
   - Generate execution plan
   - Break down task into steps
   - Identify required tools

3. **ACT** (`titan/orchestrator/phases/act.py`)
   - Execute tool calls
   - Monitor execution
   - Handle errors

4. **VERIFY** (`titan/orchestrator/phases/verify.py`)
   - Run tests
   - Verify changes
   - Generate report

## State Management

### StateMachine (`titan/orchestrator/state_machine.py`)
- Manages phase transitions
- Enforces workflow order
- Handles state persistence

### StateManager (`titan/orchestrator/state/manager.py`)
- Persists job state
- Recovers from failures
- Manages state files

### BudgetManager (`titan/orchestrator/budget.py`)
- Tracks LLM calls
- Tracks tool calls
- Tracks wall time
- Enforces budget limits

## Configuration Management

### Varlord Integration
- **CLI**: Uses varlord for CLI argument parsing
- **API/Lib**: Uses varlord via `ConfigLoader` for type-safe configuration
- **Centralized models**: All config models in `titan/config/models.py`
- **Multi-source loading**: YAML files, environment variables, .env files

### ConfigLoader (`titan/config/loader.py`)
- `setup()`: Initialize configuration (call once at startup)
- `get()`: Get configuration (access from anywhere)
- Type-safe: Returns `TitanConfig` (validated by varlord)

## Key Components

### AgentLoop (`titan/orchestrator/agent_loop.py`)
- **Size**: 39 lines (98.3% reduction from original 2344 lines)
- **Purpose**: Thin wrapper around Workflow
- **Single method**: `run()` - executes workflow

### WorkflowCoordinator (`titan/orchestrator/coordinator.py`)
- Manages workflow execution
- Coordinates phases
- Handles state transitions
- Manages budget

### ToolExecutor (`titan/orchestrator/executor/tool_executor.py`)
- Executes tool calls
- Handles tool errors
- Formats tool output

## Dependencies

### Core Dependencies
- **lexilux**: LLM client communication
- **noxrunner**: Sandbox execution
- **varlord**: Configuration management (CLI + API/Lib)

### Development Dependencies
- **pytest**: Testing
- **ruff**: Linting and formatting
- **mypy**: Type checking

## File Organization

```
titan/
├── api/              # API layer (TaskRunner)
├── cli/              # CLI layer (minimal)
├── config/           # Configuration (varlord)
├── llm/              # LLM client (lexilux)
├── orchestrator/     # Workflow orchestration
├── runtime/          # Runtime execution
├── retrieval/        # Code retrieval
├── memory/           # Memory management
├── logging/          # Event logging
├── tools/            # Tool implementations
└── skills/           # Skill system
```

## Internationalization

- **Code**: All in English
- **Logs**: All in English
- **Prompts**: English templates in `titan/llm/prompts/en/`
- **Template support**: `PromptLoader` enables language switching

## Testing

- **Unit tests**: Test individual components
- **Integration tests**: Test component interactions
- **E2E tests**: Test complete workflows
- **Validation tests**: Verify code quality and configuration
- **Total**: 100+ tests, 100% pass rate

## Performance Considerations

- **Token limits**: Configurable via `AIPerformanceConfig`
- **Memory compression**: Automatic history compression
- **Context limits**: Configurable via `limits.py`
- **Budget tracking**: Enforced at runtime
