"""Factory functions for creating test AgentState instances."""

from typing import Any, Dict, List, Optional

from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory


def create_sample_state(
    step: int = 1,
    phase: str = "PLAN",
    task_goal: Optional[str] = None,
    created_files: Optional[List[str]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
    has_error: bool = False,
    stage: str = "early",  # "early", "mid", "late"
) -> AgentState:
    """
    Create a sample AgentState for testing.

    Args:
        step: Current step number
        phase: Current phase
        task_goal: Task goal (optional)
        created_files: List of created files (optional)
        tool_results: List of tool execution results (optional)
        has_error: Whether to include error information
        stage: Stage of task execution ("early", "mid", "late")

    Returns:
        AgentState instance configured for testing
    """
    memory = Memory()

    # Set task summary if task_goal provided
    if task_goal:
        memory.task_summary = f"Task: {task_goal}"

    # Set created files
    if created_files:
        memory.created_files = created_files
    elif stage in ["mid", "late"]:
        memory.created_files = ["generate_data.py"]
        if stage == "late":
            memory.created_files.append("plot_kline.py")

    # Set execution plan
    if stage == "early":
        memory.plan = [
            "检查当前目录和Python环境",
            "检查必要的Python库（如matplotlib, pandas）",
            "创建数据生成脚本",
            "创建绘图脚本",
            "运行脚本生成图表",
        ]
    elif stage == "mid":
        memory.plan = [
            "✓ 检查当前目录和Python环境",
            "✓ 检查必要的Python库",
            "✓ 创建数据生成脚本",
            "创建绘图脚本",
            "运行脚本生成图表",
        ]
    else:  # late
        memory.plan = [
            "✓ 检查当前目录和Python环境",
            "✓ 检查必要的Python库",
            "✓ 创建数据生成脚本",
            "✓ 创建绘图脚本",
            "运行脚本生成图表",
            "验证图表生成",
        ]

    # Set important decisions
    if step >= 2:
        memory.important_decisions = [
            {
                "step": 2,
                "content": "Initial plan created (5 steps)",
                "importance": 0.9,
            }
        ]

    # Set milestones
    if stage in ["mid", "late"]:
        memory.milestones = [
            {
                "step": 7,
                "content": "Created data generation script",
                "importance": 0.8,
            }
        ]
        if stage == "late":
            memory.milestones.append(
                {
                    "step": 10,
                    "content": "Created plotting script",
                    "importance": 0.9,
                }
            )

    # Set tool results history
    if tool_results:
        memory.tool_results_history = tool_results
    else:
        # Create default tool results based on stage
        memory.tool_results_history = _create_default_tool_results(step, stage)

    # Set attempts (without results field, as per new design)
    if step >= 3:
        memory.attempts = [
            {
                "step": step - 1,
                "files": memory.created_files if memory.created_files else [],
                "success": True,
            }
        ]

    # Set decisions
    if step >= 2:
        memory.decisions = [
            {
                "step": step - 1,
                "actions_count": 2,
                "stop_reason": "continue",
                "actions": [
                    {"tool": "run", "args": {"cmd": "python3 --version"}},
                    {"tool": "run", "args": {"cmd": "ls -la"}},
                ],
            }
        ]

    # Set last error if needed
    last_error = LastError()
    if has_error:
        last_error.summary = "FileNotFoundError: Data file 'stock_data.csv' not found"
        last_error.raw_stderr_tail = (
            "Traceback (most recent call last):\n"
            '  File "plot_kline.py", line 1049, in <module>\n'
            "    df = load_stock_data('stock_data.csv')\n"
            "FileNotFoundError: Data file 'stock_data.csv' not found."
        )

    # Set artifacts
    artifacts = Artifacts()
    if stage in ["mid", "late"]:
        artifacts.current_diff = "+++ generate_data.py\n@@ -0,0 +1,85 @@\n+import numpy as np\n..."

    return AgentState(
        step=step,
        phase=phase,
        memory=memory,
        last_error=last_error,
        artifacts=artifacts,
        budget_used=BudgetUsed(llm_calls=step, tool_calls=step * 2),
    )


def _create_default_tool_results(step: int, stage: str) -> List[Dict[str, Any]]:
    """Create default tool results based on stage."""
    results = []

    if step >= 3:
        results.append(
            {
                "step": 3,
                "tool": "run",
                "args": {
                    "cmd": "python3 --version && pip list | grep -E 'matplotlib|pandas|numpy'"
                },
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "Python 3.10.12\nmatplotlib 3.10.8\nnumpy 2.2.6\npandas 2.3.3",
                    "stderr": "",
                },
                "modified_files": [],
            }
        )

        results.append(
            {
                "step": 3,
                "tool": "run",
                "args": {"cmd": "ls -la"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "total 0\ndrwxrwxrwx 2 root root 10 Jan 13 04:54 .",
                    "stderr": "",
                },
                "modified_files": [],
            }
        )

    if stage in ["mid", "late"]:
        results.append(
            {
                "step": 7,
                "tool": "write_file",
                "args": {"path": "generate_data.py"},
                "placeholder": "WRITE_FILE_CONTENT_file:generate_data.py",
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "File created successfully",
                    "stderr": "",
                },
                "modified_files": ["generate_data.py"],
            }
        )

    if stage == "late":
        results.append(
            {
                "step": 10,
                "tool": "write_file",
                "args": {"path": "plot_kline.py"},
                "placeholder": "WRITE_FILE_CONTENT_file:plot_kline.py",
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "File created successfully",
                    "stderr": "",
                },
                "modified_files": ["plot_kline.py"],
            }
        )

        results.append(
            {
                "step": 11,
                "tool": "run",
                "args": {"cmd": "python3 generate_data.py"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "Data saved to stock_data.csv\nGenerated 30 days of OHLC data",
                    "stderr": "",
                },
                "modified_files": [],
            }
        )

    return results


def create_sample_state_with_error(step: int = 12) -> AgentState:
    """Create a sample AgentState with error information."""
    return create_sample_state(
        step=step,
        stage="late",
        has_error=True,
        created_files=["generate_data.py", "plot_kline.py"],
    )
