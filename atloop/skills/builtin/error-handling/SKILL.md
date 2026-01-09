---
name: error-handling
description: Error handling strategies and debugging techniques. Use when encountering errors, debugging issues, or handling edge cases.
---

# Error Handling Skill

This skill provides error handling strategies and debugging techniques.

## Understanding Errors

### 1. Exit Codes Are Unreliable
- Many commands return exit_code=0 even when there are errors
- Always check stdout/stderr content, not just exit_code
- Look for error messages in output

### 2. Common Error Patterns
- **Syntax errors**: Check code syntax carefully
- **Import errors**: Verify module installation and paths
- **Type errors**: Check variable types and conversions
- **Value errors**: Validate input values and ranges

## Debugging Strategies

### 1. Read Error Messages Carefully
- Error messages contain valuable information
- Look for line numbers, file paths, and error types
- Check both stdout and stderr

### 2. Check Tool Output
- Don't assume success based on exit_code
- Read full stdout/stderr output
- Look for warnings, errors, or unexpected output

### 3. Incremental Testing
- Test after each change
- Isolate the problem
- Use print statements or logging for debugging

## Error Recovery

### 1. When Tests Fail
1. Read the full test output
2. Identify which test failed and why
3. Check the error message and stack trace
4. Fix the issue and rerun tests

### 2. When Commands Fail
1. Check the command syntax
2. Verify file paths and permissions
3. Check for missing dependencies
4. Review error messages in stderr

### 3. When Code Fails
1. Check syntax and indentation
2. Verify imports and dependencies
3. Check variable types and values
4. Use debugging tools (print, logging, debugger)

## Common Error Types

### Python Errors

**ZeroDivisionError**
```python
if b == 0:
    raise ZeroDivisionError("Cannot divide by zero")
return a / b
```

**FileNotFoundError**
```python
try:
    with open(path) as f:
        content = f.read()
except FileNotFoundError:
    # Handle error
```

**TypeError**
```python
# Check types before operations
if isinstance(value, int):
    result = value * 2
```

**ValueError**
```python
# Validate input values
if value < 0:
    raise ValueError("Value must be non-negative")
```

## Best Practices

### 1. Fail Fast
- Validate inputs early
- Check preconditions
- Raise exceptions for invalid states

### 2. Clear Error Messages
- Provide context in error messages
- Include relevant values
- Suggest fixes when possible

### 3. Logging
- Log errors with context
- Include stack traces for debugging
- Use appropriate log levels

### 4. Error Propagation
- Let exceptions propagate when appropriate
- Catch and handle specific exceptions
- Don't catch all exceptions unless necessary

## Tool-Specific Errors

### Shell Commands
- Check command syntax
- Verify file paths exist
- Check permissions
- Look for error messages in stderr

### File Operations
- Check file existence before reading
- Verify write permissions
- Handle encoding issues
- Check disk space

### Testing
- Read full test output
- Check for test failures, not just exit codes
- Look for assertion errors and exceptions
- Verify test setup and teardown

