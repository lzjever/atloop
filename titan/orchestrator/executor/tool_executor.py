"""Tool executor for executing tool calls."""

import logging
from typing import Any, Dict, List

from titan.orchestrator.coordinator import WorkflowCoordinator

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
        logger.debug(f"[ToolExecutor] Initialized")

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
            logger.debug(f"[ToolExecutor] Executing action {i+1}/{len(actions)}: {action.get('tool')}")
            try:
                result = self._execute_action(action)
                results.append(result)
                logger.debug(f"[ToolExecutor] Action {i+1} completed: success={result.get('success', False)}")
            except Exception as e:
                logger.error(f"[ToolExecutor] Action {i+1} failed: {e}")
                logger.debug(f"[ToolExecutor] Exception details: {type(e).__name__}: {e}", exc_info=True)
                results.append({
                    "success": False,
                    "error": str(e),
                    "action": action,
                })

        logger.debug(f"[ToolExecutor] All actions executed: {len(results)} results")
        return results

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single action.
        
        Args:
            action: Action dictionary
            
        Returns:
            Tool execution result
        """
        tool_name = action.get("tool")
        args = action.get("args", {})
        
        logger.debug(f"[ToolExecutor] Executing tool: {tool_name} with args: {list(args.keys())}")

        # Execute tool via tool_runtime registry
        result = self.coordinator.tool_runtime.registry.execute(tool_name, args)
        logger.debug(f"[ToolExecutor] Tool execution completed: {tool_name}")

        # Convert result to dict
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        elif isinstance(result, dict):
            result_dict = result
        else:
            result_dict = {"result": str(result)}

        return {
            "success": result_dict.get("success", True),
            "tool": tool_name,
            "args": args,
            "result": result_dict,
            "ok": result_dict.get("ok", result_dict.get("success", True)),
            "stdout": result_dict.get("stdout", ""),
            "stderr": result_dict.get("stderr", ""),
            "error": result_dict.get("error", ""),
        }
