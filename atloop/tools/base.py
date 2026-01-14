"""Base classes and types for tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from atloop.tools.output_semantic_type import OutputSemanticType


@dataclass
class ToolResult:
    """Result of tool execution."""

    ok: bool
    stdout: str
    stderr: str
    meta: Dict[str, Any]

    def __repr__(self) -> str:
        """String representation."""
        status = "✓" if self.ok else "✗"
        return f"ToolResult({status}, stdout_len={len(self.stdout)}, stderr_len={len(self.stderr)})"


class BaseTool(ABC):
    """Base class for all tools.

    Tools can declare their output semantic types to enable automatic
    application of appropriate output size limits.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @property
    def output_semantic_type(self) -> OutputSemanticType:
        """Return the semantic type of tool output.

        Default: STATUS_MESSAGE (suitable for most tools that return
        simple success/failure messages).

        Subclasses can override this property to declare their output
        semantic type.

        Returns:
            OutputSemanticType enum value
        """
        return OutputSemanticType.STATUS_MESSAGE

    @property
    def stdout_semantic_type(self) -> OutputSemanticType:
        """Return the semantic type of stdout output.

        Default: Uses output_semantic_type.

        Subclasses can override this if stdout has a different semantic
        type than the general output.

        Returns:
            OutputSemanticType enum value
        """
        return self.output_semantic_type

    @property
    def stderr_semantic_type(self) -> OutputSemanticType:
        """Return the semantic type of stderr output.

        Default: ERROR_MESSAGE (stderr is typically error information).

        Subclasses can override this if stderr has a different semantic type.

        Returns:
            OutputSemanticType enum value
        """
        return OutputSemanticType.ERROR_MESSAGE

    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """Execute tool with given arguments."""
        pass

    def needs_permission(self, args: Dict[str, Any]) -> bool:
        """Whether this tool needs user permission."""
        return False

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate tool arguments. Returns (is_valid, error_message)."""
        return True, None

    def get_detailed_description(self) -> str:
        """
        Generate detailed tool description for LLM prompts.
        
        Extracts comprehensive information from the tool's docstring including:
        - Main description
        - Usage guidelines
        - Important warnings
        - Parameters
        - Examples
        - When to use vs other tools
        
        Returns:
            Formatted detailed description string suitable for LLM prompts
        """
        import inspect
        import re
        
        # Get class docstring
        docstring = inspect.getdoc(self.__class__) or ""
        if not docstring:
            # Fallback to simple description
            return f"{self.description}\n\n*No detailed documentation available.*"
        
        # Extract main description (first paragraph before any ** markers or empty line)
        lines = docstring.split('\n')
        main_desc_parts = []
        
        for line in lines:
            line_stripped = line.strip()
            # Stop at first ** marker (section start) or after first paragraph
            if line_stripped.startswith('**'):
                break
            if line_stripped:
                main_desc_parts.append(line_stripped)
            elif main_desc_parts:  # Empty line after content - end of first paragraph
                break
        
        main_desc = ' '.join(main_desc_parts).strip()
        if not main_desc:
            main_desc = self.description
        
        # Extract key sections from docstring
        sections = {}
        
        # Extract **Important**, **Use cases**, **When to use**, etc.
        current_section = None
        current_content = []
        
        for line in lines:
            line_stripped = line.strip()
            # Check for section headers (lines starting with **)
            # Match patterns like **CRITICAL**, **⚠️ CRITICAL**:, **Use cases:**, etc.
            # Note: Some headers end with : instead of **
            if line_stripped.startswith('**'):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                # Extract section name - remove ** markers from start and end
                # Handle patterns like **CRITICAL**, **⚠️ CRITICAL**:, **Use cases:**
                # Also handle cases where content is on the same line: **⚠️ CRITICAL**: content
                section_line = line_stripped
                # Remove leading **
                if section_line.startswith('**'):
                    section_line = section_line[2:]
                
                # Find where the section name ends (either **, :, or end of line)
                # Look for : followed by content, or ** at end
                section_name = section_line
                content_after_colon = None
                
                # Check if there's content after a colon (same-line content)
                if ':' in section_line:
                    colon_pos = section_line.find(':')
                    # Check if this looks like a section header with content
                    # Pattern: **Name**: content
                    potential_name = section_line[:colon_pos].strip()
                    potential_content = section_line[colon_pos+1:].strip()
                    # If there's substantial content after colon, it's same-line content
                    if potential_content and len(potential_content) > 3:
                        section_name = potential_name
                        content_after_colon = potential_content
                    else:
                        # Just a trailing colon, remove it
                        section_name = section_line.rstrip(':').strip()
                elif section_line.endswith('**'):
                    section_name = section_line[:-2].strip()
                else:
                    section_name = section_line.strip()
                
                # Normalize section names (remove emoji, keep key words)
                # Check for CRITICAL first (most specific)
                if 'CRITICAL' in section_name.upper():
                    current_section = 'CRITICAL'
                elif '⚠️' in section_name and ('Important' in section_name or 'WARNING' in section_name):
                    current_section = 'Important'
                elif 'Important' in section_name:
                    current_section = 'Important'
                elif 'WARNING' in section_name:
                    current_section = 'WARNING'
                else:
                    current_section = section_name
                
                # If there was content on the same line, add it immediately
                if content_after_colon:
                    current_content = [content_after_colon]
                else:
                    current_content = []
            elif current_section:
                # Continue collecting content for current section
                # Include empty lines if we already have content (preserves formatting)
                if line_stripped or (current_content and not line_stripped):
                    current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        # Build detailed description
        parts = [main_desc]
        
        # Add important warnings/notes first (highest priority)
        # Check normalized section names
        warning_keys = ['CRITICAL', 'Important', 'WARNING']
        for key in warning_keys:
            if key in sections:
                warning_text = sections[key]
                # Clean up markdown formatting but preserve content
                warning_text = re.sub(r'\*\*', '', warning_text)  # Remove bold markers
                parts.append(f"\n⚠️ **Important**: {warning_text}")
                break  # Only show first warning
        
        # Add usage guidelines
        usage_keys = ['Use cases', 'When to use', 'Usage', 'Why use this tool', 'Benefits']
        for key in usage_keys:
            if key in sections:
                parts.append(f"\n**{key}**:\n{sections[key]}")
                break  # Only show first usage section
        
        # Add differences from other tools
        diff_keys = ['Key differences', 'Why use this instead', 'vs', 'When to use vs']
        for key in diff_keys:
            if key in sections:
                parts.append(f"\n**{key}**:\n{sections[key]}")
                break
        
        # Add parameter information from execute() method docstring
        try:
            execute_doc = inspect.getdoc(self.execute)
            if execute_doc:
                # Extract Args section with better regex
                args_pattern = r'\*\*Args?:\*\*\s*\n(.*?)(?=\n\s*\*\*(?:Returns?|Examples?|Note|Error|WARNING|⚠️)|\Z)'
                args_match = re.search(args_pattern, execute_doc, re.DOTALL | re.IGNORECASE)
                if args_match:
                    args_text = args_match.group(1).strip()
                    # Clean up: normalize whitespace but preserve structure
                    args_text = re.sub(r'[ \t]+', ' ', args_text)  # Normalize spaces
                    args_text = re.sub(r'\n\s*\n', '\n\n', args_text)  # Normalize blank lines
                    if args_text:
                        parts.append(f"\n**Parameters**:\n{args_text}")
                
                # Extract Examples section
                examples_pattern = r'\*\*Examples?:\*\*\s*\n(.*?)(?=\n\s*\*\*(?:Note|Error|WARNING|⚠️)|\Z)'
                examples_match = re.search(examples_pattern, execute_doc, re.DOTALL | re.IGNORECASE)
                if examples_match:
                    examples_text = examples_match.group(1).strip()
                    if examples_text:
                        parts.append(f"\n**Examples**:\n{examples_text}")
        except Exception:
            # If extraction fails, continue without parameters/examples
            pass
        
        result = '\n'.join(parts)
        
        # If result is too short, add simple description
        # Handle case where description might be a property/method
        try:
            desc_str = self.description if isinstance(self.description, str) else str(self.description)
            if len(result) < len(desc_str) + 50:
                result = f"{desc_str}\n\n{result}"
        except Exception:
            # If description access fails, just return what we have
            pass
        
        return result
