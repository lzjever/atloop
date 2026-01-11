# Verbose and Breakpoint Features Implementation

## Summary

Successfully implemented `--verbose` and `--breakpoint` features for the `atloopc execute` command.

## Changes Made

### 1. CLI Arguments (`atloop/cli/main.py`)
- Added `--verbose` flag: Shows detailed memory statistics and saves LLM I/O
- Added `--breakpoint` flag: Pauses after each LLM response

### 2. Command Handler (`atloop/cli/commands/execute.py`)
- Passes `verbose` and `breakpoint` flags to TaskRunner via task_config

### 3. Task Runner (`atloop/api/runner.py`)
- Extracts `verbose` and `breakpoint` from task_config
- Passes them to AgentLoop

### 4. Agent Loop (`atloop/orchestrator/agent_loop.py`)
- Added `verbose` and `breakpoint` parameters to `__init__`
- Passes them to WorkflowCoordinator

### 5. Workflow Coordinator (`atloop/orchestrator/coordinator.py`)
- Added `verbose` and `breakpoint` parameters to `__init__`
- Stores them as instance attributes

### 6. Workflow (`atloop/orchestrator/workflow/workflow.py`)
- Added `_print_memory_stats()` method
- Calls it after each iteration if `verbose` is enabled

### 7. Plan Phase (`atloop/orchestrator/phases/plan.py`)
- Added `_save_llm_io()` method to save LLM input/output to files
- Added `_wait_for_breakpoint()` method to pause execution
- Saves LLM input before calling LLM
- Saves LLM output after receiving response
- Waits for user input if `breakpoint` is enabled

### 8. Memory Statistics (`atloop/orchestrator/memory_stats.py`)
- New module with `format_memory_stats()` function
- Creates formatted panel showing:
  - Step and Phase
  - Facts (created files, attempts, key files, notes, tool results, modified files)
  - Long-term memory (plan, task summary, important decisions, milestones, learnings)
  - Partially visible (decisions)
  - Debug-only (LLM responses)
  - Skills (loaded skills, cached resources)
  - Progress tracking (action history)
  - Budget usage (LLM calls, tool calls, wall time)
  - Last error (if any)

## File Structure

### Debug Files Location
```
runs/<task_id>/debug/
├── step_001_input.txt    # LLM input for step 1
├── step_001_output.txt   # LLM output for step 1
├── step_002_input.txt    # LLM input for step 2
├── step_002_output.txt   # LLM output for step 2
...
```

## Usage Examples

### Verbose Mode Only
```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --verbose
```

### Breakpoint Mode Only
```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --breakpoint
```

### Both Modes
```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --verbose \
  --breakpoint
```

## Testing

✅ **Verified:**
- Memory statistics panel displays correctly
- LLM input files are saved to `runs/<task_id>/debug/step_XXX_input.txt`
- LLM output files are saved to `runs/<task_id>/debug/step_XXX_output.txt`
- Panel shows accurate counts for all memory categories
- Files contain complete LLM input/output content

## Notes

- Breakpoint mode requires interactive terminal (stdin must be available)
- In non-interactive environments (e.g., CI), breakpoint will skip gracefully
- Debug files are saved in UTF-8 encoding
- Memory statistics panel uses box-drawing characters for visual clarity
- All features are backward compatible (default behavior unchanged)
