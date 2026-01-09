"""End-to-end tests for CLI commands using subprocess execution.

These tests execute the actual CLI command as a subprocess and validate:
- Command execution and exit codes
- Output validation
- File creation and content verification
- Error handling
- Edge cases and boundary conditions
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

logger = logging.getLogger(__name__)


class TestCLIE2ESubprocess:
    """End-to-end tests for CLI using subprocess execution."""

    @pytest.fixture
    def test_workspace(self, tmp_path):
        """Create a temporary workspace for testing."""
        workspace = tmp_path / "test_ws" / "w1"
        workspace.mkdir(parents=True, exist_ok=True)
        yield workspace
        # Cleanup
        if workspace.exists():
            shutil.rmtree(workspace.parent, ignore_errors=True)

    def _run_cli_command(
        self,
        workspace: Path,
        prompt: str,
        local_test: bool = True,
        timeout: int = 120,
        expect_success: bool = True,
    ) -> tuple[int, str, str]:
        """
        Run the CLI command as subprocess and return exit code, stdout, stderr.

        Args:
            workspace: Workspace directory path
            prompt: Task prompt
            local_test: Whether to use local test mode
            timeout: Command timeout in seconds
            expect_success: Whether to expect successful execution

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = [
            "timeout",
            str(timeout),
            "uv",
            "run",
            "python",
            "-m",
            "atloop.cli.main",
            "execute",
            "--workspace",
            str(workspace),
            "--prompt",
            prompt,
        ]

        if local_test:
            cmd.append("--local-test")

        logger.info(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # Add buffer for subprocess timeout
                cwd=Path(__file__).parent.parent,  # Run from project root
            )

            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr

            logger.info(f"Exit code: {exit_code}")
            logger.debug(f"Stdout:\n{stdout}")
            if stderr:
                logger.debug(f"Stderr:\n{stderr}")

            return exit_code, stdout, stderr

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout} seconds")
            return 124, "", "Command timed out"
        except Exception as e:
            logger.error(f"Error running command: {e}")
            return 1, "", str(e)

    def test_e2e_cli_execute_basic_write_python_code(
        self, real_config_file: Path, test_workspace: Path
    ):
        """
        Test basic CLI execution: write some arbitrary Python code.

        This is the reference test case matching the user's example command.
        """
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("=" * 70)
        logger.info("Testing CLI execute: write some arbitrary python code")
        logger.info("=" * 70)

        # Ensure workspace is clean
        for file in test_workspace.glob("*"):
            if file.is_file():
                file.unlink()

        # Run the command
        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        # Check if files were created (even if exit code indicates failure)
        python_files = list(test_workspace.glob("*.py"))
        files_created = len(python_files) > 0

        # Validate exit code - should be 0 for success
        # If exit code is not 0, this indicates a bug in the business code
        assert exit_code == 0, (
            f"Command failed with exit code {exit_code}. "
            f"This indicates a bug in the business code - the task may have been partially completed. "
            f"Files created: {files_created} ({len(python_files)} Python files). "
            f"Stdout: {stdout[-2000:]}\nStderr: {stderr[-2000:]}"
        )

        # Validate that at least one Python file was created
        assert len(python_files) > 0, (
            f"No Python files were created in workspace {test_workspace}. "
            f"Files present: {list(test_workspace.iterdir())}"
        )

        # Validate that the created file has content
        for py_file in python_files:
            content = py_file.read_text(encoding="utf-8")
            assert len(content) > 0, f"Python file {py_file} was created but is empty"
            # Basic validation: should contain some Python-like content
            # (not just whitespace or comments)
            non_comment_lines = [
                line.strip()
                for line in content.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]
            assert len(non_comment_lines) > 0, (
                f"Python file {py_file} contains only comments or whitespace"
            )

        logger.info(f"✅ Test passed: Created {len(python_files)} Python file(s)")

    def test_e2e_cli_execute_create_specific_file(
        self, real_config_file: Path, test_workspace: Path
    ):
        """Test CLI execution with specific file creation request."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: create specific file")

        target_file = test_workspace / "hello_world.py"
        if target_file.exists():
            target_file.unlink()

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="Create a file named hello_world.py that prints 'Hello, World!'",
            local_test=True,
            timeout=120,
        )

        assert exit_code == 0, (
            f"Command failed with exit code {exit_code}. Stdout: {stdout}\nStderr: {stderr}"
        )

        # Validate specific file was created
        assert target_file.exists(), (
            f"Target file {target_file} was not created. "
            f"Files present: {list(test_workspace.iterdir())}"
        )

        # Validate file content
        content = target_file.read_text(encoding="utf-8")
        assert "Hello" in content or "hello" in content.lower(), (
            f"File {target_file} does not contain expected 'Hello' text. Content: {content[:200]}"
        )

        logger.info("✅ Test passed: Specific file created with correct content")

    def test_e2e_cli_execute_empty_workspace(self, real_config_file: Path, test_workspace: Path):
        """Test CLI execution with empty workspace."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: empty workspace")

        # Ensure workspace is empty
        for item in test_workspace.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        assert exit_code == 0, (
            f"Command failed with exit code {exit_code} on empty workspace. "
            f"Stdout: {stdout}\nStderr: {stderr}"
        )

        # Should still create files
        files = list(test_workspace.iterdir())
        assert len(files) > 0, (
            f"No files were created in empty workspace. Workspace: {test_workspace}"
        )

        logger.info("✅ Test passed: Files created in empty workspace")

    def test_e2e_cli_execute_existing_files_preserved(
        self, real_config_file: Path, test_workspace: Path
    ):
        """Test that existing files are preserved during execution."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: preserve existing files")

        # Create an existing file
        existing_file = test_workspace / "existing.py"
        original_content = "print('This file already exists')"
        existing_file.write_text(original_content)

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        assert exit_code == 0, (
            f"Command failed with exit code {exit_code}. Stdout: {stdout}\nStderr: {stderr}"
        )

        # Validate existing file is still there and unchanged
        assert existing_file.exists(), f"Existing file {existing_file} was deleted or moved"

        current_content = existing_file.read_text(encoding="utf-8")
        assert current_content == original_content, (
            f"Existing file {existing_file} was modified. "
            f"Original: {original_content}\nCurrent: {current_content}"
        )

        logger.info("✅ Test passed: Existing files preserved")

    def test_e2e_cli_execute_invalid_workspace(self, real_config_file: Path, tmp_path):
        """Test CLI execution with invalid/non-existent workspace."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: invalid workspace")

        invalid_workspace = tmp_path / "non_existent" / "workspace"

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=invalid_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
            expect_success=False,  # May succeed if workspace is created
        )

        # The command might succeed (if workspace is auto-created) or fail
        # Either way, we should get a valid exit code
        assert exit_code in [0, 1], (
            f"Unexpected exit code {exit_code}. Stdout: {stdout}\nStderr: {stderr}"
        )

        logger.info(f"✅ Test passed: Handled invalid workspace (exit_code={exit_code})")

    def test_e2e_cli_execute_timeout_handling(self, real_config_file: Path, test_workspace: Path):
        """Test that timeout is properly handled."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: timeout handling")

        # Use a very short timeout to test timeout behavior
        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=5,  # Very short timeout
        )

        # Exit code 124 is timeout from the timeout command
        # Exit code 1 might be returned if the process handles timeout gracefully
        assert exit_code in [0, 1, 124], (
            f"Unexpected exit code {exit_code} for timeout test. Stdout: {stdout}\nStderr: {stderr}"
        )

        logger.info(f"✅ Test passed: Timeout handled (exit_code={exit_code})")

    def test_e2e_cli_execute_multiple_files(self, real_config_file: Path, test_workspace: Path):
        """Test CLI execution that creates multiple files."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: create multiple files")

        # Clean workspace
        for file in test_workspace.glob("*"):
            if file.is_file():
                file.unlink()

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="Create two Python files: file1.py and file2.py, each with a simple function",
            local_test=True,
            timeout=120,
        )

        assert exit_code == 0, (
            f"Command failed with exit code {exit_code}. Stdout: {stdout}\nStderr: {stderr}"
        )

        # Should have created at least 2 files
        python_files = list(test_workspace.glob("*.py"))
        assert len(python_files) >= 2, (
            f"Expected at least 2 Python files, found {len(python_files)}. "
            f"Files: {[f.name for f in python_files]}"
        )

        # Validate each file has content
        for py_file in python_files:
            content = py_file.read_text(encoding="utf-8")
            assert len(content) > 0, f"File {py_file} is empty"

        logger.info(f"✅ Test passed: Created {len(python_files)} Python files")

    def test_e2e_cli_execute_with_syntax_error_handling(
        self, real_config_file: Path, test_workspace: Path
    ):
        """Test that the system handles tasks that might result in syntax errors."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: syntax error handling")

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        # Command should complete (even if code has issues)
        assert exit_code in [0, 1], (
            f"Unexpected exit code {exit_code}. Stdout: {stdout}\nStderr: {stderr}"
        )

        # If files were created, they should be readable
        python_files = list(test_workspace.glob("*.py"))
        for py_file in python_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                # File should be readable even if it has syntax errors
                assert content is not None
            except Exception as e:
                pytest.fail(f"Failed to read created file {py_file}: {e}")

        logger.info("✅ Test passed: Syntax error handling works")

    def test_e2e_cli_execute_output_validation(self, real_config_file: Path, test_workspace: Path):
        """Test that CLI output contains expected information."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: output validation")

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        # Validate exit code
        assert exit_code in [0, 1], (
            f"Unexpected exit code {exit_code}. Stdout: {stdout}\nStderr: {stderr}"
        )

        # Output should not be None (even if empty)
        assert stdout is not None, "Stdout should not be None"
        assert stderr is not None, "Stderr should not be None"

        # If command succeeded, should have some output
        if exit_code == 0:
            # Successful execution should produce some output
            # (at minimum, file creation messages or status)
            total_output = stdout + stderr
            assert len(total_output) > 0 or len(list(test_workspace.glob("*"))) > 0, (
                "Successful execution should produce output or create files"
            )

        logger.info("✅ Test passed: Output validation works")

    def test_e2e_cli_execute_workspace_permissions(
        self, real_config_file: Path, test_workspace: Path
    ):
        """Test CLI execution with workspace permission checks."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: workspace permissions")

        # Ensure workspace is writable
        test_workspace.chmod(0o755)

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        # Should succeed with writable workspace
        assert exit_code == 0, (
            f"Command failed with exit code {exit_code} on writable workspace. "
            f"Stdout: {stdout}\nStderr: {stderr}"
        )

        logger.info("✅ Test passed: Workspace permissions handled correctly")

    def test_e2e_cli_execute_file_creation_despite_error(
        self, real_config_file: Path, test_workspace: Path
    ):
        """
        Test that verifies file creation even when exit code indicates failure.

        This test helps identify bugs where the task is partially completed
        but the system reports failure due to internal errors.
        """
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI execute: file creation despite error")

        # Clean workspace
        for file in test_workspace.glob("*"):
            if file.is_file():
                file.unlink()

        exit_code, stdout, stderr = self._run_cli_command(
            workspace=test_workspace,
            prompt="write some arbitrary python code",
            local_test=True,
            timeout=120,
        )

        # Check if files were created regardless of exit code
        python_files = list(test_workspace.glob("*.py"))

        # If files were created but exit code is not 0, this is a bug
        if len(python_files) > 0 and exit_code != 0:
            logger.warning(
                f"⚠️  BUG DETECTED: Files were created ({len(python_files)} files) "
                f"but exit code is {exit_code} (expected 0). "
                f"This indicates the task was completed but the system reported failure."
            )
            # Validate file content
            for py_file in python_files:
                content = py_file.read_text(encoding="utf-8")
                assert len(content) > 0, f"File {py_file} is empty"
            # This is still a failure - exit code should be 0 when task succeeds
            pytest.fail(
                f"Business code bug: Task completed (created {len(python_files)} files) "
                f"but returned exit code {exit_code}. Stderr: {stderr[-1000:]}"
            )

        # Normal case: if exit code is 0, files should be created
        if exit_code == 0:
            assert len(python_files) > 0, (
                f"Exit code is 0 but no Python files were created. "
                f"Files present: {list(test_workspace.iterdir())}"
            )

        logger.info("✅ Test passed: File creation validation works")
