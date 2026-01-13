"""Memory formatter for formatting memory data into prompt strings."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from atloop.memory.state import AgentState

from atloop.config.limits import (
    MEMORY_SUMMARY_STDOUT_STDERR_OTHER,
    MEMORY_SUMMARY_STDOUT_STDERR_SHELL,
)
from atloop.tools.base import BaseTool
from atloop.tools.output_limit_strategy import OutputLimitStrategy
from atloop.tools.output_semantic_type import OutputSemanticType


class ToolResultFormatter:
    """格式化工具执行结果"""

    @staticmethod
    def format_single_result(
        tool_result: Dict[str, Any],
        tool_registry: Optional[Any] = None,
        include_full_output: bool = False,
    ) -> str:
        """
        格式化单个工具执行结果。

        Args:
            tool_result: 工具执行结果字典，格式：
                {
                    "step": int,
                    "tool": str,
                    "args": Dict,
                    "placeholder": Optional[str],
                    "result": Dict
                }
            tool_registry: 工具注册表（用于获取输出限制策略）
            include_full_output: 是否包含完整输出

        Returns:
            格式化后的字符串，格式：
            - Step N: [状态] [工具] (参数信息)
              [输出内容]
        """
        step = tool_result.get("step", "?")
        tool_name = tool_result.get("tool", "unknown")
        placeholder = tool_result.get("placeholder")
        args = tool_result.get("args", {})
        result = tool_result.get("result", {})
        ok = result.get("ok", False)
        status = "✓" if ok else "✗"

        # 构建标题行（符合设计文档格式）
        if tool_name == "run" and "cmd" in args:
            cmd = str(args["cmd"])
            title = f"- Step {step}: {status} [{tool_name}] `{cmd}`"
        elif placeholder:
            title = f"- Step {step}: {status} [{tool_name}] ({placeholder})"
        elif tool_name in ["write_file", "edit_file", "append_file"] and "path" in args:
            path = args.get("path", "")
            title = f"- Step {step}: {status} [{tool_name}] (path: {path})"
        else:
            title = f"- Step {step}: {status} [{tool_name}]"

        lines = [title]

        # 格式化输出（使用统一的截断策略，符合设计文档格式）
        stdout_text = None
        stderr_text = None

        if result.get("stdout"):
            stdout_text = ToolResultFormatter._format_output(
                result.get("stdout", ""),
                tool_name,
                tool_registry,
                args,
                is_stderr=False,
                include_full=include_full_output,
            )

        if result.get("stderr"):
            stderr_text = ToolResultFormatter._format_output(
                result.get("stderr", ""),
                tool_name,
                tool_registry,
                args,
                is_stderr=True,
                include_full=include_full_output,
            )

        # 添加输出内容（使用代码块包裹）
        if stdout_text:
            lines.append(f"  ```\n{stdout_text}\n  ```")

        if stderr_text:
            lines.append(f"  ```\n{stderr_text}\n  ```")

        # 添加状态信息（符合设计文档格式）
        exit_code = result.get("exit_code", -1)
        if ok:
            status_text = "✅ **Status**: Success"
            if exit_code != -1 and exit_code != 0:
                status_text += f" - Exit Code: {exit_code}"
        else:
            status_text = "❌ **Status**: Failed"
            if exit_code != -1:
                status_text += f" - Exit Code: {exit_code}"
        lines.append(f"  {status_text}")

        if not ok:
            error = result.get("error", "")
            if error:
                lines.append(f"  🔍 **Root Cause**: {error}")
                lines.append(f"  💡 **Solution**: Check error details above and fix the issue")

        return "\n".join(lines)

    @staticmethod
    def format_results_list(
        tool_results: List[Dict[str, Any]],
        tool_registry: Optional[Any] = None,
        max_count: int = 5,
    ) -> str:
        """
        格式化工具结果列表。

        Args:
            tool_results: 工具结果列表
            tool_registry: 工具注册表
            max_count: 最大显示数量

        Returns:
            格式化后的字符串，包含多个工具结果
        """
        if not tool_results:
            return ""

        # 取最后 max_count 个结果
        recent_results = tool_results[-max_count:]

        formatted_results = []
        for tool_result in recent_results:
            formatted = ToolResultFormatter.format_single_result(
                tool_result,
                tool_registry=tool_registry,
                include_full_output=False,
            )
            formatted_results.append(formatted)

        return "\n\n".join(formatted_results)

    @staticmethod
    def _format_output(
        output: str,
        tool_name: str,
        tool_registry: Optional[Any],
        args: Dict[str, Any],
        is_stderr: bool,
        include_full: bool,
    ) -> str:
        """
        格式化输出内容（统一截断策略）。

        Args:
            output: 输出内容
            tool_name: 工具名称
            tool_registry: 工具注册表
            args: 工具参数
            is_stderr: 是否为 stderr
            include_full: 是否包含完整输出

        Returns:
            格式化后的输出字符串
        """
        if not output:
            return ""

        if include_full:
            return output

        # 获取工具实例
        tool_instance: Optional[BaseTool] = None
        if tool_registry:
            tool_instance = tool_registry.get(tool_name)

        # 确定最大长度
        if tool_instance:
            max_length = OutputLimitStrategy.get_limit_for_memory_summary(
                tool_instance, is_stderr=is_stderr
            )
        else:
            # Fallback: use tool name-based logic
            is_shell = tool_name == "run"
            max_length = (
                MEMORY_SUMMARY_STDOUT_STDERR_SHELL
                if is_shell
                else MEMORY_SUMMARY_STDOUT_STDERR_OTHER
            )

        # 特殊处理：对于知识/文件内容类型，显示更多预览
        if tool_instance:
            semantic_type = (
                tool_instance.stderr_semantic_type
                if is_stderr
                else tool_instance.stdout_semantic_type
            )
            if semantic_type in (
                OutputSemanticType.KNOWLEDGE_CONTENT,
                OutputSemanticType.FILE_CONTENT,
            ):
                # 对于知识/文件内容，使用更大的预览（5000字符）
                max_preview = 5000
                if len(output) > max_preview:
                    return (
                        output[:max_preview]
                        + f"\n... [Omitted {len(output) - max_preview} chars] ..."
                    )
                return output

        # 标准截断策略
        if len(output) <= max_length:
            return output

        # 截断：显示前半部分和后半部分
        half_length = max_length // 2
        return (
            output[:half_length]
            + f"\n... [Omitted {len(output) - max_length} chars] ...\n"
                + output[-half_length:]
        )


class MemoryFormatter:
    """格式化 Memory 数据为 prompt 字符串"""

    def __init__(self, tool_registry: Optional[Any] = None):
        """
        初始化 MemoryFormatter。

        Args:
            tool_registry: 工具注册表（用于获取输出限制策略）
        """
        self.tool_registry = tool_registry
        self.tool_result_formatter = ToolResultFormatter()

    def format(
        self,
        state: "AgentState",
        task_goal: Optional[str] = None,
        format_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        格式化 Memory 数据。

        Args:
            state: AgentState 实例
            task_goal: 任务目标（可选，用于任务概览）
            format_options: 格式选项
                - tool_results_count: int (默认 5)
                - steps_summary_count: int (默认 3)
                - include_file_content: bool (默认 True)
                - max_file_content_length: int (默认 20000)

        Returns:
            格式化后的字符串，格式符合 MEMORY_PROMPT_FORMAT_DEMO.md
        """
        options = format_options or {}
        parts = []

        # 1. Critical Warnings
        warnings = self._format_critical_warnings(state)
        if warnings:
            parts.append(warnings)

        # 2. Task Overview
        parts.append(self._format_task_overview(state, task_goal))

        # 3. Execution Plan
        parts.append(self._format_execution_plan(state))

        # 4. Important Context
        parts.append(self._format_important_context(state))

        # 5. Recent Activity
        parts.append(
            self._format_recent_activity(
                state, steps_count=options.get("steps_summary_count", 3)
            )
        )

        # 6. Tool Execution Results
        parts.append(
            self._format_tool_execution_results(
                state, max_count=options.get("tool_results_count", 5)
            )
        )

        # 7. Modified Files Content
        if options.get("include_file_content", True):
            parts.append(
                self._format_modified_files_content(
                    state, max_length=options.get("max_file_content_length", 20000)
                )
            )

        # 8. Current State
        parts.append(self._format_current_state(state))

        # 9. Next Steps Guidance
        parts.append(self._format_next_steps_guidance(state, task_goal))

        # 拼接所有部分
        result = "\n\n".join(filter(None, parts))  # 过滤空部分

        # 应用长度限制
        max_length = options.get("max_length")
        if max_length and len(result) > max_length:
            result = self._apply_length_limit(result, max_length)

        return result

    def _format_critical_warnings(self, state: "AgentState") -> str:
        """格式化关键警告（已创建的文件）"""
        if not state.memory.created_files:
            return ""

        parts = ["### ⚠️ Critical Warnings"]
        parts.append("🚨 **DO NOT recreate these files**:")
        for file_path in state.memory.created_files[-20:]:  # Last 20 files
            parts.append(f"- ✅ `{file_path}`")
        if len(state.memory.created_files) > 20:
            parts.append(f"... ({len(state.memory.created_files) - 20} more files)")

        return "\n".join(parts)

    def _format_task_overview(
        self, state: "AgentState", task_goal: Optional[str] = None
    ) -> str:
        """格式化任务概览"""
        parts = ["### 📋 Task Overview"]

        if task_goal:
            parts.append(f"**Goal**: {task_goal}")
        elif state.memory.task_summary:
            parts.append(f"**Goal**: {state.memory.task_summary}")
        else:
            parts.append("**Goal**: (Not specified)")

        # Determine status
        # This is a simplified version - in real implementation, we'd check more conditions
        status = "进行中"
        if state.phase == "DONE":
            status = "已完成"
        elif state.phase == "FAIL":
            status = "已失败"

        parts.append(f"**Status**: {status}")

        # Created files
        if state.memory.created_files:
            files_str = ", ".join([f"`{f}`" for f in state.memory.created_files[-10:]])
            if len(state.memory.created_files) > 10:
                files_str += f" ... (+{len(state.memory.created_files) - 10} more)"
            parts.append(f"**Created Files**: [{files_str}]")
        else:
            parts.append("**Created Files**: []")

        return "\n".join(parts)

    def _format_execution_plan(self, state: "AgentState") -> str:
        """格式化执行计划"""
        parts = ["### 📝 Execution Plan"]

        if state.memory.plan:
            from atloop.memory.plan import PlanManager

            plan_str = PlanManager.plan_to_string(state.memory.plan)
            if plan_str:
                # Split by lines and format
                plan_lines = plan_str.split("\n")
                for line in plan_lines:
                    if line.strip():
                        parts.append(line)
            else:
                parts.append("(No plan available)")
        else:
            parts.append("(No plan available)")

        return "\n".join(parts)

    def _format_important_context(self, state: "AgentState") -> str:
        """格式化重要上下文（决策、里程碑、经验）"""
        parts = ["### 🎯 Important Context"]

        # Key Decisions
        if state.memory.important_decisions:
            parts.append("**Key Decisions**:")
            # Sort by importance and take top 5
            sorted_decisions = sorted(
                state.memory.important_decisions,
                key=lambda x: x.get("importance", 0),
                reverse=True,
            )[:5]
            for decision in sorted_decisions:
                step = decision.get("step", "?")
                content = decision.get("content", "")
                importance = decision.get("importance", 0)
                stars = "⭐" * min(3, int(importance * 3) + 1)
                parts.append(f"- {stars} Step {step}: {content}")
        else:
            parts.append("**Key Decisions**: (无)")

        # Milestones
        if state.memory.milestones:
            parts.append("**Milestones**:")
            sorted_milestones = sorted(
                state.memory.milestones,
                key=lambda x: x.get("importance", 0),
                reverse=True,
            )[:5]
            for milestone in sorted_milestones:
                step = milestone.get("step", "?")
                content = milestone.get("content", "")
                importance = milestone.get("importance", 0)
                stars = "⭐" * min(3, int(importance * 3) + 1)
                parts.append(f"- {stars} Step {step}: {content}")
        else:
            parts.append("**Milestones**: (无)")

        # Learnings
        if state.memory.learnings:
            parts.append("**Learnings**:")
            # Take top 3 (assuming they're already sorted by importance)
            for learning in state.memory.learnings[:3]:
                parts.append(f"- ⭐ {learning}")
        else:
            parts.append("**Learnings**: (无)")

        return "\n".join(parts)

    def _format_recent_activity(self, state: "AgentState", steps_count: int = 3) -> str:
        """格式化最近活动"""
        parts = [f"### 📊 Recent Activity (Last {steps_count} Steps)"]

        # Steps Summary
        if state.memory.decisions:
            parts.append("**Steps**:")
            for decision in state.memory.decisions[-steps_count:]:
                step = decision.get("step", "?")
                actions = decision.get("actions", [])
                tools_used = [a.get("tool", "?") for a in actions[:3]]
                tools_str = ", ".join(tools_used)
                if len(actions) > 3:
                    tools_str += f" ... (+{len(actions) - 3} more)"
                stop_reason = decision.get("stop_reason", "?")
                parts.append(f"- Step {step}: [{tools_str}] → {stop_reason}")
        else:
            parts.append("**Steps**: (无)")

        # Files Modified
        parts.append("**Files Modified**:")
        if state.memory.tool_results_history:
            # Extract file modifications by step
            step_files = {}
            for tool_result in state.memory.tool_results_history:
                step = tool_result.get("step", 0)
                modified_files = tool_result.get("modified_files", [])
                if modified_files:
                    if step not in step_files:
                        step_files[step] = []
                    step_files[step].extend(modified_files)

            if step_files:
                recent_steps = sorted(step_files.keys(), reverse=True)[:steps_count]
                for step in recent_steps:
                    files = list(set(step_files[step]))  # Remove duplicates
                    files_str = ", ".join([f"`{f}`" for f in files[:5]])
                    if len(files) > 5:
                        files_str += f" ... (+{len(files) - 5} more)"
                    parts.append(f"- Step {step}: [{files_str}]")
            else:
                parts.append("(无文件修改)")
        else:
            parts.append("(无文件修改)")

        return "\n".join(parts)

    def _format_tool_execution_results(
        self, state: "AgentState", max_count: int = 5
    ) -> str:
        """格式化工具执行结果"""
        parts = [f"### 🔧 Tool Execution Results (Last {max_count})"]

        if state.memory.tool_results_history:
            formatted = self.tool_result_formatter.format_results_list(
                state.memory.tool_results_history,
                tool_registry=self.tool_registry,
                max_count=max_count,
            )
            if formatted:
                parts.append(formatted)
            else:
                parts.append("(无工具执行结果)")
        else:
            parts.append("(无工具执行结果)")

        return "\n".join(parts)

    def _format_modified_files_content(
        self, state: "AgentState", max_length: int = 20000
    ) -> str:
        """格式化修改的文件内容"""
        if not state.memory.modified_files_content:
            return ""

        parts = ["### 📄 Modified Files Content"]

        # Sort by importance and take top 5
        sorted_files = sorted(
            state.memory.modified_files_content,
            key=lambda x: (x.get("importance_score", 0), x.get("last_modified_step", 0)),
            reverse=True,
        )[:5]

        total_size = 0
        for file_record in sorted_files:
            path = file_record.get("path", "?")
            content = file_record.get("content", "")
            step = file_record.get("last_modified_step", "?")
            size = file_record.get("size", 0)
            importance = file_record.get("importance_score", 0)

            # Check if we exceed total limit
            if total_size + size > max_length:
                remaining = max_length - total_size
                if remaining > 100:
                    content = content[:remaining] + f"\n... [File truncated, full content {size} bytes]"
                else:
                    parts.append(f"**{path}** (Step {step}, Importance: {importance:.2f}): [File too large, content not shown]")
                    continue

            parts.append(f"**{path}** (Step {step}, Importance: {importance:.2f}):")
            parts.append(f"```python\n{content}\n```")

            total_size += min(size, max_length - total_size)
            if total_size >= max_length:
                remaining_files = len(sorted_files) - sorted_files.index(file_record) - 1
                if remaining_files > 0:
                    parts.append(f"\n... [{remaining_files} more files not shown]")
                break

        return "\n".join(parts)

    def _format_current_state(self, state: "AgentState") -> str:
        """格式化当前状态"""
        parts = ["### ⚠️ Current State"]

        # Last Error
        if state.last_error.summary:
            parts.append(f"**Last Error**: {state.last_error.summary}")
        else:
            parts.append("**Last Error**: None")

        # Current Diff
        if state.artifacts.current_diff:
            parts.append("**Current Diff**:")
            parts.append("```")
            # Truncate if too long
            diff_preview = state.artifacts.current_diff[:1000]
            if len(state.artifacts.current_diff) > 1000:
                diff_preview += "\n... [Diff truncated]"
            parts.append(diff_preview)
            parts.append("```")
        else:
            parts.append("**Current Diff**: No changes")

        # Test Results
        if state.artifacts.test_results:
            parts.append(f"**Test Results**: {state.artifacts.test_results}")
        else:
            parts.append("**Test Results**: No verification command available")

        return "\n".join(parts)

    def _format_next_steps_guidance(
        self, state: "AgentState", task_goal: Optional[str] = None
    ) -> str:
        """格式化下一步指导"""
        parts = ["### 💡 Next Steps Guidance"]

        # Analyze current state and provide guidance
        guidance_parts = []

        # Check if files were created
        if state.memory.created_files:
            latest_file = state.memory.created_files[-1]
            guidance_parts.append(f"✅ **Latest File Created**: `{latest_file}`")

        # Check execution plan progress
        if state.memory.plan:
            from atloop.memory.plan import PlanManager

            plan_str = PlanManager.plan_to_string(state.memory.plan)
            if plan_str:
                # Count completed steps (marked with ✅)
                completed = plan_str.count("✅")
                total = len([line for line in plan_str.split("\n") if line.strip()])
                if completed > 0:
                    guidance_parts.append(f"📊 **Progress**: {completed}/{total} steps completed")

        # Check for errors
        if state.last_error.summary:
            guidance_parts.append("❌ **Error Detected**: Check error details above")
            guidance_parts.append("🔍 **Investigation Needed**: Analyze error and fix the issue")
            guidance_parts.append("➡️ **Next Action**: Fix the error and retry")

        # Check recent tool results
        if state.memory.tool_results_history:
            last_result = state.memory.tool_results_history[-1]
            tool_name = last_result.get("tool", "")
            result = last_result.get("result", {})
            ok = result.get("ok", False)

            if tool_name == "run" and ok:
                guidance_parts.append("✅ **Last Command Successful**: Continue with next step")
            elif not ok:
                guidance_parts.append("❌ **Last Command Failed**: Review error and fix")

        # Always include next action (even if we have other guidance)
        if not any("Next Action" in part for part in guidance_parts):
            guidance_parts.append("➡️ **Next Action**: Continue with the execution plan")

        parts.extend(guidance_parts)
        return "\n".join(parts)

    def _apply_length_limit(self, text: str, max_length: int) -> str:
        """
        应用长度限制（智能截断）。

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text

        # 优先保留的部分（按顺序）
        priority_sections = [
            "Critical Warnings",
            "Task Overview",
            "Execution Plan",
            "Important Context",
            "Current State",
        ]

        # 简单实现：保留前面的部分，截断后面的部分
        # 在实际实现中，可以更智能地截断
        return text[:max_length] + "\n... [Content truncated due to length limit]"
