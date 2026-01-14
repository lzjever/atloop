"""Tool executor for executing tool calls."""

import logging
import time
from typing import Any, Dict, List

from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.executor.result_adapter import ResultAdapter
from atloop.output.emitter import OutputEventEmitter
from atloop.output.events import ToolCallEvent, ToolResultEvent

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Tool executor for executing tool calls."""

    def __init__(self, coordinator: WorkflowCoordinator):
        """
        Initialize tool executor.

        Args:
            coordinator: Workflow coordinator instance
        """
        self.coordinator = coordinator
        logger.debug("[ToolExecutor] Initialized")

    def execute_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute a list of actions.

        Args:
            actions: List of action dictionaries

        Returns:
            List of tool execution results
        """
        logger.debug(f"[ToolExecutor] Executing {len(actions)} actions")
        results = []

        for i, action in enumerate(actions):
            logger.debug(
                f"[ToolExecutor] Executing action {i + 1}/{len(actions)}: {action.get('tool')}"
            )
            try:
                result = self._execute_action(action)
                results.append(result)
                logger.debug(
                    f"[ToolExecutor] Action {i + 1} completed: success={result.get('success', False)}"
                )
            except Exception as e:
                logger.error(f"[ToolExecutor] Action {i + 1} failed: {e}")
                logger.debug(
                    f"[ToolExecutor] Exception details: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                results.append(
                    ResultAdapter._from_error(
                        action.get("tool", "unknown"),
                        action.get("args", {}),
                        str(e),
                    )
                )

        logger.debug(f"[ToolExecutor] All actions executed: {len(results)} results")
        return results

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single action.

        ToolRegistry.execute() returns ToolResult in all code paths (success,
        unknown tool, or invalid args). ResultAdapter handles conversion to
        unified format, with defensive support for legacy/alternate implementations.

        Args:
            action: Action dictionary with 'tool' and 'args' keys

        Returns:
            Dict with keys: success, tool, args, result, ok, stdout, stderr,
            error, exit_code (format expected by ActPhase and MemorySummarizer)
        """
        tool_name = action.get("tool")
        args = action.get("args", {})

        logger.debug(f"[ToolExecutor] Executing tool: {tool_name} with args: {list(args.keys())}")

        # Get event emitter and context
        event_emitter = OutputEventEmitter()
        state = self.coordinator.state_manager.agent_state
        step = state.step
        task_id = self.coordinator.task_spec.task_id
        tool_id = f"{tool_name}_{step}_{int(time.time() * 1000)}"  # Unique tool ID

        # Emit tool call event
        event_emitter.emit(
            ToolCallEvent(
                step=step,
                task_id=task_id,
                tool_name=tool_name,
                tool_args=args,
                tool_id=tool_id,
            )
        )

        # Execute tool
        start_time = time.time()
        result = self.coordinator.tool_runtime.registry.execute(tool_name, args)
        duration_ms = int((time.time() - start_time) * 1000)

        logger.debug(
            f"[ToolExecutor] Tool execution completed: {tool_name}, "
            f"ok={result.ok if hasattr(result, 'ok') else 'N/A'}"
        )

        # Convert to unified format using ResultAdapter
        action_result = ResultAdapter.to_action_result(tool_name, args, result)

        # Emit tool result event
        event_emitter.emit(
            ToolResultEvent(
                step=step,
                task_id=task_id,
                tool_name=tool_name,
                tool_id=tool_id,
                success=action_result.get("success", False),
                stdout=action_result.get("stdout", "")[:5000],  # Truncate long output
                stderr=action_result.get("stderr", "")[:5000],
                exit_code=action_result.get("exit_code"),
                error=action_result.get("error"),
                duration_ms=duration_ms,
            )
        )

        return action_result
