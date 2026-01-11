# Verbose and Breakpoint Features

## Overview

Two new debugging features have been added to the `atloopc execute` command:
- `--verbose`: Shows detailed memory statistics and saves LLM I/O to files
- `--breakpoint`: Pauses after each LLM response, waiting for user input

## Usage

### Verbose Mode

```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --verbose
```

**What it does:**
- Prints a memory statistics panel after each iteration
- Saves LLM input to `runs/<task_id>/debug/step_XXX_input.txt`
- Saves LLM output to `runs/<task_id>/debug/step_XXX_output.txt`

**Memory Statistics Panel:**
The panel shows:
- 📁 **FACTS**: Created files, attempts, key files, notes, tool results, modified files
- 🧠 **LONG-TERM MEMORY**: Plan, task summary, important decisions, milestones, learnings
- 👁️ **PARTIALLY VISIBLE**: Decisions (facts only)
- 🔍 **DEBUG-ONLY**: LLM responses (not fed back to LLM)
- 🛠️ **SKILLS**: Loaded skills and cached resources
- 📈 **PROGRESS TRACKING**: Action history
- 💰 **BUDGET USAGE**: LLM calls, tool calls, wall time

### Breakpoint Mode

```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --breakpoint
```

**What it does:**
- After each LLM response (in PLAN phase), pauses execution
- Displays a breakpoint message with step number
- Waits for user to press Enter before continuing
- Allows you to review the step's debug information before proceeding

### Combined Usage

```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --verbose \
  --breakpoint
```

This combines both features:
- Shows memory statistics after each iteration
- Saves LLM I/O to files
- Pauses after each LLM response for review

## Example Output

### Memory Statistics Panel

```
╔════════════════════════════════════════════════════════════════╗
║                    📊 Memory Statistics Panel                 ║
╠════════════════════════════════════════════════════════════════╣
║ Step:   5 │ Phase: PLAN                                    ║
╠════════════════════════════════════════════════════════════════╣
║ 📁 FACTS (Objective Data)                                      ║
╠════════════════════════════════════════════════════════════════╣
║   📄 Created Files:          2 files                    ║
║   🔧 Attempts:              3 attempts                    ║
║   🔑 Key Files:             1 files                     ║
║   📝 Notes:                  0 notes                       ║
║   📊 Tool Results History:   5 entries              ║
║   📝 Modified Files:         2 files                    ║
╠════════════════════════════════════════════════════════════════╣
║ 🧠 LONG-TERM MEMORY (Validated Information)                   ║
╠════════════════════════════════════════════════════════════════╣
║   📋 Plan:                 list            (  3 items)          ║
║   📝 Task Summary:         250 chars                      ║
║   ⭐ Important Decisions:    1 decisions                ║
║   🏆 Milestones:             1 milestones                 ║
║   💡 Learnings:             2 learnings                  ║
...
```

### Breakpoint Message

```
============================================================
⏸️  BREAKPOINT: Step 5 - LLM response received
============================================================
Press Enter to continue...
```

## Debug Files Location

Debug files are saved in:
```
runs/<task_id>/debug/
├── step_001_input.txt
├── step_001_output.txt
├── step_002_input.txt
├── step_002_output.txt
...
```

Each file contains:
- **input.txt**: Complete user message sent to LLM (includes memory summary, context, etc.)
- **output.txt**: Complete LLM response (JSON with actions, stop_reason, etc.)

## Use Cases

### Debugging Memory Issues
Use `--verbose` to see how memory grows over time and identify if memory is being properly tracked.

### Analyzing LLM Behavior
Use `--breakpoint` to step through each LLM decision and review the input/output files to understand why the LLM made certain choices.

### Performance Analysis
Use `--verbose` to track budget usage and see how many steps are needed to complete tasks.

### Development and Testing
Use both flags together when developing new features or debugging issues to get full visibility into system behavior.

## Notes

- Debug files are saved in the run directory, which persists across sessions if using the same task_id
- Breakpoint mode requires interactive terminal (stdin must be available)
- Memory statistics are printed to stdout, so they appear in console output
- Both features add minimal overhead to execution
