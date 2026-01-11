# Verbose and Breakpoint Improvements

## Changes Made

### 1. Replaced Box-Drawing Characters with PrettyTable

**File**: `atloop/orchestrator/memory_stats.py`

- Replaced manual box-drawing character formatting with `PrettyTable`
- Creates multiple tables for different memory categories:
  - 📁 FACTS (Objective Data)
  - 🧠 LONG-TERM MEMORY (Validated Information)
  - 👁️ PARTIALLY VISIBLE (Facts Only)
  - 🔍 DEBUG-ONLY (Not Fed to LLM)
  - 🛠️ SKILLS
  - 📈 PROGRESS TRACKING
  - 💰 BUDGET USAGE
  - ⚠️ LAST ERROR (if present)

**Benefits**:
- Cleaner, more readable table format
- Automatic alignment
- Better cross-platform compatibility
- Easier to maintain

### 2. Breakpoint Shows Job ID

**File**: `atloop/orchestrator/workflow/workflow.py`

- Breakpoint now displays:
  - Step number
  - Job ID (task_id, which is the directory name in `runs/`)
  - Debug files location: `runs/<job_id>/debug/`

**Example Output**:
```
======================================================================
⏸️  BREAKPOINT: Step 5 - LLM response received
======================================================================
📁 Job ID: 446dcb46-0e2d-420e-bec2-c7bf77953e71
📂 Debug files: runs/446dcb46-0e2d-420e-bec2-c7bf77953e71/debug/
======================================================================
Press Enter to continue...
```

### 3. Execution Order: Verbose First, Then Breakpoint

**File**: `atloop/orchestrator/workflow/workflow.py`

- Execution order:
  1. Phase executes (e.g., PLAN phase gets LLM response)
  2. **Verbose output is printed** (memory statistics)
  3. **Breakpoint pauses** (if enabled and in PLAN phase)
  4. User can review stats and debug files
  5. User presses Enter to continue
  6. Transition to next phase

This ensures users see the memory statistics **before** the breakpoint pause, allowing them to review the current state before continuing.

### 4. Added PrettyTable Dependency

**File**: `pyproject.toml`

- Added `prettytable>=3.0.0` to core dependencies

## Usage

### Verbose Mode with PrettyTable

```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --verbose
```

**Output**: Clean tables showing memory statistics after each iteration.

### Breakpoint Mode with Job ID

```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --breakpoint
```

**Behavior**:
1. After each PLAN phase (LLM response received)
2. Prints memory statistics (if verbose is also enabled)
3. Displays breakpoint message with Job ID
4. Shows debug files location
5. Waits for user to press Enter

### Combined Usage

```bash
uv run atloopc execute \
  --workspace ./workspace \
  --prompt-file ./prompt.txt \
  --local-test \
  --verbose \
  --breakpoint
```

**Execution Flow**:
1. PLAN phase executes, LLM responds
2. LLM I/O saved to `runs/<job_id>/debug/step_XXX_input.txt` and `step_XXX_output.txt`
3. Memory statistics printed (PrettyTable format)
4. Breakpoint pauses, shows Job ID and debug file location
5. User reviews stats and debug files
6. User presses Enter to continue

## Example Output

### Memory Statistics (PrettyTable)

```
======================================================================
📊 Memory Statistics Panel - Step 5 │ Phase: PLAN
======================================================================

+---------------------------+-------+
| 📁 FACTS (Objective Data) | Count |
+---------------------------+-------+
| 📄 Created Files          |     2 |
| 🔧 Attempts               |     3 |
| 🔑 Key Files              |     1 |
| 📝 Notes                  |     0 |
| 📊 Tool Results History   |     5 |
| 📝 Modified Files         |     2 |
+---------------------------+-------+

+---------------------------------------------+----------------+
| 🧠 LONG-TERM MEMORY (Validated Information) |          Value |
+---------------------------------------------+----------------+
| 📋 Plan                                     | list (3 items) |
| 📝 Task Summary                             |      250 chars |
| ⭐ Important Decisions                      |              1 |
| 🏆 Milestones                               |              1 |
| 💡 Learnings                                |              2 |
+---------------------------------------------+----------------+
...
```

### Breakpoint Message

```
======================================================================
⏸️  BREAKPOINT: Step 5 - LLM response received
======================================================================
📁 Job ID: 446dcb46-0e2d-420e-bec2-c7bf77953e71
📂 Debug files: runs/446dcb46-0e2d-420e-bec2-c7bf77953e71/debug/
======================================================================
Press Enter to continue...
```

## Technical Details

### Breakpoint Triggering

- Breakpoint only triggers after **PLAN phase** execution
- This is when LLM response is received
- Breakpoint happens **after** verbose output is printed
- Allows user to review memory stats and debug files before continuing

### Job ID Source

- Job ID is the `task_id` from `TaskSpec`
- This is the same as the directory name in `runs/`
- Format: UUID (e.g., `446dcb46-0e2d-420e-bec2-c7bf77953e71`)
- Used to locate debug files: `runs/<job_id>/debug/`

### Fallback Behavior

- If `prettytable` is not available, falls back to simple text format
- If stdin is not available (non-interactive), breakpoint skips gracefully
- All features are backward compatible
