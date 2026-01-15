"""Command validator for preventing command injection attacks.

This module provides validation and sanitization for shell commands to prevent
command injection attacks in the sandbox environment.
"""

import logging
import re
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Exception raised for security violations."""

    pass


class CommandValidator:
    """
    Validates shell commands to prevent command injection attacks.

    Uses a combination of:
    - Whitelist of allowed base commands
    - Blacklist of dangerous patterns
    - Sanitization of shell metacharacters
    """

    # Default whitelist of allowed commands
    DEFAULT_ALLOWED_COMMANDS: Set[str] = {
        # File operations
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        "find",
        "locate",
        "diff",
        "file",
        "stat",
        "readlink",
        "realpath",
        "basename",
        "dirname",
        # Text processing
        "sed",
        "awk",
        "cut",
        "sort",
        "uniq",
        "tr",
        "tee",
        # Build tools
        "make",
        "cmake",
        "cargo",
        "npm",
        "yarn",
        "pip",
        "pip3",
        "python",
        "python3",
        "node",
        # Testing
        "pytest",
        "unittest",
        "coverage",
        # Version control
        "git",
        # System
        "which",
        "type",
        "pwd",
        "cd",
        "echo",
        "date",
        "uname",
        # Archives
        "tar",
        "zip",
        "unzip",
        "gzip",
        "gunzip",
    }

    # Dangerous patterns that are never allowed
    BLOCKED_PATTERNS: List[str] = [
        "rm -rf",  # Destructive
        "rm -fr",  # Destructive
        "rm -r",  # Destructive (allow only rm without flags for single files)
        "curl",  # Network access
        "wget",  # Network access
        "nc",  # Network access
        "netcat",  # Network access
        "telnet",  # Network access
        "ssh",  # Network access
        "scp",  # Network access
        "rsync",  # Network access
        "> /dev/",  # Writing to system devices
        ">> /etc/",  # Writing to system config
        "mv ~",  # Moving home directory
        "chmod -R",  # Recursive permission changes
        "chown -R",  # Recursive ownership changes
        ":(){:|:&};:",  # Fork bomb
        "dd if=",  # Disk manipulation
        "mkfs",  # Filesystem creation
        "fdisk",  # Disk partitioning
        "mount",  # Mount operations
        "umount",  # Unmount operations
        "kill -9",  # Force kill (allow with restrictions)
        "killall",  # Kill all processes
        "pkill",  # Kill processes by name
    ]

    # Shell metacharacters that enable command chaining
    DANGEROUS_METACHARS: List[str] = [
        "&&",  # Command chaining
        "||",  # Command chaining
        ";",  # Command separator
        "|",  # Pipe (allow with restrictions)
        "&",  # Background execution
        "`",  # Command substitution
        "$(",  # Command substitution
        "${",  # Variable expansion
        "\n",  # Newline (command separator)
        "\r",  # Carriage return
    ]

    def __init__(
        self,
        allowed_commands: Optional[Set[str]] = None,
        allow_pipes: bool = True,
        allow_redirection: bool = True,
    ):
        """
        Initialize command validator.

        Args:
            allowed_commands: Set of allowed base commands. If None, uses DEFAULT_ALLOWED_COMMANDS.
            allow_pipes: Whether to allow pipe (|) for command chaining
            allow_redirection: Whether to allow output redirection (> , >>)
        """
        self.allowed_commands = allowed_commands or self.DEFAULT_ALLOWED_COMMANDS.copy()
        self.allow_pipes = allow_pipes
        self.allow_redirection = allow_redirection

    def validate(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a shell command for security.

        Args:
            command: Shell command to validate

        Returns:
            Tuple of (is_valid, error_message)

        Raises:
            SecurityError: If command violates security policies
        """
        # Check for blocked patterns first
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in command:
                logger.warning("Blocked dangerous pattern: %s in command", pattern)
                return False, f"Command contains blocked pattern: {pattern}"

        # Check for dangerous metacharacters
        for char in self.DANGEROUS_METACHARACTORS:
            if char in command:
                # Allow pipe if configured
                if char == "|" and self.allow_pipes:
                    continue
                # Allow redirection if configured
                if char in [">", ">>"] and self.allow_redirection:
                    continue
                # Other metachars are always blocked
                logger.warning("Blocked dangerous metacharacter: %s in command", char)
                return False, f"Command contains dangerous metacharacter: {char}"

        # Extract base command (first word)
        base_cmd = self._extract_base_command(command)
        if not base_cmd:
            return False, "Could not extract base command from input"

        # Check if base command is allowed
        if base_cmd not in self.allowed_commands:
            logger.warning(
                "Base command not in whitelist: %s (not in %s)",
                base_cmd,
                sorted(self.allowed_commands),
            )
            return False, f"Command not allowed: {base_cmd}. Allowed commands: {', '.join(sorted(self.allowed_commands))}"

        # Additional checks for specific commands
        if base_cmd == "rm":
            # Only allow 'rm' without recursive flags for single files
            if "-r" in command or "-R" in command or "--recursive" in command:
                return False, "Recursive rm is not allowed (rm -r)"
            if "-f" in command or "--force" in command:
                return False, "Force rm is not allowed (rm -f)"

        if base_cmd == "python" or base_cmd == "python3":
            # Check for potentially dangerous python operations
            if "subprocess" in command and "shell=True" in command:
                return False, "Python subprocess with shell=True is not allowed"

        logger.debug("Command validated successfully: %s", command[:100])
        return True, None

    def _extract_base_command(self, command: str) -> Optional[str]:
        """
        Extract the base command from a command string.

        Args:
            command: Command string

        Returns:
            Base command (first word) or None
        """
        # Remove leading whitespace
        command = command.strip()

        # Handle shell builtins and common patterns
        # Extract first word (base command)
        match = re.match(r"^(\S+)", command)
        if match:
            return match.group(1)

        return None


# Global validator instance with default settings
_default_validator: Optional[CommandValidator] = None


def get_default_validator() -> CommandValidator:
    """Get or create the default command validator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = CommandValidator()
    return _default_validator


def validate_command(
    command: str,
    allowed_commands: Optional[Set[str]] = None,
    allow_pipes: bool = True,
    allow_redirection: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Validate a shell command for security.

    Convenience function that uses the default validator or creates a new one.

    Args:
        command: Shell command to validate
        allowed_commands: Optional set of allowed base commands
        allow_pipes: Whether to allow pipes
        allow_redirection: Whether to allow output redirection

    Returns:
        Tuple of (is_valid, error_message)

    Raises:
        SecurityError: If command violates security policies
    """
    validator = CommandValidator(
        allowed_commands=allowed_commands,
        allow_pipes=allow_pipes,
        allow_redirection=allow_redirection,
    )
    return validator.validate(command)
