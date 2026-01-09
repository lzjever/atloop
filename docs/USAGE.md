# atloop Usage Guide

## Installation

### Prerequisites

- Python 3.10+
- `uv` (recommended) or `pip`
- Sandbox server (for execution)

### Install atloop

```bash
# Using uv (recommended)
uv pip install atloop

# Or with CLI support
uv pip install atloop[cli]

# Using pip
pip install atloop
pip install atloop[cli]  # With CLI support
```

### Development Installation

```bash
git clone <repository>
cd atloop
make dev-install  # Or: uv sync --all-extras
```

## Quick Start

### 1. Initialize Configuration

```bash
atloop init
```

This creates `~/.atloop/config/atloop.yaml` with default settings.

### 2. Configure AI Endpoint

Edit `~/.atloop/config/atloop.yaml`:

```yaml
ai:
  completion:
    model: "your-model"
    api_base: "https://api.example.com/v1"
    api_key: "${API_KEY}"  # Or set environment variable
```

### 3. Start Sandbox Server

```bash
# Start sandbox server (required for execution)
# See sandbox documentation for details
```

### 4. Execute a Task

```bash
atloop execute \
  --workspace /path/to/your/project \
  --prompt "Fix the bug in src/main.py"
```

## CLI Usage

### Command: `init`

Initialize atloop configuration.

```bash
atloop init [--atloop-dir DIR]
```

**Options:**
- `--atloop-dir DIR`: Custom atloop directory (for testing)

**Example:**
```bash
atloop init
atloop init --atloop-dir /tmp/test-atloop
```

### Command: `execute`

Execute a task.

```bash
atloop execute \
  --workspace DIR \
  [--prompt TEXT] \
  [--prompt-file FILE] \
  [--sandbox-url URL] \
  [--local-test] \
  [--session SESSION_ID] \
  [--atloop-dir DIR]
```

**Required Options:**
- `--workspace DIR`: Workspace directory (project root)

**Optional Options:**
- `--prompt TEXT`: Task prompt (text)
- `--prompt-file FILE`: Task prompt (file path)
- `--sandbox-url URL`: Sandbox base URL (default: `http://127.0.0.1:8080`)
- `--local-test`: Use local test mode (no sandbox server)
- `--session SESSION_ID`: Session ID for resuming
- `--atloop-dir DIR`: Custom atloop directory

**Examples:**

```bash
# Simple bug fix
atloop execute \
  --workspace /path/to/project \
  --prompt "Fix the division by zero error in calculator.py"

# Feature implementation with prompt file
atloop execute \
  --workspace /path/to/project \
  --prompt-file requirements.txt

# Custom sandbox URL
atloop execute \
  --workspace /path/to/project \
  --prompt "Add logging to all functions" \
  --sandbox-url http://localhost:9000

# Local test mode (no sandbox)
atloop execute \
  --workspace /path/to/project \
  --prompt "Format code" \
  --local-test
```

### Command: `config`

Show current configuration.

```bash
atloop config [--atloop-dir DIR]
```

**Options:**
- `--atloop-dir DIR`: Custom atloop directory

**Example:**
```bash
atloop config
atloop config --atloop-dir /tmp/test-atloop
```

## API Usage

### Basic Usage

```python
from atloop.api import TaskRunner

# Initialize runner
runner = TaskRunner()

# Execute task
result = runner.execute({
    "goal": "Fix the bug in calculator.py",
    "workspace_root": "/path/to/project",
    "task_type": "bugfix",
})

# Check result
if result["success"]:
    print(f"Task completed: {result['status']}")
else:
    print(f"Task failed: {result.get('error')}")
```

### Advanced Usage

```python
from atloop.api import TaskRunner

# Initialize with custom config directory
runner = TaskRunner(atloop_dir="/path/to/.atloop")

# Execute with full configuration
result = runner.execute(
    task_config={
        "goal": "Add error handling to all functions",
        "workspace_root": "/path/to/project",
        "task_type": "refactor",
        "constraints": [
            "Maintain backward compatibility",
            "Add unit tests",
        ],
        "budget": {
            "max_llm_calls": 100,
            "max_tool_calls": 200,
            "max_wall_time_sec": 7200,
        },
        "sandbox": {
            "base_url": "http://localhost:8080",
            "local_test": False,
        },
    },
    console=True,  # Show console output
)

# Access result
print(f"Success: {result['success']}")
print(f"Task ID: {result['task_id']}")
print(f"Status: {result['status']}")
print(f"Report: {result['report']}")
```

### Task Configuration

#### Task Types

- `"bugfix"`: Fix bugs in code
- `"feature"`: Implement new features
- `"refactor"`: Refactor existing code

#### Budget Configuration

```python
budget = {
    "max_llm_calls": 80,      # Maximum LLM API calls
    "max_tool_calls": 200,    # Maximum tool executions
    "max_wall_time_sec": 3600,  # Maximum execution time (seconds)
}
```

#### Sandbox Configuration

```python
sandbox = {
    "base_url": "http://127.0.0.1:8080",  # Sandbox server URL
    "local_test": False,  # Use local test mode (no sandbox)
}
```

## Configuration

### Configuration File

Location: `~/.atloop/config/atloop.yaml`

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

### Environment Variables

Override configuration using environment variables:

```bash
export ATLOOP__AI__COMPLETION__MODEL="gpt-4-turbo"
export ATLOOP__AI__COMPLETION__API_BASE="https://api.openai.com/v1"
export ATLOOP__DEFAULT_BUDGET__MAX_LLM_CALLS=100
```

### Configuration Priority

1. Environment variables (`ATLOOP__*`)
2. `.env` file (in current directory)
3. Project config (`./.atloop/config/atloop.yaml`)
4. User config (`~/.atloop/config/atloop.yaml`)

## Examples

### Example 1: Bug Fix

**CLI:**
```bash
atloop execute \
  --workspace /path/to/project \
  --prompt "Fix the division by zero error in calculator.py"
```

**API:**
```python
from atloop.api import TaskRunner

runner = TaskRunner()
result = runner.execute({
    "goal": "Fix the division by zero error in calculator.py",
    "workspace_root": "/path/to/project",
    "task_type": "bugfix",
})
```

### Example 2: Feature Implementation

**CLI:**
```bash
atloop execute \
  --workspace /path/to/project \
  --prompt "Add a square root function to calculator.py"
```

**API:**
```python
from atloop.api import TaskRunner

runner = TaskRunner()
result = runner.execute({
    "goal": "Add a square root function to calculator.py",
    "workspace_root": "/path/to/project",
    "task_type": "feature",
})
```

### Example 3: Refactoring

**CLI:**
```bash
atloop execute \
  --workspace /path/to/project \
  --prompt "Refactor calculator.py to use a class-based design"
```

**API:**
```python
from atloop.api import TaskRunner

runner = TaskRunner()
result = runner.execute({
    "goal": "Refactor calculator.py to use a class-based design",
    "workspace_root": "/path/to/project",
    "task_type": "refactor",
    "constraints": [
        "Maintain backward compatibility",
        "Add unit tests",
    ],
})
```

### Example 4: Multi-file Edit

**CLI:**
```bash
atloop execute \
  --workspace /path/to/project \
  --prompt "Add error handling to all Python files in src/"
```

**API:**
```python
from atloop.api import TaskRunner

runner = TaskRunner()
result = runner.execute({
    "goal": "Add error handling to all Python files in src/",
    "workspace_root": "/path/to/project",
    "task_type": "refactor",
})
```

## Troubleshooting

### Common Issues

#### 1. Configuration Not Found

**Error:** `KeyError: 'atloop'` or configuration not loading

**Solution:**
- Run `atloop init` to create default configuration
- Check that `~/.atloop/config/atloop.yaml` exists
- Verify file permissions

#### 2. Sandbox Connection Error

**Error:** `ConnectionError` or sandbox not responding

**Solution:**
- Verify sandbox server is running
- Check `sandbox.base_url` in configuration
- Use `--local-test` for testing without sandbox

#### 3. Budget Exhausted

**Error:** Task stops with "budget exhausted"

**Solution:**
- Increase budget in configuration
- Use `budget` parameter in API call
- Check task complexity (may need to break into smaller tasks)

#### 4. Import Errors

**Error:** `ModuleNotFoundError` or import errors

**Solution:**
- Ensure atloop is installed: `pip install atloop`
- Check Python version (3.10+)
- Verify virtual environment is activated

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:

```bash
export ATLOOP_LOG_LEVEL=DEBUG
```

## Best Practices

### 1. Task Definition
- Be specific about the goal
- Include constraints when necessary
- Provide context in the prompt

### 2. Budget Management
- Set appropriate budgets for task complexity
- Monitor budget usage
- Adjust based on task type

### 3. Workspace Organization
- Keep workspace clean
- Use version control
- Test changes before committing

### 4. Error Handling
- Check result status
- Handle errors gracefully
- Use state recovery for long tasks

## Advanced Topics

### Custom Configuration

Use project-specific configuration:

```bash
# Create ./.atloop/config/atloop.yaml
# This overrides user config
```

### State Recovery

Resume interrupted tasks:

```bash
atloop execute \
  --workspace /path/to/project \
  --prompt "Continue previous task" \
  --session PREVIOUS_SESSION_ID
```

### Custom Tools

Extend atloop with custom tools (see tool development documentation).

### Custom Skills

Add custom skills for domain-specific guidance (see skills documentation).

## Support

For issues and questions:
- Check documentation
- Review error messages
- Enable debug logging
- Check configuration
