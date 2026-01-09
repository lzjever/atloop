# End-to-End Testing for atloop CLI

## Overview

The end-to-end tests in `test_e2e_cli_subprocess.py` test the atloop CLI by executing the actual command as a subprocess, matching the user's exact usage pattern.

## Test Command Format

The tests use the exact command format:
```bash
timeout 120 uv run python -m atloop.cli.main execute \
  --workspace ./test_ws/w1 \
  --prompt "write some arbitrary python code" \
  --local-test
```

## Test Philosophy

These tests are **strict** and do **not accommodate bugs** in the business code:
- Exit code must be 0 for successful execution
- Files must be created when expected
- Content must be validated
- Errors in business code are reported as test failures

## Running Tests

### Run all E2E tests
```bash
uv run pytest tests/test_e2e_cli_subprocess.py -v
```

### Run a specific test
```bash
uv run pytest tests/test_e2e_cli_subprocess.py::TestCLIE2ESubprocess::test_e2e_cli_execute_basic_write_python_code -v
```

### Run with timeout (recommended for CI)
```bash
timeout 600 uv run pytest tests/test_e2e_cli_subprocess.py -v --tb=short
```

## Test Cases

1. **test_e2e_cli_execute_basic_write_python_code**: Basic test matching the reference command
2. **test_e2e_cli_execute_create_specific_file**: Tests specific file creation with content validation
3. **test_e2e_cli_execute_empty_workspace**: Tests execution in empty workspace
4. **test_e2e_cli_execute_existing_files_preserved**: Tests that existing files are not modified
5. **test_e2e_cli_execute_invalid_workspace**: Tests handling of invalid workspace paths
6. **test_e2e_cli_execute_timeout_handling**: Tests timeout behavior
7. **test_e2e_cli_execute_multiple_files**: Tests creation of multiple files
8. **test_e2e_cli_execute_with_syntax_error_handling**: Tests handling of syntax errors
9. **test_e2e_cli_execute_output_validation**: Tests CLI output validation
10. **test_e2e_cli_execute_workspace_permissions**: Tests workspace permission handling
11. **test_e2e_cli_execute_file_creation_despite_error**: Detects bugs where files are created but exit code is wrong

## Known Issues

If tests fail with exit code 1 but files are created, this indicates a bug in the business code where:
- The task is completed (files created)
- But the system reports failure due to internal errors (e.g., NoneType errors)

The tests will report these bugs clearly to help with debugging.

## Test Duration

Each test can take 30-120 seconds depending on:
- LLM API response time
- Task complexity
- System performance

Total test suite may take 10-20 minutes to complete.
