"""
Progress Tracker for monitoring task execution progress.

This module tracks concrete, measurable progress indicators to determine
whether the LLM is making forward progress or stuck in a loop.

Design Philosophy:
- Track FACTS only: tool calls, results, file changes
- Do NOT track LLM's interpretations (thought_summary, plans)
- Progress must be quantifiable and objective
"""

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ActionCategory(Enum):
    """Categories of actions for progress tracking."""

    VIEW = "view"  # Reading/viewing operations (cat, head, grep, etc.)
    MODIFY = "modify"  # File modification operations (write_file, edit_file)
    EXECUTE = "execute"  # Code execution operations (run python, node, etc.)
    EXPLORE = "explore"  # Exploration operations (ls, find, pwd)
    OTHER = "other"  # Other operations


@dataclass
class ActionRecord:
    """Record of a single action execution."""

    step: int
    tool: str
    args: Dict[str, Any]
    args_signature: str  # Hash of normalized args for comparison
    category: ActionCategory
    target_file: Optional[str]  # Primary file being operated on
    success: bool
    has_output: bool  # Whether the action produced meaningful output
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step": self.step,
            "tool": self.tool,
            "args": self.args,
            "args_signature": self.args_signature,
            "category": self.category.value,
            "target_file": self.target_file,
            "success": self.success,
            "has_output": self.has_output,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRecord":
        """Create from dictionary."""
        return cls(
            step=data["step"],
            tool=data["tool"],
            args=data.get("args", {}),
            args_signature=data.get("args_signature", ""),
            category=ActionCategory(data.get("category", "other")),
            target_file=data.get("target_file"),
            success=data.get("success", False),
            has_output=data.get("has_output", False),
            timestamp=data.get("timestamp", 0.0),
        )


@dataclass
class ProgressMetrics:
    """Quantifiable progress metrics."""

    files_created: int = 0
    files_modified: int = 0
    commands_executed: int = 0
    tests_run: int = 0
    errors_encountered: int = 0
    errors_fixed: int = 0

    # Pattern analysis
    total_actions: int = 0
    unique_actions: int = 0  # Actions with unique signatures
    repeated_actions: int = 0  # Actions that repeat previous ones
    view_actions: int = 0
    modify_actions: int = 0
    execute_actions: int = 0

    # Ratio metrics
    view_to_modify_ratio: float = 0.0  # High ratio = "view without fix"
    repetition_rate: float = 0.0  # High rate = stuck in loop

    # Streak tracking
    consecutive_view_count: int = 0  # Current streak of view-only actions
    consecutive_same_pattern: int = 0  # Current streak of same action pattern (exact signature)
    consecutive_semantic_pattern: int = 0  # Current streak of same semantic pattern

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "commands_executed": self.commands_executed,
            "tests_run": self.tests_run,
            "errors_encountered": self.errors_encountered,
            "errors_fixed": self.errors_fixed,
            "total_actions": self.total_actions,
            "unique_actions": self.unique_actions,
            "repeated_actions": self.repeated_actions,
            "view_actions": self.view_actions,
            "modify_actions": self.modify_actions,
            "execute_actions": self.execute_actions,
            "view_to_modify_ratio": self.view_to_modify_ratio,
            "repetition_rate": self.repetition_rate,
            "consecutive_view_count": self.consecutive_view_count,
            "consecutive_same_pattern": self.consecutive_same_pattern,
            "consecutive_semantic_pattern": self.consecutive_semantic_pattern,
        }


class ProgressTracker:
    """
    Tracks task execution progress based on concrete, measurable indicators.

    This tracker maintains a history of actions and calculates metrics
    that can be used to detect loops and measure progress.
    """

    # Commands that are considered "view" operations
    VIEW_COMMANDS = {
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "grep",
        "find",
        "ls",
        "wc",
        "file",
        "stat",
    }

    # Commands that are considered "execute" operations
    EXECUTE_COMMANDS = {"python", "python3", "node", "npm", "pytest", "make", "cargo", "go"}

    def __init__(self):
        """Initialize progress tracker."""
        self.action_history: List[ActionRecord] = []
        self.seen_signatures: Set[str] = set()
        self.created_files: Set[str] = set()
        self.modified_files: Set[str] = set()
        self._last_action_signature: Optional[str] = None
        self._consecutive_same_count: int = 0
        self._consecutive_view_count: int = 0
        # Semantic pattern tracking
        self._last_semantic_pattern: Optional[str] = None
        self._consecutive_semantic_pattern_count: int = 0

    def record_action(
        self,
        step: int,
        tool: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        timestamp: float = 0.0,
    ) -> ActionRecord:
        """
        Record an action execution.

        Args:
            step: Current execution step
            tool: Tool name (e.g., "run", "write_file")
            args: Tool arguments
            result: Tool execution result
            timestamp: Execution timestamp

        Returns:
            ActionRecord for the recorded action
        """
        # Categorize the action
        category = self._categorize_action(tool, args)

        # Extract target file
        target_file = self._extract_target_file(tool, args)

        # Generate signature for comparison
        signature = self._generate_signature(tool, args)

        # Determine success and output
        success = result.get("ok", False) or result.get("success", False)
        has_output = bool(result.get("stdout", "").strip())

        # Create record
        record = ActionRecord(
            step=step,
            tool=tool,
            args=args,
            args_signature=signature,
            category=category,
            target_file=target_file,
            success=success,
            has_output=has_output,
            timestamp=timestamp,
        )

        # Update tracking state
        self._update_state(record, signature)

        # Track file changes
        if category == ActionCategory.MODIFY and success and target_file:
            if tool == "write_file" and target_file not in self.modified_files:
                self.created_files.add(target_file)
            self.modified_files.add(target_file)

        # Add to history
        self.action_history.append(record)

        logger.debug(
            f"[ProgressTracker] Recorded action: {tool} (category={category.value}, "
            f"signature={signature[:16]}..., consecutive_same={self._consecutive_same_count})"
        )

        return record

    def _detect_semantic_pattern(self, record: ActionRecord) -> str:
        """
        Detect semantic pattern for an action, not just exact signature.

        This groups similar actions together for better loop detection.
        For example, all "view file" actions viewing the same file are grouped together,
        but viewing different files are considered different patterns.

        Args:
            record: Action record

        Returns:
            Semantic pattern string
        """
        # Group by category and target
        if record.category == ActionCategory.VIEW:
            # For view operations, include target file to distinguish different files
            if record.target_file:
                # Include target file in pattern to distinguish viewing different files
                return f"VIEW:{record.target_file}"
            # For run commands without target file, use tool + command structure
            if record.tool == "run":
                # Extract command structure (first word) for run commands
                cmd = record.args.get("cmd", "")
                first_word = cmd.split()[0] if cmd else "unknown"
                return f"VIEW:run:{first_word}"
            return f"VIEW:{record.tool}"
        elif record.category == ActionCategory.MODIFY:
            # Group by file being modified (different files = different patterns)
            if record.target_file:
                return f"MODIFY:{record.target_file}"
            return f"MODIFY:{record.tool}"
        elif record.category == ActionCategory.EXECUTE:
            # Group by execution type and target
            if record.target_file:
                return f"EXECUTE:{record.tool}:{record.target_file}"
            return f"EXECUTE:{record.tool}"
        elif record.category == ActionCategory.EXPLORE:
            # All exploration is similar (but could be refined)
            return "EXPLORE"
        else:
            return f"OTHER:{record.tool}"

    def _update_state(self, record: ActionRecord, signature: str) -> None:
        """Update internal tracking state."""
        # Track consecutive same patterns (exact signature match)
        if signature == self._last_action_signature:
            self._consecutive_same_count += 1
        else:
            self._consecutive_same_count = 1
            self._last_action_signature = signature

        # Track consecutive semantic patterns
        semantic_pattern = self._detect_semantic_pattern(record)
        if semantic_pattern == self._last_semantic_pattern:
            self._consecutive_semantic_pattern_count += 1
        else:
            self._consecutive_semantic_pattern_count = 1
            self._last_semantic_pattern = semantic_pattern

        # Track consecutive view operations
        if record.category == ActionCategory.VIEW:
            self._consecutive_view_count += 1
        else:
            self._consecutive_view_count = 0

        # Track unique signatures
        self.seen_signatures.add(signature)

    def _categorize_action(self, tool: str, args: Dict[str, Any]) -> ActionCategory:
        """Categorize an action based on tool and args."""
        if tool in ["write_file", "edit_file", "append_file", "multi_edit_file"]:
            return ActionCategory.MODIFY

        if tool in ["read_file", "read_skill_file"]:
            return ActionCategory.VIEW

        # load_skill and load_skill_resource tools are considered VIEW since they're loading information
        if tool in ["load_skill", "load_skill_resource"]:
            return ActionCategory.VIEW

        if tool == "run":
            cmd = args.get("cmd", "")
            cmd_lower = cmd.lower().strip()

            # Get first word of command
            first_word = cmd_lower.split()[0] if cmd_lower else ""

            # Check if it's a view command
            if any(first_word.startswith(vc) for vc in self.VIEW_COMMANDS):
                return ActionCategory.VIEW

            # Check if it's an execute command
            if any(first_word.startswith(ec) for ec in self.EXECUTE_COMMANDS):
                return ActionCategory.EXECUTE

            # Check for exploration commands
            if first_word in {"ls", "find", "pwd", "which", "type", "cd"}:
                return ActionCategory.EXPLORE

            return ActionCategory.EXECUTE  # Default for run commands

        return ActionCategory.OTHER

    def _extract_target_file(self, tool: str, args: Dict[str, Any]) -> Optional[str]:
        """Extract the primary target file from action args."""
        if tool in ["write_file", "read_file", "edit_file", "append_file"]:
            return args.get("path")

        if tool == "run":
            cmd = args.get("cmd", "")
            # Try to extract file from common patterns
            parts = cmd.split()
            for part in parts:
                if part.endswith((".py", ".js", ".ts", ".sh", ".go", ".rs")):
                    return part
                if "/" in part and "." in part.split("/")[-1]:
                    return part

        return None

    def _generate_signature(self, tool: str, args: Dict[str, Any]) -> str:
        """Generate a normalized signature for action comparison."""
        # Normalize args for comparison
        normalized = {"tool": tool}

        if tool == "run":
            # Normalize command: remove variable parts like timestamps
            cmd = args.get("cmd", "")
            # Keep just the command structure
            normalized["cmd_template"] = self._normalize_command(cmd)
        elif tool in ["write_file", "edit_file", "append_file"]:
            # For file operations, track the path but not content
            normalized["path"] = args.get("path", "")
            normalized["operation"] = tool
        else:
            # For other tools, use a subset of args
            # Include common parameter names that identify the action
            for key in ["path", "pattern", "glob", "name", "query", "content"]:
                if key in args:
                    normalized[key] = args[key]

        # Generate hash
        sig_str = str(sorted(normalized.items()))
        return hashlib.md5(sig_str.encode()).hexdigest()

    def _normalize_command(self, cmd: str) -> str:
        """Normalize a command for comparison."""
        # Split and get the command structure
        parts = cmd.strip().split()
        if not parts:
            return ""

        # Keep command and key arguments
        normalized_parts = []
        for i, part in enumerate(parts[:5]):  # First 5 parts
            # Skip variable values (numbers, paths with specific names)
            if part.isdigit():
                normalized_parts.append("<NUM>")
            elif part.startswith("/") or part.startswith("./"):
                # Normalize paths but keep file extensions
                ext = part.split(".")[-1] if "." in part else ""
                normalized_parts.append(f"<PATH>.{ext}" if ext else "<PATH>")
            else:
                normalized_parts.append(part)

        return " ".join(normalized_parts)

    def get_metrics(self, window: Optional[int] = None) -> ProgressMetrics:
        """
        Calculate progress metrics.

        Args:
            window: Optional window size (analyze last N actions).
                    If None, analyze all actions.

        Returns:
            ProgressMetrics with calculated values
        """
        if window:
            actions = self.action_history[-window:]
        else:
            actions = self.action_history

        if not actions:
            return ProgressMetrics()

        # Count by category
        view_count = sum(1 for a in actions if a.category == ActionCategory.VIEW)
        modify_count = sum(1 for a in actions if a.category == ActionCategory.MODIFY)
        execute_count = sum(1 for a in actions if a.category == ActionCategory.EXECUTE)

        # Count unique vs repeated
        seen_in_window = set()
        unique_count = 0
        repeated_count = 0
        for action in actions:
            if action.args_signature in seen_in_window:
                repeated_count += 1
            else:
                unique_count += 1
                seen_in_window.add(action.args_signature)

        # Calculate ratios
        view_to_modify = view_count / max(modify_count, 1)
        repetition_rate = repeated_count / max(len(actions), 1)

        return ProgressMetrics(
            files_created=len(self.created_files),
            files_modified=len(self.modified_files),
            commands_executed=execute_count,
            total_actions=len(actions),
            unique_actions=unique_count,
            repeated_actions=repeated_count,
            view_actions=view_count,
            modify_actions=modify_count,
            execute_actions=execute_count,
            view_to_modify_ratio=view_to_modify,
            repetition_rate=repetition_rate,
            consecutive_view_count=self._consecutive_view_count,
            consecutive_same_pattern=self._consecutive_same_count,
            consecutive_semantic_pattern=self._consecutive_semantic_pattern_count,
        )

    def get_recent_action_signatures(self, count: int = 5) -> List[str]:
        """Get signatures of recent actions for pattern matching."""
        return [a.args_signature for a in self.action_history[-count:]]

    def get_recent_actions_summary(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get summary of recent actions for debugging/logging."""
        return [
            {
                "step": a.step,
                "tool": a.tool,
                "category": a.category.value,
                "target": a.target_file,
                "success": a.success,
            }
            for a in self.action_history[-count:]
        ]

    def reset(self) -> None:
        """Reset tracker state."""
        self.action_history.clear()
        self.seen_signatures.clear()
        self.created_files.clear()
        self.modified_files.clear()
        self._last_action_signature = None
        self._consecutive_same_count = 0
        self._consecutive_view_count = 0
        self._last_semantic_pattern = None
        self._consecutive_semantic_pattern_count = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tracker state for persistence."""
        return {
            "action_history": [a.to_dict() for a in self.action_history],
            "created_files": list(self.created_files),
            "modified_files": list(self.modified_files),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressTracker":
        """Restore tracker from serialized state."""
        tracker = cls()
        tracker.action_history = [ActionRecord.from_dict(a) for a in data.get("action_history", [])]
        tracker.created_files = set(data.get("created_files", []))
        tracker.modified_files = set(data.get("modified_files", []))

        # Rebuild seen signatures
        for action in tracker.action_history:
            tracker.seen_signatures.add(action.args_signature)

        # Rebuild consecutive counts
        if tracker.action_history:
            last_sig = tracker.action_history[-1].args_signature
            tracker._last_action_signature = last_sig

            # Count consecutive same
            count = 0
            for action in reversed(tracker.action_history):
                if action.args_signature == last_sig:
                    count += 1
                else:
                    break
            tracker._consecutive_same_count = count

            # Count consecutive view
            view_count = 0
            for action in reversed(tracker.action_history):
                if action.category == ActionCategory.VIEW:
                    view_count += 1
                else:
                    break
            tracker._consecutive_view_count = view_count

            # Rebuild semantic pattern tracking
            if tracker.action_history:
                last_record = tracker.action_history[-1]
                last_semantic_pattern = tracker._detect_semantic_pattern(last_record)
                tracker._last_semantic_pattern = last_semantic_pattern

                # Count consecutive semantic pattern
                semantic_count = 0
                for action in reversed(tracker.action_history):
                    semantic_pattern = tracker._detect_semantic_pattern(action)
                    if semantic_pattern == last_semantic_pattern:
                        semantic_count += 1
                    else:
                        break
                tracker._consecutive_semantic_pattern_count = semantic_count

        return tracker
