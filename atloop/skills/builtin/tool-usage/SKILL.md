---
name: tool-usage
description: Best practices for using tools effectively. Use when you need guidance on tool usage patterns, error handling, or tool selection.
---

# Tool Usage Skill

This skill provides best practices for using tools effectively in atloop.

## Tool Selection

### When to use `run`
- Execute shell commands
- Run tests, linters, formatters
- Search files (`find`, `grep`)
- Check system status (`git status`, `ls`)

### When to use `write_file`
- Create new files
- Modify existing files
- Write configuration files
- Generate code

**Important**: Only one `write_file` action per response to avoid token limit issues.

## Best Practices

### 1. Error Handling
- Always check tool execution results
- Don't rely solely on exit codes - check stdout/stderr content
- Many commands return exit_code=0 even when there are errors

### 2. File Operations
- Use `run("cat file.py")` to read files (no separate read_file tool)
- Use `write_file` to create or modify files
- Check file existence before operations: `run("test -f file.py && echo exists")`

### 3. Testing
- Run tests after making changes: `run("python3 -m pytest test_file.py -v")`
- Check test output carefully - exit_code may be 0 even if tests fail
- Look for "FAILED" or "ERROR" in test output

### 4. Exploration
- Use `run("find . -name '*.py'")` to discover files
- Use `run("grep -r 'pattern' .")` to search content
- Use `run("ls -la")` to list directory contents

### 5. Git Operations
- Use `run("git status")` to check repository state
- Use `run("git diff")` to see changes
- Use `run("git log --oneline -5")` to see recent commits

## Common Patterns

### Reading a file
```bash
run("cat path/to/file.py")
```

### Writing a file
```json
{
  "tool": "write_file",
  "args": {
    "path": "path/to/file.py",
    "content": "file content here"
  }
}
```

### Running tests
```bash
run("python3 -m pytest test_file.py -v")
```

### Finding files
```bash
run("find . -name '*.py' -type f")
```

### Searching content
```bash
run("grep -rn 'pattern' .")
```

## Error Recovery

When a tool fails:
1. Check the full stdout/stderr output
2. Identify the specific error
3. Fix the issue and retry
4. Don't assume exit_code=0 means success

