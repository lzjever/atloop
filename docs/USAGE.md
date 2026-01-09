# TITAN Usage Guide

## Installation

### Prerequisites

- Python 3.10+
- `uv` (recommended) or `pip`
- Sandbox server (for execution)

### Install TITAN

```bash
# Using uv (recommended)
uv pip install titan

# Or with CLI support
uv pip install titan[cli]

# Using pip
pip install titan
pip install titan[cli]  # With CLI support
```

### Development Installation

```bash
git clone <repository>
cd titanx
make dev-install  # Or: uv sync --all-extras
```

## Quick Start

### 1. Initialize Configuration

```bash
titan init
```

This creates `~/.titan/config/titan.yaml` with default settings.

### 2. Configure AI Endpoint

Edit `~/.titan/config/titan.yaml`:

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
titan execute \
  --workspace /path/to/your/project \
  --prompt "Fix the bug in src/main.py"
```

## CLI Usage

### Command: `init`

Initialize TITAN configuration.

```bash
titan init [--titan-dir DIR]
```

**Options:**
- `--titan-dir DIR`: Custom Titan directory (for testing)

**Example:**
```bash
titan init
titan init --titan-dir /tmp/test-titan
```

### Command: `execute`

Execute a task.

```bash
titan execute \
  --workspace DIR \
  [--prompt TEXT] \
  [--prompt-file FILE] \
  [--sandbox-url URL] \
  [--local-test] \
  [--session SESSION_ID] \
  [--titan-dir DIR]
```

**Required Options:**
- `--workspace DIR`: Workspace directory (project root)

**Optional Options:**
- `--prompt TEXT`: Task prompt (text)
- `--prompt-file FILE`: Task prompt (file path)
- `--sandbox-url URL`: Sandbox base URL (default: `http://127.0.0.1:8080`)
- `--local-test`: Use local test mode (no sandbox server)
- `--session SESSION_ID`: Session ID for resuming
- `--titan-dir DIR`: Custom Titan directory

**Examples:**

```bash
# Simple bug fix
titan execute \
  --workspace /path/to/project \
  --prompt "Fix the division by zero error in calculator.py"

# Feature implementation with prompt file
titan execute \
  --workspace /path/to/project \
  --prompt-file requirements.txt

# Custom sandbox URL
titan execute \
  --workspace /path/to/project \
  --prompt "Add logging to all functions" \
  --sandbox-url http://localhost:9000

# Local test mode (no sandbox)
titan execute \
  --workspace /path/to/project \
  --prompt "Format code" \
  --local-test
```

### Command: `config`

Show current configuration.

```bash
titan config [--titan-dir DIR]
```

**Options:**
- `--titan-dir DIR`: Custom Titan directory

**Example:**
```bash
titan config
titan config --titan-dir /tmp/test-titan
```

## API Usage

### Basic Usage

```python
from titan.api import TaskRunner

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
from titan.api import TaskRunner

# Initialize with custom config directory
runner = TaskRunner(titan_dir="/path/to/.titan")

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

Location: `~/.titan/config/titan.yaml`

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
export TITAN__AI__COMPLETION__MODEL="gpt-4-turbo"
export TITAN__AI__COMPLETION__API_BASE="https://api.openai.com/v1"
export TITAN__DEFAULT_BUDGET__MAX_LLM_CALLS=100
```

### Configuration Priority

1. Environment variables (`TITAN__*`)
2. `.env` file (in current directory)
3. Project config (`./.titan/config/titan.yaml`)
4. User config (`~/.titan/config/titan.yaml`)

## Examples

### Example 1: Bug Fix

**CLI:**
```bash
titan execute \
  --workspace /path/to/project \
  --prompt "Fix the division by zero error in calculator.py"
```

**API:**
```python
from titan.api import TaskRunner

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
titan execute \
  --workspace /path/to/project \
  --prompt "Add a square root function to calculator.py"
```

**API:**
```python
from titan.api import TaskRunner

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
titan execute \
  --workspace /path/to/project \
  --prompt "Refactor calculator.py to use a class-based design"
```

**API:**
```python
from titan.api import TaskRunner

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
titan execute \
  --workspace /path/to/project \
  --prompt "Add error handling to all Python files in src/"
```

**API:**
```python
from titan.api import TaskRunner

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

**Error:** `KeyError: 'titan'` or configuration not loading

**Solution:**
- Run `titan init` to create default configuration
- Check that `~/.titan/config/titan.yaml` exists
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
- Ensure TITAN is installed: `pip install titan`
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
export TITAN_LOG_LEVEL=DEBUG
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
# Create ./.titan/config/titan.yaml
# This overrides user config
```

### State Recovery

Resume interrupted tasks:

```bash
titan execute \
  --workspace /path/to/project \
  --prompt "Continue previous task" \
  --session PREVIOUS_SESSION_ID
```

### Custom Tools

Extend TITAN with custom tools (see tool development documentation).

### Custom Skills

Add custom skills for domain-specific guidance (see skills documentation).

## Support

For issues and questions:
- Check documentation
- Review error messages
- Enable debug logging
- Check configuration
