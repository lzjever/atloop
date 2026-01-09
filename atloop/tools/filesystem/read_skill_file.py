"""Read skill file tool for accessing files from skill directories (local machine, not sandbox)."""

from pathlib import Path
from typing import Any, Dict, Optional

from atloop.tools.base import BaseTool, ToolResult


class ReadSkillFileTool(BaseTool):
    """
    Tool for reading files from skill directories (on local machine, not from sandbox workspace).

    **🚨🚨🚨 CRITICAL**: This tool reads from skill directories on the LOCAL machine, NOT from the sandbox!

    **Key Points:**
    - **Skill files are stored LOCALLY** (on the host machine, in ~/.atloop/skills/ or project .atloop/skills/)
    - **Workspace is a REMOTE SANDBOX** (/workspace) - it does NOT contain skill files or templates
    - **When a skill mentions other files** (e.g., "see docx-js.md", "reference guide.md"), those files are LOCAL
    - **You MUST use `read_skill_file`** to read skill-related files - they are NOT in the sandbox!
    - **DO NOT try to use `read_file` or `run("cat ...")`** to find skill files in the sandbox - they don't exist there!

    **Use cases:**
    - Reading skill files (when skill mentions other files to reference)
    - Reading files referenced in skill documentation
    - Accessing skill-specific resources (templates, guides, examples)

    **Path resolution:**
    - With skill_name: Path is relative to skill directory (most common use case)
    - Without skill_name: Absolute path or relative to ~/.atloop/
    - Supports ~ expansion for home directory

    **Important distinction:**
    - ✅ **Skill files** → Use `read_skill_file` (stored locally)
    - ✅ **Workspace files** → Use `read_file` (stored in remote sandbox /workspace)
    - ❌ **Never use `read_file` or `run` to find skill files** - they are not in the sandbox!
    """

    def __init__(self, skill_loader=None):
        """
        Initialize read skill file tool.

        Args:
            skill_loader: Optional skill loader instance for resolving skill paths
        """
        self.skill_loader = skill_loader

    @property
    def name(self) -> str:
        """Tool name."""
        return "read_skill_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "从技能目录读取文件（⚠️ 技能文件存储在本地机器，不在远程沙盒中。当 skill 中提到其他文件时，必须使用此工具读取，不能使用 read_file 或 run 命令在沙盒中查找）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "path" not in args:
            return False, "Missing required argument: 'path'"
        if not isinstance(args["path"], str):
            return False, "Argument 'path' must be a string"
        if "offset" in args and not isinstance(args.get("offset"), int):
            return False, "Argument 'offset' must be an integer"
        if "limit" in args and not isinstance(args.get("limit"), int):
            return False, "Argument 'limit' must be an integer"
        if "skill_name" in args and not isinstance(args.get("skill_name"), str):
            return False, "Argument 'skill_name' must be a string"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute read skill file tool.

        **🚨🚨🚨 CRITICAL**: This tool reads from skill directories on the LOCAL machine, NOT from the sandbox workspace!

        **Important understanding:**
        - **Skill files are stored LOCALLY** (on the host machine)
        - **Workspace is a REMOTE SANDBOX** (/workspace) - it does NOT contain skill files
        - **When a skill mentions other files**, those files are LOCAL, not in the sandbox
        - **You MUST use `read_skill_file`** to read skill-related files
        - **DO NOT try to use `read_file` or `run("cat ...")`** to find skill files in the sandbox - they don't exist there!

        Use `read_file` to read files from the sandbox workspace (/workspace).

        **Args:**
            args: Tool arguments dictionary
                - path (str, required): File path. Resolution depends on skill_name:
                  - If skill_name provided: Path is relative to skill directory
                  - If path starts with ~: Expanded to home directory
                  - If absolute path: Used as-is
                  - Otherwise: Relative to ~/.atloop/
                - skill_name (str, optional): Skill name. If provided, path is resolved
                  relative to the skill's directory. Use this when a skill mentions
                  other files to reference.
                - offset (int, optional): Start line number (1-indexed). Default: 1.
                  Use for reading large files in chunks.
                - limit (int, optional): Number of lines to read. If not specified,
                  reads from offset to end of file.

        **Returns:**
            ToolResult with:
            - ok (bool): True if file was read successfully (no errors in stderr)
            - stdout (str): File content (or metadata for binary/large files)
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains path, file_size, start_line, end_line

        **Examples:**
            # Read skill file (when skill mentions other files)
            read_skill_file(path="references/guide.md", skill_name="long_document_writer")

            # Read skill documentation
            read_skill_file(path="docx-js.md", skill_name="docx")

            # Read with line range
            read_skill_file(path="skill-doc.md", skill_name="docx", offset=1, limit=50)

        **When to use this vs read_file:**
        - ✅ Reading skill files → use `read_skill_file` (stored locally, NOT in sandbox)
        - ✅ Reading files referenced in skills → use `read_skill_file` (skill mentions are LOCAL files)
        - ✅ Reading skill templates/examples → use `read_skill_file` (stored locally)
        - ❌ Reading workspace files → use `read_file` (sandbox files in /workspace)
        - ❌ **DO NOT use `read_file` or `run` to find skill files** - they are NOT in the sandbox!

        **File Size Limits:**
        - Files larger than 10MB return metadata only
        - Use offset/limit to read specific sections of large files

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the operation succeeded
        - Check stderr for specific error messages if ok=False
        """
        path_str = args["path"]
        skill_name = args.get("skill_name")
        offset = args.get("offset")
        limit = args.get("limit")

        # Resolve file path
        if skill_name and self.skill_loader:
            # Resolve relative to skill directory
            skill = self.skill_loader.skills.get(skill_name)
            if not skill:
                return ToolResult(
                    ok=False,
                    stdout="",
                    stderr=f"Skill '{skill_name}' not found. Cannot resolve path relative to skill.",
                    meta={"path": path_str, "skill_name": skill_name},
                )
            skill_dir = skill["dir"]
            file_path = skill_dir / path_str
        elif path_str.startswith("~"):
            # Expand ~ to home directory
            file_path = Path(path_str).expanduser()
        elif Path(path_str).is_absolute():
            # Absolute path
            file_path = Path(path_str)
        else:
            # Relative to ~/.atloop/ (common case for skill resources)
            file_path = Path.home() / ".atloop" / path_str

        # Check if file exists
        if not file_path.exists():
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"File not found: {file_path}. "
                f"(Resolved from: {path_str}, skill: {skill_name or 'none'})",
                meta={"path": str(file_path), "original_path": path_str, "skill_name": skill_name},
            )

        if not file_path.is_file():
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Path is not a file: {file_path}",
                meta={"path": str(file_path)},
            )

        # Check file size
        file_size = file_path.stat().st_size
        max_file_size = 10 * 1024 * 1024  # 10MB

        if file_size > max_file_size:
            return ToolResult(
                ok=True,
                stdout=f"[File: {file_path}]\nSize: {file_size} bytes\n\nFile is too large to display (>10MB). Use offset and limit to read specific lines.",
                stderr="",
                meta={"path": str(file_path), "file_size": file_size},
            )

        # Read file content
        try:
            # Try to read as text first
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Binary file
            return ToolResult(
                ok=True,
                stdout=f"[File: {file_path}]\nType: binary\nSize: {file_size} bytes\n\nThis file is binary and cannot be displayed as text.",
                stderr="",
                meta={"path": str(file_path), "file_type": "binary", "file_size": file_size},
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Error reading file: {e}",
                meta={"path": str(file_path), "error": str(e)},
            )

        # Handle line range if specified
        if offset is not None or limit is not None:
            lines = content.split("\n")
            start_line = (offset - 1) if offset is not None else 0
            end_line = (start_line + limit) if limit is not None else len(lines)

            # Validate range
            if start_line < 0:
                start_line = 0
            if end_line > len(lines):
                end_line = len(lines)
            if start_line >= len(lines):
                return ToolResult(
                    ok=True,
                    stdout="",
                    stderr="",
                    meta={
                        "path": str(file_path),
                        "start_line": offset,
                        "end_line": end_line,
                        "total_lines": len(lines),
                    },
                )

            selected_lines = lines[start_line:end_line]
            content = "\n".join(selected_lines)

        return ToolResult(
            ok=True,
            stdout=content,
            stderr="",
            meta={
                "path": str(file_path),
                "file_size": file_size,
                "start_line": offset,
                "end_line": (offset + limit - 1) if (offset and limit) else None,
            },
        )
