---
name: best-practices
description: Software development best practices. Use when you need guidance on coding standards, code quality, or development workflows.
---

# Best Practices Skill

This skill provides software development best practices for atloop.

## Code Quality

### 1. Write Clean Code
- Use meaningful variable names
- Keep functions small and focused
- Add docstrings for functions and classes
- Follow PEP 8 (Python) or language-specific style guides

### 2. Error Handling
- Always handle edge cases (empty inputs, None values, etc.)
- Use appropriate exception types
- Provide clear error messages
- Don't silently ignore errors

### 3. Testing
- Write tests for new functionality
- Test edge cases and error conditions
- Keep tests simple and focused
- Run tests after making changes

## Development Workflow

### 1. Incremental Development
- Make small, focused changes
- Test after each change
- Commit frequently with clear messages

### 2. Code Review Checklist
- [ ] Code follows style guide
- [ ] Functions are well-documented
- [ ] Error handling is appropriate
- [ ] Tests are included and passing
- [ ] No hardcoded values or secrets

### 3. Refactoring
- Improve code structure without changing behavior
- Run tests before and after refactoring
- Make one change at a time

## Python-Specific

### 1. Type Hints
- Use type hints for function parameters and return values
- Helps with IDE support and documentation

### 2. Docstrings
- Use Google or NumPy style docstrings
- Document parameters, return values, and exceptions

### 3. Imports
- Group imports: standard library, third-party, local
- Use absolute imports when possible

## Common Pitfalls

### 1. Division by Zero
Always check for zero before division:
```python
if b == 0:
    raise ZeroDivisionError("Cannot divide by zero")
return a / b
```

### 2. None Checks
Check for None before accessing attributes:
```python
if obj is not None:
    result = obj.method()
```

### 3. File Operations
Always handle file not found errors:
```python
try:
    with open(path) as f:
        content = f.read()
except FileNotFoundError:
    # Handle error
```

## Security

### 1. Input Validation
- Validate all user inputs
- Sanitize inputs before processing
- Use parameterized queries for databases

### 2. Secrets Management
- Never hardcode secrets in code
- Use environment variables or secure vaults
- Don't commit secrets to version control

### 3. Path Traversal
- Validate file paths
- Use `os.path.join()` or `pathlib.Path` for path construction
- Avoid user-controlled paths in file operations

