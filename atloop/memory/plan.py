"""Structured plan management for tracking execution progress."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A step in the execution plan."""

    id: str
    description: str
    status: str = "pending"  # "pending", "in_progress", "completed", "skipped", "failed"
    started_at_step: Optional[int] = None
    completed_at_step: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)  # IDs of dependent steps
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "started_at_step": self.started_at_step,
            "completed_at_step": self.completed_at_step,
            "dependencies": self.dependencies,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            status=data.get("status", "pending"),
            started_at_step=data.get("started_at_step"),
            completed_at_step=data.get("completed_at_step"),
            dependencies=data.get("dependencies", []),
            notes=data.get("notes", ""),
        )


class PlanManager:
    """Manager for structured execution plans."""

    @staticmethod
    def update_plan_from_llm(
        state: Any,  # AgentState
        plan_input: Any,  # Can be str, list, or None
    ) -> bool:
        """
        Update structured plan from LLM output.

        Args:
            state: Agent state
            plan_input: Plan from LLM (can be str, list of strings, or None)

        Returns:
            True if plan was updated, False otherwise
        """
        if not plan_input:
            return False

        # Parse plan input
        if isinstance(plan_input, list):
            steps_text = [str(s).strip() for s in plan_input if s]
        elif isinstance(plan_input, str):
            # Try to parse string format (lines or comma-separated)
            if "\n" in plan_input:
                steps_text = [
                    line.strip()
                    for line in plan_input.split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
            elif "," in plan_input:
                steps_text = [s.strip() for s in plan_input.split(",") if s.strip()]
            else:
                steps_text = [plan_input.strip()] if plan_input.strip() else []
        else:
            return False

        if not steps_text:
            return False

        # Get current plan (if exists)
        current_plan = getattr(state.memory, "plan", None)
        if isinstance(current_plan, str):
            # Old format: convert to structured
            current_steps = []
        elif isinstance(current_plan, list):
            if not current_plan:
                current_steps = []
            elif isinstance(current_plan[0], dict):
                # Already structured (list of dicts)
                current_steps = [
                    PlanStep.from_dict(s) if isinstance(s, dict) else s
                    for s in current_plan
                    if isinstance(s, (dict, PlanStep))
                ]
            elif isinstance(current_plan[0], PlanStep):
                # Already structured (list of PlanStep)
                current_steps = current_plan
            else:
                # List of strings or other - treat as empty
                current_steps = []
        else:
            current_steps = []

        # Create or update steps
        new_steps = []
        for i, step_text in enumerate(steps_text):
            step_id = f"step_{i + 1}"

            # Check if step already exists
            existing = next(
                (s for s in current_steps if isinstance(s, PlanStep) and s.id == step_id), None
            )
            if existing:
                # Update description, preserve status if completed
                if existing.status == "completed":
                    # Don't change completed steps (preserve all attributes)
                    new_steps.append(existing)
                else:
                    # Update description for non-completed steps
                    existing.description = step_text
                    new_steps.append(existing)
            else:
                # New step
                new_steps.append(
                    PlanStep(
                        id=step_id,
                        description=step_text,
                        status="pending",
                    )
                )

        # Update plan
        state.memory.plan = new_steps

        # Log update
        logger.info(f"[PlanManager] 📝 更新计划: {len(new_steps)} 个步骤")
        return True

    @staticmethod
    def mark_step_completed(
        state: Any,  # AgentState
        step_id: str,
        notes: str = "",
    ) -> bool:
        """
        Mark a plan step as completed.

        Args:
            state: Agent state
            step_id: Step ID to mark as completed
            notes: Optional notes about completion

        Returns:
            True if step was found and updated, False otherwise
        """
        plan = getattr(state.memory, "plan", None)
        if not isinstance(plan, list):
            return False

        # Find step
        for step in plan:
            if isinstance(step, PlanStep) and step.id == step_id:
                step.status = "completed"
                step.completed_at_step = state.step
                if notes:
                    step.notes = notes
                logger.info(f"[PlanManager] ✅ 标记步骤完成: {step_id} - {step.description[:50]}")
                return True

        return False

    @staticmethod
    def mark_step_in_progress(
        state: Any,  # AgentState
        step_id: str,
    ) -> bool:
        """
        Mark a plan step as in progress.

        Args:
            state: Agent state
            step_id: Step ID to mark as in progress

        Returns:
            True if step was found and updated, False otherwise
        """
        plan = getattr(state.memory, "plan", None)
        if not isinstance(plan, list):
            return False

        # Find step
        for step in plan:
            if isinstance(step, PlanStep) and step.id == step_id:
                if step.status == "pending":
                    step.status = "in_progress"
                    step.started_at_step = state.step
                    logger.info(
                        f"[PlanManager] 🔄 标记步骤进行中: {step_id} - {step.description[:50]}"
                    )
                    return True

        return False

    @staticmethod
    def get_progress(state: Any) -> Dict[str, Any]:
        """
        Get plan progress statistics.

        Args:
            state: Agent state

        Returns:
            Progress statistics dictionary
        """
        plan = getattr(state.memory, "plan", None)
        if not isinstance(plan, list):
            return {
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "pending": 0,
                "completion_rate": 0.0,
            }

        # Count by status
        total = len(plan)
        completed = sum(1 for s in plan if isinstance(s, PlanStep) and s.status == "completed")
        in_progress = sum(1 for s in plan if isinstance(s, PlanStep) and s.status == "in_progress")
        pending = sum(1 for s in plan if isinstance(s, PlanStep) and s.status == "pending")

        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "completion_rate": completed / total if total > 0 else 0.0,
        }

    @staticmethod
    def plan_to_string(plan: Any) -> str:
        """
        Convert plan to string representation.

        Args:
            plan: Plan (can be str, list, or List[PlanStep])

        Returns:
            String representation
        """
        if isinstance(plan, str):
            return plan
        elif isinstance(plan, list):
            if not plan:
                return ""

            # Check if it's structured (PlanStep objects or dicts)
            if isinstance(plan[0], PlanStep):
                lines = []
                for step in plan:
                    status_icon = {
                        "completed": "✅",
                        "in_progress": "🔄",
                        "pending": "⏳",
                        "skipped": "⏭️",
                        "failed": "❌",
                    }.get(step.status, "⏳")
                    lines.append(f"{status_icon} {step.description}")
                return "\n".join(lines)
            elif isinstance(plan[0], dict):
                # Dict format
                lines = []
                for step_dict in plan:
                    status = step_dict.get("status", "pending")
                    description = step_dict.get("description", step_dict.get("id", "Unknown"))
                    status_icon = {
                        "completed": "✅",
                        "in_progress": "🔄",
                        "pending": "⏳",
                        "skipped": "⏭️",
                        "failed": "❌",
                    }.get(status, "⏳")
                    lines.append(f"{status_icon} {description}")
                return "\n".join(lines)
            else:
                # List of strings
                return "\n".join(str(s) for s in plan)
        else:
            return str(plan) if plan else ""
