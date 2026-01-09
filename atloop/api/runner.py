"""Task runner API - single execution method (uses varlord via ConfigLoader)."""

import logging
from typing import Any, Dict, Optional

from atloop.config.loader import ConfigLoader  # Uses varlord internally
from atloop.config.models import Budget, SandboxConfig, TaskSpec
from atloop.orchestrator import AgentLoop

logger = logging.getLogger(__name__)


def load_task_spec(
    goal: str,
    workspace_root: str,
    task_type: str = "bugfix",
    constraints: Optional[list] = None,
    budget: Optional[Dict[str, int]] = None,
) -> TaskSpec:
    """
    Load task specification.

    Args:
        goal: Task goal
        workspace_root: Workspace root directory
        task_type: Task type (bugfix, feature, refactor)
        constraints: Task constraints
        budget: Budget dictionary

    Returns:
        TaskSpec instance
    """
    import uuid
    from pathlib import Path

    task_id = str(uuid.uuid4())
    constraints = constraints or []

    # Get default budget from config
    config = ConfigLoader.get()
    default_budget = config.default_budget

    # Override with provided budget
    if budget:
        budget_obj = Budget(
            max_llm_calls=budget.get("max_llm_calls", default_budget.max_llm_calls),
            max_tool_calls=budget.get("max_tool_calls", default_budget.max_tool_calls),
            max_wall_time_sec=budget.get("max_wall_time_sec", default_budget.max_wall_time_sec),
        )
    else:
        budget_obj = default_budget

    return TaskSpec(
        task_id=task_id,
        goal=goal,
        workspace_root=str(Path(workspace_root).resolve()),
        constraints=constraints,
        budget=budget_obj,
        task_type=task_type,
    )


class TaskRunner:
    """Task runner - single responsibility: execute tasks (uses varlord via ConfigLoader)."""

    def __init__(self, atloop_dir: Optional[str] = None):
        """Initialize runner."""
        logger.debug(f"[TaskRunner] Initializing with atloop_dir: {atloop_dir}")
        self.atloop_dir = atloop_dir
        # Setup config once
        ConfigLoader.setup(atloop_dir=atloop_dir)
        logger.debug("[TaskRunner] Config setup complete")

    def execute(self, task_config: Dict[str, Any], console: bool = False) -> Dict[str, Any]:
        """
        Execute task - single method.

        Args:
            task_config: Task configuration
            console: Whether to show console output

        Returns:
            Execution result
        """
        logger.debug(f"[TaskRunner] Execute called with config: {task_config}, console: {console}")

        try:
            # Get config (uses varlord global config)
            config = ConfigLoader.get()
            logger.debug(f"[TaskRunner] Config loaded: ai={config.ai.completion.model}")

            # Create task spec
            logger.debug("[TaskRunner] Creating task spec")
            task_spec = load_task_spec(
                goal=task_config["goal"],
                workspace_root=task_config["workspace_root"],
                task_type=task_config.get("task_type", "bugfix"),
                constraints=task_config.get("constraints", []),
                budget=task_config.get("budget"),
            )
            logger.debug(f"[TaskRunner] Task spec created: task_id={task_spec.task_id}")

            # Override sandbox config if provided
            if "sandbox" in task_config:
                sandbox_config = SandboxConfig(
                    base_url=task_config["sandbox"].get("base_url"),
                    local_test=task_config["sandbox"].get("local_test", False),
                )
                # Update config with sandbox override
                from dataclasses import replace

                config = replace(config, sandbox=sandbox_config)
                logger.debug(f"[TaskRunner] Sandbox config overridden: {sandbox_config}")

            # Execute
            logger.info("[TaskRunner] Starting agent loop")
            loop = AgentLoop(task_spec, config)
            report = loop.run()
            logger.info(f"[TaskRunner] Agent loop completed: status={report.get('status')}")

            # Sync files back from sandbox to local workspace
            # Required for both local_test and remote modes: files created/modified in sandbox
            # need to be downloaded to local workspace. noxrunner 2.0.0+ provides unified
            # download_workspace() that works correctly for all backends.
            try:
                logger.info("[TaskRunner] Syncing files from sandbox to workspace")
                # AgentLoop -> WorkflowCoordinator -> SandboxAdapter (always present)
                sandbox_adapter = loop.coordinator.sandbox
                # Ensure sandbox is initialized (may not be if loop.run() failed early)
                if not sandbox_adapter._initialized:
                    sandbox_adapter.initialize()

                success = sandbox_adapter.download_workspace(task_spec.workspace_root)
                if success:
                    logger.info(
                        f"[TaskRunner] Files synced successfully from sandbox to {task_spec.workspace_root}"
                    )
                else:
                    logger.warning("[TaskRunner] File sync failed, but continuing")
            except Exception as e:
                logger.error(f"[TaskRunner] Error syncing files from sandbox: {e}")
                logger.debug(
                    f"[TaskRunner] Exception details: {type(e).__name__}: {e}", exc_info=True
                )
                # Don't fail the task if sync fails, but log the error

            return {
                "success": report.get("status") == "success",
                "task_id": task_spec.task_id,
                "status": report.get("status"),
                "report": report,
            }
        except Exception as e:
            logger.error(f"[TaskRunner] Execute failed: {e}")
            logger.debug(f"[TaskRunner] Exception details: {type(e).__name__}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
