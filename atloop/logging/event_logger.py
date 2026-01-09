"""Event logger for agent execution."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from atloop.config.limits import (
    EVENT_LOGGER_OUTPUT_LIMIT_NORMAL,
    EVENT_LOGGER_PROMPT_PREVIEW_LIMIT,
    LOG_FILE_MAX_SIZE_MB,
)


class EventLogger:
    """Logger for agent execution events in JSONL format."""

    def __init__(self, task_id: str, runs_dir: str = "runs"):
        """
        Initialize event logger.

        Args:
            task_id: Task identifier
            runs_dir: Base directory for runs
        """
        self.task_id = task_id
        self.runs_dir = runs_dir
        self.log_dir = Path(runs_dir) / task_id
        self.log_file = self.log_dir / "events.jsonl"

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Open log file in append mode
        self._file_handle = None
        self._open_log_file()

    def _open_log_file(self):
        """Open log file for writing."""
        if self._file_handle is None or self._file_handle.closed:
            self._file_handle = open(self.log_file, "a", encoding="utf-8")

    def _write_event(self, event_type: str, step: int, data: Dict[str, Any]):
        """
        Write an event to the log file.

        Args:
            event_type: Event type (tool_call, tool_result, llm_call, llm_result, state_change)
            step: Step number
            data: Event data
        """
        event = {
            "t": event_type,
            "step": step,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        # Write as JSONL (one JSON object per line)
        json_line = json.dumps(event, ensure_ascii=False)
        self._file_handle.write(json_line + "\n")
        self._file_handle.flush()  # Ensure immediate write

    def log_tool_call(self, step: int, tool: str, args: Dict[str, Any]):
        """
        Log a tool call event.

        Args:
            step: Step number
            tool: Tool name
            args: Tool arguments
        """
        self._write_event(
            "tool_call",
            step,
            {
                "tool": tool,
                "args": args,
            },
        )

    def log_tool_result(
        self,
        step: int,
        tool: str,
        ok: bool,
        stdout: str = "",
        stderr: str = "",
        error: Optional[str] = None,
    ):
        """
        Log a tool result event.

        Args:
            step: Step number
            tool: Tool name
            ok: Whether the tool call succeeded
            stdout: Standard output
            stderr: Standard error
            error: Error message (if any)
        """
        data = {
            "tool": tool,
            "ok": ok,
        }

        # Truncate long outputs
        max_output_length = EVENT_LOGGER_OUTPUT_LIMIT_NORMAL
        if stdout:
            data["stdout"] = stdout[:max_output_length] + (
                "..." if len(stdout) > max_output_length else ""
            )
        if stderr:
            data["stderr"] = stderr[:max_output_length] + (
                "..." if len(stderr) > max_output_length else ""
            )
        if error:
            data["error"] = error

        self._write_event("tool_result", step, data)

    def log_llm_call(
        self,
        step: int,
        prompt: str,
        tokens_in: Optional[int] = None,
        model: Optional[str] = None,
        store_prompt: bool = True,
    ):
        """
        Log an LLM call event.

        Args:
            step: Step number
            prompt: Prompt text (will be hashed)
            tokens_in: Input token count
            model: Model name
            store_prompt: Whether to store prompt preview (first 2000 chars)
        """
        # Hash prompt to avoid storing full text
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        data = {
            "prompt_hash": prompt_hash,
        }

        # Store prompt preview for debugging (first 2000 chars)
        if store_prompt:
            prompt_preview = prompt[:EVENT_LOGGER_PROMPT_PREVIEW_LIMIT] + (
                "..." if len(prompt) > EVENT_LOGGER_PROMPT_PREVIEW_LIMIT else ""
            )
            data["prompt_preview"] = prompt_preview
            data["prompt_length"] = len(prompt)

        if tokens_in is not None:
            data["tokens_in"] = tokens_in
        if model:
            data["model"] = model

        self._write_event("llm_call", step, data)

    def log_llm_result(
        self,
        step: int,
        actions: list,
        stop_reason: str,
        tokens_out: Optional[int] = None,
        error: Optional[str] = None,
        llm_output: Optional[str] = None,
    ):
        """
        Log an LLM result event.

        Args:
            step: Step number
            actions: List of actions
            stop_reason: Stop reason
            tokens_out: Output token count
            error: Error message (if any)
            llm_output: Full LLM output text (for display)
        """
        data = {
            "actions": actions,
            "stop_reason": stop_reason,
        }

        if tokens_out is not None:
            data["tokens_out"] = tokens_out
        if error:
            data["error"] = error
        if llm_output:
            # Store full LLM output for display (truncate if too long)
            max_output_length = 50000  # 50KB
            data["llm_output"] = llm_output[:max_output_length] + (
                "..." if len(llm_output) > max_output_length else ""
            )

        self._write_event("llm_result", step, data)

    def log_state_change(
        self,
        step: int,
        phase: str,
        state_summary: Optional[Dict[str, Any]] = None,
    ):
        """
        Log a state change event.

        Args:
            step: Step number
            phase: New phase
            state_summary: Optional state summary
        """
        data = {
            "phase": phase,
        }

        if state_summary:
            data["state"] = state_summary

        self._write_event("state_change", step, data)

    def log_verification(
        self,
        step: int,
        success: bool,
        command: str,
        stdout: str = "",
        stderr: str = "",
    ):
        """
        Log a verification result.

        Args:
            step: Step number
            success: Whether verification succeeded
            command: Command executed
            stdout: Standard output
            stderr: Standard error
        """
        data = {
            "success": success,
            "command": command,
        }

        # Truncate long outputs
        max_output_length = 5000
        if stdout:
            data["stdout"] = stdout[:max_output_length] + (
                "..." if len(stdout) > max_output_length else ""
            )
        if stderr:
            data["stderr"] = stderr[:max_output_length] + (
                "..." if len(stderr) > max_output_length else ""
            )

        self._write_event("verification", step, data)

    def log_dod_check(
        self,
        step: int,
        passed: bool,
        checks: List[Dict[str, Any]],
        message: str,
    ):
        """
        Log a Definition of Done check result.

        Args:
            step: Step number
            passed: Whether DoD check passed
            checks: List of check results
            message: DoD check message
        """
        data = {
            "passed": passed,
            "checks": checks,
            "message": message,
        }

        self._write_event("dod_check", step, data)

    def log_decision(
        self,
        step: int,
        stop_reason: str,
        verification_success: Optional[bool],
        reason: str,
    ):
        """
        Log a decision made in PLAN phase.

        Args:
            step: Step number
            stop_reason: Stop reason from LLM (done/continue/fail)
            verification_success: Whether verification succeeded
            reason: Human-readable reason for the decision
        """
        data = {
            "stop_reason": stop_reason,
            "verification_success": verification_success,
            "reason": reason,
        }

        self._write_event("decision", step, data)

    def close(self):
        """Close the log file."""
        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def rotate_log(self, max_size_mb: int = LOG_FILE_MAX_SIZE_MB):
        """
        Rotate log file if it exceeds max size.

        Args:
            max_size_mb: Maximum file size in MB
        """
        if not self.log_file.exists():
            return

        max_size_bytes = max_size_mb * 1024 * 1024
        if self.log_file.stat().st_size > max_size_bytes:
            # Close current file
            self.close()

            # Rename current file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_file = self.log_dir / f"events_{timestamp}.jsonl"
            self.log_file.rename(rotated_file)

            # Open new file
            self._open_log_file()
