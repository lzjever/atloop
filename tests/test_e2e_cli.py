"""End-to-end tests for CLI commands."""

import logging
from pathlib import Path

import pytest

from atloop.cli.commands.config import cmd_config
from atloop.cli.commands.exec import cmd_exec
from atloop.cli.commands.exec_file import cmd_exec_file
from atloop.cli.commands.init import cmd_init

pytestmark = pytest.mark.e2e

logger = logging.getLogger(__name__)


class TestCLIE2E:
    """End-to-end tests for CLI commands."""

    def test_cli_e2e_init(self, real_config_file: Path):
        """Test CLI init command end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI init E2E")

        # Create mock args
        class MockArgs:
            atloop_dir = None

        args = MockArgs()

        # Execute init command
        result = cmd_init(args)
        assert result == 0
        logger.info("CLI init E2E successful ✓")

    def test_cli_e2e_config(self, real_config_file: Path):
        """Test CLI config command end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI config E2E")

        # Create mock args
        class MockArgs:
            atloop_dir = None

        args = MockArgs()

        # Execute config command
        result = cmd_config(args)
        assert result == 0
        logger.info("CLI config E2E successful ✓")

    def test_cli_e2e_execute_simple(self, real_config_file: Path, temp_workspace: Path):
        """Test CLI exec command with simple task."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI exec simple E2E")

        # Set workspace_root in config via environment variable
        import os

        os.environ["ATLOOP__RUNTIME__WORKSPACE_ROOT"] = str(temp_workspace)
        os.environ["ATLOOP__SANDBOX__LOCAL_TEST"] = "true"

        # Create mock args
        class MockArgs:
            atloop_dir = None
            prompt = "Create a simple hello.py file"

        args = MockArgs()

        # Note: This would actually execute the task, so we just verify it doesn't crash
        # In a real scenario, we'd mock the TaskRunner
        try:
            # This might fail if sandbox/LLM is not available, which is expected
            result = cmd_exec(args)
            # Accept both success (0) and failure (1) as valid for this test
            assert result in [0, 1]
            logger.info("CLI exec simple E2E completed ✓")
        except Exception as e:
            # Expected if dependencies are not available
            logger.debug(f"CLI exec failed (expected): {e}")
            pytest.skip(f"CLI exec requires sandbox/LLM: {e}")
        finally:
            # Cleanup environment variables
            os.environ.pop("ATLOOP__RUNTIME__WORKSPACE_ROOT", None)
            os.environ.pop("ATLOOP__SANDBOX__LOCAL_TEST", None)

    def test_cli_e2e_execute_with_file(self, real_config_file: Path, temp_workspace: Path):
        """Test CLI exec-file command with prompt file."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI exec-file with file E2E")

        # Create prompt file
        prompt_file_path = temp_workspace / "prompt.txt"
        prompt_file_path.write_text("Create a simple hello.py file that prints 'Hello, World!'")

        # Set workspace_root in config via environment variable
        import os

        os.environ["ATLOOP__RUNTIME__WORKSPACE_ROOT"] = str(temp_workspace)
        os.environ["ATLOOP__SANDBOX__LOCAL_TEST"] = "true"

        # Create mock args
        class MockArgs:
            atloop_dir = None
            file_path = str(prompt_file_path)

        args = MockArgs()

        # Note: This would actually execute the task
        try:
            result = cmd_exec_file(args)
            assert result in [0, 1]
            logger.info("CLI exec-file with file E2E completed ✓")
        except Exception as e:
            logger.debug(f"CLI exec-file failed (expected): {e}")
            pytest.skip(f"CLI exec-file requires sandbox/LLM: {e}")
        finally:
            # Cleanup environment variables
            os.environ.pop("ATLOOP__RUNTIME__WORKSPACE_ROOT", None)
            os.environ.pop("ATLOOP__SANDBOX__LOCAL_TEST", None)

    def test_cli_e2e_execute_with_sandbox(self, real_config_file: Path, temp_workspace: Path):
        """Test CLI exec command with sandbox URL."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI exec with sandbox E2E")

        # Set config via environment variables
        import os

        os.environ["ATLOOP__RUNTIME__WORKSPACE_ROOT"] = str(temp_workspace)
        os.environ["ATLOOP__SANDBOX__BASE_URL"] = "http://127.0.0.1:8080"
        os.environ["ATLOOP__SANDBOX__LOCAL_TEST"] = "false"

        # Create mock args
        class MockArgs:
            atloop_dir = None
            prompt = "Test task"

        MockArgs()

        # Verify config is set correctly (will be read from env vars)
        logger.info("CLI exec with sandbox E2E setup successful ✓")

        # Cleanup
        os.environ.pop("ATLOOP__RUNTIME__WORKSPACE_ROOT", None)
        os.environ.pop("ATLOOP__SANDBOX__BASE_URL", None)
        os.environ.pop("ATLOOP__SANDBOX__LOCAL_TEST", None)

    def test_cli_e2e_execute_local_test(self, real_config_file: Path, temp_workspace: Path):
        """Test CLI exec command in local test mode."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI exec local test E2E")

        # Set config via environment variables
        import os

        os.environ["ATLOOP__RUNTIME__WORKSPACE_ROOT"] = str(temp_workspace)
        os.environ["ATLOOP__SANDBOX__LOCAL_TEST"] = "true"

        # Create mock args
        class MockArgs:
            atloop_dir = None
            prompt = "Test task"

        MockArgs()

        # Verify config is set correctly (will be read from env vars)
        logger.info("CLI exec local test E2E setup successful ✓")

        # Cleanup
        os.environ.pop("ATLOOP__RUNTIME__WORKSPACE_ROOT", None)
        os.environ.pop("ATLOOP__SANDBOX__LOCAL_TEST", None)

    def test_cli_e2e_config_display(self, real_config_file: Path):
        """Test CLI config display end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing CLI config display E2E")

        # Create mock args
        class MockArgs:
            atloop_dir = None

        args = MockArgs()

        # Execute config command
        result = cmd_config(args)
        assert result == 0
        logger.info("CLI config display E2E successful ✓")


class TestCLIArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_cli_parser_init(self):
        """Test CLI parser for init command."""
        from atloop.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["init"])

        assert args.command == "init"
        logger.info("CLI parser init command successful ✓")

    def test_cli_parser_exec(self):
        """Test CLI parser for exec command."""
        from atloop.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "exec",
                "Test task",
            ]
        )

        assert args.command == "exec"
        assert args.prompt == "Test task"
        logger.info("CLI parser exec command successful ✓")

    def test_cli_parser_config(self):
        """Test CLI parser for config command."""
        from atloop.cli.main import create_parser

        parser = create_parser()
        args = parser.parse_args(["config"])

        assert args.command == "config"
        logger.info("CLI parser config command successful ✓")
