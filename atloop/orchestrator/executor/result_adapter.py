"""Result adapter for converting tool execution results to unified format."""

import logging
from typing import Any, Dict

from atloop.tools.base import ToolResult

logger = logging.getLogger(__name__)


class ResultAdapter:
    """Adapter for converting various result types to unified action result format."""

    @staticmethod
    def to_action_result(tool_name: str, args: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """
        Convert tool execution result to unified action result format.

        Supports:
        - ToolResult (primary, from ToolRegistry.execute())
        - Objects with to_dict() method (defensive/legacy)
        - Dict results (defensive/legacy)
        - Other types (error case)

        Args:
            tool_name: Name of the tool that was executed
            args: Arguments passed to the tool
            result: Result from tool execution (ToolResult, dict, or other)

        Returns:
            Dict with keys: success, tool, args, result, ok, stdout, stderr,
            error, exit_code (format expected by ActPhase and MemorySummarizer)
        """
        if isinstance(result, ToolResult):
            return ResultAdapter._from_tool_result(tool_name, args, result)
        elif hasattr(result, "to_dict"):
            return ResultAdapter._from_dict_like(tool_name, args, result.to_dict())
        elif isinstance(result, dict):
            return ResultAdapter._from_dict_like(tool_name, args, result)
        else:
            logger.warning(
                f"[ResultAdapter] Unexpected result type from {tool_name}: {type(result)}"
            )
            return ResultAdapter._from_error(
                tool_name, args, f"Unexpected result type: {type(result)}"
            )

    @staticmethod
    def _from_tool_result(
        tool_name: str, args: Dict[str, Any], result: ToolResult
    ) -> Dict[str, Any]:
        """Convert ToolResult to action result (primary code path)."""
        meta = result.meta or {}
        exit_code = meta.get("exitCode", meta.get("exit_code", -1))
        return {
            "success": result.ok,
            "tool": tool_name,
            "args": args,
            "result": {
                "ok": result.ok,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "meta": meta,
            },
            "ok": result.ok,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.stderr if not result.ok else "",
            "exit_code": exit_code,
        }

    @staticmethod
    def _from_dict_like(
        tool_name: str, args: Dict[str, Any], result_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert dict-like result to action result (defensive/legacy path)."""
        meta = result_dict.get("meta") or result_dict.get("result") or {}
        if isinstance(meta, dict):
            exit_code = meta.get("exitCode", meta.get("exit_code", -1))
        else:
            exit_code = result_dict.get("exit_code", -1)

        return {
            "success": result_dict.get("success", result_dict.get("ok", True)),
            "tool": tool_name,
            "args": args,
            "result": result_dict,
            "ok": result_dict.get("ok", result_dict.get("success", True)),
            "stdout": result_dict.get("stdout", ""),
            "stderr": result_dict.get("stderr", ""),
            "error": result_dict.get("error", ""),
            "exit_code": result_dict.get("exit_code", exit_code),
        }

    @staticmethod
    def _from_error(tool_name: str, args: Dict[str, Any], error_msg: str) -> Dict[str, Any]:
        """Create error result for unexpected failures."""
        return {
            "success": False,
            "tool": tool_name,
            "args": args,
            "result": {"error": error_msg},
            "ok": False,
            "stdout": "",
            "stderr": error_msg,
            "error": error_msg,
            "exit_code": -1,
        }
