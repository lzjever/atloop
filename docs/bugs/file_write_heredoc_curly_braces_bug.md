# Bug Report: File Content with Curly Braces Missing When Written via write_file

## Summary

When the LLM generates file content containing curly braces (e.g., `{error_output}`), those lines are completely missing from the file written to the sandbox, even though they appear in the LLM's response.

## Severity

**HIGH** - Data loss/corruption. File content is silently dropped, leading to incorrect files being written.

## Symptoms

- LLM generates content with lines containing `{error_output}` or similar curly brace patterns
- Content appears correctly in LLM response and placeholder extraction
- File written to sandbox is missing those lines entirely
- No error messages are generated (silent failure)

## Example

**LLM Generated Content:**
```python
### **Error Details:**
The buggy_script.py has been executed and produced the following critical errors:

```
{error_output}
```

### **Specific Errors Identified:**
```

**Actual File Written:**
```python
### **Error Details:**
The buggy_script.py has been executed and produced the following critical errors:



### **Specific Errors Identified:**
```

Notice the lines with `{error_output}` are completely missing.

## Root Cause Analysis

### Pipeline Flow

1. **LLM Response Parsing** (`atloop/llm/schema.py`):
   - `_extract_file_contents()` extracts content between `---((WRITE_FILE_CONTENT_*))---` delimiters
   - Content with `{error_output}` is correctly preserved as-is
   - ✅ **Status: Working correctly**

2. **Placeholder Replacement** (`atloop/orchestrator/phases/placeholder_replacer.py`):
   - `{error_output}` is NOT a recognized placeholder (only `WRITE_FILE_CONTENT_*`, `EDIT_FILE_CONTENT_*`, etc. are valid)
   - Content passes through unchanged (as expected for literal text)
   - ✅ **Status: Working correctly**

3. **write_file Tool** (`atloop/tools/filesystem/write_file.py`):
   - Constructs heredoc command: `cat > file <<'FILE_EOF'\n{content}\nFILE_EOF`
   - Uses single quotes around `FILE_EOF` delimiter (should prevent expansion)
   - Passes command as string to `sandbox.exec_shell()`
   - ⚠️ **Status: Command construction looks correct, but heredoc may have issues**

4. **Sandbox Adapter** (`atloop/runtime/sandbox_adapter.py`):
   - Calls `noxrunner.client.exec_shell()` with command string
   - ✅ **Status: Working correctly**

5. **NoxRunner Client** (`noxrunner/client.py`):
   - Converts command string to `["sh", "-c", "command_string"]` format
   - ✅ **Status: Working correctly**

6. **Sandbox Manager** (`sandbox/manager-service/main.go`):
   - Detects `sh -c` pattern → uses `isCommandWithStringArg()`
   - Uses `escapeForDoubleQuotes()` which:
     - Escapes `\` and `"`
     - **DOES NOT escape `$`, `` ` ``, or `{`/`}`**
   - Wraps entire command in double quotes: `sh -c "escaped_command"`
   - ❌ **Status: This is where the bug occurs**

### The Bug

**Location:** `sandbox/manager-service/main.go` - `execCmd()` function

**Problem:**
1. The heredoc command is wrapped in double quotes: `sh -c "cat > file <<'FILE_EOF'\n{content}\nFILE_EOF"`
2. The `escapeForDoubleQuotes()` function does NOT escape curly braces `{` and `}`
3. When the heredoc content contains `{error_output}`, the shell may interpret it as:
   - Brace expansion (bash/zsh feature)
   - Parameter expansion attempt
   - Or the heredoc may fail to process correctly
4. Result: Lines containing `{error_output}` are either:
   - Removed by shell brace expansion
   - Cause heredoc to terminate early
   - Fail silently during shell processing

**Code Reference:**
```go
// sandbox/manager-service/main.go:532-542
func escapeForDoubleQuotes(s string) string {
	// Escape backslashes first (must be first to avoid double-escaping)
	escaped := strings.ReplaceAll(s, "\\", "\\\\")
	// Escape double quotes
	escaped = strings.ReplaceAll(escaped, "\"", "\\\"")
	// DO NOT escape $ - we want variable expansion in double quotes
	// DO NOT escape ` - backticks are also allowed in double quotes
	// ❌ BUG: Also does NOT escape { or } - causes issues with heredoc content
	return escaped
}
```

**The heredoc delimiter uses single quotes** (`<<'FILE_EOF'`), which should prevent expansion, but because the **entire command string is wrapped in double quotes**, the shell may still process the heredoc content incorrectly.

## Impact

- **Data Loss**: File content is silently corrupted
- **Silent Failure**: No error messages, making debugging difficult
- **Affects**: Any file content containing curly braces `{...}` patterns
- **Common Cases**: 
  - Template strings with placeholders
  - JSON-like structures in code comments
  - Error messages with `{error_output}` patterns
  - Python f-string examples in documentation

## Proposed Solutions

### Option 1: Use Base64 Encoding (Recommended)

**Pros:**
- Handles ALL special characters safely
- No shell escaping issues
- Works with arbitrary binary content
- Most secure approach

**Implementation:**
```python
# In write_file.py
import base64
content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
cmd = f"echo {shlex.quote(content_b64)} | base64 -d > {path_escaped}"
```

**Cons:**
- Requires base64 encoding/decoding
- Slightly more complex

### Option 2: Use stdin Piping (Best for Large Files)

**Pros:**
- Avoids command line length limits
- Handles all special characters
- Most robust for large content
- No encoding overhead

**Implementation:**
- Modify sandbox adapter to support stdin
- Pipe content via stdin: `cat > file` with content piped

**Cons:**
- Requires changes to sandbox API
- More complex implementation

### Option 3: Fix Heredoc Escaping

**Pros:**
- Minimal changes to existing code
- Preserves current approach

**Implementation:**
- Escape curly braces in heredoc content
- Use more unique delimiter
- Ensure heredoc content is properly quoted

**Cons:**
- Still vulnerable to other special characters
- Complex escaping logic

### Option 4: Use printf Instead of Heredoc

**Pros:**
- Simpler than heredoc
- Better control over escaping

**Implementation:**
```python
# Escape % and backslashes, then use printf
escaped_content = content.replace('\\', '\\\\').replace('%', '%%')
cmd = f"printf '%s' {shlex.quote(escaped_content)} > {path_escaped}"
```

**Cons:**
- Still requires careful escaping
- Less readable than heredoc

## Recommended Solution

**Use Option 1 (Base64 Encoding)** because:
1. It's the safest approach for arbitrary content
2. Minimal changes required (only in `write_file.py`)
3. No shell interpretation issues
4. Works with all special characters
5. Already supported by all Unix systems

## Files to Modify

1. `atloop/atloop/tools/filesystem/write_file.py` - Change heredoc to base64 encoding
2. (Optional) `sandbox/manager-service/main.go` - Consider escaping curly braces in `escapeForDoubleQuotes()` for defense in depth

## Testing

After fix, test with:
1. Content containing `{error_output}`
2. Content containing `{variable}` patterns
3. Content containing `{{double}}` braces
4. Content containing `$VAR` and other shell special characters
5. Large files (>100KB)
6. Binary content (if applicable)

## Related Issues

- This may also affect `edit_file` and `append_file` tools which use similar heredoc approach
- Check `atloop/atloop/tools/filesystem/edit_file.py` and `append_file.py` for similar issues

## References

- Heredoc documentation: https://www.gnu.org/software/bash/manual/html_node/Redirections.html
- Shell brace expansion: https://www.gnu.org/software/bash/manual/html_node/Brace-Expansion.html
- Base64 encoding: Standard Unix utility available everywhere

---

**Reported:** [Date]
**Status:** Open
**Priority:** High
**Assigned:** [TBD]
