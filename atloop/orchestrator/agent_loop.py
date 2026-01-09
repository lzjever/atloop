"""Agent loop - thin wrapper."""

import logging
from typing import Any, Dict

from atloop.config.models import AtloopConfig, TaskSpec
from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.workflow import Workflow

logger = logging.getLogger(__name__)


class AgentLoop:
    """Agent loop - single responsibility: coordinate workflow execution."""

    def __init__(self, task_spec: TaskSpec, config: AtloopConfig):
        """Initialize agent loop."""
        logger.debug(f"[AgentLoop] Initializing for task: {task_spec.task_id}")
        self.coordinator = WorkflowCoordinator(task_spec, config)
        self.workflow = Workflow(self.coordinator)
        logger.debug("[AgentLoop] Initialization complete")

    def run(self) -> Dict[str, Any]:
        """Run agent - single method."""
        logger.info(f"[AgentLoop] Starting task: {self.coordinator.task_spec.task_id}")
        try:
            result = self.workflow.run()
            status = result.get("status")
            logger.info(f"[AgentLoop] Task completed: status={status}, step={result.get('step')}")
            logger.debug(f"[AgentLoop] Result details: {result}")
            return result
        except Exception as e:
            logger.error(f"[AgentLoop] Task failed: {e}")
            logger.debug(f"[AgentLoop] Exception details: {type(e).__name__}: {e}", exc_info=True)
            return {
                "status": "failure",
                "task_id": self.coordinator.task_spec.task_id,
                "reason": f"Execution error: {e}",
            }
