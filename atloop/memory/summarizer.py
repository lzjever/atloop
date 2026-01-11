"""Memory summarizer for condensing memory into prompts."""

from typing import Optional

from atloop.config.limits import (
    MEMORY_SUMMARY_DEFAULT_LIMIT,
    MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER,
    MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL,
    MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT,
    MEMORY_SUMMARY_STDERR_TAIL,
    MEMORY_SUMMARY_STDOUT_STDERR_OTHER,
    MEMORY_SUMMARY_STDOUT_STDERR_SHELL,
)
from atloop.memory.state import AgentState


class MemorySummarizer:
    """Summarize agent memory for LLM input."""

    @staticmethod
    def get_memory_overview(state: AgentState) -> str:
        """
        Get a brief overview of memory for terminal output.

        Args:
            state: Agent state

        Returns:
            Brief overview string (single line, compact format)
        """
        parts = []

        # Created files count
        if state.memory.created_files:
            parts.append(f"📁 {len(state.memory.created_files)} files")
            # Show last file name (truncated if too long)
            last_file = state.memory.created_files[-1]
            if len(last_file) > 30:
                last_file = "..." + last_file[-27:]
            parts.append(f"Latest: {last_file}")

        # Recent attempts
        if state.memory.attempts:
            last_attempt = state.memory.attempts[-1]
            success = last_attempt.get("success", False)
            files = last_attempt.get("files", [])
            status = "✓" if success else "✗"
            parts.append(f"{status} Modified {len(files)} files")

        # Budget usage
        parts.append(f"💰 LLM:{state.budget_used.llm_calls} Tools:{state.budget_used.tool_calls}")

        # Long-term memory preview
        if state.memory.plan or state.memory.task_summary:
            long_term_parts = []
            if state.memory.plan:
                from atloop.memory.plan import PlanManager

                plan_str = PlanManager.plan_to_string(state.memory.plan)
                if plan_str:
                    plan_preview = plan_str[:40] + "..." if len(plan_str) > 40 else plan_str
                    long_term_parts.append(f"Plan: {plan_preview}")
            if state.memory.important_decisions:
                long_term_parts.append(f"Decisions:{len(state.memory.important_decisions)}")
            if state.memory.milestones:
                long_term_parts.append(f"Milestones:{len(state.memory.milestones)}")
            if long_term_parts:
                parts.append(f"📋 {' | '.join(long_term_parts)}")

        # Last error (if any, very brief)
        if state.last_error.summary:
            error_preview = state.last_error.summary[:50]
            if len(state.last_error.summary) > 50:
                error_preview += "..."
            # Extract first line or key info
            error_first_line = error_preview.split("\n")[0]
            parts.append(f"⚠️ {error_first_line}")

        return " | ".join(parts) if parts else "No memory information"

    @staticmethod
    def summarize(
        state: AgentState,
        max_length: int = MEMORY_SUMMARY_DEFAULT_LIMIT,
        task_goal: Optional[str] = None,
    ) -> str:
        """
        Summarize agent state memory.

        Args:
            state: Agent state
            max_length: Maximum summary length
            task_goal: Optional task goal for completion detection

        Returns:
            Summary string
        """
        parts = []

        # If memory is completely empty, return a minimal summary
        if (
            not state.memory.task_summary
            and not state.memory.plan
            and not state.memory.decisions
            and not state.memory.attempts
            and not state.memory.important_decisions
            and not state.memory.milestones
            and not state.memory.learnings
            and not state.memory.llm_responses
            and not state.memory.tool_results_history
            and not state.memory.modified_files_content
        ):
            return "Initial state: Task just started, no operations executed yet."

        # Long-term memory: Task summary (shown first, persists across steps)
        if state.memory.task_summary:
            parts.append("## 📋 Task Overview (Long-term Memory)")
            parts.append(state.memory.task_summary)
            parts.append("")

        # Long-term memory: Current plan (can be dynamically updated)
        if state.memory.plan:
            from atloop.memory.plan import PlanManager, PlanStep

            parts.append("## 📝 Current Execution Plan (Long-term Memory, Dynamically Updated)")

            # Convert plan to string representation
            plan_str = PlanManager.plan_to_string(state.memory.plan)
            if plan_str:
                parts.append(plan_str)

                # Show progress if structured
                if (
                    isinstance(state.memory.plan, list)
                    and state.memory.plan
                    and isinstance(state.memory.plan[0], (PlanStep, dict))
                ):
                    progress = PlanManager.get_progress(state)
                    if progress["total"] > 0:
                        parts.append(
                            f"\nProgress: {progress['completed']}/{progress['total']} completed "
                            f"({progress['completion_rate'] * 100:.0f}%), "
                            f"{progress['in_progress']} in progress, {progress['pending']} pending"
                        )
            parts.append("")

        # Long-term memory: Important decisions (sorted by importance)
        if state.memory.important_decisions:
            from atloop.memory.scorer import ImportanceScorer

            parts.append("## 🎯 Important Decisions (Long-term Memory)")

            # Score and sort by importance
            scored_decisions = []
            for decision in state.memory.important_decisions:
                score = ImportanceScorer.score_decision(decision)
                scored_decisions.append((score, decision))

            # Sort by score (descending) and take top 5
            scored_decisions.sort(key=lambda x: x[0], reverse=True)
            for score, decision in scored_decisions[:5]:
                step = decision.get("step", "?")
                content = decision.get("content", "")
                # Show importance indicator
                importance_indicator = "⭐" * min(3, int(score * 3) + 1)
                parts.append(f"- {importance_indicator} Step {step}: {content}")
            parts.append("")

        # Long-term memory: Milestones (sorted by importance)
        if state.memory.milestones:
            from atloop.memory.scorer import ImportanceScorer

            parts.append("## 🏆 Achieved Milestones (Long-term Memory)")

            # Score and sort by importance
            scored_milestones = []
            for milestone in state.memory.milestones:
                score = ImportanceScorer.score_milestone(milestone)
                scored_milestones.append((score, milestone))

            # Sort by score (descending) and take top 5
            scored_milestones.sort(key=lambda x: x[0], reverse=True)
            for score, milestone in scored_milestones[:5]:
                step = milestone.get("step", "?")
                content = milestone.get("content", "")
                importance_indicator = "⭐" * min(3, int(score * 3) + 1)
                parts.append(f"- {importance_indicator} Step {step}: {content}")
            parts.append("")

        # Long-term memory: Learnings (sorted by importance)
        if state.memory.learnings:
            from atloop.memory.scorer import ImportanceScorer

            parts.append("## 💡 Important Learnings (Long-term Memory)")

            # Score and sort by importance
            scored_learnings = []
            for learning in state.memory.learnings:
                score = ImportanceScorer.score_learning(learning)
                scored_learnings.append((score, learning))

            # Sort by score (descending) and take top 3
            scored_learnings.sort(key=lambda x: x[0], reverse=True)
            for score, learning in scored_learnings[:3]:
                importance_indicator = "⭐" * min(3, int(score * 3) + 1)
                parts.append(f"- {importance_indicator} {learning}")
            parts.append("")

        # Recent Steps Summary (FACTS ONLY - no LLM interpretations)
        # NOTE: We intentionally do NOT show thought_summary or LLM plans here
        # to prevent feedback loops where LLM's previous hypotheses become "facts"
        if state.memory.decisions:
            parts.append("## Recent Steps (Facts Only)")
            for decision in state.memory.decisions[-3:]:
                step = decision.get("step", "?")
                actions = decision.get("actions", [])
                actions_count = len(actions)
                stop_reason = decision.get("stop_reason", "?")
                
                # Show only factual information: what tools were called
                tools_used = [a.get("tool", "?") for a in actions[:3]]
                tools_str = ", ".join(tools_used)
                if len(actions) > 3:
                    tools_str += f" ... (+{len(actions) - 3} more)"
                
                parts.append(f"- Step {step}: {actions_count} actions [{tools_str}] ({stop_reason})")
        
        # NOTE: llm_responses are NOT shown to LLM to prevent feedback loops
        # They are preserved in memory for debugging only

        # Recent attempts (last 3) - include detailed tool execution results
        # CRITICAL: Show ALL tool outputs, especially for shell commands
        if state.memory.attempts:
            parts.append("\n## Recent Attempts")
            for attempt in state.memory.attempts[-3:]:
                files = attempt.get("files", [])
                success = attempt.get("success", False)
                status = "Success" if success else "Failed"
                parts.append(f"- Modified {len(files)} files: {status}")

                # Include detailed tool execution results for LLM to judge
                results = attempt.get("results", [])
                if results:
                    parts.append("  Tool Execution Details:")
                    for i, result in enumerate(results[-3:], 1):  # Last 3 results
                        tool = result.get("tool", "unknown")
                        tool_ok = result.get("ok", False)
                        exit_code = result.get("exit_code", -1)
                        stderr = result.get("stderr", "")
                        stdout = result.get("stdout", "")
                        error = result.get("error", "")

                        status_icon = "✓" if tool_ok else "✗"
                        parts.append(f"    {status_icon} [{tool}] Exit Code: {exit_code}")

                        # For shell commands (run tool), show more output
                        is_shell = tool == "run"
                        max_stderr = (
                            MEMORY_SUMMARY_STDOUT_STDERR_SHELL
                            if is_shell
                            else MEMORY_SUMMARY_STDOUT_STDERR_OTHER
                        )
                        max_stdout = (
                            MEMORY_SUMMARY_STDOUT_STDERR_SHELL
                            if is_shell
                            else MEMORY_SUMMARY_STDOUT_STDERR_OTHER
                        )

                        if error:
                            parts.append(f"      Error: {error}")
                        if stderr:
                            if len(stderr) > max_stderr:
                                stderr_preview = (
                                    stderr[: max_stderr // 2]
                                    + f"\n... [Omitted {len(stderr) - max_stderr} chars] ...\n"
                                    + stderr[-max_stderr // 2 :]
                                )
                            else:
                                stderr_preview = stderr
                            parts.append(f"      Stderr ({len(stderr)} chars):\n{stderr_preview}")
                        if stdout:
                            # Always show stdout for shell commands, even if long
                            if len(stdout) > max_stdout:
                                stdout_preview = (
                                    stdout[: max_stdout // 2]
                                    + f"\n... [Omitted {len(stdout) - max_stdout} chars] ...\n"
                                    + stdout[-max_stdout // 2 :]
                                )
                            else:
                                stdout_preview = stdout
                            parts.append(f"      Stdout ({len(stdout)} chars):\n{stdout_preview}")

        # Task completion status check (add at the beginning for visibility)
        # Check if task goal matches created files for simple "write code" tasks
        if task_goal and state.memory.created_files:
            task_goal_lower = task_goal.lower()
            # Simple heuristic: if goal contains "write" and "code" and file is created, task might be complete
            if ("write" in task_goal_lower or "create" in task_goal_lower) and (
                "code" in task_goal_lower
                or "file" in task_goal_lower
                or "python" in task_goal_lower
            ):
                parts.insert(0, "\n## ✅ Task Completion Status")
                parts.insert(1, f"**Task Goal**: {task_goal}")
                parts.insert(2, f"**Created Files**: {', '.join(state.memory.created_files)}")
                parts.insert(3, "")
                parts.insert(
                    4,
                    "**Analysis**: File(s) have been created. For simple 'write code' tasks, this typically means the task is complete.",
                )
                parts.insert(
                    5,
                    "**Recommendation**: If the created file(s) satisfy the task goal, please set `stop_reason='done'`.",
                )
                parts.insert(6, "")

        # Created files (for resume capability) - Important but after long-term memory
        if state.memory.created_files:
            parts.insert(0, "\n## ⚠️⚠️⚠️ Created Files (CRITICAL: Do NOT recreate!)")
            parts.insert(1, f"**{len(state.memory.created_files)} files created**:")
            for i, file_path in enumerate(state.memory.created_files[-20:], 1):  # Last 20 files
                parts.insert(1 + i, f"- ✅ {file_path}")
            if len(state.memory.created_files) > 20:
                parts.insert(
                    1 + len(state.memory.created_files[-20:]) + 1,
                    f"... ({len(state.memory.created_files) - 20} more files)",
                )
            insert_pos = (
                1
                + min(20, len(state.memory.created_files))
                + (2 if len(state.memory.created_files) > 20 else 1)
            )
            parts.insert(insert_pos, "")
            parts.insert(insert_pos + 1, "🚨🚨🚨 **CRITICAL WARNING**:")
            parts.insert(insert_pos + 2, "1. **These files already exist, DO NOT recreate them!**")
            parts.insert(
                insert_pos + 3,
                "2. If task requires multiple files, continue creating **remaining files** (not in the list above)",
            )
            parts.insert(
                insert_pos + 4,
                "3. If files above need modification, use `edit_file` tool, do NOT use `write_file` to recreate",
            )
            parts.insert(
                insert_pos + 5,
                "4. **Before creating any new file, check the list above to ensure no duplicates**",
            )
            parts.insert(
                insert_pos + 6,
                "5. If a file is in the list above, it already exists - use `read_file` to read or `edit_file` to modify",
            )

        # Key files
        if state.memory.key_files:
            parts.append("\n## Key Files")
            for key_file in state.memory.key_files[-5:]:  # Last 5
                path = key_file.get("path", "?")
                reason = key_file.get("reason", "")
                parts.append(f"- {path}: {reason}")

        # Phase 5: Recently modified files content (auto-read)
        if state.memory.modified_files_content:
            parts.append("\n## Recently Modified File Content (Auto-read)")

            # Sort by importance, take top N
            sorted_files = sorted(
                state.memory.modified_files_content,
                key=lambda x: (x.get("importance_score", 0), x.get("last_modified_step", 0)),
                reverse=True,
            )

            # Show recently modified, most important files (max 5)
            max_files_to_show = 5
            total_size = 0
            max_total_size = 20000  # Max 20KB content (~5k tokens)

            for file_record in sorted_files[:max_files_to_show]:
                path = file_record.get("path", "?")
                content = file_record.get("content", "")
                step = file_record.get("last_modified_step", "?")
                size = file_record.get("size", 0)
                importance = file_record.get("importance_score", 0)

                # If total size exceeds limit, truncate content
                if total_size + size > max_total_size:
                    remaining = max_total_size - total_size
                    if remaining > 100:  # At least show 100 chars
                        content = (
                            content[:remaining]
                            + f"\n... [File too large, truncated, full content {size} bytes]"
                        )
                    else:
                        content = f"[File too large ({size} bytes), content not shown]"
                        parts.append(f"\n### {path} (Step {step}, Importance: {importance:.2f})")
                        parts.append(f"```\n{content}\n```")
                        total_size += 100  # Estimate
                        continue

                parts.append(f"\n### {path} (Step {step}, Importance: {importance:.2f})")

                # Display strategy based on file size
                if size > 10000:  # Larger than 10KB
                    # Show first 5000 chars and last 500 chars
                    preview = (
                        content[:5000]
                        + f"\n... [Omitted {size - 5500} chars] ...\n"
                        + content[-500:]
                    )
                    parts.append(f"```\n{preview}\n```")
                else:
                    parts.append(f"```\n{content}\n```")

                total_size += min(size, max_total_size - total_size)
                if total_size >= max_total_size:
                    remaining_files = len(sorted_files) - max_files_to_show
                    if remaining_files > 0:
                        parts.append(f"\n... [{remaining_files} more files not shown]")
                    break

        # Notes
        if state.memory.notes:
            parts.append("\n## Important Notes")
            for note in state.memory.notes[-3:]:  # Last 3
                parts.append(f"- {note}")

        # NOTE: Loop detection and intervention is now handled by LoopDetector
        # which provides more robust pattern detection and graduated interventions.
        # The intervention messages are injected at PlanPhase level, not here.

        # Last error (includes all recent tool execution results)
        # CRITICAL: This is the PRIMARY source of tool execution info for LLM
        # Must include ALL outputs, especially stderr which often contains critical error info
        if state.last_error.summary:
            parts.append("\n## Last Tool Execution Result (Most Important)")
            parts.append("⚠️ Key Points:")
            parts.append(
                "  - Even if exit_code=0, error messages in stderr (e.g., 'not found', 'error', 'failed') need to be handled"
            )
            parts.append("  - Please carefully check complete content of stderr and stdout")
            parts.append(
                "  - For shell commands, stderr usually contains the real execution status"
            )
            parts.append("")
            parts.append(f"{state.last_error.summary}")
            if state.last_error.repro_cmd:
                parts.append(f"\nRepro Command: {state.last_error.repro_cmd}")
            if state.last_error.raw_stderr_tail:
                # Show more of stderr tail for detailed analysis
                stderr_tail = (
                    state.last_error.raw_stderr_tail[-MEMORY_SUMMARY_STDERR_TAIL:]
                    if len(state.last_error.raw_stderr_tail) > MEMORY_SUMMARY_STDERR_TAIL
                    else state.last_error.raw_stderr_tail
                )
                parts.append(
                    f"\nComplete Stderr Details ({len(state.last_error.raw_stderr_tail)} chars):\n{stderr_tail}"
                )

        # Phase 3: Enhanced - Show recent tool results from tool_results_history if available
        if state.memory.tool_results_history:
            parts.append("\n## Recent Tool Execution Results (Enhanced Storage)")
            for tool_result in state.memory.tool_results_history[-5:]:  # Last 5 tool results
                step = tool_result.get("step", "?")
                tool = tool_result.get("tool", "unknown")
                result = tool_result.get("result", {})
                ok = result.get("ok", False)
                status = "✓" if ok else "✗"
                parts.append(f"- Step {step}: {status} [{tool}]")
                if result.get("stdout"):
                    stdout_preview = result.get("stdout", "")[:100]
                    if len(result.get("stdout", "")) > 100:
                        stdout_preview += "..."
                    parts.append(f"  Stdout: {stdout_preview}")
                if result.get("stderr"):
                    stderr_preview = result.get("stderr", "")[:100]
                    if len(result.get("stderr", "")) > 100:
                        stderr_preview += "..."
                    parts.append(f"  Stderr: {stderr_preview}")
            parts.append("")

        # Recent tool executions (both success and failure) - let LLM judge
        # CRITICAL: Include ALL tool outputs so LLM has complete context
        # This is especially important for shell commands where stderr may contain critical info
        if state.memory.attempts:
            recent_executions = []
            for attempt in state.memory.attempts[-2:]:  # Last 2 attempts
                results = attempt.get("results", [])
                for result in results[-2:]:  # Last 2 results per attempt
                    tool = result.get("tool", "unknown")
                    tool_ok = result.get("ok", False)
                    exit_code = result.get("exit_code", -1)
                    stderr = result.get("stderr", "")
                    stdout = result.get("stdout", "")
                    error = result.get("error", "")

                    # Build comprehensive execution info (success or failure)
                    # For shell commands, preserve more output
                    is_shell = tool == "run"
                    max_stderr = (
                        MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL
                        if is_shell
                        else MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER
                    )
                    max_stdout = (
                        MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL
                        if is_shell
                        else MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER
                    )

                    exec_parts = [f"[{tool}] Exit Code: {exit_code}, Success: {tool_ok}"]
                    if error:
                        exec_parts.append(f"Error: {error}")
                    if stderr:
                        if len(stderr) > max_stderr:
                            stderr_preview = (
                                stderr[: max_stderr // 2]
                                + f"\n... [Omitted {len(stderr) - max_stderr} chars] ...\n"
                                + stderr[-max_stderr // 2 :]
                            )
                        else:
                            stderr_preview = stderr
                        exec_parts.append(f"Stderr ({len(stderr)} chars):\n{stderr_preview}")
                    if stdout:
                        if len(stdout) > max_stdout:
                            stdout_preview = (
                                stdout[: max_stdout // 2]
                                + f"\n... [Omitted {len(stdout) - max_stdout} chars] ...\n"
                                + stdout[-max_stdout // 2 :]
                            )
                        else:
                            stdout_preview = stdout
                        exec_parts.append(f"Stdout ({len(stdout)} chars):\n{stdout_preview}")

                    recent_executions.append("\n".join(exec_parts))

            if recent_executions:
                parts.append("\n## Recent Tool Execution Results")
                parts.append(
                    "⚠️ Important: Includes both success and failure, please judge based on complete information (especially stderr)"
                )
                for execution in recent_executions[-3:]:  # Last 3 executions
                    parts.append(f"- {execution}")

        summary = "\n".join(parts)

        # Smart truncation with importance-based prioritization
        # Priority order: long-term memory > last_error > high-importance items > others
        effective_max_length = max(max_length, MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT)
        if len(summary) > effective_max_length:
            # Strategy: Keep long-term memory + last_error + high-importance items
            # Find section boundaries
            long_term_end = summary.find("## Recent Decisions")
            last_error_start = summary.find("## Last Tool Execution Result")

            # Calculate what we can keep
            if long_term_end > 0:
                long_term_section = summary[:long_term_end]
            else:
                long_term_section = ""

            # Try to preserve last_error section
            if last_error_start > 0:
                # Keep long-term + last_error
                remaining = effective_max_length - len(long_term_section)
                if remaining > 0:
                    # Find end of last_error section (before "## Recent Tool Execution Results" or end)
                    recent_exec_start = summary.find(
                        "## Recent Tool Execution Results", last_error_start
                    )
                    if recent_exec_start > 0:
                        last_error_section = summary[last_error_start:recent_exec_start]
                    else:
                        # Take as much as we can
                        last_error_section = summary[
                            last_error_start : last_error_start + remaining
                        ]

                    # Truncate last_error_section if needed
                    if len(long_term_section) + len(last_error_section) > effective_max_length:
                        available = (
                            effective_max_length - len(long_term_section) - 100
                        )  # Reserve 100 chars for message
                        last_error_section = last_error_section[:available] + "..."

                    summary = long_term_section + "\n" + last_error_section
                    if len(summary) < effective_max_length:
                        summary += "\n[Summary truncated, but preserved long-term memory and last tool execution result...]"
                else:
                    summary = (
                        long_term_section
                        + "\n[Summary truncated, but preserved long-term memory...]"
                    )
            else:
                # Fallback: simple truncation
                summary = summary[:effective_max_length] + "\n[Summary truncated...]"

        return summary if summary.strip() else "No memory information"
