"""Memory summarizer for condensing memory into prompts."""

from titan.config.limits import (
    MEMORY_SUMMARY_DEFAULT_LIMIT,
    MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_OTHER,
    MEMORY_SUMMARY_LAST_ERROR_STDOUT_STDERR_SHELL,
    MEMORY_SUMMARY_MIN_EFFECTIVE_LIMIT,
    MEMORY_SUMMARY_STDERR_TAIL,
    MEMORY_SUMMARY_STDOUT_STDERR_OTHER,
    MEMORY_SUMMARY_STDOUT_STDERR_SHELL,
)
from titan.memory.state import AgentState


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
            parts.append(f"📁 {len(state.memory.created_files)} 文件")
            # Show last file name (truncated if too long)
            last_file = state.memory.created_files[-1]
            if len(last_file) > 30:
                last_file = "..." + last_file[-27:]
            parts.append(f"最新: {last_file}")
        
        # Recent attempts
        if state.memory.attempts:
            last_attempt = state.memory.attempts[-1]
            success = last_attempt.get("success", False)
            files = last_attempt.get("files", [])
            status = "✓" if success else "✗"
            parts.append(f"{status} 修改 {len(files)} 文件")
        
        # Budget usage
        parts.append(f"💰 LLM:{state.budget_used.llm_calls} 工具:{state.budget_used.tool_calls}")
        
        # Long-term memory preview
        if state.memory.plan or state.memory.task_summary:
            long_term_parts = []
            if state.memory.plan:
                from titan.memory.plan import PlanManager
                plan_str = PlanManager.plan_to_string(state.memory.plan)
                if plan_str:
                    plan_preview = plan_str[:40] + "..." if len(plan_str) > 40 else plan_str
                    long_term_parts.append(f"计划: {plan_preview}")
            if state.memory.important_decisions:
                long_term_parts.append(f"决策:{len(state.memory.important_decisions)}")
            if state.memory.milestones:
                long_term_parts.append(f"里程碑:{len(state.memory.milestones)}")
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
        
        return " | ".join(parts) if parts else "无记忆信息"

    @staticmethod
    def summarize(state: AgentState, max_length: int = MEMORY_SUMMARY_DEFAULT_LIMIT) -> str:
        """
        Summarize agent state memory.

        Args:
            state: Agent state
            max_length: Maximum summary length

        Returns:
            Summary string
        """
        parts = []
        
        # If memory is completely empty, return a minimal summary
        if (not state.memory.task_summary and 
            not state.memory.plan and 
            not state.memory.decisions and 
            not state.memory.attempts and
            not state.memory.important_decisions and
            not state.memory.milestones and
            not state.memory.learnings and
            not state.memory.llm_responses and
            not state.memory.tool_results_history and
            not state.memory.modified_files_content):
            return "初始状态：任务刚开始，还没有执行任何操作。"
        
        # Long-term memory: Task summary (shown first, persists across steps)
        if state.memory.task_summary:
            parts.append("## 📋 任务概览（长期记忆）")
            parts.append(state.memory.task_summary)
            parts.append("")
        
        # Long-term memory: Current plan (can be dynamically updated)
        if state.memory.plan:
            from titan.memory.plan import PlanManager, PlanStep
            parts.append("## 📝 当前执行计划（长期记忆，可动态更新）")
            
            # Convert plan to string representation
            plan_str = PlanManager.plan_to_string(state.memory.plan)
            if plan_str:
                parts.append(plan_str)
                
                # Show progress if structured
                if isinstance(state.memory.plan, list) and state.memory.plan and isinstance(state.memory.plan[0], (PlanStep, dict)):
                    progress = PlanManager.get_progress(state)
                    if progress["total"] > 0:
                        parts.append(f"\n进度: {progress['completed']}/{progress['total']} 已完成 "
                                   f"({progress['completion_rate']*100:.0f}%), "
                                   f"{progress['in_progress']} 进行中, {progress['pending']} 待处理")
            parts.append("")
        
        # Long-term memory: Important decisions (sorted by importance)
        if state.memory.important_decisions:
            from titan.memory.scorer import ImportanceScorer
            parts.append("## 🎯 重要决策（长期记忆）")
            
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
            from titan.memory.scorer import ImportanceScorer
            parts.append("## 🏆 已达成里程碑（长期记忆）")
            
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
            from titan.memory.scorer import ImportanceScorer
            parts.append("## 💡 重要经验（长期记忆）")
            
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

        # Recent decisions (last 3) - Enhanced with LLM response details
        if state.memory.decisions:
            parts.append("## 最近决策")
            for decision in state.memory.decisions[-3:]:
                step = decision.get("step", "?")
                actions_count = len(decision.get("actions", []))
                thought_summary = decision.get("thought_summary", "")
                stop_reason = decision.get("stop_reason", "?")
                
                # Show decision with thought summary if available
                if thought_summary:
                    parts.append(f"- Step {step}: {thought_summary[:100]}... (执行了 {actions_count} 个动作, {stop_reason})")
                else:
                    parts.append(f"- Step {step}: 执行了 {actions_count} 个动作 ({stop_reason})")
        
        # Phase 3: Enhanced - Show recent LLM responses if available
        if state.memory.llm_responses:
            parts.append("\n## 最近 LLM 回复（增强存储）")
            for response in state.memory.llm_responses[-3:]:  # Last 3 responses
                step = response.get("step", "?")
                thought = response.get("thought_summary", "")
                plan = response.get("plan", [])
                if thought:
                    parts.append(f"- Step {step}: {thought[:80]}...")
                if plan:
                    plan_preview = ", ".join(str(p)[:30] for p in plan[:2])
                    if len(plan) > 2:
                        plan_preview += f" ... (共 {len(plan)} 步)"
                    parts.append(f"  计划: {plan_preview}")

        # Recent attempts (last 3) - include detailed tool execution results
        # CRITICAL: Show ALL tool outputs, especially for shell commands
        if state.memory.attempts:
            parts.append("\n## 最近尝试")
            for attempt in state.memory.attempts[-3:]:
                files = attempt.get("files", [])
                success = attempt.get("success", False)
                status = "成功" if success else "失败"
                parts.append(f"- 修改了 {len(files)} 个文件: {status}")

                # Include detailed tool execution results for LLM to judge
                results = attempt.get("results", [])
                if results:
                    parts.append("  工具执行详情:")
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
                                    + f"\n... [省略 {len(stderr) - max_stderr} 字符] ...\n"
                                    + stderr[-max_stderr // 2 :]
                                )
                            else:
                                stderr_preview = stderr
                            parts.append(f"      Stderr ({len(stderr)} 字符):\n{stderr_preview}")
                        if stdout:
                            # Always show stdout for shell commands, even if long
                            if len(stdout) > max_stdout:
                                stdout_preview = (
                                    stdout[: max_stdout // 2]
                                    + f"\n... [省略 {len(stdout) - max_stdout} 字符] ...\n"
                                    + stdout[-max_stdout // 2 :]
                                )
                            else:
                                stdout_preview = stdout
                            parts.append(f"      Stdout ({len(stdout)} 字符):\n{stdout_preview}")

        # Created files (for resume capability) - Important but after long-term memory
        if state.memory.created_files:
            parts.insert(0, "\n## ⚠️⚠️⚠️ 已创建的文件（CRITICAL：不要重复创建！）")
            parts.insert(1, f"**已创建 {len(state.memory.created_files)} 个文件**：")
            for i, file_path in enumerate(state.memory.created_files[-20:], 1):  # Last 20 files
                parts.insert(1 + i, f"- ✅ {file_path}")
            if len(state.memory.created_files) > 20:
                parts.insert(1 + len(state.memory.created_files[-20:]) + 1, f"... (还有 {len(state.memory.created_files) - 20} 个文件)")
            insert_pos = 1 + min(20, len(state.memory.created_files)) + (2 if len(state.memory.created_files) > 20 else 1)
            parts.insert(insert_pos, "")
            parts.insert(insert_pos + 1, "🚨🚨🚨 **CRITICAL 警告**：")
            parts.insert(insert_pos + 2, "1. **这些文件已经存在，绝对不要重复创建！**")
            parts.insert(insert_pos + 3, "2. 如果任务需要创建多个文件，请继续创建**剩余的文件**（不在上述列表中的文件）")
            parts.insert(insert_pos + 4, "3. 如果上述文件需要修改，使用 `edit_file` 工具进行修改，不要使用 `write_file` 重新创建")
            parts.insert(insert_pos + 5, "4. **在创建任何新文件之前，必须先检查上述列表，确保不会重复创建**")
            parts.insert(insert_pos + 6, "5. 如果看到上述列表中有文件，说明该文件已经存在，直接使用 `read_file` 读取或 `edit_file` 修改")

        # Key files
        if state.memory.key_files:
            parts.append("\n## 关键文件")
            for key_file in state.memory.key_files[-5:]:  # Last 5
                path = key_file.get("path", "?")
                reason = key_file.get("reason", "")
                parts.append(f"- {path}: {reason}")

        # Phase 5: Recently modified files content (auto-read)
        if state.memory.modified_files_content:
            parts.append("\n## 最近修改的文件内容（自动读取）")
            
            # 按重要性排序，取最重要的 N 个
            sorted_files = sorted(
                state.memory.modified_files_content,
                key=lambda x: (
                    x.get("importance_score", 0),
                    x.get("last_modified_step", 0)
                ),
                reverse=True
            )
            
            # 显示最近修改的、最重要的文件（最多 5 个）
            max_files_to_show = 5
            total_size = 0
            max_total_size = 20000  # 最多显示 20KB 内容（约 5k tokens）
            
            for file_record in sorted_files[:max_files_to_show]:
                path = file_record.get("path", "?")
                content = file_record.get("content", "")
                step = file_record.get("last_modified_step", "?")
                size = file_record.get("size", 0)
                importance = file_record.get("importance_score", 0)
                
                # 如果总大小超过限制，截断内容
                if total_size + size > max_total_size:
                    remaining = max_total_size - total_size
                    if remaining > 100:  # 至少显示 100 字符
                        content = content[:remaining] + f"\n... [文件过大，已截断，完整内容 {size} 字节]"
                    else:
                        content = f"[文件过大 ({size} 字节)，未显示内容]"
                        parts.append(f"\n### {path} (Step {step}, 重要性: {importance:.2f})")
                        parts.append(f"```\n{content}\n```")
                        total_size += 100  # 估算
                        continue
                
                parts.append(f"\n### {path} (Step {step}, 重要性: {importance:.2f})")
                
                # 根据文件大小决定显示策略
                if size > 10000:  # 大于 10KB
                    # 只显示前 5000 字符和后 500 字符
                    preview = content[:5000] + f"\n... [省略 {size - 5500} 字符] ...\n" + content[-500:]
                    parts.append(f"```\n{preview}\n```")
                else:
                    parts.append(f"```\n{content}\n```")
                
                total_size += min(size, max_total_size - total_size)
                if total_size >= max_total_size:
                    remaining_files = len(sorted_files) - max_files_to_show
                    if remaining_files > 0:
                        parts.append(f"\n... [还有 {remaining_files} 个文件未显示]")
                    break

        # Notes
        if state.memory.notes:
            parts.append("\n## 重要备注")
            for note in state.memory.notes[-3:]:  # Last 3
                parts.append(f"- {note}")

        # Detect repetitive viewing without fixing pattern
        if state.memory.attempts:
            # Count file viewing actions (cat, head, tail, grep, sed) and write_file actions
            viewing_commands = ["cat", "head", "tail", "grep", "sed -n"]
            viewing_count = 0
            write_file_count = 0
            recent_viewing_without_fix = False

            # Check last 3 attempts for "view without fix" pattern
            for attempt in state.memory.attempts[-3:]:
                results = attempt.get("results", [])
                has_viewing = False
                has_write_file = False

                for result in results:
                    tool = result.get("tool", "")
                    if tool == "run":
                        cmd = result.get("command", "") or result.get("meta", {}).get("cmd", "")
                        cmd_lower = str(cmd).lower()
                        # Check if this is a file viewing command
                        if any(view_cmd in cmd_lower for view_cmd in viewing_commands):
                            has_viewing = True
                            viewing_count += 1
                    elif tool == "write_file":
                        has_write_file = True
                        write_file_count += 1

                # If this attempt had viewing but no write_file, it's a "view without fix" pattern
                if has_viewing and not has_write_file:
                    recent_viewing_without_fix = True

            # Warn LLM if it's viewing files without fixing
            if recent_viewing_without_fix and viewing_count >= 2:
                parts.append('\n## 警告：检测到"查看文件但不修复"的行为')
                parts.append(
                    f"你已经执行了 {viewing_count} 次文件查看操作（cat, grep, head, tail 等），但只有 {write_file_count} 次修复操作（write_file）。"
                )
                parts.append("")
                parts.append("**重要理解**：")
                parts.append("- 你在 PLAN 阶段生成所有 actions，系统在 ACT 阶段依次执行")
                parts.append("- **执行完所有 actions 后，你才能看到结果**（在下一轮的 PLAN 阶段）")
                parts.append(
                    "- 因此，如果你需要查看文件内容才能修复，**不要在同一轮中既查看又修复**"
                )
                parts.append("")
                parts.append("**正确的修复流程**：")
                parts.append(
                    "1. **如果错误信息已经明确指出问题**（如 ImportError 指出了缺失的函数名）："
                )
                parts.append("   - **直接使用 `write_file` 修复**，不需要先查看")
                parts.append("   - 从错误信息或之前的上下文中推断实际存在的函数名，直接修复")
                parts.append("")
                parts.append("2. **如果你需要查看文件内容才能修复**：")
                parts.append(
                    '   - **第一轮**：只执行查看操作（如 `run("grep ...")`），设置 `stop_reason="continue"`'
                )
                parts.append("   - **等待系统执行并返回结果**")
                parts.append("   - **第二轮**：看到查看结果后，**必须立即**执行 `write_file` 修复")
                parts.append("   - **禁止**：看到结果后继续查看其他文件而不修复")
                parts.append("")
                parts.append("**你当前的问题**：")
                parts.append("- 你已经查看了文件，但还没有修复")
                parts.append("- **必须**：在下一轮看到查看结果后，立即执行 `write_file` 修复")
                parts.append("- **禁止**：继续查看其他文件而不修复")

        # Detect repetitive exploration actions (for new project creation)
        if state.memory.attempts:
            # Count exploration actions (ls, find, pwd, which, type)
            exploration_commands = ["ls", "find", "pwd", "which", "type"]
            exploration_count = 0
            file_creation_count = 0
            for attempt in state.memory.attempts:
                results = attempt.get("results", [])
                for result in results:
                    tool = result.get("tool", "")
                    if tool == "run":
                        # Get command from result (stored in _phase_act)
                        cmd = result.get("command", "") or result.get("meta", {}).get("cmd", "")
                        cmd_lower = str(cmd).lower()
                        # Check if this looks like exploration (but not file viewing)
                        if any(explore_cmd in cmd_lower for explore_cmd in exploration_commands):
                            exploration_count += 1
                    elif tool == "write_file":
                        file_creation_count += 1

            # If we've done many exploration actions but no file creation, warn LLM
            if exploration_count >= 3 and file_creation_count == 0:
                parts.append("\n## ⚠️ 重要提示：请开始创建文件")
                parts.append(
                    f"你已经执行了 {exploration_count} 次探索操作（ls, find, pwd 等），但还没有开始创建任何文件。"
                )
                parts.append("如果已经了解了项目结构，请立即开始创建文件，不要再继续探索。")
                parts.append(
                    "使用 write_file 工具创建项目文件，使用 run('mkdir -p ...') 创建目录结构。"
                )
                parts.append("对于新项目创建任务，探索 2-3 次就足够了，应该立即开始创建文件。")

        # Last error (includes all recent tool execution results)
        # CRITICAL: This is the PRIMARY source of tool execution info for LLM
        # Must include ALL outputs, especially stderr which often contains critical error info
        if state.last_error.summary:
            parts.append("\n## 最后工具执行结果（最重要）")
            parts.append("⚠️ 关键提示：")
            parts.append(
                "  - 即使 exit_code=0，stderr 中的错误信息（如 'not found', 'error', 'failed'）也需要处理"
            )
            parts.append("  - 请仔细检查 stderr 和 stdout 的完整内容")
            parts.append("  - 对于 shell 命令，stderr 通常包含命令执行的真实状态")
            parts.append("")
            parts.append(f"{state.last_error.summary}")
            if state.last_error.repro_cmd:
                parts.append(f"\n复现命令: {state.last_error.repro_cmd}")
            if state.last_error.raw_stderr_tail:
                # Show more of stderr tail for detailed analysis
                stderr_tail = (
                    state.last_error.raw_stderr_tail[-MEMORY_SUMMARY_STDERR_TAIL:]
                    if len(state.last_error.raw_stderr_tail) > MEMORY_SUMMARY_STDERR_TAIL
                    else state.last_error.raw_stderr_tail
                )
                parts.append(
                    f"\n完整 Stderr 详情 ({len(state.last_error.raw_stderr_tail)} 字符):\n{stderr_tail}"
                )

        # Phase 3: Enhanced - Show recent tool results from tool_results_history if available
        if state.memory.tool_results_history:
            parts.append("\n## 最近工具执行结果（增强存储）")
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
                                + f"\n... [省略 {len(stderr) - max_stderr} 字符] ...\n"
                                + stderr[-max_stderr // 2 :]
                            )
                        else:
                            stderr_preview = stderr
                        exec_parts.append(f"Stderr ({len(stderr)} 字符):\n{stderr_preview}")
                    if stdout:
                        if len(stdout) > max_stdout:
                            stdout_preview = (
                                stdout[: max_stdout // 2]
                                + f"\n... [省略 {len(stdout) - max_stdout} 字符] ...\n"
                                + stdout[-max_stdout // 2 :]
                            )
                        else:
                            stdout_preview = stdout
                        exec_parts.append(f"Stdout ({len(stdout)} 字符):\n{stdout_preview}")

                    recent_executions.append("\n".join(exec_parts))

            if recent_executions:
                parts.append("\n## 最近工具执行结果")
                parts.append(
                    "⚠️ 重要：包括成功和失败，请根据完整信息（特别是 stderr）判断是否需要处理"
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
            long_term_end = summary.find("## 最近决策")
            last_error_start = summary.find("## 最后工具执行结果")
            
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
                    # Find end of last_error section (before "## 最近工具执行结果" or end)
                    recent_exec_start = summary.find("## 最近工具执行结果", last_error_start)
                    if recent_exec_start > 0:
                        last_error_section = summary[last_error_start:recent_exec_start]
                    else:
                        # Take as much as we can
                        last_error_section = summary[last_error_start:last_error_start + remaining]
                    
                    # Truncate last_error_section if needed
                    if len(long_term_section) + len(last_error_section) > effective_max_length:
                        available = effective_max_length - len(long_term_section) - 100  # Reserve 100 chars for message
                        last_error_section = last_error_section[:available] + "..."
                    
                    summary = long_term_section + "\n" + last_error_section
                    if len(summary) < effective_max_length:
                        summary += "\n[摘要已截断，但保留了长期记忆和最后工具执行结果...]"
                else:
                    summary = long_term_section + "\n[摘要已截断，但保留了长期记忆...]"
            else:
                # Fallback: simple truncation
                summary = summary[:effective_max_length] + "\n[摘要已截断...]"

        return summary if summary.strip() else "无记忆信息"
