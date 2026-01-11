# Tool Output Limit Design

## Overview

This document describes the unified output limit strategy system based on semantic types rather than tool names.

## Design Principles

1. **Semantic Type Based**: Limits are determined by the semantic type of output content, not the tool that produces it
2. **Unified Strategy**: Single source of truth for all output limits
3. **Automatic Application**: Tools declare semantic types, system automatically applies appropriate limits
4. **Easy to Extend**: New tools only need to declare semantic types, no need to modify core logic

## Semantic Types

### OutputSemanticType Enum

```python
class OutputSemanticType(Enum):
    KNOWLEDGE_CONTENT = "knowledge_content"  # skill, documentation
    FILE_CONTENT = "file_content"  # read_file, read_skill_file
    EXECUTION_RESULT = "execution_result"  # run command outputs
    FILE_VIEW_RESULT = "file_view_result"  # run("cat file.txt")
    STATUS_MESSAGE = "status_message"  # write_file, edit_file success/failure
    ERROR_MESSAGE = "error_message"  # stderr outputs
```

## Limit Mappings

### Formatting Limits (last_error.summary)

| Semantic Type | Limit | Use Case |
|--------------|-------|----------|
| KNOWLEDGE_CONTENT | 60KB | Skill content, documentation |
| FILE_CONTENT | 60KB | File reading outputs |
| FILE_VIEW_RESULT | 60KB | File viewing command outputs |
| EXECUTION_RESULT | 8KB | Normal command outputs |
| STATUS_MESSAGE | 2KB | Simple success/failure messages |
| ERROR_MESSAGE | 8KB | Error outputs |

### Memory Summary Limits

| Semantic Type | Limit | Use Case |
|--------------|-------|----------|
| KNOWLEDGE_CONTENT | 12KB | Skill content in memory summary |
| FILE_CONTENT | 12KB | File content in memory summary |
| FILE_VIEW_RESULT | 12KB | File viewing results in memory summary |
| EXECUTION_RESULT | 12KB | Command outputs in memory summary |
| STATUS_MESSAGE | 4KB | Status messages in memory summary |
| ERROR_MESSAGE | 12KB | Error messages in memory summary |

## Tool Implementation

### Declaring Semantic Types

Tools declare their output semantic types by overriding properties in `BaseTool`:

```python
class ReadFileTool(BaseTool):
    @property
    def output_semantic_type(self) -> OutputSemanticType:
        return OutputSemanticType.FILE_CONTENT
```

### Default Behavior

- **Default semantic type**: `STATUS_MESSAGE` (2KB limit)
- **Default stderr type**: `ERROR_MESSAGE` (8KB limit)
- Tools can override these defaults as needed

## Usage

### ToolResultFormatter

```python
# Automatically uses semantic type to determine limit
summary = ToolResultFormatter.format_result_summary(tool_instance, args, result)
```

### MemorySummarizer

```python
# Automatically uses semantic type to determine limit
summary = MemorySummarizer.summarize(
    state,
    tool_registry=registry  # Required for semantic type lookup
)
```

## Benefits

1. **No Missing Tools**: All tools automatically get appropriate limits based on semantic types
2. **Easy Maintenance**: Limits are centralized in `OutputLimitStrategy`
3. **Easy Extension**: New tools just declare semantic types
4. **Consistent Behavior**: Same semantic type always gets same limit

---

**Last Updated**: 2026-01-11  
**Version**: 1.0
