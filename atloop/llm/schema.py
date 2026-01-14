"""Action JSON schema definition and validation."""

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from atloop.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Try to import optional JSON repair libraries
try:
    from json_repair import repair_json

    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False
    logger.debug("json-repair not available, will use fallback JSON repair methods")

try:
    import json5

    JSON5_AVAILABLE = True
except ImportError:
    JSON5_AVAILABLE = False
    logger.debug("json5 not available, will use standard JSON parsing only")

# Action JSON Schema
# Note: Tool enum is now dynamic - generated from ToolRegistry at runtime
# This schema is used for JSON structure validation only, not tool enumeration
ACTION_JSON_SCHEMA = {
    "type": "object",
    "required": ["actions", "stop_reason"],
    "properties": {
        "current_step_thoughts": {"type": "string"},
        "plan": {"type": "array", "items": {"type": "string"}},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["tool", "args"],
                "properties": {
                    "tool": {"type": "string"},  # No enum - validated dynamically via ToolRegistry
                    "args": {"type": "object"},
                },
            },
        },
        "stop_reason": {
            "type": "string",
            "enum": ["continue", "done", "fail"],
        },
        "result_message": {"type": "string"},
    },
}

# DEPRECATED: VALID_TOOLS is no longer used for validation
# Tool validation is now done dynamically via ToolRegistry
# Kept for backward compatibility in error messages only
VALID_TOOLS = set()  # Empty set - will be populated dynamically if needed


class ActionJSONValidationError(ValueError):
    """Exception raised when ActionJSON validation fails."""

    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Initialize validation error.

        Args:
            message: Validation error message
            data: The invalid data that failed validation (for debugging)
        """
        super().__init__(message)
        self.message = message
        self.data = data


class ActionJSON:
    """Action JSON data structure.

    Design principle: Fail Fast
    - Data validation happens at construction time
    - Invalid data is rejected immediately with clear error messages
    - Downstream code can trust that ActionJSON instances are valid
    """

    def __init__(
        self,
        actions: List[Dict[str, Any]],
        stop_reason: str,
        current_step_thoughts: Optional[str] = None,
        plan: Optional[List[str]] = None,
        result_message: Optional[str] = None,
    ):
        """
        Initialize Action JSON.

        Args:
            actions: List of action dictionaries
            stop_reason: Stop reason (continue, done, fail)
            current_step_thoughts: Optional current step thoughts (not a summary)
            plan: Optional plan steps
            result_message: Optional result message

        Raises:
            ActionJSONValidationError: If data is invalid
        """
        # Type checks for constructor arguments (defensive programming at API boundary)
        if not isinstance(actions, list):
            raise ActionJSONValidationError(
                f"'actions' must be a list, but got {type(actions).__name__}."
            )
        if not isinstance(stop_reason, str):
            raise ActionJSONValidationError(
                f"'stop_reason' must be a string, but got {type(stop_reason).__name__}."
            )
        if stop_reason not in ["continue", "done", "fail"]:
            raise ActionJSONValidationError(
                f"Invalid stop_reason: '{stop_reason}'. Must be one of: 'continue', 'done', 'fail'."
            )

        # Validate each action
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                raise ActionJSONValidationError(
                    f"action[{i}] must be a dictionary, but got {type(action).__name__}."
                )
            if "tool" not in action:
                raise ActionJSONValidationError(f"action[{i}] missing required field: 'tool'.")
            if "args" not in action:
                raise ActionJSONValidationError(f"action[{i}] missing required field: 'args'.")

        self.actions = actions
        self.stop_reason = stop_reason
        self.current_step_thoughts = current_step_thoughts
        self.plan = plan or []
        self.result_message = result_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "actions": self.actions,
            "stop_reason": self.stop_reason,
        }
        if self.current_step_thoughts:
            result["current_step_thoughts"] = self.current_step_thoughts
        if self.plan:
            result["plan"] = self.plan
        if self.result_message:
            result["result_message"] = self.result_message
        return result

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        validate: bool = True,
        tool_registry: Optional["ToolRegistry"] = None,
    ) -> "ActionJSON":
        """
        Create from dictionary with validation.

        Design principle: Validate at the boundary
        - Data entering the system is validated immediately
        - Invalid data is rejected with clear error messages
        - Downstream code can trust the data structure

        Args:
            data: Dictionary containing action JSON data
            validate: Whether to validate the data (default: True)
            tool_registry: Optional ToolRegistry instance for dynamic tool validation.
                If provided, validates tool existence and delegates argument validation
                to tool.validate_args(). If not provided, only performs structural checks.

        Returns:
            ActionJSON instance

        Raises:
            ActionJSONValidationError: If data is invalid and validate=True
            TypeError: If data is not a dictionary
        """
        # Type check at boundary
        if not isinstance(data, dict):
            raise TypeError(
                f"ActionJSON.from_dict() expects a dict, but got {type(data).__name__}."
            )

        # Validate data structure if requested
        if validate:
            is_valid, error_msg = validate_action_json(data, tool_registry=tool_registry)
            if not is_valid:
                raise ActionJSONValidationError(error_msg, data=data)

        # Extract and construct (data is now guaranteed to be valid)
        # Support both old and new field names for backward compatibility
        current_step_thoughts = data.get("current_step_thoughts") or data.get("thought_summary")
        return cls(
            actions=data.get("actions", []),
            stop_reason=data.get("stop_reason", "continue"),
            current_step_thoughts=current_step_thoughts,
            plan=data.get("plan"),
            result_message=data.get("result_message"),
        )


def validate_action_json(
    data: Dict[str, Any], tool_registry: Optional["ToolRegistry"] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate Action JSON structure with detailed error messages.

    This function performs structural validation only. Tool-specific argument
    validation is delegated to each tool's validate_args() method.

    Args:
        data: Action JSON dictionary
        tool_registry: Optional ToolRegistry instance for dynamic tool validation.
            If provided, validates tool existence and delegates argument validation
            to tool.validate_args(). If not provided, only performs structural checks.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    if "actions" not in data:
        return (
            False,
            "Missing required field: 'actions'. Your JSON must include an 'actions' array.",
        )
    if "stop_reason" not in data:
        return (
            False,
            "Missing required field: 'stop_reason'. Your JSON must include a 'stop_reason' field (one of: 'continue', 'done', 'fail').",
        )

    # Check stop_reason
    if data["stop_reason"] not in ["continue", "done", "fail"]:
        return (
            False,
            f"Invalid stop_reason: '{data['stop_reason']}'. Must be one of: 'continue', 'done', 'fail'.",
        )

    # Check actions
    if not isinstance(data["actions"], list):
        return False, f"'actions' must be a list/array, but got {type(data['actions']).__name__}."

    # Get available tools from registry if provided
    available_tools = None
    if tool_registry:
        available_tools = set(tool_registry.list_tools())

    # Count write_file actions - only one allowed per response
    write_file_count = 0
    for i, action in enumerate(data["actions"]):
        if not isinstance(action, dict):
            return (
                False,
                f"action[{i}] must be a dictionary/object, but got {type(action).__name__}.",
            )

        if "tool" not in action:
            tool_list_msg = (
                f" (one of: {sorted(available_tools)})"
                if available_tools
                else ""
            )
            return (
                False,
                f"action[{i}] missing required field: 'tool'. Each action must have a 'tool' field{tool_list_msg}.",
            )
        if "args" not in action:
            return (
                False,
                f"action[{i}] missing required field: 'args'. Each action must have an 'args' object/dictionary.",
            )

        tool = action["tool"]
        if not isinstance(tool, str):
            return False, f"action[{i}].tool must be a string, but got {type(tool).__name__}."

        # Check args type BEFORE tool validation (type check is structural, not tool-specific)
        if not isinstance(action["args"], dict):
            return (
                False,
                f"action[{i}].args must be a dictionary/object, but got {type(action['args']).__name__}.",
            )

        # Validate tool existence if registry is available
        if tool_registry:
            if tool not in available_tools:
                return (
                    False,
                    f"action[{i}] invalid tool: '{tool}'. Valid tools are: {sorted(available_tools)}.",
                )

            # Delegate tool-specific argument validation to the tool itself
            tool_instance = tool_registry.get(tool)
            if tool_instance:
                is_valid, error_msg = tool_instance.validate_args(action["args"])
                if not is_valid:
                    return (
                        False,
                        f"action[{i}] (tool='{tool}') invalid arguments: {error_msg or 'Validation failed'}.",
                    )

        # Track write_file actions for enforcement rule
        if tool == "write_file":
            write_file_count += 1

    # Enforce single file creation per response
    if write_file_count > 1:
        return (
            False,
            f"Only one 'write_file' action allowed per response (found {write_file_count}). Create files one at a time to avoid token limit issues.",
        )

    return True, None


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON from text (handles cases where LLM adds extra text).

    Improved extraction logic:
    1. Try to find JSON object markers (```json, ```, {)
    2. Handle nested braces correctly
    3. Handle strings with escaped quotes
    4. Try multiple extraction strategies
    5. If multiple codeblocks found, try all and return the first valid one

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON string or None
    """
    # Strategy 1: Look for code block markers (```json or ```)
    # Try all codeblocks and find the best one
    json_block_markers = [
        ("```json", "```"),
        ("```", "```"),
    ]

    candidates = []
    
    for start_marker, end_marker in json_block_markers:
        # Find all occurrences of this marker type
        start_idx = 0
        while True:
            start_idx = text.find(start_marker, start_idx)
            if start_idx == -1:
                break
            
            # Find the end marker after start marker
            content_start = start_idx + len(start_marker)
            end_idx = text.find(end_marker, content_start)
            if end_idx != -1:
                json_candidate = text[content_start:end_idx].strip()
                candidates.append((json_candidate, start_marker))
                start_idx = end_idx + len(end_marker)
            else:
                break
    
    # Try all candidates and return the first valid one (with required fields)
    valid_json = None
    if candidates:
        logger.debug(f"[extract_json_from_text] Found {len(candidates)} codeblock(s), trying all to find valid JSON")
    
    for json_candidate, marker_type in candidates:
        # Try to parse it
        try:
            # Fast path: try direct parsing first
            parsed = json.loads(json_candidate)
            # Validate it has required fields for ActionJSON
            if isinstance(parsed, dict) and "actions" in parsed and "stop_reason" in parsed:
                logger.debug(f"[extract_json_from_text] Found valid JSON in {marker_type} codeblock")
                valid_json = json_candidate
                break  # Found valid one, stop searching
        except json.JSONDecodeError:
            # If direct parsing fails, try json repair if available
            if JSON_REPAIR_AVAILABLE:
                try:
                    repaired_json = repair_json(json_candidate)
                    # Verify the repaired JSON is valid
                    parsed = json.loads(repaired_json)
                    # Validate it has required fields
                    if isinstance(parsed, dict) and "actions" in parsed and "stop_reason" in parsed:
                        logger.debug(f"[extract_json_from_text] Found valid JSON in {marker_type} codeblock (repaired)")
                        valid_json = repaired_json
                        break  # Found valid one, stop searching
                except Exception:
                    # Repair failed, continue to next candidate
                    pass
    
    if valid_json:
        return valid_json
    
    # Strategy 2: Find first { and match braces (handling strings)
    # Skip codeblocks we already tried - look for JSON outside codeblocks
    start_idx = 0
    while True:
        start_idx = text.find("{", start_idx)
        if start_idx == -1:
            return None
        
        # Check if this { is inside a codeblock we already tried
        in_codeblock = False
        for start_marker, end_marker in json_block_markers:
            # Find the codeblock that contains this position
            codeblock_start = text.rfind(start_marker, 0, start_idx)
            if codeblock_start != -1:
                codeblock_end = text.find(end_marker, codeblock_start + len(start_marker))
                if codeblock_end != -1 and start_idx < codeblock_end:
                    # This { is inside a codeblock, skip it
                    in_codeblock = True
                    start_idx = codeblock_end + len(end_marker)
                    break
        
        if not in_codeblock:
            break  # Found a { outside codeblocks
    
    # Find matching closing brace, handling strings with escaped quotes
    brace_count = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    # Found complete JSON object
                    json_candidate = text[start_idx : i + 1]
                    # Validate it has required fields
                    try:
                        parsed = json.loads(json_candidate)
                        if isinstance(parsed, dict) and "actions" in parsed and "stop_reason" in parsed:
                            logger.debug("[extract_json_from_text] Found valid JSON outside codeblocks")
                            return json_candidate
                    except json.JSONDecodeError:
                        pass
                    # If validation fails, still return it (will be handled by caller)
                    return json_candidate

    return None


def parse_action_json(
    text: str,
    max_retries: int = 2,
    tool_registry: Optional["ToolRegistry"] = None,
) -> Tuple[Optional[ActionJSON], Optional[str], Dict[str, str]]:
    """
    Parse Action JSON from text with improved error handling.

    Also extracts file contents from placeholders (TYPE_descriptive-name format)
    that follow the JSON in the format:
    ---((WRITE_FILE_CONTENT_descriptive-name))---
    <file content>
    ---((SHELL_COMMAND_descriptive-name))---
    <command>
    ...

    Tries multiple strategies:
    1. Direct JSON parsing
    2. Extract JSON from code blocks (```json or ```)
    3. Extract JSON by matching braces (handling strings)
    4. Fix common JSON errors
    5. Use json-repair if available
    6. Use json5 if available

    Args:
        text: Text containing JSON and optionally file contents
        max_retries: Maximum number of retries (unused, kept for compatibility)
        tool_registry: Optional ToolRegistry instance for dynamic tool validation.
            If provided, validates tool existence and delegates argument validation
            to tool.validate_args(). If not provided, only performs structural checks.

    Returns:
        Tuple of (ActionJSON or None, error_message, file_contents_dict)
        file_contents_dict maps placeholder names (e.g., "WRITE_FILE_CONTENT_descriptive-name") to actual content
    """
    if not text or not text.strip():
        return None, "Empty text provided. Your response must contain valid JSON.", {}

    # Extract file contents from placeholders (e.g., ---(FILE_CONTENT_#1)--- ... ---(FILE_CONTENT_#2)---)
    file_contents = _extract_file_contents(text)
    if file_contents:
        logger.debug(
            f"[parse_action_json] Extracted {len(file_contents)} file contents: "
            f"keys={list(file_contents.keys())}"
        )

    # Remove file content sections from text to get pure JSON
    json_text = _remove_file_content_sections(text)

    # Strategy 1: Try direct JSON parsing first
    try:
        data = json.loads(json_text)
        is_valid, error = validate_action_json(data, tool_registry=tool_registry)
        if is_valid:
            # Data already validated, skip validation in from_dict() for performance
            return ActionJSON.from_dict(data, validate=False, tool_registry=tool_registry), None, file_contents
        else:
            return None, error, file_contents  # Return detailed validation error
    except json.JSONDecodeError as e:
        # Store the JSON decode error for later use
        json_decode_error = str(e)
    except Exception as e:
        return None, f"Unexpected error during JSON parsing: {e}", file_contents

    # Strategy 2: Try to extract JSON from text (handles code blocks, extra text)
    json_str = extract_json_from_text(json_text)
    if json_str:
        try:
            data = json.loads(json_str)
            is_valid, error = validate_action_json(data, tool_registry=tool_registry)
            if is_valid:
                return ActionJSON.from_dict(data, tool_registry=tool_registry), None, file_contents
            else:
                return None, error, file_contents  # Return detailed validation error
        except json.JSONDecodeError as e:
            return (
                None,
                f"Extracted JSON is invalid: {e}. Please ensure your JSON is properly formatted with matching braces and quotes.",
                file_contents,
            )
        except Exception as e:
            return None, f"Unexpected error while parsing extracted JSON: {e}", file_contents

    # Strategy 3: Try to fix common JSON errors (especially for long text content)
    # This is critical for handling long text in write_file content that may have unescaped characters
    fixed_json_str = _fix_json_errors(json_text if json_str is None else json_str)
    if fixed_json_str:
        try:
            data = json.loads(fixed_json_str)
            is_valid, error = validate_action_json(data, tool_registry=tool_registry)
            if is_valid:
                logger.info("[parse_action_json] ✓ 使用JSON修复成功解析")
                return ActionJSON.from_dict(data, tool_registry=tool_registry), None, file_contents
            else:
                return None, error, file_contents
        except json.JSONDecodeError:
            pass

    # Strategy 4: Try json-repair if available (most powerful) - prioritize this
    if JSON_REPAIR_AVAILABLE:
        try:
            json_to_repair = json_text if json_str is None else json_str
            repaired_json = repair_json(json_to_repair)
            data = json.loads(repaired_json)
            is_valid, error = validate_action_json(data, tool_registry=tool_registry)
            if is_valid:
                logger.info("[parse_action_json] ✓ 使用json-repair成功修复并解析")
                return ActionJSON.from_dict(data, tool_registry=tool_registry), None, file_contents
            else:
                return None, error, file_contents
        except Exception as e:
            logger.debug(f"[parse_action_json] json-repair修复失败: {e}")

    # Strategy 5: Try json5 if available (supports more lenient JSON)
    if JSON5_AVAILABLE:
        try:
            json_to_parse = json_text if json_str is None else json_str
            data = json5.loads(json_to_parse)
            is_valid, error = validate_action_json(data, tool_registry=tool_registry)
            if is_valid:
                logger.info("[parse_action_json] ✓ 使用json5成功解析")
                return ActionJSON.from_dict(data, tool_registry=tool_registry), None, file_contents
            else:
                return None, error, file_contents
        except Exception as e:
            logger.debug(f"[parse_action_json] json5解析失败: {e}")

    # If all strategies fail, return detailed error
    error_msg = "Could not extract valid JSON from text. "
    if "json_decode_error" in locals():
        error_msg += f"JSON parse error: {json_decode_error}. "
    error_msg += "Please ensure your response is valid JSON with the required fields: 'actions' (array) and 'stop_reason' (string: 'continue', 'done', or 'fail')."
    error_msg += " For long text content, use placeholders (FILE_CONTENT_#1, FILE_CONTENT_#2, etc.) and provide content after the JSON."

    return None, error_msg, file_contents


def _fix_json_errors(json_str: str) -> Optional[str]:
    """
    Fix common JSON errors in LLM output, especially for long text content.

    Fixes:
    1. Unescaped quotes in strings (especially in long text content)
    2. Unescaped newlines, tabs, and control characters
    3. Trailing commas
    4. Missing commas
    5. Single quotes (convert to double quotes where safe)

    Args:
        json_str: JSON string that may contain errors

    Returns:
        Fixed JSON string, or None if fixing is not possible
    """
    if not json_str or not json_str.strip():
        return None

    try:
        # Quick check: if already valid, return as-is
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    # Try to fix common errors
    fixed = json_str

    # 1. Remove comments (single-line and multi-line)
    lines = fixed.split("\n")
    fixed_lines = []
    for line in lines:
        if "//" in line:
            # Only remove comment if we're not inside a string
            quote_count = line.count('"') - line.count('\\"')
            if quote_count % 2 == 0:  # Even number of quotes = not in string
                line = line.split("//")[0].rstrip()
        fixed_lines.append(line)
    fixed = "\n".join(fixed_lines)
    fixed = re.sub(r"/\*.*?\*/", "", fixed, flags=re.DOTALL)

    # 2. Fix trailing commas
    fixed = re.sub(r",\s*}", "}", fixed)
    fixed = re.sub(r",\s*]", "]", fixed)

    # 3. Fix missing commas between objects/arrays
    fixed = re.sub(r"}\s*{", "}, {", fixed)
    fixed = re.sub(r"]\s*{", "], {", fixed)
    fixed = re.sub(r'}\s*"', '}, "', fixed)
    fixed = re.sub(r']\s*"', '], "', fixed)

    # 4. Most critical: Fix unescaped control characters in strings
    # This is the main issue with long text content (newlines, tabs, etc.)
    fixed = _escape_control_chars_safe(fixed)

    # 5. Try to fix unescaped quotes in strings (very carefully, conservative approach)
    # This is risky, so we do it last and only if the JSON is still invalid
    # Only fix quotes that are clearly inside string values and clearly problematic
    try:
        json.loads(fixed)
        # Already valid after control char fix, don't risk breaking it
        return fixed
    except json.JSONDecodeError:
        # Still invalid, try fixing quotes (but be very conservative)
        fixed = _fix_unescaped_quotes_in_strings(fixed)

    # Verify the fix worked
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        # Fix didn't work, but return it anyway for json5 to try
        return fixed


def _escape_control_chars_safe(text: str) -> str:
    """
    Safely escape control characters in JSON strings.

    Only escapes control characters that are inside string values,
    not in keys or outside strings.

    Args:
        text: JSON text

    Returns:
        Text with control characters escaped
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\":
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            # Inside a string: escape control characters
            if char == "\n":
                result.append("\\n")
            elif char == "\t":
                result.append("\\t")
            elif char == "\r":
                result.append("\\r")
            elif ord(char) < 32:  # Other control characters
                result.append(f"\\u{ord(char):04x}")
            else:
                result.append(char)
        else:
            # Outside string: keep as-is
            result.append(char)

        i += 1

    return "".join(result)


def _fix_unescaped_quotes_in_strings(text: str) -> str:
    """
    Fix unescaped quotes inside string values.

    This is very tricky - we need to be conservative to avoid breaking valid JSON.
    Only fix quotes that are clearly inside string values and clearly unescaped.

    Strategy: When we encounter a quote inside a string, check if it's followed
    by valid JSON structure. If not, it's likely an unescaped quote in content.

    Args:
        text: JSON text

    Returns:
        Text with unescaped quotes in strings fixed (conservatively)
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\":
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"':
            if not in_string:
                # Starting a new string
                in_string = True
                result.append(char)
            else:
                # Inside a string - check if this is the closing quote
                # Look ahead to see if this is followed by valid JSON structure
                lookahead = text[i + 1 :].lstrip()

                # Check for common patterns that indicate this is a closing quote:
                # - Followed by : (key-value separator)
                # - Followed by , (array/object separator)
                # - Followed by } or ] (structure end)
                # - Followed by whitespace then one of the above
                is_closing_quote = (
                    lookahead.startswith(":")
                    or lookahead.startswith(",")
                    or lookahead.startswith("}")
                    or lookahead.startswith("]")
                    or not lookahead  # End of text
                )

                if is_closing_quote:
                    # This is a closing quote
                    in_string = False
                    result.append(char)
                else:
                    # This might be an unescaped quote inside the string
                    # But be conservative - only escape if it's clearly wrong
                    # Check if next non-whitespace char is a letter/digit (likely content)
                    next_char = lookahead[0] if lookahead else ""
                    if next_char.isalnum() or next_char in ".,;:!?":
                        # Likely an unescaped quote in content - escape it
                        result.append('\\"')
                    else:
                        # Might be valid - keep as-is
                        result.append(char)
            i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def _clean_extracted_content(content: str, placeholder_type: str) -> str:
    """
    Clean extracted placeholder content by removing markdown artifacts and trailing whitespace.
    
    This function removes:
    - Markdown code block markers (```) at the start or end for executable types (SHELL_COMMAND, etc.)
    - Trailing whitespace and newlines
    - Common markdown artifacts that LLMs sometimes include
    
    Important: For file content types (WRITE_FILE_CONTENT, EDIT_FILE_CONTENT, APPEND_FILE_CONTENT),
    code blocks in the middle are preserved (they're part of the actual file content, e.g., markdown files
    with code examples). However, code block markers at the very start or end are removed as they are
    markdown artifacts, not part of the file content.
    
    Args:
        content: Raw extracted content
        placeholder_type: Type of placeholder (SHELL_COMMAND, PYTHON_SCRIPT, etc.)
    
    Returns:
        Cleaned content
    """
    import re
    
    if not content:
        return content
    
    # Remove leading/trailing whitespace first
    content = content.rstrip()
    
    # For file content types, we need to be careful:
    # - Remove code block markers at the very start/end (they're artifacts)
    # - But preserve code blocks in the middle (they're part of the content)
    file_content_types = ("WRITE_FILE_CONTENT", "EDIT_FILE_CONTENT", "APPEND_FILE_CONTENT")
    
    if placeholder_type in file_content_types:
        # For file content, remove code block markers only at the very start and end
        # This prevents markdown artifacts from polluting the file content
        
        original_content = content
        # Remove code block markers at the very start (must be at beginning of content)
        # Pattern: ``` optionally followed by language identifier, then optional whitespace/newline
        content = re.sub(r'^```[a-z]*\s*\n?', '', content, flags=re.MULTILINE)
        
        # Remove code block markers at the very end (must be at end of content)
        # Pattern: optional whitespace/newline, then ```
        content = re.sub(r'\n?\s*```\s*$', '', content, flags=re.MULTILINE)
        
        # Remove any trailing backticks that might be left over (but preserve content in the middle)
        while content and content.endswith('`') and len(content) > 1:
            # Check if removing the backtick would leave valid content
            test_content = content[:-1].rstrip()
            if test_content and not test_content.endswith('`'):
                content = test_content
            else:
                break
        
        # Log if we removed codeblock markers
        if content != original_content:
            logger.debug(f"[_clean_extracted_content] Removed codeblock markers from {placeholder_type} content")
        
        return content.rstrip()
    
    # For executable types (SHELL_COMMAND, PYTHON_SCRIPT, SHELL_SCRIPT), remove code block markers
    # These are markdown artifacts, not part of the actual code
    
    # Remove markdown code block markers (```) that might be at the very end
    # Pattern: optional whitespace, then ```, then optional language identifier, then end of string
    content = re.sub(r'\s*```[a-z]*\s*$', '', content, flags=re.MULTILINE)
    
    # Remove markdown code block markers at the very start
    # Only match if it's at the beginning of the entire content
    content = re.sub(r'^```[a-z]*\s*\n?', '', content, flags=re.MULTILINE)
    
    # Remove trailing backticks that might be left over (but preserve content in the middle)
    # Only remove if they're at the very end
    while content and content.endswith('`') and not content.rstrip('`').endswith('`'):
        content = content[:-1]
    
    # Be more aggressive with trailing cleanup for executable types
    content = content.rstrip()
    # Remove trailing backticks and newlines (with safety limit)
    max_iterations = 10  # Prevent infinite loop
    iterations = 0
    while iterations < max_iterations and (content.endswith('`') or content.endswith('\n')):
        new_content = content.rstrip('`\n')
        if new_content == content:  # No change, break to avoid infinite loop
            break
        content = new_content
        iterations += 1
    
    return content


def _extract_file_contents(text: str) -> Dict[str, str]:
    """
    Extract contents from type-specific placeholders in the format:
    ---((WRITE_FILE_CONTENT_descriptive-name))---
    <file content>
    ---((EDIT_FILE_CONTENT_descriptive-name))---
    <old>old_string</old><new>new_string</new>
    ---((SHELL_COMMAND_descriptive-name))---
    <command>
    ---((PYTHON_SCRIPT_descriptive-name))---
    <python code>
    ...

    Args:
        text: Full text containing JSON and placeholder contents

    Returns:
        Dictionary mapping placeholder names (e.g., "WRITE_FILE_CONTENT_descriptive-name") to content
        Content is cleaned to remove markdown artifacts while preserving indentation and formatting.
    """
    from atloop.llm.placeholder_patterns import (
        extract_placeholder_name,
        find_placeholder_delimiters,
    )

    file_contents = {}
    matches = find_placeholder_delimiters(text)

    for i, match in enumerate(matches):
        placeholder_type, placeholder = extract_placeholder_name(match)
        # Start position is after the delimiter (skip the newline if present)
        start_pos = match.end()
        # Skip leading newline if present
        if start_pos < len(text) and text[start_pos] == "\n":
            start_pos += 1

        # Find the end position (next placeholder or end of text)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(text)

        # Extract content
        content = text[start_pos:end_pos]
        
        # Clean content to remove markdown artifacts (especially for commands/scripts)
        # placeholder_type is already the type (e.g., "SHELL_COMMAND"), placeholder is the full name
        content = _clean_extracted_content(content, placeholder_type)
        
        file_contents[placeholder] = content

    return file_contents


def _remove_file_content_sections(text: str) -> str:
    """
    Remove placeholder content sections from text, leaving only JSON.

    Removes sections like:
    ---((WRITE_FILE_CONTENT_descriptive-name))---
    <content>
    ---((SHELL_COMMAND_descriptive-name))---
    <command>
    ...

    Also handles cases where the entire output is wrapped in code blocks (```json or ```).
    This ensures compatibility even if LLM doesn't follow the no-codeblock rule.

    Args:
        text: Full text containing JSON and placeholder contents

    Returns:
        Text with placeholder content sections removed, and outer code blocks stripped if present
    """
    from atloop.llm.placeholder_patterns import PLACEHOLDER_SECTION_REGEX

    # First, try to strip outer code blocks if the entire text is wrapped
    # This handles cases where LLM wraps everything in ```json ... ``` or ``` ... ```
    import re
    stripped_text = text.strip()
    
    # Check for code block markers at start and end
    # Try ```json first (more specific), then generic ```
    if stripped_text.startswith('```json'):
        # Remove ```json at start (with optional whitespace/newline)
        stripped_text = re.sub(r'^```json\s*\n?', '', stripped_text, count=1)
        # Remove ``` at end (with optional whitespace/newline before it)
        stripped_text = re.sub(r'\n?```\s*$', '', stripped_text, count=1)
        stripped_text = stripped_text.strip()
    elif stripped_text.startswith('```'):
        # Remove ``` at start (with optional whitespace/newline)
        stripped_text = re.sub(r'^```\s*\n?', '', stripped_text, count=1)
        # Remove ``` at end (with optional whitespace/newline before it)
        stripped_text = re.sub(r'\n?```\s*$', '', stripped_text, count=1)
        stripped_text = stripped_text.strip()
    
    # Remove all placeholder content sections
    result = PLACEHOLDER_SECTION_REGEX.sub("", stripped_text)

    return result.strip()
