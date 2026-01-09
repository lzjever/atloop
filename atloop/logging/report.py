"""Report generation for agent execution."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from atloop.config.limits import (
    REPORT_DIFF_LIMIT,
    REPORT_STDERR_LIMIT,
    REPORT_TEST_RESULTS_LIMIT,
)
from atloop.logging.replay import EventReplay


class ReportGenerator:
    """Generate execution reports from events."""

    def __init__(self, events_file: Path):
        """
        Initialize report generator.

        Args:
            events_file: Path to events.jsonl file
        """
        self.replay = EventReplay(events_file)

    def generate_success_report(
        self,
        task_id: str,
        goal: str,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate success report.

        Args:
            task_id: Task identifier
            goal: Task goal
            summary: Optional summary text

        Returns:
            Success report dictionary
        """
        final_state = self.replay.get_final_state()
        reproduce_commands = self.replay.get_reproduce_commands()
        diff = self.replay.get_final_diff()
        test_results = self.replay.get_test_results()

        # Get statistics
        tool_calls = self.replay.get_tool_calls()
        llm_calls = self.replay.get_llm_calls()

        report = {
            "status": "success",
            "task_id": task_id,
            "goal": goal,
            "timestamp": datetime.now().isoformat(),
            "final_step": final_state.get("step", 0) if final_state else 0,
            "final_phase": final_state.get("phase", "DONE") if final_state else "DONE",
            "summary": summary or "任务成功完成",
            "statistics": {
                "total_events": len(self.replay.events),
                "tool_calls": len(tool_calls),
                "llm_calls": len(llm_calls),
            },
            "reproduce_commands": reproduce_commands,
            "diff": diff,
            "test_results": test_results,
        }

        return report

    def generate_failure_report(
        self,
        task_id: str,
        goal: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate failure report.

        Args:
            task_id: Task identifier
            goal: Task goal
            reason: Failure reason

        Returns:
            Failure report dictionary
        """
        final_state = self.replay.get_final_state()
        reproduce_commands = self.replay.get_reproduce_commands()
        diff = self.replay.get_final_diff()

        # Get failed tool calls
        tool_results = self.replay.get_tool_results()
        failed_tools = [r for r in tool_results if not r.get("ok", True)]

        # Get attempted paths (from tool calls)
        tool_calls = self.replay.get_tool_calls()
        attempted_actions = [
            {
                "step": call.get("step", 0),
                "tool": call.get("tool", ""),
                "args": call.get("args", {}),
            }
            for call in tool_calls
        ]

        # Get error information from last failed tool result
        last_error = None
        if failed_tools:
            last_failed = failed_tools[-1]
            last_error = {
                "tool": last_failed.get("tool", ""),
                "error": last_failed.get("error", ""),
                "stderr": last_failed.get("stderr", ""),
                "exit_code": last_failed.get("exit_code", -1),
            }

        report = {
            "status": "failure",
            "task_id": task_id,
            "goal": goal,
            "timestamp": datetime.now().isoformat(),
            "final_step": final_state.get("step", 0) if final_state else 0,
            "final_phase": final_state.get("phase", "FAIL") if final_state else "FAIL",
            "reason": reason or "任务执行失败",
            "last_error": last_error,
            "attempted_actions": attempted_actions[-10:],  # Last 10 attempts
            "failed_tool_calls": len(failed_tools),
            "reproduce_commands": reproduce_commands,
            "current_diff": diff,
        }

        return report

    def generate_markdown_report(
        self,
        report: Dict[str, Any],
        output_file: Optional[Path] = None,
    ) -> str:
        """
        Generate markdown format report.

        Args:
            report: Report dictionary
            output_file: Optional output file path

        Returns:
            Markdown report string
        """
        status = report.get("status", "unknown")
        task_id = report.get("task_id", "unknown")
        goal = report.get("goal", "")
        timestamp = report.get("timestamp", "")

        lines = []
        lines.append("# atloop Agent 执行报告")
        lines.append("")
        lines.append(f"**任务ID**: {task_id}")
        lines.append(f"**目标**: {goal}")
        lines.append(f"**状态**: {status.upper()}")
        lines.append(f"**生成时间**: {timestamp}")
        lines.append("")

        if status == "success":
            lines.append("## ✅ 执行成功")
            lines.append("")
            summary = report.get("summary", "")
            if summary:
                lines.append(f"**摘要**: {summary}")
                lines.append("")

            # Statistics
            stats = report.get("statistics", {})
            if stats:
                lines.append("### 执行统计")
                lines.append("")
                lines.append(f"- 总事件数: {stats.get('total_events', 0)}")
                lines.append(f"- 工具调用: {stats.get('tool_calls', 0)}")
                lines.append(f"- LLM调用: {stats.get('llm_calls', 0)}")
                lines.append("")

            # Reproduce commands
            commands = report.get("reproduce_commands", [])
            if commands:
                lines.append("### 复现命令")
                lines.append("")
                for cmd in commands:
                    lines.append("```bash")
                    lines.append(cmd)
                    lines.append("```")
                lines.append("")

            # Diff
            diff = report.get("diff", "")
            if diff:
                lines.append("### 代码变更 (Diff)")
                lines.append("")
                lines.append("```diff")
                lines.append(diff[:5000])  # Limit diff size
                if len(diff) > 5000:
                    lines.append("\n... (diff truncated)")
                lines.append("```")
                lines.append("")

            # Test results
            test_results = report.get("test_results", "")
            if test_results:
                lines.append("### 测试结果")
                lines.append("")
                lines.append("```")
                lines.append(test_results[:REPORT_TEST_RESULTS_LIMIT])
                if len(test_results) > REPORT_TEST_RESULTS_LIMIT:
                    lines.append("\n... (test results truncated)")
                lines.append("```")
                lines.append("")

        else:  # failure
            lines.append("## ❌ 执行失败")
            lines.append("")
            reason = report.get("reason", "")
            if reason:
                lines.append(f"**失败原因**: {reason}")
                lines.append("")

            # Last error
            last_error = report.get("last_error")
            if last_error:
                lines.append("### 最后错误")
                lines.append("")
                lines.append(f"- **工具**: {last_error.get('tool', 'unknown')}")
                if last_error.get("error"):
                    lines.append(f"- **错误**: {last_error['error']}")
                if last_error.get("exit_code") is not None:
                    lines.append(f"- **退出码**: {last_error['exit_code']}")
                if last_error.get("stderr"):
                    lines.append("- **错误输出**:")
                    lines.append("```")
                    lines.append(last_error["stderr"][:REPORT_STDERR_LIMIT])
                    if len(last_error["stderr"]) > REPORT_STDERR_LIMIT:
                        lines.append("\n... (stderr truncated)")
                    lines.append("```")
                lines.append("")

            # Attempted actions
            attempted = report.get("attempted_actions", [])
            if attempted:
                lines.append("### 已尝试的操作")
                lines.append("")
                for action in attempted[-5:]:  # Last 5
                    lines.append(f"- Step {action.get('step', 0)}: {action.get('tool', 'unknown')}")
                lines.append("")

            # Reproduce commands
            commands = report.get("reproduce_commands", [])
            if commands:
                lines.append("### 复现命令")
                lines.append("")
                for cmd in commands:
                    lines.append("```bash")
                    lines.append(cmd)
                    lines.append("```")
                lines.append("")

            # Current diff
            diff = report.get("current_diff", "")
            if diff:
                lines.append("### 当前代码变更 (Diff)")
                lines.append("")
                lines.append("```diff")
                lines.append(diff[:REPORT_DIFF_LIMIT])
                if len(diff) > REPORT_DIFF_LIMIT:
                    lines.append("\n... (diff truncated)")
                lines.append("```")
                lines.append("")

        markdown = "\n".join(lines)

        # Write to file if specified
        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(markdown)

        return markdown
