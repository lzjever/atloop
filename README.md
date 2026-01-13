# atloop 🤖

[![PyPI version](https://img.shields.io/pypi/v/atloop.svg)](https://pypi.org/project/atloop/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Documentation](https://readthedocs.org/projects/atloop/badge/?version=latest)](https://atloop.readthedocs.io)
[![CI](https://github.com/lzjever/atloop/workflows/CI/badge.svg)](https://github.com/lzjever/atloop/actions)

> **Tool-Integrated Task Automation Node** - Autonomous AI agent for code tasks in sandbox environments.

**atloop** is an AI-powered task automation system that autonomously executes coding tasks in isolated sandbox environments. It understands task requirements, analyzes code, generates solutions, executes changes, and verifies results—all while maintaining complete auditability through structured logging and reporting.

## 🎯 The Problem We Solve

### Real-World Development Challenges

Every developer faces these time-consuming scenarios:

#### ❌ **Repetitive Bug Fixes**
> "The same type of bug appears in multiple files. I have to manually fix each one, test, and verify."

#### ❌ **Test-Driven Development Overhead**
> "I need to write tests first, then implement, then fix tests, then refactor... This takes hours."

#### ❌ **Code Review Backlog**
> "Simple fixes pile up in PR reviews. I wish I could automate the straightforward ones."

#### ❌ **Legacy Code Maintenance**
> "This old codebase needs refactoring, but I'm afraid to touch it without breaking things."

#### ❌ **Multi-File Changes**
> "This feature requires changes across 10 files. I have to keep track of all dependencies manually."

### ✓ **atloop's Solution**

**Autonomous execution. Sandbox isolation. Complete auditability. Structured workflow.**

```python
from atloop.api import TaskRunner
from atloop.config.models import TaskSpec, Budget

# Create task specification
task = TaskSpec(
    task_id="fix-test-failure",
    goal="Fix the failing test_add function in test_math.py",
    workspace_root="/path/to/project",
    budget=Budget(max_llm_calls=20, max_tool_calls=100, max_wall_time_sec=600),
)

# Execute - atloop handles everything
runner = TaskRunner()
result = runner.execute(task)

# Review results
if result["status"] == "success":
    print(f"✓ Task completed in {result['step']} steps")
    print(f"📝 Diff:\n{result['diff']}")
    print(f"📊 Budget used: {result['budget_used']}")
else:
    print(f"❌ Task failed: {result['reason']}")
```

**What just happened?**

1. **✓ Autonomous Execution**: atloop analyzed the codebase, identified the issue, and fixed it
2. **✓ Sandbox Isolation**: All changes executed in isolated environment—your workspace stays safe
3. **✓ Automatic Verification**: Tests run automatically after changes
4. **✓ Complete Audit Trail**: Every action logged with full context
5. **✓ Structured Output**: Clean diff, test results, and execution report

**Try it:**

```bash
# CLI usage
atloopc execute \
  --goal "Fix the failing test_add function" \
  --workspace /path/to/project \
  --task-type bugfix

# Or use Python API
python -c "
from atloop.api import TaskRunner
from atloop.config.models import TaskSpec, Budget

task = TaskSpec(
    task_id='quick-fix',
    goal='Fix the syntax error in main.py',
    workspace_root='./my-project',
    budget=Budget(max_llm_calls=10, max_tool_calls=50),
)

runner = TaskRunner()
result = runner.execute(task)
print(f'Status: {result[\"status\"]}')
"
```

---

## 🌟 Why atloop?

### 🎯 **Core Value Propositions**

| Problem | atloop Solution | Impact |
|---------|----------------|--------|
| **Manual repetitive fixes** | Autonomous execution in sandbox | Save hours on routine tasks |
| **Fear of breaking code** | Isolated sandbox execution | Safe experimentation |
| **No audit trail** | Complete event logging | Full transparency |
| **Complex multi-step tasks** | Structured workflow (DISCOVER→PLAN→ACT→VERIFY) | Reliable execution |
| **Budget overruns** | Built-in budget management | Cost control |
| **Context loss** | Intelligent memory management | Maintains awareness across steps |

### 💡 **Key Differentiators**

1. **🎯 Structured Workflow**: DISCOVER → PLAN → ACT → VERIFY cycle ensures reliable execution
2. **🔒 Sandbox Isolation**: All changes execute in isolated environments—your workspace is never touched until you review
3. **📊 Complete Observability**: Every action logged with full context for audit and debugging
4. **🧠 Intelligent Memory**: Automatic compression and summarization for long-running tasks
5. **🛠️ Rich Tool Ecosystem**: Auto-discovered tools for filesystem, search, execution, and more
6. **⚡ Production Ready**: Battle-tested architecture with budget management and error recovery

---

## 🚀 Quick Start

### Installation

```bash
# Using pip
pip install atloop

# Using uv (recommended for development)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install atloop
```

### Development Setup

```bash
# Clone repository
git clone https://github.com/lzjever/atloop.git
cd atloop

# Install with uv (recommended)
make dev-install

# Or using pip
pip install -e ".[dev]"
```

### Configuration

Create `~/.atloop/config/atloop.yaml`:

```yaml
ai:
  completion:
    model: "deepseek-chat"
    api_base: "https://api.deepseek.com"
    api_key: "${DEEPSEEK_API_KEY}"
  embedding:
    model: "text-embedding-ada-002"
    api_base: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"

sandbox:
  base_url: "http://127.0.0.1:8080"
  local_test: false

memory:
  summary_max_length: 64000
  llm_compression_enabled: true
```

### Basic Usage (30 seconds)

**CLI:**

```bash
# Fix a failing test
atloopc execute \
  --goal "Fix the failing test_add function" \
  --workspace /path/to/project \
  --task-type bugfix

# Implement a new feature
atloopc execute \
  --goal "Add user authentication with JWT tokens" \
  --workspace /path/to/project \
  --task-type feature
```

**Python API:**

```python
from atloop.api import TaskRunner
from atloop.config.models import TaskSpec, Budget

# Create task
task = TaskSpec(
    task_id="my-task",
    goal="Fix the bug in calculate_total() function",
    workspace_root="/path/to/project",
    budget=Budget(max_llm_calls=20, max_tool_calls=100),
)

# Execute
runner = TaskRunner()
result = runner.execute(task)

# Check results
print(f"Status: {result['status']}")
if result["status"] == "success":
    print(f"Steps: {result['step']}")
    print(f"Diff:\n{result.get('diff', '')}")
```

---

## 💼 Real-World Use Cases

### Use Case 1: Automated Bug Fixes

**Problem**: Multiple test failures across the codebase need fixing.

**Solution**:
```python
task = TaskSpec(
    task_id="fix-tests",
    goal="Fix all failing tests in the test suite",
    workspace_root="./project",
    task_type="bugfix",
    constraints=["All tests must pass", "No breaking changes"],
    budget=Budget(max_llm_calls=50, max_tool_calls=200),
)

runner = TaskRunner()
result = runner.execute(task)
# atloop automatically: analyzes failures, fixes code, runs tests, verifies
```

**Benefits**:
- ✓ Handles multiple files automatically
- ✓ Runs tests after each change
- ✓ Stops when all tests pass
- ✓ Provides complete diff for review

### Use Case 2: Feature Implementation

**Problem**: Need to implement a new feature with tests and documentation.

**Solution**:
```python
task = TaskSpec(
    task_id="add-auth",
    goal="Implement user authentication with JWT tokens, including tests and API docs",
    workspace_root="./api-server",
    task_type="feature",
    definition_of_done=[
        "All unit tests pass",
        "Integration tests added",
        "API documentation updated",
    ],
)

runner = TaskRunner()
result = runner.execute(task)
```

**Benefits**:
- ✓ Creates multiple files in correct structure
- ✓ Implements tests alongside code
- ✓ Updates documentation automatically
- ✓ Verifies completion criteria

### Use Case 3: Code Refactoring

**Problem**: Legacy code needs refactoring while maintaining behavior.

**Solution**:
```python
task = TaskSpec(
    task_id="refactor-legacy",
    goal="Refactor the legacy payment module to use dependency injection",
    workspace_root="./payment-service",
    task_type="refactor",
    constraints=[
        "All existing tests must still pass",
        "No changes to public API",
        "Improve code readability",
    ],
)

runner = TaskRunner()
result = runner.execute(task)
```

**Benefits**:
- ✓ Maintains test coverage
- ✓ Preserves functionality
- ✓ Improves code structure
- ✓ Complete audit trail

---

## 🎨 Key Features

### 1. **Structured Workflow**

atloop uses a unified 4-phase workflow:

```
DISCOVER → PLAN → ACT → VERIFY
   ↓        ↓      ↓      ↓
Analyze  Generate Execute Verify
Context  Actions  Tools  Results
```

- **DISCOVER**: Analyzes workspace, retrieves relevant context
- **PLAN**: LLM generates execution plan and actions
- **ACT**: Executes tools (run commands, edit files, etc.)
- **VERIFY**: Runs tests, validates results

### 2. **Rich Tool Ecosystem**

Auto-discovered tools for comprehensive task execution:

- **Filesystem**: `read_file`, `write_file`, `edit_file`, `append_file`, `glob`
- **System**: `run` (execute shell commands)
- **Search**: `search` (regex search with context)
- **Interaction**: `todo_write`, `todo_read`, `skill` (load knowledge)

### 3. **Intelligent Memory Management**

- **Automatic Compression**: Compresses old history when context grows
- **Smart Summarization**: LLM-powered summarization for long tasks
- **Selective Retention**: Keeps important decisions and milestones

### 4. **Budget Management**

```python
budget = Budget(
    max_llm_calls=50,      # Limit LLM API calls
    max_tool_calls=200,    # Limit tool executions
    max_wall_time_sec=600, # Limit execution time
)
```

### 5. **Complete Observability**

- **Event Logging**: Every action logged with full context
- **Event Replay**: Replay execution history step-by-step
- **Report Generation**: Markdown reports with diff, test results, budget usage

### 6. **Sandbox Isolation**

- **Safe Execution**: All changes in isolated sandbox
- **File Synchronization**: Automatic sync between sandbox and workspace
- **Local Testing Mode**: Test without remote sandbox backend

---

## 📚 Documentation

- **📖 Full Documentation**: [https://atloop.readthedocs.io](https://atloop.readthedocs.io)
- **🚀 Quick Start Guide**: [docs/USAGE.md](docs/USAGE.md)
- **🏗️ Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **✨ Features**: [docs/FEATURES.md](docs/FEATURES.md)
- **🎯 API Reference**: [docs/](docs/)

---

## 🧠 Memory Aids (Quick Reference)

### The atloop Workflow

> **"DISCOVER context → PLAN actions → ACT on tools → VERIFY results → Repeat until done."**

### Task Types

- **`bugfix`**: Fix bugs, ensure tests pass
- **`feature`**: Implement new features with tests
- **`refactor`**: Improve code structure, maintain behavior

### Budget Guidelines

```python
# Small fixes
Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=300)

# Medium tasks
Budget(max_llm_calls=30, max_tool_calls=150, max_wall_time_sec=900)

# Large features
Budget(max_llm_calls=80, max_tool_calls=300, max_wall_time_sec=1800)
```

---

## 🏢 Production Proven

**atloop** is part of the **Agentsmith** ecosystem, battle-tested in production environments:

- ✓ Used for automated code fixes in production codebases
- ✓ Handles complex multi-file refactoring tasks
- ✓ Manages long-running tasks with intelligent memory compression
- ✓ Provides complete audit trails for compliance

### 🌟 Agentsmith Open-Source Projects

- **[Varlord](https://github.com/lzjever/varlord)** ⚙️ - Configuration management library
- **[Routilux](https://github.com/lzjever/routilux)** ⚡ - Event-driven workflow orchestration
- **[Serilux](https://github.com/lzjever/serilux)** 📦 - Flexible serialization framework
- **[Lexilux](https://github.com/lzjever/lexilux)** 🚀 - Unified LLM API client
- **[NoxRunner](https://github.com/lzjever/noxrunner)** 🏃 - Sandbox execution backend client
- **[atloop](https://github.com/lzjever/atloop)** 🤖 - Autonomous task automation agent (this project)

These projects work together to provide a complete AI agent development platform.

---

## 🧪 Testing

```bash
# Run all unit tests
make test

# Run with coverage
make test-cov

# Run linting
make lint

# Format code
make format
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

---

## 🎯 TL;DR

**atloop automates coding tasks autonomously:**

1. ✓ **Define your task** - goal, workspace, constraints
2. ✓ **Set budget** - control LLM calls, tool calls, time
3. ✓ **Execute** - atloop handles discovery, planning, execution, verification
4. ✓ **Review results** - diff, test results, execution report

**No manual file editing. No test running. No diff generation. atloop does it all.**

```python
# Before: Hours of manual work
# After: One function call
task = TaskSpec(goal="Fix failing tests", workspace_root="./project")
result = TaskRunner().execute(task)
```

**That's the atloop promise. 🤖**

---

## 🔗 Links

- **📦 PyPI**: [pypi.org/project/atloop](https://pypi.org/project/atloop)
- **📚 Documentation**: [atloop.readthedocs.io](https://atloop.readthedocs.io)
- **🐙 GitHub**: [github.com/lzjever/atloop](https://github.com/lzjever/atloop)
- **≡ Issues**: [github.com/lzjever/atloop/issues](https://github.com/lzjever/atloop/issues)

---

**Built with ❤️ by the atloop Team**
