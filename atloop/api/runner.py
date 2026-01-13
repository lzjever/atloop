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
    budget: Optional[Dict[str, int]] = None,
) -> TaskSpec:
    """
    Load task specification.

    Args:
        goal: Task goal
        workspace_root: Workspace root directory
        budget: Budget dictionary

    Returns:
        TaskSpec instance
    """
    import uuid
    from pathlib import Path

    task_id = str(uuid.uuid4())

    # Get default budget from config
    config = ConfigLoader.get()
    default_budget = config.runtime.default_budget

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
        budget=budget_obj,
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

    def execute(
        self, task_config: Dict[str, Any], console: bool = False, upload_workspace: bool = False
    ) -> Dict[str, Any]:
        """
        Execute task - single method.

        Args:
            task_config: Task configuration
            console: Whether to show console output
            upload_workspace: Whether to upload workspace files to sandbox before execution

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

            # Sandbox session: from config or task_config override
            sandbox_session_id = task_config.get("sandbox_session_id")
            if not sandbox_session_id:
                # Use config default (will fallback to task_id in Coordinator)
                sandbox_session_id = config.sandbox.default_session_id

            # Agent session: from task_config or config default
            agent_session_id = task_config.get("agent_session_id")
            if not agent_session_id:
                agent_session_id = config.runtime.default_agent_session_id

            # Create agent loop (creates coordinator and sandbox adapter)
            logger.info("[TaskRunner] Creating agent loop")
            loop = AgentLoop(task_spec, config, agent_session_id=agent_session_id)

            # Upload workspace files to sandbox before execution (only if requested)
            if upload_workspace:
                try:
                    logger.info("[TaskRunner] Uploading workspace files to sandbox")
                    sandbox_adapter = loop.coordinator.sandbox
                    if not sandbox_adapter.upload_workspace(task_spec.workspace_root):
                        logger.error("[TaskRunner] Failed to upload workspace to sandbox")
                        return {"success": False, "error": "Failed to upload workspace to sandbox"}
                    logger.info("[TaskRunner] Workspace files uploaded to sandbox successfully")
                except Exception as e:
                    logger.error(f"[TaskRunner] Error uploading workspace: {e}")
                    logger.debug(
                        f"[TaskRunner] Exception details: {type(e).__name__}: {e}", exc_info=True
                    )
                    return {"success": False, "error": f"Failed to upload workspace: {e}"}
            else:
                logger.info("[TaskRunner] Skipping workspace upload (use --upload to enable)")

            # Execute
            logger.info("[TaskRunner] Starting agent loop")
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
