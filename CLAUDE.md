# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Testing
```bash
# Run all unit tests (excludes integration tests)
make test
# or
uv run pytest tests/ -v

# Run tests with coverage
make test-cov

# Run integration tests (requires external services)
make test-integration

# Run specific test
uv run pytest tests/test_specific_file.py::test_function_name -v

# Run E2E CLI tests (see tests/README_E2E_TESTING.md)
uv run pytest tests/test_e2e_cli_subprocess.py -v
```

### Code Quality
```bash
# Run linting checks
make lint
# or
uv run ruff check atloop/ tests/

# Format code
make format
# or
uv run ruff format atloop/ tests/

# Check formatting without making changes
make format-check
# or
uv run ruff format --check atloop/ tests/

# Run all checks (lint + format check + tests)
make check
```

### Build and Install
```bash
# Development install (recommended)
make dev-install

# Install dependencies without installing package (for CI/tools only)
make setup-venv

# Build distributions
make build
```

## High-Level Architecture

atloop is an autonomous AI agent system that executes coding tasks through a structured **DISCOVER → PLAN → ACT → VERIFY** workflow cycle.

### Layered Architecture

```
Entry Layer
  ├─ CLI (atloop/cli/)          - argparse-based CLI with commands: init, exec, exec-file, config
  └─ API (atloop/api/)          - TaskRunner class for programmatic access

Orchestration Layer
  ├─ AgentLoop                  - Thin wrapper creating workflow and handling top-level errors
  ├─ Workflow                   - 4-phase execution loop with budget management and breakpoints
  ├─ WorkflowCoordinator        - Central hub managing all subsystems (DI container)
  └─ StateMachine               - Phase transition enforcement (DISCOVER/PLAN/ACT/VERIFY → DONE/FAIL)

Phase Layer (atloop/orchestrator/phases/)
  ├─ DiscoverPhase              - Workspace analysis, context pack building
  ├─ PlanPhase                  - LLM prompt generation, action planning
  ├─ ActPhase                   - Tool execution, result processing
  └─ VerifyPhase                - Test execution, completion validation

Infrastructure Layer
  ├─ Memory (atloop/memory/)    - Long-term memory with intelligent compression
  ├─ Tools (atloop/tools/)      - Auto-discovered tool registry (filesystem, search, system)
  ├─ LLM (atloop/llm/)          - Multi-provider LLM client with prompt templates
  ├─ Sandbox (atloop/runtime/)  - noxrunner adapter for isolated execution
  ├─ Retrieval (atloop/retrieval/) - Workspace indexing and context pack building
  └─ State (atloop/orchestrator/state/) - Persistent state management
```

### Key Design Patterns

1. **Dependency Injection**: Components receive dependencies through constructors (coordinator pattern)
2. **State Machine**: Explicit phase transitions with terminal states (DONE, FAIL)
3. **Event-Driven**: Structured event emitter for logging and output handling
4. **Sandbox Isolation**: All tool execution happens in isolated environments via noxrunner

### Component Interaction Flow

```
TaskSpec → TaskRunner → AgentLoop → Workflow → Coordinator
                                                    ↓
                                    Initializes all subsystems
                                                    ↓
Workflow executes phase loop:
  DISCOVER → build context pack (Retrieval + Memory)
  PLAN → generate actions (LLM + Memory)
  ACT → execute tools (Tools + Sandbox)
  VERIFY → run tests (Tools + Sandbox)
  → repeat until DONE/FAIL
```

## Important Architecture Notes

### Memory System
- **Two-layer memory**: Short-term (agent state) and long-term (plan, decisions, milestones)
- **Intelligent compression**: Rule-based compression + LLM summarization when context grows
- **Formatter**: Converts memory state to formatted strings for LLM context
- **Key distinction**: Memory system handles storage/formatting, ContextPack handles prompt assembly

### Tool System
- **Auto-discovery**: Tools discovered dynamically and registered in ToolRegistry
- **Categories**:
  - Filesystem: `read_file`, `write_file`, `edit_file`, `append_file`, `glob_files`
  - System: `run_command`, `run_python_script`
  - Search: `search` (regex with context)
  - Interaction: `todo_read`, `todo_write`, `load_skill`
- **Validation**: All tool arguments validated before execution

### State Persistence
- All state persisted to `runs/{task_id}/agent_state.json` after each step
- Enables resumable execution and debugging
- Includes memory, artifacts, budget usage, and error tracking

### Error Handling
- **Classification**: Recoverable vs Fatal errors (ErrorClassifier)
- **Recovery workflow**: Transition to PLAN phase with error context for LLM recovery
- **Loop detection**: LoopDetector with intervention for repetitive failures

### Phase Transitions
- DISCOVER → PLAN (context built)
- PLAN → ACT (actions generated) or DONE (task complete)
- ACT → VERIFY (actions executed)
- VERIFY → DISCOVER (continue) or DONE (complete) or FAIL (fatal error)

## Configuration

- Uses **varlord** for configuration management
- Config file: `~/.atloop/config/atloop.yaml`
- Environment variable support with `${VAR_NAME}` syntax
- Key sections:
  - `ai.completion`: LLM provider settings (model, api_base, api_key)
  - `ai.embedding`: Embedding model for retrieval
  - `sandbox`: noxrunner backend settings (base_url, local_test)
  - `memory`: Compression and summarization settings

## Testing Notes

### E2E Tests
- Located in `tests/test_e2e_cli_subprocess.py`
- Execute actual CLI commands as subprocess
- **Strict philosophy**: Exit code must be 0, files must be created, content validated
- Each test can take 30-120 seconds depending on LLM response time
- Use `--tb=short` for cleaner failure output

### Test Structure
- Unit tests in `tests/` mirror package structure
- Integration tests marked with `@pytest.mark.integration`
- Use fixtures for common test setup (see `tests/conftest.py`)

## Skills System

Skills are loadable knowledge modules (see `atloop/skills/builtin/`):
- `error-handling`: Error classification and recovery patterns
- `tool-usage`: Tool execution best practices
- `best-practices`: General development guidelines
- Skills loaded via `load_skill` tool during ACT phase

## Common Gotchas

1. **Memory vs Context Pack**: Memory stores/formats data, ContextPack assembles prompts
2. **Phase transitions**: Must use StateMachine, never transition directly
3. **Sandbox paths**: All file operations happen in sandbox, sync to workspace on completion
4. **LLM placeholders**: Use `${placeholder}` syntax, replaced by PlaceholderReplacer
5. **State persistence**: State saved after every step - don't rely on in-memory state across steps
6. **Tool results**: Processed through ResultAdapter before being stored in memory
7. **Budget management**: Check budget at phase boundaries, not during tool execution
