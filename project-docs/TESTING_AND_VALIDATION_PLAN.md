# atloop Testing and Validation Plan

## Overview

This document outlines a comprehensive testing and validation plan for the refactored atloop project. The plan covers unit tests, integration tests, end-to-end tests, performance tests, and validation criteria.

**Target Coverage**: >80%  
**Test Framework**: pytest  
**Real Configuration**: Uses `/home/percy/.atloop/config/atloop.yaml`

---

## Phase 1: Module Completion and Unit Tests

### 1.1 Missing Modules to Copy/Implement

**Priority: HIGH** - These modules are required for full functionality:

1. **atloop.skills** - Skill loading system
   - `EnhancedSkillLoader` class
   - Skill directory management
   - Skill file reading

2. **atloop.runtime** - Runtime execution layer
   - `SandboxAdapter` - Sandbox communication
   - `ToolRuntime` - Tool execution wrapper
   - Tool implementations (read_file, write_file, edit_file, etc.)

3. **atloop.retrieval** - Code retrieval system
   - `WorkspaceIndexer` - Workspace indexing
   - `ProjectProfileDetector` - Project type detection
   - `ContextPackBuilder` - Context packaging

4. **atloop.logging** - Event logging system
   - `EventLogger` - Event recording
   - `EventReplay` - Event replay functionality
   - `ReportGenerator` - Report generation

5. **atloop.memory** - Memory management
   - `MemoryManager` - Memory management
   - `MemorySummarizer` - Memory summarization
   - `AgentState` - Agent state model

### 1.2 Unit Tests by Module

#### A. Configuration Module (`atloop/config/`)

**File**: `tests/test_config_unit.py`

**Test Cases**:
- [ ] `test_config_loader_setup` - ConfigLoader.setup() with real config
- [ ] `test_config_loader_get` - ConfigLoader.get() returns valid config
- [ ] `test_config_loader_custom_dir` - Custom atloop directory support
- [ ] `test_config_loader_env_override` - Environment variable overrides
- [ ] `test_config_loader_priority` - Config source priority (env > project > user)
- [ ] `test_titan_config_validation` - AtloopConfig model validation
- [ ] `test_task_spec_creation` - TaskSpec creation and validation
- [ ] `test_budget_creation` - Budget model creation
- [ ] `test_sandbox_config_creation` - SandboxConfig model creation
- [ ] `test_memory_config_creation` - MemoryConfig model creation
- [ ] `test_config_type_safety` - Type safety validation (varlord)

**Acceptance Criteria**:
- All config loading scenarios pass
- Type safety enforced by varlord
- Real config file loads correctly
- Custom directories work correctly

#### B. LLM Client Module (`atloop/llm/`)

**File**: `tests/test_llm_client_unit.py`

**Test Cases**:
- [ ] `test_llm_client_initialization` - LLMClient initialization
- [ ] `test_llm_client_prompt_loader` - PromptLoader integration
- [ ] `test_llm_client_system_prompt` - System prompt loading
- [ ] `test_llm_client_developer_prompt` - Developer prompt loading
- [ ] `test_llm_client_language_switching` - Language switching (en/zh)
- [ ] `test_action_json_validation` - ActionJSON validation
- [ ] `test_action_json_parsing` - ActionJSON parsing from LLM response
- [ ] `test_action_json_repair` - JSON repair functionality
- [ ] `test_action_json_extraction` - JSON extraction from text
- [ ] `test_llm_client_error_handling` - Error handling (API failures, timeouts)
- [ ] `test_llm_client_token_limits` - Token limit enforcement
- [ ] `test_llm_client_placeholder_replacement` - Placeholder replacement

**Acceptance Criteria**:
- All prompt loading scenarios work
- ActionJSON parsing handles malformed JSON
- Error handling is robust
- Token limits are enforced

#### C. Orchestrator Module (`atloop/orchestrator/`)

**File**: `tests/test_orchestrator_unit.py`

**Test Cases**:
- [ ] `test_workflow_coordinator_init` - WorkflowCoordinator initialization
- [ ] `test_workflow_coordinator_components` - All components initialized
- [ ] `test_state_manager_init` - StateManager initialization
- [ ] `test_state_manager_persistence` - State persistence (save/load)
- [ ] `test_state_machine_transitions` - StateMachine valid transitions
- [ ] `test_state_machine_invalid_transitions` - Invalid transition handling
- [ ] `test_budget_manager_init` - BudgetManager initialization
- [ ] `test_budget_manager_tracking` - Budget tracking (LLM, tools, time)
- [ ] `test_budget_manager_exhaustion` - Budget exhaustion detection
- [ ] `test_phase_discover_execute` - DiscoverPhase execution
- [ ] `test_phase_plan_execute` - PlanPhase execution
- [ ] `test_phase_act_execute` - ActPhase execution
- [ ] `test_phase_verify_execute` - VerifyPhase execution
- [ ] `test_tool_executor_execute` - ToolExecutor execution
- [ ] `test_agent_loop_init` - AgentLoop initialization
- [ ] `test_agent_loop_run` - AgentLoop.run() basic flow
- [ ] `test_workflow_run` - Workflow.run() execution
- [ ] `test_verifier_init` - Verifier initialization
- [ ] `test_verifier_verify` - Verifier verification logic

**Acceptance Criteria**:
- All components initialize correctly
- State transitions are valid
- Budget tracking is accurate
- Phases execute in correct order

#### D. Runtime Module (`atloop/runtime/`)

**File**: `tests/test_runtime_unit.py`

**Test Cases**:
- [ ] `test_sandbox_adapter_init` - SandboxAdapter initialization
- [ ] `test_sandbox_adapter_connect` - Sandbox connection
- [ ] `test_sandbox_adapter_execute` - Command execution
- [ ] `test_sandbox_adapter_local_test` - Local test mode
- [ ] `test_tool_runtime_init` - ToolRuntime initialization
- [ ] `test_tool_read_file` - read_file tool
- [ ] `test_tool_write_file` - write_file tool
- [ ] `test_tool_edit_file` - edit_file tool
- [ ] `test_tool_append_file` - append_file tool
- [ ] `test_tool_run` - run tool
- [ ] `test_tool_glob` - glob tool
- [ ] `test_tool_search` - search tool
- [ ] `test_tool_error_handling` - Tool error handling
- [ ] `test_tool_timeout` - Tool timeout handling

**Acceptance Criteria**:
- All tools execute correctly
- Error handling is robust
- Timeouts are handled properly

#### E. Retrieval Module (`atloop/retrieval/`)

**File**: `tests/test_retrieval_unit.py`

**Test Cases**:
- [ ] `test_workspace_indexer_init` - WorkspaceIndexer initialization
- [ ] `test_workspace_indexer_index` - Workspace indexing
- [ ] `test_workspace_indexer_search` - Code search functionality
- [ ] `test_project_profile_detector_init` - ProjectProfileDetector initialization
- [ ] `test_project_profile_detector_detect_python` - Python project detection
- [ ] `test_project_profile_detector_detect_nodejs` - Node.js project detection
- [ ] `test_project_profile_detector_detect_go` - Go project detection
- [ ] `test_context_pack_builder_init` - ContextPackBuilder initialization
- [ ] `test_context_pack_builder_build` - Context pack building
- [ ] `test_context_pack_builder_keywords` - Keyword extraction

**Acceptance Criteria**:
- Workspace indexing works correctly
- Project types are detected accurately
- Context packs are built correctly

#### F. Memory Module (`atloop/memory/`)

**File**: `tests/test_memory_unit.py`

**Test Cases**:
- [ ] `test_memory_manager_init` - MemoryManager initialization
- [ ] `test_memory_manager_add_decision` - Add decision to memory
- [ ] `test_memory_manager_add_attempt` - Add attempt to memory
- [ ] `test_memory_manager_add_error` - Add error to memory
- [ ] `test_memory_manager_compression` - Memory compression
- [ ] `test_memory_summarizer_init` - MemorySummarizer initialization
- [ ] `test_memory_summarizer_summarize` - Memory summarization
- [ ] `test_memory_summarizer_length_limit` - Summary length limits
- [ ] `test_agent_state_init` - AgentState initialization
- [ ] `test_agent_state_serialization` - AgentState serialization
- [ ] `test_agent_state_deserialization` - AgentState deserialization

**Acceptance Criteria**:
- Memory management works correctly
- Compression reduces memory size
- Summarization maintains important information

#### G. Logging Module (`atloop/logging/`)

**File**: `tests/test_logging_unit.py`

**Test Cases**:
- [ ] `test_event_logger_init` - EventLogger initialization
- [ ] `test_event_logger_log_tool_call` - Tool call logging
- [ ] `test_event_logger_log_tool_result` - Tool result logging
- [ ] `test_event_logger_log_llm_call` - LLM call logging
- [ ] `test_event_logger_log_state_change` - State change logging
- [ ] `test_event_replay_init` - EventReplay initialization
- [ ] `test_event_replay_replay_to_step` - Replay to specific step
- [ ] `test_event_replay_get_events` - Get events by step
- [ ] `test_report_generator_init` - ReportGenerator initialization
- [ ] `test_report_generator_success_report` - Success report generation
- [ ] `test_report_generator_failure_report` - Failure report generation
- [ ] `test_report_generator_markdown` - Markdown report generation

**Acceptance Criteria**:
- All events are logged correctly
- Event replay works accurately
- Reports are generated correctly

#### H. Skills Module (`atloop/skills/`)

**File**: `tests/test_skills_unit.py`

**Test Cases**:
- [ ] `test_skill_loader_init` - EnhancedSkillLoader initialization
- [ ] `test_skill_loader_load_builtin` - Builtin skill loading
- [ ] `test_skill_loader_load_project` - Project skill loading
- [ ] `test_skill_loader_load_custom` - Custom skill loading
- [ ] `test_skill_loader_read_skill_file` - Skill file reading

**Acceptance Criteria**:
- Skills load from all directories
- Skill files are read correctly

#### I. CLI Module (`atloop/cli/`)

**File**: `tests/test_cli_unit.py`

**Test Cases**:
- [ ] `test_cli_main_parser` - CLI argument parser
- [ ] `test_cli_init_command` - init command
- [ ] `test_cli_execute_command` - execute command
- [ ] `test_cli_config_command` - config command
- [ ] `test_cli_error_handling` - Error handling
- [ ] `test_cli_prompt_file` - Prompt file reading
- [ ] `test_cli_workspace_validation` - Workspace validation

**Acceptance Criteria**:
- All CLI commands work correctly
- Error messages are clear
- Input validation works

#### J. API Module (`atloop/api/`)

**File**: `tests/test_api_unit.py`

**Test Cases**:
- [ ] `test_task_runner_init` - TaskRunner initialization
- [ ] `test_task_runner_execute` - TaskRunner.execute()
- [ ] `test_task_runner_config_loading` - Config loading
- [ ] `test_task_runner_error_handling` - Error handling
- [ ] `test_task_runner_result_format` - Result format validation

**Acceptance Criteria**:
- TaskRunner initializes correctly
- Execute method works
- Results are formatted correctly

---

## Phase 2: Integration Tests

### 2.1 Component Integration Tests

**File**: `tests/test_integration_components.py`

**Test Cases**:
- [ ] `test_config_loader_integration` - ConfigLoader with real config (✅ DONE)
- [ ] `test_api_runner_integration` - TaskRunner with real config (✅ DONE)
- [ ] `test_workflow_integration` - Workflow components (✅ DONE)
- [ ] `test_cli_integration` - CLI commands with real config (⚠️ PARTIAL)
- [ ] `test_llm_client_config_integration` - LLMClient with real config
- [ ] `test_orchestrator_config_integration` - Orchestrator with real config
- [ ] `test_runtime_sandbox_integration` - Runtime with sandbox
- [ ] `test_retrieval_workspace_integration` - Retrieval with workspace
- [ ] `test_memory_persistence_integration` - Memory persistence
- [ ] `test_logging_file_integration` - Logging to files

### 2.2 Workflow Integration Tests

**File**: `tests/test_integration_workflow.py`

**Test Cases**:
- [ ] `test_discover_phase_integration` - DISCOVER phase with real components
- [ ] `test_plan_phase_integration` - PLAN phase with real LLM
- [ ] `test_act_phase_integration` - ACT phase with real tools
- [ ] `test_verify_phase_integration` - VERIFY phase with real verifier
- [ ] `test_workflow_phase_transitions` - Phase transitions
- [ ] `test_workflow_budget_tracking` - Budget tracking across phases
- [ ] `test_workflow_state_persistence` - State persistence across phases
- [ ] `test_workflow_error_recovery` - Error recovery in workflow

### 2.3 End-to-End Integration Tests

**File**: `tests/test_integration_e2e.py`

**Test Cases**:
- [ ] `test_e2e_simple_bugfix` - Simple bugfix end-to-end
- [ ] `test_e2e_simple_feature` - Simple feature implementation
- [ ] `test_e2e_simple_refactor` - Simple refactoring
- [ ] `test_e2e_multi_file_edit` - Multi-file editing
- [ ] `test_e2e_with_tests` - End-to-end with test execution
- [ ] `test_e2e_error_scenarios` - Error scenario handling
- [ ] `test_e2e_budget_exhaustion` - Budget exhaustion handling
- [ ] `test_e2e_state_recovery` - State recovery after failure

---

## Phase 3: End-to-End Tests

### 3.1 Real-World Scenarios

**File**: `tests/test_e2e_scenarios.py`

**Test Cases**:
- [ ] `test_e2e_calculator_bugfix` - Calculator bugfix scenario
- [ ] `test_e2e_python_project_setup` - Python project setup
- [ ] `test_e2e_nodejs_project_setup` - Node.js project setup
- [ ] `test_e2e_go_project_setup` - Go project setup
- [ ] `test_e2e_multi_language_project` - Multi-language project
- [ ] `test_e2e_large_codebase` - Large codebase handling
- [ ] `test_e2e_complex_refactoring` - Complex refactoring scenario

### 3.2 CLI End-to-End Tests

**File**: `tests/test_e2e_cli.py`

**Test Cases**:
- [ ] `test_cli_e2e_init` - CLI init end-to-end
- [ ] `test_cli_e2e_execute_simple` - CLI execute simple task
- [ ] `test_cli_e2e_execute_with_file` - CLI execute with prompt file
- [ ] `test_cli_e2e_execute_with_sandbox` - CLI execute with sandbox
- [ ] `test_cli_e2e_execute_local_test` - CLI execute in local test mode
- [ ] `test_cli_e2e_config_display` - CLI config display

### 3.3 API End-to-End Tests

**File**: `tests/test_e2e_api.py`

**Test Cases**:
- [ ] `test_api_e2e_task_runner` - TaskRunner end-to-end
- [ ] `test_api_e2e_custom_config` - Custom config end-to-end
- [ ] `test_api_e2e_sandbox_override` - Sandbox override end-to-end
- [ ] `test_api_e2e_error_handling` - API error handling

---

## Phase 4: Performance and Stress Tests

### 4.1 Performance Tests

**File**: `tests/test_performance.py`

**Test Cases**:
- [ ] `test_performance_config_loading` - Config loading performance
- [ ] `test_performance_llm_call` - LLM call performance
- [ ] `test_performance_tool_execution` - Tool execution performance
- [ ] `test_performance_workspace_indexing` - Workspace indexing performance
- [ ] `test_performance_memory_compression` - Memory compression performance
- [ ] `test_performance_large_file_handling` - Large file handling
- [ ] `test_performance_concurrent_operations` - Concurrent operations

### 4.2 Stress Tests

**File**: `tests/test_stress.py`

**Test Cases**:
- [ ] `test_stress_large_event_log` - Large event log (1000+ events)
- [ ] `test_stress_large_memory` - Large memory (100+ decisions/attempts)
- [ ] `test_stress_many_state_transitions` - Many state transitions (10+ cycles)
- [ ] `test_stress_budget_tracking` - Budget tracking (50+ operations)
- [ ] `test_stress_many_tool_calls` - Many tool calls (100+ calls)
- [ ] `test_stress_large_workspace` - Large workspace (1000+ files)
- [ ] `test_stress_long_running_task` - Long-running task (1+ hour)

---

## Phase 5: Validation Tests

### 5.1 Configuration Validation

**File**: `tests/test_validation_config.py`

**Test Cases**:
- [ ] `test_validation_real_config` - Real config validation (✅ DONE)
- [ ] `test_validation_config_structure` - Config structure validation
- [ ] `test_validation_config_types` - Config type validation
- [ ] `test_validation_config_required_fields` - Required fields validation
- [ ] `test_validation_config_ranges` - Config value ranges
- [ ] `test_validation_config_env_overrides` - Environment variable overrides

### 5.2 Code Quality Validation

**File**: `tests/test_validation_code_quality.py`

**Test Cases**:
- [ ] `test_validation_agent_loop_size` - AgentLoop < 50 lines (✅ DONE: 39 lines)
- [ ] `test_validation_cli_main_size` - CLI main < 100 lines (✅ DONE: 71 lines)
- [ ] `test_validation_module_sizes` - All modules < 300 lines
- [ ] `test_validation_no_chinese_text` - No Chinese text in code
- [ ] `test_validation_english_logs` - All logs in English
- [ ] `test_validation_type_hints` - Type hints coverage
- [ ] `test_validation_docstrings` - Docstring coverage

### 5.3 Functionality Validation

**File**: `tests/test_validation_functionality.py`

**Test Cases**:
- [ ] `test_validation_single_workflow` - Only one workflow implementation
- [ ] `test_validation_single_execution_method` - Only one execution method
- [ ] `test_validation_varlord_usage` - Varlord usage in lib/api
- [ ] `test_validation_prompt_templates` - Prompt templates (English)
- [ ] `test_validation_rich_logging` - Rich debug logging
- [ ] `test_validation_config_loader` - ConfigLoader usage

---

## Phase 6: Test Infrastructure

### 6.1 Test Fixtures and Utilities

**File**: `tests/conftest.py` (✅ DONE)

**Fixtures**:
- [x] `real_config_dir` - Real config directory
- [x] `real_config_file` - Real config file path
- [x] `temp_workspace` - Temporary workspace
- [x] `temp_titan_dir` - Temporary atloop directory
- [ ] `mock_sandbox` - Mock sandbox adapter
- [ ] `mock_llm_client` - Mock LLM client
- [ ] `sample_task_spec` - Sample TaskSpec
- [ ] `sample_config` - Sample AtloopConfig

### 6.2 Test Data

**Directory**: `tests/fixtures/`

**Files**:
- [ ] `sample_workspace/` - Sample workspace for testing
- [ ] `sample_prompts/` - Sample prompts for testing
- [ ] `sample_configs/` - Sample config files
- [ ] `sample_events/` - Sample event logs

### 6.3 Test Utilities

**File**: `tests/utils.py`

**Utilities**:
- [ ] `create_test_workspace()` - Create test workspace
- [ ] `create_test_config()` - Create test config
- [ ] `create_test_task_spec()` - Create test TaskSpec
- [ ] `assert_config_valid()` - Assert config validity
- [ ] `assert_result_format()` - Assert result format

---

## Phase 7: Test Execution and Reporting

### 7.1 Test Execution Commands

```bash
# Run all tests
uv run pytest tests/ -v --cov=atloop --cov-report=html

# Run unit tests only
uv run pytest tests/test_*_unit.py -v

# Run integration tests only
uv run pytest tests/test_integration_*.py -v

# Run end-to-end tests only
uv run pytest tests/test_e2e_*.py -v

# Run with real config
uv run pytest tests/ -v --real-config

# Run performance tests
uv run pytest tests/test_performance.py -v --benchmark

# Run stress tests
uv run pytest tests/test_stress.py -v -m stress
```

### 7.2 Coverage Requirements

**Target**: >80% code coverage

**Coverage by Module**:
- Config: >90%
- LLM Client: >85%
- Orchestrator: >85%
- Runtime: >80%
- Retrieval: >80%
- Memory: >80%
- Logging: >80%
- CLI: >75%
- API: >75%

### 7.3 Test Reports

**Reports to Generate**:
- [ ] Unit test report
- [ ] Integration test report
- [ ] End-to-end test report
- [ ] Performance test report
- [ ] Coverage report (HTML)
- [ ] Code quality report

---

## Phase 8: Continuous Integration

### 8.1 CI/CD Pipeline Tests

**File**: `.github/workflows/ci.yml` (✅ DONE)

**Test Stages**:
- [x] Linting (ruff)
- [x] Type checking (mypy)
- [x] Unit tests
- [ ] Integration tests
- [ ] Coverage check (>80%)
- [ ] Code quality checks

### 8.2 Pre-commit Hooks

**File**: `.pre-commit-config.yaml` (TODO)

**Hooks**:
- [ ] Ruff linting
- [ ] MyPy type checking
- [ ] Unit tests (fast)
- [ ] Code formatting

---

## Acceptance Criteria

### Code Quality
- [x] `agent_loop.py` < 50 lines (✅ 39 lines)
- [x] `cli/main.py` < 100 lines (✅ 71 lines)
- [ ] Each module < 300 lines
- [x] Only one workflow implementation
- [x] Only one execution method
- [x] All code and logs in English

### Functionality
- [ ] All tests pass
- [ ] Coverage > 80%
- [ ] Complete functionality
- [x] Prompts as templates (English version)
- [x] lib/api uses varlord (via ConfigLoader)
- [x] CLI uses varlord (for CLI argument parsing)
- [x] Rich debug logging

### Testing
- [x] Integration tests created (9 tests passing)
- [ ] Unit tests for all modules
- [ ] Integration tests for all components
- [ ] End-to-end tests for real scenarios
- [ ] Performance tests
- [ ] Stress tests
- [ ] Validation tests

---

## Execution Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Module Completion | 2-3 days | ⚠️ IN PROGRESS |
| Phase 2: Integration Tests | 2-3 days | ✅ PARTIAL |
| Phase 3: End-to-End Tests | 2-3 days | ⏳ PENDING |
| Phase 4: Performance Tests | 1-2 days | ⏳ PENDING |
| Phase 5: Validation Tests | 1-2 days | ⏳ PENDING |
| Phase 6: Test Infrastructure | 1 day | ✅ PARTIAL |
| Phase 7: Test Execution | Ongoing | ⏳ PENDING |
| Phase 8: CI/CD | 1 day | ✅ PARTIAL |

**Total Estimated Time**: 10-15 days

---

## Test Priority

### High Priority (Must Have)
1. Unit tests for all core modules
2. Integration tests for workflow
3. End-to-end tests for basic scenarios
4. Configuration validation tests
5. Code quality validation tests

### Medium Priority (Should Have)
1. Performance tests
2. Stress tests
3. Advanced end-to-end scenarios
4. CLI end-to-end tests
5. API end-to-end tests

### Low Priority (Nice to Have)
1. Benchmark tests
2. Load tests
3. Security tests
4. Compatibility tests

---

## Notes

- All tests use real configuration from `/home/percy/.atloop/config/atloop.yaml` when possible
- Tests are designed to be strict and not accommodate bugs
- Tests validate both structure and values
- Custom directory tests use temporary directories to avoid side effects
- Integration tests require all modules to be copied/implemented first

---

**Document Version**: 1.0  
**Created**: 2025-01-XX  
**Last Updated**: 2025-01-XX
