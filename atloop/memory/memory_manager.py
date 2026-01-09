"""Memory manager for dynamic memory updates."""

import logging
from typing import Any, Dict, Optional

from atloop.memory.state import AgentState

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manager for dynamic memory updates."""

    @staticmethod
    def update_plan(state: AgentState, plan: str, reason: Optional[str] = None) -> None:
        """
        Update the execution plan in long-term memory.

        Args:
            state: Agent state
            plan: New plan text
            reason: Optional reason for the update
        """
        old_plan = state.memory.plan
        state.memory.plan = plan
        if reason:
            logger.info(f"[MemoryManager] 📝 更新计划 (原因: {reason}): {plan[:100]}...")
        else:
            logger.info(f"[MemoryManager] 📝 更新计划: {plan[:100]}...")

        # Log the change
        if old_plan:
            logger.debug(f"[MemoryManager] 旧计划: {old_plan[:100]}...")

    @staticmethod
    def add_important_decision(
        state: AgentState,
        content: str,
        step: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an important decision to long-term memory.

        Args:
            state: Agent state
            content: Decision content
            step: Step number (defaults to current step)
            context: Optional context information
        """
        decision = {
            "step": step if step is not None else state.step,
            "content": content,
            "context": context or {},
        }
        state.memory.important_decisions.append(decision)

        # Keep only last 20 important decisions
        if len(state.memory.important_decisions) > 20:
            state.memory.important_decisions = state.memory.important_decisions[-20:]

        logger.info(f"[MemoryManager] 🎯 记录重要决策: {content[:100]}...")

    @staticmethod
    def add_milestone(
        state: AgentState,
        content: str,
        step: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a milestone to long-term memory.

        Args:
            state: Agent state
            content: Milestone content
            step: Step number (defaults to current step)
            context: Optional context information
        """
        milestone = {
            "step": step if step is not None else state.step,
            "content": content,
            "context": context or {},
        }
        state.memory.milestones.append(milestone)

        # Keep only last 20 milestones
        if len(state.memory.milestones) > 20:
            state.memory.milestones = state.memory.milestones[-20:]

        logger.info(f"[MemoryManager] 🏆 记录里程碑: {content[:100]}...")

    @staticmethod
    def add_learning(
        state: AgentState,
        learning: str,
        step: Optional[int] = None,
    ) -> None:
        """
        Add a learning to long-term memory.

        Args:
            state: Agent state
            learning: Learning content
            step: Step number (defaults to current step)
        """
        learning_entry = f"[Step {step if step is not None else state.step}] {learning}"
        state.memory.learnings.append(learning_entry)

        # Keep only last 10 learnings
        if len(state.memory.learnings) > 10:
            state.memory.learnings = state.memory.learnings[-10:]

        logger.info(f"[MemoryManager] 💡 记录经验: {learning[:100]}...")

    @staticmethod
    def update_task_summary(
        state: AgentState,
        summary: str,
    ) -> None:
        """
        Update task summary in long-term memory.

        Args:
            state: Agent state
            summary: Task summary text
        """
        old_summary = state.memory.task_summary
        state.memory.task_summary = summary
        logger.info(f"[MemoryManager] 📋 更新任务概览: {summary[:100]}...")

        if old_summary:
            logger.debug(f"[MemoryManager] 旧概览: {old_summary[:100]}...")

    @staticmethod
    def get_long_term_memory_summary(state: AgentState) -> str:
        """
        Get a summary of long-term memory.

        Args:
            state: Agent state

        Returns:
            Summary string
        """
        parts = []

        if state.memory.task_summary:
            parts.append(f"任务: {state.memory.task_summary[:100]}")

        if state.memory.plan:
            plan_preview = (
                state.memory.plan[:100] + "..."
                if len(state.memory.plan) > 100
                else state.memory.plan
            )
            parts.append(f"计划: {plan_preview}")

        if state.memory.important_decisions:
            parts.append(f"重要决策: {len(state.memory.important_decisions)} 个")

        if state.memory.milestones:
            parts.append(f"里程碑: {len(state.memory.milestones)} 个")

        if state.memory.learnings:
            parts.append(f"经验: {len(state.memory.learnings)} 条")

        return " | ".join(parts) if parts else "无长期记忆"
