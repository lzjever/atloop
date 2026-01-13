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

    # Create compact single-row table with four columns
    table = PrettyTable()
    table.field_names = ["📁 Files", "🔧 Execution", "🧠 Memory", "💰 Budget"]
    table.header = True
    table.border = True
    table.hrules = 0  # No horizontal rules between rows
    table.vrules = 1  # Vertical rules between columns

    # Single row with all information
    files_info = (
        f"Created: {len(memory.created_files)}\nModified: {len(memory.modified_files_content)}"
    )
    execution_info = (
        f"Attempts: {len(memory.attempts)}\nTool Results: {len(memory.tool_results_history)}"
    )
    memory_info = f"Plan: {plan_size} items\nDecisions: {len(memory.important_decisions)}\nMilestones: {len(memory.milestones)}"
    budget_info = f"LLM: {state.budget_used.llm_calls}\nTools: {state.budget_used.tool_calls}\nTime: {state.budget_used.wall_time_sec}s"

    table.add_row([files_info, execution_info, memory_info, budget_info])

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
    lines.append(
        f"📁 Files: Created={len(memory.created_files)}, Modified={len(memory.modified_files_content)}"
    )
    lines.append(
        f"🔧 Execution: Attempts={len(memory.attempts)}, Tool Results={len(memory.tool_results_history)}"
    )
    lines.append(
        f"🧠 Memory: Plan={plan_size} items, Decisions={len(memory.important_decisions)}, Milestones={len(memory.milestones)}"
    )
    lines.append(
        f"💰 Budget: LLM={state.budget_used.llm_calls}, Tools={state.budget_used.tool_calls}, Time={state.budget_used.wall_time_sec}s"
    )

    if state.last_error.summary:
        error_preview = state.last_error.summary[:150].replace("\n", " ")
        lines.append(f"⚠️  Last Error: {error_preview}")

    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)
