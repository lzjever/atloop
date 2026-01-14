"""Memory formatter for formatting memory data into prompt strings."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from atloop.memory.state import AgentState

from atloop.config.loader import ConfigLoader
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
            status_text = "✓ **Status**: Success"
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
                lines.append("  💡 **Solution**: Check error details above and fix the issue")

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
            config = ConfigLoader.get()
            is_shell = tool_name == "run"
            max_length = (
                config.memory.summary_stdout_stderr_shell
                if is_shell
                else config.memory.summary_stdout_stderr_other
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
        # Load default format options from config (single source of truth)
        self._load_default_format_options()

    def _load_default_format_options(self) -> None:
        """Load default format options from config.

        This ensures all formatting options come from a single source of truth
        (MemoryConfig), avoiding hardcoded values scattered across the codebase.
        """
        config = ConfigLoader.get()
        self.default_format_options = {
            "steps_summary_count": config.memory.steps_summary_count,
            "tool_results_count": config.memory.tool_results_count,
            "max_file_content_length": config.memory.max_file_content_length,
            "include_file_content": config.memory.include_file_content,
        }

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
            format_options: 格式选项（可选，会覆盖配置中的默认值）
                - tool_results_count: int (默认从 MemoryConfig 读取)
                - steps_summary_count: int (默认从 MemoryConfig 读取)
                - include_file_content: bool (默认从 MemoryConfig 读取)
                - max_file_content_length: int (默认从 MemoryConfig 读取)
                
                注意：所有默认值现在从 MemoryConfig 读取，确保单一数据源。
                可以通过 format_options 参数覆盖特定调用的值。

        Returns:
            格式化后的字符串，格式符合 MEMORY_PROMPT_FORMAT_DEMO.md
        """
        # Merge default options from config with user-provided options
        # User options override defaults (allows per-call customization)
        options = {**self.default_format_options, **(format_options or {})}
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
            self._format_recent_activity(state, steps_count=options["steps_summary_count"])
        )

        # 6. Tool Execution Results
        parts.append(
            self._format_tool_execution_results(
                state, max_count=options["tool_results_count"]
            )
        )

        # 7. Modified Files Content
        if options["include_file_content"]:
            parts.append(
                self._format_modified_files_content(
                    state, max_length=options["max_file_content_length"]
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
            parts.append(f"- ✓ `{file_path}`")
        if len(state.memory.created_files) > 20:
            parts.append(f"... ({len(state.memory.created_files) - 20} more files)")

        return "\n".join(parts)

    def _format_task_overview(self, state: "AgentState", task_goal: Optional[str] = None) -> str:
        """格式化任务概览"""
        parts = ["### ≡ Task Overview"]

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

    def _get_current_plan_item(self, state: "AgentState") -> Optional[str]:
        """
        Get the current plan item being executed (marked with ↻).

        Args:
            state: AgentState instance

        Returns:
            The plan item description without emoji, or None if not found
        """
        plan = state.memory.plan
        if not plan:
            return None

        # Handle list format
        if isinstance(plan, list) and plan:
            # Check first item to determine format
            first_item = plan[0]

            # Handle list of strings (with emoji markers)
            if isinstance(first_item, str):
                for item in plan:
                    if "↻" in str(item):
                        # Remove emoji markers and return clean description
                        clean_item = (
                            str(item).replace("↻", "").replace("✓", "").replace("≡", "").strip()
                        )
                        return clean_item if clean_item else None

            # Handle PlanStep objects or dicts
            else:
                from atloop.memory.plan import PlanStep

                for item in plan:
                    # Check if it's a PlanStep object
                    if isinstance(item, PlanStep):
                        if item.status == "in_progress":
                            return item.description or item.id
                    # Check if it's a dict
                    elif isinstance(item, dict):
                        status = item.get("status", "")
                        if status == "in_progress":
                            description = item.get("description", "")
                            if description:
                                return description
                            return item.get("id", "")
                    # Fallback: check for status attribute
                    elif hasattr(item, "status"):
                        if getattr(item, "status", "") == "in_progress":
                            description = getattr(item, "description", "")
                            if description:
                                return description
                            return getattr(item, "id", "")

        # Handle string format (old format)
        elif isinstance(plan, str):
            lines = plan.split("\n")
            for line in lines:
                if "↻" in line:
                    clean_line = line.replace("↻", "").replace("✓", "").replace("≡", "").strip()
                    return clean_line if clean_line else None

        return None

    def _format_recent_activity(self, state: "AgentState", steps_count: int) -> str:
        """格式化最近活动"""
        parts = [f"### 📊 Recent Activity (Last {steps_count} Steps)"]

        # Get current plan item being executed (if any)
        current_plan_item = self._get_current_plan_item(state)

        # Steps Summary
        if state.memory.decisions:
            parts.append("**Steps**:")
            for decision in state.memory.decisions[-steps_count:]:
                step = decision.get("step", "?")
                actions = decision.get("actions", [])
                tools_used = [a.get("tool", "?") for a in actions[:3]]
                tools_str = ", ".join(tools_used)
                if len(actions) > 5:
                    tools_str += f" ... (+{len(actions) - 5} more)"
                stop_reason = decision.get("stop_reason", "?")

                # Add current plan item if available
                step_entry = f"- Step {step}: [{tools_str}] → {stop_reason}"
                if current_plan_item:
                    step_entry += f" (↻ {current_plan_item})"
                parts.append(step_entry)
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

    def _format_tool_execution_results(self, state: "AgentState", max_count: int = 5) -> str:
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

    def _format_modified_files_content(self, state: "AgentState", max_length: int = 20000) -> str:
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
                    content = (
                        content[:remaining] + f"\n... [File truncated, full content {size} bytes]"
                    )
                else:
                    parts.append(
                        f"**{path}** (Step {step}, Importance: {importance:.2f}): [File too large, content not shown]"
                    )
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
        """格式化当前状态摘要
        
        架构设计原则：
        - Memory Context 只包含状态摘要，不包含完整内容
        - 完整内容通过 Prompt Template 的占位符显示（{CURRENT_DIFF}, {RECENT_ERROR}, {TEST_RESULTS}）
        - 这样可以避免重复，节省 token，并保持职责清晰
        
        职责边界：
        - Memory Formatter: 格式化 memory 相关信息（plan, context, activity, tool results）
        - Artifacts: 通过 Prompt Template 占位符显示完整内容（diff, errors, test results）
        """
        parts = ["### ⚠️ Current State"]

        # Last Error - 只显示摘要（第一行或关键信息）
        # 完整错误信息在 Prompt Template 的 {RECENT_ERROR} 中显示
        if state.last_error.summary:
            error_lines = state.last_error.summary.split('\n')
            error_summary = error_lines[0]  # 第一行通常是错误类型和位置
            if len(state.last_error.summary) > 200:
                error_summary += " (see Recent Errors section below for full details)"
            parts.append(f"**Last Error**: {error_summary}")
        else:
            parts.append("**Last Error**: None")

        # Current Diff - 只显示统计信息
        # 完整 diff 在 Prompt Template 的 {CURRENT_DIFF} 中显示
        if state.artifacts.current_diff:
            diff_lines = state.artifacts.current_diff.count('\n')
            files_changed = self._extract_files_from_diff(state.artifacts.current_diff)
            if files_changed:
                files_summary = ', '.join(files_changed[:3])  # 最多显示3个文件
                if len(files_changed) > 3:
                    files_summary += f" (+{len(files_changed) - 3} more)"
                parts.append(
                    f"**Current Diff**: {diff_lines} lines changed in {len(files_changed)} file(s): "
                    f"{files_summary} (see Current Diff section below for full details)"
                )
            else:
                parts.append(
                    f"**Current Diff**: {diff_lines} lines changed "
                    f"(see Current Diff section below for full details)"
                )
        else:
            parts.append("**Current Diff**: No changes")

        # Test Results - 只显示状态摘要
        # 完整测试结果在 Prompt Template 的 {TEST_RESULTS} 中显示
        if state.artifacts.test_results:
            test_result_lower = state.artifacts.test_results.lower()
            # 检测测试状态关键词
            if "passed" in test_result_lower or "✓" in state.artifacts.test_results or "success" in test_result_lower:
                parts.append("**Test Results**: ✓ Passed (see Test Results section below for details)")
            elif "failed" in test_result_lower or "❌" in state.artifacts.test_results or "error" in test_result_lower:
                parts.append("**Test Results**: ❌ Failed (see Test Results section below for details)")
            else:
                parts.append("**Test Results**: ⚠️ Unknown (see Test Results section below for details)")
        else:
            parts.append("**Test Results**: No verification command available")

        return "\n".join(parts)

    def _extract_files_from_diff(self, diff: str) -> List[str]:
        """从 diff 中提取修改的文件列表
        
        Args:
            diff: Git diff 格式的字符串
            
        Returns:
            修改的文件路径列表
        """
        files = []
        for line in diff.split('\n')[:100]:  # 只检查前100行（通常足够）
            if line.startswith('+++ ') or line.startswith('--- '):
                file_path = line[4:].strip()
                # 移除可能的 a/ 或 b/ 前缀（Git diff 格式）
                if file_path.startswith('a/') or file_path.startswith('b/'):
                    file_path = file_path[2:]
                if file_path and file_path not in files:
                    files.append(file_path)
        return files

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
            guidance_parts.append(f"✓ **Latest File Created**: `{latest_file}`")

        # Check execution plan progress
        if state.memory.plan:
            from atloop.memory.plan import PlanManager

            plan_str = PlanManager.plan_to_string(state.memory.plan)
            if plan_str:
                # Count completed steps (marked with ✓)
                completed = plan_str.count("✓")
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
                guidance_parts.append("✓ **Last Command Successful**: Continue with next step")
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

        # 简单实现：保留前面的部分，截断后面的部分
        # 在实际实现中，可以更智能地截断
        return text[:max_length] + "\n... [Content truncated due to length limit]"
