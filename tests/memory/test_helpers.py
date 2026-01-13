"""Test helper functions for memory module tests."""

import re
from typing import Dict, List, Optional


def assert_memory_format_valid(text: str) -> None:
    """
    Assert that the memory format text is valid according to design.
    
    Args:
        text: Formatted memory text to validate
    
    Raises:
        AssertionError: If format is invalid
    """
    # Check required sections
    required_sections = [
        "Task Overview",
        "Execution Plan",
        "Recent Activity",
        "Tool Execution Results",
        "Current State",
    ]
    
    for section in required_sections:
        if section not in text:
            raise AssertionError(f"Required section '{section}' not found in formatted text")
    
    # Check format structure (should have proper markdown headers)
    lines = text.split("\n")
    header_count = sum(1 for line in lines if line.startswith("###"))
    
    if header_count < len(required_sections):
        raise AssertionError(
            f"Expected at least {len(required_sections)} sections, "
            f"found {header_count} headers"
        )


def extract_sections(text: str) -> Dict[str, str]:
    """
    Extract sections from formatted memory text.
    
    Args:
        text: Formatted memory text
    
    Returns:
        Dictionary mapping section names to their content
    """
    sections = {}
    current_section = None
    current_content = []
    
    for line in text.split("\n"):
        # Check for section header (### Section Name)
        match = re.match(r"^###\s+(.+)$", line)
        if match:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            
            # Start new section
            current_section = match.group(1)
            current_content = []
        else:
            if current_section:
                current_content.append(line)
    
    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()
    
    return sections


def count_tool_results(text: str) -> int:
    """
    Count the number of tool execution results in formatted text.
    
    Args:
        text: Formatted memory text
    
    Returns:
        Number of tool results found
    """
    # Look for tool result entries (format: "- Step N: [status] [tool]")
    pattern = r"^- Step \d+:\s+[✓✗]\s+\["
    matches = re.findall(pattern, text, re.MULTILINE)
    return len(matches)


def extract_tool_results(text: str) -> List[Dict[str, str]]:
    """
    Extract tool execution results from formatted text.
    
    Args:
        text: Formatted memory text
    
    Returns:
        List of tool result dictionaries with keys: step, status, tool, args
    """
    results = []
    
    # Find the "Tool Execution Results" section
    tool_section_match = re.search(
        r"###\s+Tool Execution Results.*?\n(.*?)(?=###|\Z)",
        text,
        re.DOTALL,
    )
    
    if not tool_section_match:
        return results
    
    tool_section = tool_section_match.group(1)
    
    # Extract individual tool results
    # Pattern: "- Step N: [status] [tool] (args)"
    pattern = r"- Step (\d+):\s+([✓✗])\s+\[([^\]]+)\]\s*(?:\(([^)]+)\))?"
    
    for match in re.finditer(pattern, tool_section):
        step = int(match.group(1))
        status = "success" if match.group(2) == "✓" else "failure"
        tool = match.group(3)
        args = match.group(4) if match.group(4) else ""
        
        results.append({
            "step": step,
            "status": status,
            "tool": tool,
            "args": args,
        })
    
    return results


def assert_no_duplicate_tool_results(text: str) -> None:
    """
    Assert that there are no duplicate tool results in the formatted text.
    
    Args:
        text: Formatted memory text
    
    Raises:
        AssertionError: If duplicate tool results are found
    """
    results = extract_tool_results(text)
    
    # Check for duplicates (same step + tool + args)
    seen = set()
    for result in results:
        key = (result["step"], result["tool"], result["args"])
        if key in seen:
            raise AssertionError(
                f"Duplicate tool result found: Step {result['step']}, "
                f"Tool {result['tool']}, Args {result['args']}"
            )
        seen.add(key)


def count_sections(text: str) -> int:
    """
    Count the number of sections in formatted text.
    
    Args:
        text: Formatted memory text
    
    Returns:
        Number of sections found
    """
    # Count markdown headers (###)
    pattern = r"^###\s+"
    matches = re.findall(pattern, text, re.MULTILINE)
    return len(matches)
