"""Memory statistics display for verbose mode."""

from typing import Any

try:
    from prettytable import PrettyTable
except ImportError:
    # Fallback if prettytable is not available
    PrettyTable = None


def format_memory_stats(state: Any) -> str:
    """
    Format memory statistics as a compact two-column table using PrettyTable.
    
    Args:
        state: AgentState instance
        
    Returns:
        Formatted string with memory statistics
    """
    if PrettyTable is None:
        # Fallback to simple text format
        return _format_memory_stats_simple(state)
    
    memory = state.memory
    
    # Calculate plan size
    if isinstance(memory.plan, list):
        plan_size = len(memory.plan)
    elif isinstance(memory.plan, str):
        plan_size = len(memory.plan.split("\n")) if memory.plan else 0
    else:
        plan_size = 1 if memory.plan else 0
    
    # Create compact two-column table
    table = PrettyTable()
    table.field_names = ["Left", "Right"]  # Unique field names required by PrettyTable
    table.header = False  # No header row
    table.border = True
    table.hrules = 1  # Only horizontal rules between rows
    table.vrules = 1  # Vertical rule in the middle
    
    # Left column: Files and Memory
    # Right column: Execution and Budget
    
    # Row 1: Files section
    left_col = "📁 Files"
    right_col = "🔧 Execution"
    table.add_row([left_col, right_col])
    
    # Row 2: Created and Modified files
    left_col = f"  Created: {len(memory.created_files)}"
    right_col = f"  Attempts: {len(memory.attempts)}"
    table.add_row([left_col, right_col])
    
    # Row 3: Modified files and Tool Results
    left_col = f"  Modified: {len(memory.modified_files_content)}"
    right_col = f"  Tool Results: {len(memory.tool_results_history)}"
    table.add_row([left_col, right_col])
    
    # Row 4: Memory section
    left_col = "🧠 Memory"
    right_col = "💰 Budget"
    table.add_row([left_col, right_col])
    
    # Row 5: Plan and Decisions
    left_col = f"  Plan: {plan_size} items"
    right_col = f"  LLM: {state.budget_used.llm_calls}"
    table.add_row([left_col, right_col])
    
    # Row 6: Decisions and Tool Calls
    left_col = f"  Decisions: {len(memory.important_decisions)}"
    right_col = f"  Tools: {state.budget_used.tool_calls}"
    table.add_row([left_col, right_col])
    
    # Row 7: Milestones and Time
    left_col = f"  Milestones: {len(memory.milestones)}"
    right_col = f"  Time: {state.budget_used.wall_time_sec}s"
    table.add_row([left_col, right_col])
    
    # Build output
    output_lines = []
    output_lines.append("")
    output_lines.append("=" * 70)
    output_lines.append(f"📊 Memory Stats - Step {state.step} │ Phase: {state.phase}")
    output_lines.append("=" * 70)
    output_lines.append("")
    output_lines.append(table.get_string())
    output_lines.append("")
    
    # Error info (if exists) - shown separately below table
    if state.last_error.summary:
        error_preview = state.last_error.summary[:150].replace("\n", " ")
        output_lines.append(f"⚠️  Last Error: {error_preview}")
        output_lines.append("")
    
    output_lines.append("=" * 70)
    output_lines.append("")
    
    return "\n".join(output_lines)


def _format_memory_stats_simple(state: Any) -> str:
    """Fallback simple format if PrettyTable is not available."""
    memory = state.memory
    
    # Calculate plan size
    if isinstance(memory.plan, list):
        plan_size = len(memory.plan)
    elif isinstance(memory.plan, str):
        plan_size = len(memory.plan.split("\n")) if memory.plan else 0
    else:
        plan_size = 1 if memory.plan else 0
    
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"📊 Memory Stats - Step {state.step} │ Phase: {state.phase}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"📁 Files: Created={len(memory.created_files)}, Modified={len(memory.modified_files_content)}")
    lines.append(f"🔧 Execution: Attempts={len(memory.attempts)}, Tool Results={len(memory.tool_results_history)}")
    lines.append(f"🧠 Memory: Plan={plan_size} items, Decisions={len(memory.important_decisions)}, Milestones={len(memory.milestones)}")
    lines.append(f"💰 Budget: LLM={state.budget_used.llm_calls}, Tools={state.budget_used.tool_calls}, Time={state.budget_used.wall_time_sec}s")
    
    if state.last_error.summary:
        error_preview = state.last_error.summary[:150].replace("\n", " ")
        lines.append(f"⚠️  Last Error: {error_preview}")
    
    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)
