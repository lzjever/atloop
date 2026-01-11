"""Tool result processing utilities for ActPhase."""

import logging
from typing import Any, Dict

from atloop.config.limits import (
    ERROR_SUMMARY_LIMIT_FILE_VIEW,
    ERROR_SUMMARY_LIMIT_NORMAL,
    STDERR_TAIL_LIMIT,
    STDOUT_STDERR_LIMIT_FILE_VIEW,
    STDOUT_STDERR_LIMIT_NORMAL,
    STDOUT_STDERR_LIMIT_OTHER,
    is_file_view_command,
)

logger = logging.getLogger(__name__)


class ToolResultFormatter:
    """Formats tool execution results for LLM consumption."""

    @staticmethod
    def format_result_summary(tool: str, args: Dict[str, Any], result: Dict[str, Any]) -> str:
        """
        Format a tool execution result into a comprehensive summary for LLM.

        Args:
            tool: Tool name
            args: Tool arguments
            result: Tool execution result

        Returns:
            Formatted result summary string
        """
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        error_msg = result.get("error", "")

        parts = []
        parts.append(f"Tool: {tool}")
        parts.append(
            "⚠️ Important: Please carefully read the stdout and stderr content below to determine if the command succeeded."
        )

        if tool == "run":
            cmd = args.get("cmd", "")
            if cmd:
                parts.append(f"Command: {cmd}")

        if error_msg:
            parts.append(f"Error: {error_msg}")

        # Format stderr
        if stderr:
            stderr_preview = ToolResultFormatter._format_output(
                stderr, tool, args, is_stderr=True
            )
            parts.append(f"Stderr ({len(stderr)} chars):\n{stderr_preview}")

        # Format stdout
        if stdout:
            stdout_preview = ToolResultFormatter._format_output(
                stdout, tool, args, is_stderr=False
            )
            parts.append(f"Stdout ({len(stdout)} chars):\n{stdout_preview}")

        return "\n".join(parts)

    @staticmethod
    def _format_output(
        output: str, tool: str, args: Dict[str, Any], is_stderr: bool
    ) -> str:
        """
        Format stdout or stderr output with appropriate limits.

        Args:
            output: Output content
            tool: Tool name
            args: Tool arguments
            is_stderr: Whether this is stderr (True) or stdout (False)

        Returns:
            Formatted output string
        """
        if tool == "run":
            cmd = args.get("cmd", "")
            max_size = (
                STDOUT_STDERR_LIMIT_FILE_VIEW
                if is_file_view_command(cmd)
                else STDOUT_STDERR_LIMIT_NORMAL
            )
        else:
            max_size = STDOUT_STDERR_LIMIT_OTHER

        if len(output) > max_size:
            omitted = len(output) - max_size
            return (
                output[: max_size // 2]
                + f"\n... [omitted {omitted} chars in middle] ...\n"
                + output[-max_size // 2 :]
            )
        return output


class ErrorAnalyzer:
    """Analyzes errors to provide better context and suggestions."""
    
    @staticmethod
    def analyze_error(tool: str, args: Dict[str, Any], result: Dict[str, Any]) -> str:
        """
        Analyze error and provide enhanced context and suggestions.
        
        Args:
            tool: Tool name
            args: Tool arguments
            result: Tool execution result
            
        Returns:
            Enhanced error message with suggestions
        """
        stderr = result.get("stderr", "")
        error_msg = result.get("error", "")
        combined_error = error_msg + "\n" + stderr if error_msg else stderr
        
        suggestions = []
        
        # Detect shell escaping issues
        if tool == "run":
            cmd = args.get("cmd", "")
            if "python3 -c" in cmd or "bash -c" in cmd:
                if "SyntaxError" in stderr or "SyntaxError" in error_msg:
                    if "invalid syntax" in stderr.lower() or "invalid syntax" in error_msg.lower():
                        suggestions.append(
                            "⚠️ **Shell Escaping Issue Detected**: "
                            "The SyntaxError is likely caused by shell escaping problems with quotes/f-strings. "
                            "**Solution**: Use `run_python_script_string` with `PYTHON_SCRIPT_#N` placeholder instead of `run` with `python3 -c`. "
                            "This avoids all shell escaping issues."
                        )
        
        # Detect placeholder-related errors
        if "FILE_CONTENT" in stderr or "placeholder" in stderr.lower():
            suggestions.append(
                "⚠️ **Placeholder Issue**: Check that you're using the correct placeholder type for each tool. "
                "See tool documentation for correct placeholder types."
            )
        
        # Detect import errors that might be path issues
        if "ImportError" in stderr or "ModuleNotFoundError" in stderr:
            if "python3" in str(args.get("cmd", "")):
                suggestions.append(
                    "💡 **Import Error**: If importing local modules, ensure the script runs from the correct directory. "
                    "Consider using `run_python_script_string` which automatically sets up the Python path."
                )
        
        # Combine suggestions with original error
        if suggestions:
            enhanced = "\n\n".join(suggestions) + "\n\n" + "Original Error:\n" + combined_error
            return enhanced
        
        return combined_error


class ErrorStateManager:
    """Manages error state updates in ActPhase."""

    @staticmethod
    def update_error_state(
        state: Any,
        tool: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        result_summary: str,
    ) -> bool:
        """
        Update error state if there's an actual error.

        Args:
            state: Agent state
            tool: Tool name
            args: Tool arguments
            result: Tool execution result
            result_summary: Formatted result summary

        Returns:
            True if error state was updated, False otherwise
        """
        stderr = result.get("stderr", "")
        error_msg = result.get("error", "")
        has_error = bool(error_msg or stderr.strip())

        if not has_error:
            logger.debug(
                f"[ErrorStateManager] Tool {tool} succeeded, preserving existing error state "
                f"(if any): {bool(state.last_error.summary)}"
            )
            return False

        # Determine max summary size
        if tool == "run":
            cmd = args.get("cmd", "")
            max_summary = (
                ERROR_SUMMARY_LIMIT_FILE_VIEW
                if is_file_view_command(cmd)
                else ERROR_SUMMARY_LIMIT_NORMAL
            )
        else:
            max_summary = ERROR_SUMMARY_LIMIT_NORMAL

        # Analyze error for better context
        enhanced_error = ErrorAnalyzer.analyze_error(tool, args, result)
        
        # Update error state with enhanced error message
        if state.last_error.summary and state.last_error.summary.strip():
            # Append to existing error
            separator = "\n\n" + "=" * 80 + "\n"
            # Use enhanced error if available, otherwise use result_summary
            error_content = enhanced_error if enhanced_error != (result.get("error", "") + "\n" + result.get("stderr", "")) else result_summary
            combined = state.last_error.summary + separator + error_content
            state.last_error.summary = combined[:max_summary]
            logger.debug(
                f"[ErrorStateManager] Appended tool error to existing error summary "
                f"(total length: {len(state.last_error.summary)})"
            )
        else:
            # Set new error with enhanced message
            error_content = enhanced_error if enhanced_error != (result.get("error", "") + "\n" + result.get("stderr", "")) else result_summary
            state.last_error.summary = error_content[:max_summary]
            logger.debug(
                f"[ErrorStateManager] Set last_error with enhanced analysis: summary_length={len(state.last_error.summary)}"
            )

        # Update repro command and stderr tail
        if tool == "run":
            cmd = args.get("cmd", "")
            if cmd:
                state.last_error.repro_cmd = cmd

        state.last_error.raw_stderr_tail = stderr[-STDERR_TAIL_LIMIT:] if stderr else ""

        return True


class FileChangeTracker:
    """Tracks file changes and updates state accordingly."""

    @staticmethod
    def track_file_creation(
        state: Any,
        coordinator: Any,
        file_path: str,
        file_content: str,
        modified_files: list,
    ) -> None:
        """
        Track a newly created file and update state.

        Args:
            state: Agent state
            coordinator: Workflow coordinator
            file_path: Path of the created file
            file_content: Content of the file
            modified_files: List to append file_path to
        """
        if not file_path:
            return

        modified_files.append(file_path)

        if file_path not in state.memory.created_files:
            state.memory.created_files.append(file_path)
            logger.info(
                f"[FileChangeTracker] Tracking newly created file: {file_path} "
                f"(total: {len(state.memory.created_files)})"
            )

            # Update current_diff to show file creation
            # Note: Even empty files should have a diff (showing file was created)
            diff_content = FileChangeTracker._create_file_creation_diff(
                file_path, file_content or ""
            )
            state.artifacts.current_diff = diff_content[:5000]  # Limit diff size
            logger.debug(
                f"[FileChangeTracker] Updated current_diff after file creation: {file_path}"
            )

            coordinator.state_manager.save()

    @staticmethod
    def _create_file_creation_diff(file_path: str, file_content: str) -> str:
        """
        Create a diff string showing file creation.

        Args:
            file_path: Path of the created file
            file_content: Content of the file

        Returns:
            Diff-formatted string
        """
        lines = file_content.splitlines()
        diff_content = f"+++ {file_path}\n@@ -0,0 +1,{len(lines)} @@\n"
        for line in lines[:50]:  # First 50 lines
            diff_content += f"+{line}\n"
        if len(lines) > 50:
            diff_content += f"... ({len(lines) - 50} more lines)\n"
        return diff_content
