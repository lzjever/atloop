"""Memory statistics display for verbose mode."""

from typing import Any

try:
    from prettytable import PrettyTable
except ImportError:
    # Fallback if prettytable is not available
    PrettyTable = None


def format_memory_stats(state: Any) -> str:
    """
    Format memory statistics as a readable table using PrettyTable.
    
    Args:
        state: AgentState instance
        
    Returns:
        Formatted string with memory statistics
    """
    if PrettyTable is None:
        # Fallback to simple text format
        return _format_memory_stats_simple(state)
    
    memory = state.memory
    
    # Create main table
    output_lines = []
    output_lines.append("")
    output_lines.append("=" * 70)
    output_lines.append(f"📊 Memory Statistics Panel - Step {state.step} │ Phase: {state.phase}")
    output_lines.append("=" * 70)
    output_lines.append("")
    
    # Facts Table
    facts_table = PrettyTable()
    facts_table.field_names = ["📁 FACTS (Objective Data)", "Count"]
    facts_table.align["📁 FACTS (Objective Data)"] = "l"
    facts_table.align["Count"] = "r"
    facts_table.add_row(["📄 Created Files", len(memory.created_files)])
    facts_table.add_row(["🔧 Attempts", len(memory.attempts)])
    facts_table.add_row(["🔑 Key Files", len(memory.key_files)])
    facts_table.add_row(["📝 Notes", len(memory.notes)])
    facts_table.add_row(["📊 Tool Results History", len(memory.tool_results_history)])
    facts_table.add_row(["📝 Modified Files", len(memory.modified_files_content)])
    output_lines.append(facts_table.get_string())
    output_lines.append("")
    
    # Long-term Memory Table
    longterm_table = PrettyTable()
    longterm_table.field_names = ["🧠 LONG-TERM MEMORY (Validated Information)", "Value"]
    longterm_table.align["🧠 LONG-TERM MEMORY (Validated Information)"] = "l"
    longterm_table.align["Value"] = "r"
    
    plan_type = type(memory.plan).__name__
    if isinstance(memory.plan, list):
        plan_size = len(memory.plan)
    elif isinstance(memory.plan, str):
        plan_size = len(memory.plan.split("\n")) if memory.plan else 0
    else:
        plan_size = 1 if memory.plan else 0
    longterm_table.add_row(["📋 Plan", f"{plan_type} ({plan_size} items)"])
    
    task_summary_len = len(memory.task_summary) if memory.task_summary else 0
    longterm_table.add_row(["📝 Task Summary", f"{task_summary_len} chars"])
    longterm_table.add_row(["⭐ Important Decisions", len(memory.important_decisions)])
    longterm_table.add_row(["🏆 Milestones", len(memory.milestones)])
    longterm_table.add_row(["💡 Learnings", len(memory.learnings)])
    output_lines.append(longterm_table.get_string())
    output_lines.append("")
    
    # Partially Visible Table
    partial_table = PrettyTable()
    partial_table.field_names = ["👁️  PARTIALLY VISIBLE (Facts Only)", "Count"]
    partial_table.align["👁️  PARTIALLY VISIBLE (Facts Only)"] = "l"
    partial_table.align["Count"] = "r"
    partial_table.add_row(["📋 Decisions", len(memory.decisions)])
    output_lines.append(partial_table.get_string())
    output_lines.append("")
    
    # Debug-Only Table
    debug_table = PrettyTable()
    debug_table.field_names = ["🔍 DEBUG-ONLY (Not Fed to LLM)", "Count"]
    debug_table.align["🔍 DEBUG-ONLY (Not Fed to LLM)"] = "l"
    debug_table.align["Count"] = "r"
    debug_table.add_row(["💬 LLM Responses", len(memory.llm_responses)])
    output_lines.append(debug_table.get_string())
    output_lines.append("")
    
    # Skills Table
    skill_count = len(memory.skill_cache)
    total_resources = sum(
        len(skill_data.get("resources", {}).get("scripts", {}))
        + len(skill_data.get("resources", {}).get("references", {}))
        + len(skill_data.get("resources", {}).get("assets", {}))
        for skill_data in memory.skill_cache.values()
    )
    skills_table = PrettyTable()
    skills_table.field_names = ["🛠️  SKILLS", "Count"]
    skills_table.align["🛠️  SKILLS"] = "l"
    skills_table.align["Count"] = "r"
    skills_table.add_row(["📚 Loaded Skills", skill_count])
    skills_table.add_row(["📦 Cached Resources", total_resources])
    output_lines.append(skills_table.get_string())
    output_lines.append("")
    
    # Progress Tracking Table
    progress_table = PrettyTable()
    progress_table.field_names = ["📈 PROGRESS TRACKING", "Count"]
    progress_table.align["📈 PROGRESS TRACKING"] = "l"
    progress_table.align["Count"] = "r"
    progress_table.add_row(["📊 Action History", len(memory.action_history)])
    output_lines.append(progress_table.get_string())
    output_lines.append("")
    
    # Budget Table
    budget_table = PrettyTable()
    budget_table.field_names = ["💰 BUDGET USAGE", "Value"]
    budget_table.align["💰 BUDGET USAGE"] = "l"
    budget_table.align["Value"] = "r"
    budget_table.add_row(["🤖 LLM Calls", state.budget_used.llm_calls])
    budget_table.add_row(["🔧 Tool Calls", state.budget_used.tool_calls])
    budget_table.add_row(["⏱️  Wall Time", f"{state.budget_used.wall_time_sec} seconds"])
    output_lines.append(budget_table.get_string())
    output_lines.append("")
    
    # Error Info
    if state.last_error.summary:
        error_table = PrettyTable()
        error_table.field_names = ["⚠️  LAST ERROR"]
        error_table.align["⚠️  LAST ERROR"] = "l"
        error_preview = state.last_error.summary[:200].replace("\n", " ")
        error_table.add_row([error_preview])
        output_lines.append(error_table.get_string())
        output_lines.append("")
    
    output_lines.append("=" * 70)
    output_lines.append("")
    
    return "\n".join(output_lines)


def _format_memory_stats_simple(state: Any) -> str:
    """Fallback simple format if PrettyTable is not available."""
    memory = state.memory
    lines = []
    lines.append(f"\n📊 Memory Statistics - Step {state.step} │ Phase: {state.phase}")
    lines.append("-" * 70)
    lines.append(f"📁 FACTS: Created Files={len(memory.created_files)}, Attempts={len(memory.attempts)}")
    lines.append(f"🧠 LONG-TERM: Plan={type(memory.plan).__name__}, Decisions={len(memory.important_decisions)}")
    lines.append(f"💰 BUDGET: LLM Calls={state.budget_used.llm_calls}, Tool Calls={state.budget_used.tool_calls}")
    lines.append("-" * 70)
    lines.append("")
    return "\n".join(lines)
