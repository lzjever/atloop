"""Agent state data structures."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

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
    """Memory for tracking decisions and attempts."""

    decisions: List[Dict[str, Any]] = field(default_factory=list)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    key_files: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)  # Track created files for resume

    # Long-term memory (persists across steps, can be dynamically updated)
    plan: Union[str, List[Any]] = field(
        default_factory=list
    )  # Current execution plan (structured: List[PlanStep], or legacy: str)
    task_summary: str = ""  # Summary of task goal and constraints
    important_decisions: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Important decisions that should be remembered
    milestones: List[Dict[str, Any]] = field(default_factory=list)  # Key milestones achieved
    learnings: List[str] = field(default_factory=list)  # Important learnings from execution

    # Enhanced storage for Memory-Only architecture (Phase 3)
    # Store LLM responses for better history tracking
    llm_responses: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {"step": int, "thought_summary": str, "plan": List[str], "actions": List[Dict], "stop_reason": str, "llm_output": str}

    # Store tool execution results history (separate from attempts for better organization)
    tool_results_history: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {"step": int, "tool": str, "args": Dict, "result": Dict}

    # Auto-read file content after modification (Phase 5)
    modified_files_content: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {
    #     "path": str,
    #     "content": str,  # Full file content
    #     "content_hash": str,  # SHA256 hash for deduplication
    #     "step": int,  # When it was modified
    #     "size": int,  # File size in bytes
    #     "last_modified_step": int,  # Last modification step (for replacement)
    #     "access_count": int,  # How many times this file was referenced in decisions
    #     "importance_score": float,  # Calculated importance (0-1)
    # }

    # Auto-read file content after modification (Phase 5)
    modified_files_content: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {
    #     "path": str,
    #     "content": str,  # Full file content
    #     "content_hash": str,  # SHA256 hash for deduplication
    #     "step": int,  # When it was modified
    #     "size": int,  # File size in bytes
    #     "last_modified_step": int,  # Last modification step (for replacement)
    #     "access_count": int,  # How many times this file was referenced in decisions
    #     "importance_score": float,  # Calculated importance (0-1)
    # }


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
                "decisions": self.memory.decisions,
                "attempts": self.memory.attempts,
                "key_files": self.memory.key_files,
                "notes": self.memory.notes,
                "created_files": self.memory.created_files,
                "plan": (
                    [s.to_dict() if hasattr(s, "to_dict") else s for s in self.memory.plan]
                    if isinstance(self.memory.plan, list)
                    else self.memory.plan
                ),
                "task_summary": self.memory.task_summary,
                "important_decisions": self.memory.important_decisions,
                "milestones": self.memory.milestones,
                "learnings": self.memory.learnings,
                "llm_responses": self.memory.llm_responses,
                "tool_results_history": self.memory.tool_results_history,
                "modified_files_content": self.memory.modified_files_content,
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
            decisions=memory_data.get("decisions", []),
            attempts=memory_data.get("attempts", []),
            key_files=memory_data.get("key_files", []),
            notes=memory_data.get("notes", []),
            created_files=memory_data.get("created_files", []),  # Load created_files
            plan=plan,
            task_summary=memory_data.get("task_summary", ""),
            important_decisions=memory_data.get("important_decisions", []),
            milestones=memory_data.get("milestones", []),
            learnings=memory_data.get("learnings", []),
            llm_responses=memory_data.get("llm_responses", []),
            tool_results_history=memory_data.get("tool_results_history", []),
            modified_files_content=memory_data.get("modified_files_content", []),
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
