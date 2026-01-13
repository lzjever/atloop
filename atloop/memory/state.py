"""Agent state data structures."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    pass  # AgentState is defined in this file, no need to import

# Import PlanStep for type hints (avoid circular import)
try:
    from atloop.memory.plan import PlanStep
except ImportError:
    PlanStep = Any  # Fallback for type hints


@dataclass
class LastError:
    """Last error information."""

    summary: str = ""
    repro_cmd: str = ""
    raw_stderr_tail: str = ""
    error_signature: str = ""  # Hash of key error lines


@dataclass
class Memory:
    """Memory for tracking decisions and attempts.
    
    Memory is organized into three categories:
    
    1. FACTS (used for LLM context):
       - created_files, modified_files_content, tool_results_history
       - These are objective, verifiable facts from tool execution
       
    2. LONG-TERM (used for LLM context):
       - plan, task_summary, milestones, learnings
       - These are validated/verified information
       
    3. DEBUG-ONLY (NOT fed back to LLM):
       - decisions, llm_responses
       - These contain LLM's interpretations which could cause feedback loops
    
    Memory 模块负责：
    - ✅ 原始数据的存储和管理
    - ✅ 各个条目的格式转换和控制输出（考虑约束：单条长度、字符串映射等）
    - ✅ 提供统一的格式化接口，返回可直接注入 prompt 的字符串
    
    Memory 模块不负责：
    - ❌ 数据压缩（由独立的 CompressionPolicy 负责）
    - ❌ 数据重要性评分（由独立的 Scorer 负责，如果使用）
    """

    # =========================================================================
    # FACTS - Objective data from tool execution (fed to LLM)
    # =========================================================================
    created_files: List[str] = field(default_factory=list)  # Track created files
    attempts: List[Dict[str, Any]] = field(default_factory=list)  # Tool execution attempts
    key_files: List[Dict[str, Any]] = field(default_factory=list)  # Key files identified
    notes: List[str] = field(default_factory=list)  # Factual notes
    
    # Store tool execution results history
    tool_results_history: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {"step": int, "tool": str, "args": Dict, "result": Dict}
    
    # Auto-read file content after modification
    modified_files_content: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {"path": str, "content": str, "content_hash": str, ...}
    
    # =========================================================================
    # PROGRESS TRACKING - For loop detection (fed to LLM as metrics only)
    # =========================================================================
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {"step": int, "tool": str, "category": str, "signature": str, ...}
    # This is serialized from ProgressTracker for persistence

    # =========================================================================
    # LONG-TERM MEMORY - Validated information (fed to LLM)
    # =========================================================================
    plan: Union[str, List[Any]] = field(default_factory=list)
    task_summary: str = ""
    important_decisions: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    learnings: List[str] = field(default_factory=list)
    
    # Skill cache for lazy loading of skill resources
    # Format:
    # {
    #     "skill_name": {
    #         "metadata": {
    #             "name": str,
    #             "description": str,
    #             "body": str,  # SKILL.md body
    #             "loaded_at_step": int
    #         },
    #         "resources": {
    #             "scripts": Dict[str, Dict[str, Any]],  # {filename: {content, loaded_at_step}}
    #             "references": Dict[str, Dict[str, Any]],
    #             "assets": Dict[str, Dict[str, Any]]  # May not cache binary content
    #         }
    #     }
    # }
    skill_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # =========================================================================
    # PARTIALLY VISIBLE - Facts only (NOT fully DEBUG-ONLY)
    # =========================================================================
    # decisions: Partially visible to LLM - only factual information is shown
    #   - ✅ Visible: step, actions_count, tools_used, stop_reason
    #   - ❌ NOT visible: current_step_thoughts, plan, llm_output
    #   - Purpose: Provide context about what was done, without LLM's thinking process
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    # NOTE: Contains current_step_thoughts - this field is NOT shown to LLM
    #       Only factual information (tools, actions, stop_reason) is shown in MemorySummary

    # =========================================================================
    # DEBUG-ONLY - LLM interpretations (NOT fed back to LLM)
    # =========================================================================
    # llm_responses: Completely invisible to LLM - only for debugging/logging
    llm_responses: List[Dict[str, Any]] = field(default_factory=list)
    # WARNING: Contains current_step_thoughts - DO NOT feed back to LLM
    # Format: {"step": int, "current_step_thoughts": str, "plan": List[str], ...}

    def get_formatted_context(
        self,
        state: "AgentState",
        task_goal: Optional[str] = None,
        max_length: Optional[int] = None,
        format_options: Optional[Dict[str, Any]] = None,
        tool_registry: Optional[Any] = None,
    ) -> str:
        """
        获取格式化后的记忆上下文，可直接注入到 prompt 中。
        
        这是 Memory 模块的主要输出接口，返回格式化的字符串。
        
        Args:
            state: AgentState 实例（需要访问 memory, last_error, artifacts）
            task_goal: 任务目标（可选，用于任务概览）
            max_length: 最大长度限制（可选）
            format_options: 格式选项
                - tool_results_count: int (默认 5)
                - steps_summary_count: int (默认 3)
                - include_file_content: bool (默认 True)
                - max_file_content_length: int (默认 20000)
                - string_mappings: Dict[str, str] (字符串映射规则)
            tool_registry: 工具注册表（用于输出限制策略）
        
        Returns:
            格式化后的字符串，可直接用于 prompt 注入
            格式：符合 MEMORY_PROMPT_FORMAT_DEMO.md 中定义的格式
        """
        from atloop.memory.formatter import MemoryFormatter

        formatter = MemoryFormatter(tool_registry=tool_registry)

        # 合并 format_options 和 max_length
        options = format_options or {}
        if max_length:
            options["max_length"] = max_length

        return formatter.format(state, task_goal=task_goal, format_options=options)


@dataclass
class Artifacts:
    """Artifacts produced during execution."""

    current_diff: str = ""
    test_results: str = ""
    verification_success: Optional[bool] = None  # Latest verification result
    dod_result: Optional[Any] = None  # DoD check result (for reporting, not stopping)


@dataclass
class BudgetUsed:
    """Budget usage tracking."""

    llm_calls: int = 0
    tool_calls: int = 0
    wall_time_sec: int = 0


@dataclass
class AgentState:
    """Agent execution state."""

    step: int = 0
    phase: str = "DISCOVER"  # DISCOVER, PLAN, ACT, VERIFY, DONE, FAIL
    last_error: LastError = field(default_factory=LastError)
    memory: Memory = field(default_factory=Memory)
    artifacts: Artifacts = field(default_factory=Artifacts)
    budget_used: BudgetUsed = field(default_factory=BudgetUsed)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step": self.step,
            "phase": self.phase,
            "last_error": {
                "summary": self.last_error.summary,
                "repro_cmd": self.last_error.repro_cmd,
                "raw_stderr_tail": self.last_error.raw_stderr_tail,
                "error_signature": self.last_error.error_signature,
            },
            "memory": {
                # Facts
                "created_files": self.memory.created_files,
                "attempts": self.memory.attempts,
                "key_files": self.memory.key_files,
                "notes": self.memory.notes,
                "tool_results_history": self.memory.tool_results_history,
                "modified_files_content": self.memory.modified_files_content,
                # Progress tracking
                "action_history": self.memory.action_history,
                # Long-term memory
                "plan": (
                    [s.to_dict() if hasattr(s, "to_dict") else s for s in self.memory.plan]
                    if isinstance(self.memory.plan, list)
                    else self.memory.plan
                ),
                "task_summary": self.memory.task_summary,
                "important_decisions": self.memory.important_decisions,
                "milestones": self.memory.milestones,
                "learnings": self.memory.learnings,
                # Debug-only (preserved for logging, NOT fed to LLM)
                "decisions": self.memory.decisions,
                "llm_responses": self.memory.llm_responses,
            },
            "artifacts": {
                "current_diff": self.artifacts.current_diff,
                "test_results": self.artifacts.test_results,
                "dod_result": (
                    {
                        "passed": self.artifacts.dod_result.passed,
                        "checks": self.artifacts.dod_result.checks,
                        "message": self.artifacts.dod_result.message,
                    }
                    if self.artifacts.dod_result
                    else None
                ),
            },
            "budget_used": {
                "llm_calls": self.budget_used.llm_calls,
                "tool_calls": self.budget_used.tool_calls,
                "wall_time_sec": self.budget_used.wall_time_sec,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Create from dictionary."""
        last_error = LastError(**data.get("last_error", {}))
        memory_data = data.get("memory", {})

        # Handle plan: can be string or list of dicts (structured)
        plan_data = memory_data.get("plan", [])
        if isinstance(plan_data, str):
            plan = plan_data
        elif isinstance(plan_data, list):
            # Structured format: convert dicts to PlanStep objects
            try:
                from atloop.memory.plan import PlanStep

                plan = [PlanStep.from_dict(s) if isinstance(s, dict) else s for s in plan_data]
            except ImportError:
                # Fallback: keep as list of dicts
                plan = plan_data
        else:
            plan = []

        memory = Memory(
            # Facts
            created_files=memory_data.get("created_files", []),
            attempts=memory_data.get("attempts", []),
            key_files=memory_data.get("key_files", []),
            notes=memory_data.get("notes", []),
            tool_results_history=memory_data.get("tool_results_history", []),
            modified_files_content=memory_data.get("modified_files_content", []),
            # Progress tracking
            action_history=memory_data.get("action_history", []),
            # Long-term memory
            plan=plan,
            task_summary=memory_data.get("task_summary", ""),
            important_decisions=memory_data.get("important_decisions", []),
            milestones=memory_data.get("milestones", []),
            learnings=memory_data.get("learnings", []),
            # Debug-only
            decisions=memory_data.get("decisions", []),
            llm_responses=memory_data.get("llm_responses", []),
        )
        artifacts = Artifacts(**data.get("artifacts", {}))
        budget_used = BudgetUsed(**data.get("budget_used", {}))

        return cls(
            step=data.get("step", 0),
            phase=data.get("phase", "DISCOVER"),
            last_error=last_error,
            memory=memory,
            artifacts=artifacts,
            budget_used=budget_used,
        )
