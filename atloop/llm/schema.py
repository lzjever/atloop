"""Action JSON schema definition and validation."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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
ACTION_JSON_SCHEMA = {
    "type": "object",
    "required": ["actions", "stop_reason"],
    "properties": {
        "thought_summary": {"type": "string"},
        "plan": {"type": "array", "items": {"type": "string"}},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["tool", "args"],
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": [
                            "run",
                            "write_file",
                            "append_file",
                            "read_file",
                            "read_skill_file",
                            "edit_file",
                            "multi_edit_file",
                            "glob",
                            "search",
                            "todo_write",
                            "todo_read",
                            "skill",
                        ],
                    },
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

# Valid tool names
VALID_TOOLS = {
    "run",
    "write_file",
    "append_file",  # Append content to files
    "read_file",  # Enhanced file reading with type detection (sandbox files)
    "read_skill_file",  # Read files from skill directories (skill files only, stored locally)
    "edit_file",  # Git-style diff editing
    "multi_edit_file",  # Batch multi-file editing
    "glob",  # File matching with glob patterns
    "search",  # Enhanced search with regex, context lines, file filtering
    "todo_write",  # Write and manage todo lists
    "todo_read",  # Read todo lists
    "skill",  # Load skill knowledge on-demand
}


class ActionJSON:
    """Action JSON data structure."""

    def __init__(
        self,
        actions: List[Dict[str, Any]],
        stop_reason: str,
        thought_summary: Optional[str] = None,
        plan: Optional[List[str]] = None,
        result_message: Optional[str] = None,
    ):
        """
        Initialize Action JSON.

        Args:
            actions: List of action dictionaries
            stop_reason: Stop reason (continue, done, fail)
            thought_summary: Optional thought summary
            plan: Optional plan steps
            result_message: Optional result message
        """
        self.actions = actions
        self.stop_reason = stop_reason
        self.thought_summary = thought_summary
        self.plan = plan or []
        self.result_message = result_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "actions": self.actions,
            "stop_reason": self.stop_reason,
        }
        if self.thought_summary:
            result["thought_summary"] = self.thought_summary
        if self.plan:
            result["plan"] = self.plan
        if self.result_message:
            result["result_message"] = self.result_message
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionJSON":
        """Create from dictionary."""
        return cls(
            actions=data.get("actions", []),
            stop_reason=data.get("stop_reason", "continue"),
            thought_summary=data.get("thought_summary"),
            plan=data.get("plan"),
            result_message=data.get("result_message"),
        )


def validate_action_json(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate Action JSON structure with detailed error messages.

    Args:
        data: Action JSON dictionary

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

    # Count write_file actions - only one allowed per response
    write_file_count = 0
    for i, action in enumerate(data["actions"]):
        if not isinstance(action, dict):
            return (
                False,
                f"action[{i}] must be a dictionary/object, but got {type(action).__name__}.",
            )

        if "tool" not in action:
            return (
                False,
                f"action[{i}] missing required field: 'tool'. Each action must have a 'tool' field (one of: {sorted(VALID_TOOLS)}).",
            )
        if "args" not in action:
            return (
                False,
                f"action[{i}] missing required field: 'args'. Each action must have an 'args' object/dictionary.",
            )

        tool = action["tool"]
        if not isinstance(tool, str):
            return False, f"action[{i}].tool must be a string, but got {type(tool).__name__}."

        if tool not in VALID_TOOLS:
            return (
                False,
                f"action[{i}] invalid tool: '{tool}'. Valid tools are: {sorted(VALID_TOOLS)}.",
            )

        if not isinstance(action["args"], dict):
            return (
                False,
                f"action[{i}].args must be a dictionary/object, but got {type(action['args']).__name__}.",
            )

        # Validate tool-specific args
        if tool == "run":
            if "cmd" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='run') missing required arg: 'cmd'. The 'run' tool requires a 'cmd' string argument.",
                )
        elif tool == "write_file":
            if "path" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='write_file') missing required arg: 'path'. The 'write_file' tool requires a 'path' string argument.",
                )
            if "content" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='write_file') missing required arg: 'content'. The 'write_file' tool requires a 'content' string argument.",
                )
            write_file_count += 1
        elif tool == "append_file":
            if "path" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='append_file') missing required arg: 'path'. The 'append_file' tool requires a 'path' string argument.",
                )
            if "content" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='append_file') missing required arg: 'content'. The 'append_file' tool requires a 'content' string argument.",
                )
        elif tool == "read_file":
            if "path" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='read_file') missing required arg: 'path'. The 'read_file' tool requires a 'path' string argument.",
                )
        elif tool == "read_local_file":
            if "path" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='read_skill_file') missing required arg: 'path'. The 'read_skill_file' tool requires a 'path' string argument.",
                )
        elif tool == "edit_file":
            if "path" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='edit_file') missing required arg: 'path'. The 'edit_file' tool requires a 'path' string argument.",
                )
            if "content" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='edit_file') missing required arg: 'content'. The 'edit_file' tool requires a 'content' string argument in format: <old>old_string</old><new>new_string</new>.",
                )
        elif tool == "multi_edit_file":
            if "edits" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='multi_edit_file') missing required arg: 'edits'. The 'multi_edit_file' tool requires an 'edits' array argument.",
                )
            if not isinstance(action["args"].get("edits"), list):
                return (
                    False,
                    f"action[{i}] (tool='multi_edit_file') invalid arg: 'edits' must be an array of edit objects.",
                )
            if len(action["args"].get("edits", [])) == 0:
                return (
                    False,
                    f"action[{i}] (tool='multi_edit_file') invalid arg: 'edits' array must contain at least one edit.",
                )
        elif tool == "glob":
            if "pattern" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='glob') missing required arg: 'pattern'. The 'glob' tool requires a 'pattern' string argument.",
                )
        elif tool == "search":
            if "query" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='search') missing required arg: 'query'. The 'search' tool requires a 'query' string argument.",
                )
            if "output_mode" in action["args"] and action["args"]["output_mode"] not in [
                "content",
                "files_with_matches",
                "count",
            ]:
                return (
                    False,
                    f"action[{i}] (tool='search') invalid arg: 'output_mode' must be one of 'content', 'files_with_matches', 'count'.",
                )
        elif tool == "todo_write":
            if "todos" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='todo_write') missing required arg: 'todos'. The 'todo_write' tool requires a 'todos' array argument.",
                )
            if not isinstance(action["args"].get("todos"), list):
                return (
                    False,
                    f"action[{i}] (tool='todo_write') invalid arg: 'todos' must be an array.",
                )
            if len(action["args"].get("todos", [])) == 0:
                return (
                    False,
                    f"action[{i}] (tool='todo_write') invalid arg: 'todos' array cannot be empty.",
                )
            for j, todo in enumerate(action["args"].get("todos", [])):
                if not isinstance(todo, dict):
                    return False, f"action[{i}] (tool='todo_write') todo[{j}] must be a dictionary."
                if "content" not in todo:
                    return (
                        False,
                        f"action[{i}] (tool='todo_write') todo[{j}] missing required field: 'content'.",
                    )
                if "activeForm" not in todo:
                    return (
                        False,
                        f"action[{i}] (tool='todo_write') todo[{j}] missing required field: 'activeForm'.",
                    )
                if "status" not in todo:
                    return (
                        False,
                        f"action[{i}] (tool='todo_write') todo[{j}] missing required field: 'status'.",
                    )
                if todo.get("status") not in ["pending", "in_progress", "completed"]:
                    return (
                        False,
                        f"action[{i}] (tool='todo_write') todo[{j}] invalid status: must be 'pending', 'in_progress', or 'completed'.",
                    )
        elif tool == "skill":
            if "name" not in action["args"]:
                return (
                    False,
                    f"action[{i}] (tool='skill') missing required arg: 'name'. The 'skill' tool requires a 'name' string argument.",
                )

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

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON string or None
    """
    # Strategy 1: Look for code block markers (```json or ```)
    json_block_markers = [
        ("```json", "```"),
        ("```", "```"),
    ]

    for start_marker, end_marker in json_block_markers:
        start_idx = text.find(start_marker)
        if start_idx != -1:
            # Find the end marker after start marker
            content_start = start_idx + len(start_marker)
            end_idx = text.find(end_marker, content_start)
            if end_idx != -1:
                json_candidate = text[content_start:end_idx].strip()
                # Try to parse it
                try:
                    json.loads(json_candidate)
                    return json_candidate
                except json.JSONDecodeError:
                    pass

    # Strategy 2: Find first { and match braces (handling strings)
    start_idx = text.find("{")
    if start_idx == -1:
        return None

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
                    return text[start_idx : i + 1]

    return None


def parse_action_json(
    text: str, max_retries: int = 2
) -> Tuple[Optional[ActionJSON], Optional[str], Dict[str, str]]:
    """
    Parse Action JSON from text with improved error handling.

    Also extracts file contents from placeholders (FILE_CONTENT_#1, FILE_CONTENT_#2, etc.)
    that follow the JSON in the format:
    ---(FILE_CONTENT_#1)---
    <file content>
    ---(FILE_CONTENT_#2)---
    <file content>
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

    Returns:
        Tuple of (ActionJSON or None, error_message, file_contents_dict)
        file_contents_dict maps placeholder names (e.g., "FILE_CONTENT_#1") to actual content
    """
    if not text or not text.strip():
        return None, "Empty text provided. Your response must contain valid JSON.", {}

    # Extract file contents from placeholders (e.g., ---(FILE_CONTENT_#1)--- ... ---(FILE_CONTENT_#2)---)
    file_contents = _extract_file_contents(text)

    # Remove file content sections from text to get pure JSON
    json_text = _remove_file_content_sections(text)

    # Strategy 1: Try direct JSON parsing first
    try:
        data = json.loads(json_text)
        is_valid, error = validate_action_json(data)
        if is_valid:
            return ActionJSON.from_dict(data), None, file_contents
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
            is_valid, error = validate_action_json(data)
            if is_valid:
                return ActionJSON.from_dict(data), None, file_contents
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
            is_valid, error = validate_action_json(data)
            if is_valid:
                logger.info("[parse_action_json] ✅ 使用JSON修复成功解析")
                return ActionJSON.from_dict(data), None, file_contents
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
            is_valid, error = validate_action_json(data)
            if is_valid:
                logger.info("[parse_action_json] ✅ 使用json-repair成功修复并解析")
                return ActionJSON.from_dict(data), None, file_contents
            else:
                return None, error, file_contents
        except Exception as e:
            logger.debug(f"[parse_action_json] json-repair修复失败: {e}")

    # Strategy 5: Try json5 if available (supports more lenient JSON)
    if JSON5_AVAILABLE:
        try:
            json_to_parse = json_text if json_str is None else json_str
            data = json5.loads(json_to_parse)
            is_valid, error = validate_action_json(data)
            if is_valid:
                logger.info("[parse_action_json] ✅ 使用json5成功解析")
                return ActionJSON.from_dict(data), None, file_contents
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


def _extract_file_contents(text: str) -> Dict[str, str]:
    """
    Extract file contents from placeholders in the format:
    ---(FILE_CONTENT_#1)---
    <file content>
    ---(FILE_CONTENT_#2)---
    <file content>
    ...

    For edit_file, the content format is:
    ---(FILE_CONTENT_#N)---
    <old>old_string</old><new>new_string</new>

    Args:
        text: Full text containing JSON and file contents

    Returns:
        Dictionary mapping placeholder names (e.g., "FILE_CONTENT_#1") to content
    """
    file_contents = {}

    # Pattern to match: ---(FILE_CONTENT_#N)---
    pattern = r"---\(FILE_CONTENT_#(\d+)\)---"

    matches = list(re.finditer(pattern, text))

    for i, match in enumerate(matches):
        placeholder = f"FILE_CONTENT_#{match.group(1)}"
        start_pos = match.end()

        # Find the end position (next placeholder or end of text)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(text)

        # Extract content (strip leading/trailing whitespace)
        content = text[start_pos:end_pos].strip()
        file_contents[placeholder] = content

    return file_contents


def _remove_file_content_sections(text: str) -> str:
    """
    Remove file content sections from text, leaving only JSON.

    Removes sections like:
    ---(FILE_CONTENT_#1)---
    <content>
    ---(FILE_CONTENT_#2)---
    <content>

    Args:
        text: Full text containing JSON and file contents

    Returns:
        Text with file content sections removed
    """
    # Pattern to match: ---(FILE_CONTENT_#N)--- ... (until next placeholder or end)
    pattern = r"---\(FILE_CONTENT_#\d+\)---.*?(?=---\(FILE_CONTENT_#\d+\)---|$)"

    # Remove all file content sections
    result = re.sub(pattern, "", text, flags=re.DOTALL)

    return result.strip()
