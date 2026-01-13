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
        self,
        goal: str,
        workspace_root: Optional[str] = None,
        upload_workspace: Optional[bool] = None,
        budget: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Execute task - single method.

        Args:
            goal: Task goal/prompt
            workspace_root: Workspace root directory (overrides config default)
            upload_workspace: Whether to upload workspace files to sandbox (overrides config default)
            budget: Optional budget override

        Returns:
            Execution result
        """
        logger.debug(
            f"[TaskRunner] Execute called with goal (length: {len(goal)}), "
            f"workspace_root: {workspace_root}, upload_workspace: {upload_workspace}"
        )

        try:
            # Get config (uses varlord global config)
            config = ConfigLoader.get()
            logger.debug(f"[TaskRunner] Config loaded: ai={config.ai.completion.model}")

            # Use workspace_root from parameter or config (defaults to current directory)
            if workspace_root is None:
                workspace_root = config.runtime.workspace_root
                if workspace_root is None:
                    from pathlib import Path

                    workspace_root = str(Path.cwd())
                    logger.debug(f"[TaskRunner] Using current directory as workspace: {workspace_root}")
                else:
                    from pathlib import Path

                    workspace_root = str(Path(workspace_root).resolve())
                    logger.debug(f"[TaskRunner] Using workspace_root from config: {workspace_root}")
            else:
                from pathlib import Path

                workspace_root = str(Path(workspace_root).resolve())
                logger.debug(f"[TaskRunner] Using workspace_root from parameter: {workspace_root}")

            # Use upload_workspace from parameter or config
            if upload_workspace is None:
                upload_workspace = config.runtime.upload_workspace
                logger.debug(f"[TaskRunner] Using upload_workspace from config: {upload_workspace}")
            else:
                logger.debug(f"[TaskRunner] Using upload_workspace from parameter: {upload_workspace}")

            # Create task spec
            logger.debug("[TaskRunner] Creating task spec")
            task_spec = load_task_spec(
                goal=goal,
                workspace_root=workspace_root,
                budget=budget,
            )
            logger.debug(f"[TaskRunner] Task spec created: task_id={task_spec.task_id}")

            # Sandbox session: from config (will fallback to task_id in Coordinator)
            sandbox_session_id = config.sandbox.default_session_id

            # Agent session: from config
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
                logger.info("[TaskRunner] Skipping workspace upload (configure via runtime.upload_workspace)")

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
