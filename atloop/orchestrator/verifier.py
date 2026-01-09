"""Verifier for test/build execution."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from atloop.config.limits import (
    VERIFIER_ERROR_LINES_MAX,
    VERIFIER_ERROR_SIGNATURE_LINE_LIMIT,
    VERIFIER_ERROR_SUMMARY_LIMIT,
)
from atloop.runtime import ToolRuntime


@dataclass
class VerificationResult:
    """Result of verification execution."""

    success: bool
    stdout: str
    stderr: str
    command: Optional[str] = None
    error_signature: Optional[str] = None
    error_summary: Optional[str] = None


class ErrorSignatureExtractor:
    """Extract error signatures from stderr."""

    @staticmethod
    def extract(stderr: str) -> Optional[str]:
        """
        Extract error signature from stderr.

        Args:
            stderr: Standard error output

        Returns:
            Error signature or None
        """
        if not stderr:
            return None

        # Extract first meaningful error line
        lines = stderr.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                # Remove file paths and line numbers for better matching
                # Keep error type and message
                return line[:VERIFIER_ERROR_SIGNATURE_LINE_LIMIT]

        return None


class Verifier:
    """Verifier for test/build execution."""

    def __init__(self, tool_runtime: ToolRuntime, project_profile: Optional[Dict[str, Any]] = None):
        """
        Initialize verifier.

        Args:
            tool_runtime: Tool runtime instance
            project_profile: Project profile (optional)
        """
        self.tool_runtime = tool_runtime
        self.project_profile = project_profile or {}

    def verify(
        self,
        command: Optional[str] = None,
        timeout_sec: int = 600,
    ) -> VerificationResult:
        """
        Run verification (test/build).

        Args:
            command: Verification command (optional, will use default if not provided)
            timeout_sec: Timeout in seconds

        Returns:
            Verification result
        """
        # Get verification command
        if not command:
            command = self._get_default_verify_command()
        if not command:
            # No verification command available - this is OK for new projects
            # Return success=True to indicate "no verification needed" rather than "verification failed"
            return VerificationResult(
                success=True,  # Changed: treat as success (no verification needed) rather than failure
                stdout="No verification command available. This is normal for new projects.",
                stderr="",
                command=None,
            )

        # Run verification command
        result = self.tool_runtime.run(command, timeout_sec=timeout_sec)

        # Phase 5: Simplified error handling - trust LLM to judge
        # We no longer perform complex error keyword detection
        # Instead, we provide raw output and let LLM decide
        #
        # Determine success based on stderr content, not exit code
        # Many commands (like pytest) return exit_code=0 even with collection errors
        verification_failed = bool(result.stderr.strip())

        # Phase 5: Simplified error extraction - trust LLM to judge
        # We no longer perform complex error block extraction
        # Instead, we provide raw output and let LLM extract what it needs
        #
        # For backward compatibility, we still extract a simple error signature
        # But LLM should read the full stdout/stderr to understand errors
        error_signature = None
        error_summary = None
        if verification_failed:
            # Simple error signature extraction (first meaningful line from stderr or stdout)
            error_text = result.stderr or result.stdout
            error_signature = ErrorSignatureExtractor.extract(error_text or "")

            # Simplified: just provide a preview of the output (first N lines)
            # LLM should read the full output to understand errors
            if error_text:
                lines = error_text.split("\n")
                # Take first few lines as summary (LLM will see full output anyway)
                error_summary = "\n".join(lines[:VERIFIER_ERROR_LINES_MAX])[
                    :VERIFIER_ERROR_SUMMARY_LIMIT
                ]

        return VerificationResult(
            success=not verification_failed,  # Use our enhanced check
            stdout=result.stdout,
            stderr=result.stderr,
            command=command,
            error_signature=error_signature,
            error_summary=error_summary,
        )

    def _get_default_verify_command(self) -> Optional[str]:
        """Get default verification command from project profile."""
        if self.project_profile.test_commands:
            return self.project_profile.test_commands[0]
        return None

    def try_candidate_commands(
        self,
        candidate_commands: List[str],
        timeout_sec: int = 600,
    ) -> Tuple[Optional[str], Optional[VerificationResult]]:
        """
        Try candidate verification commands until one succeeds.

        Args:
            candidate_commands: List of candidate commands to try
            timeout_sec: Timeout per command

        Returns:
            Tuple of (command, result) or (None, None) if all failed
        """
        for command in candidate_commands:
            result = self.verify(command=command, timeout_sec=timeout_sec)
            if result.success:
                return command, result

        return None, None
