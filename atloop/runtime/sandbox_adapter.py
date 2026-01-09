"""Sandbox adapter for noxrunner."""

from pathlib import Path
from typing import Dict, List, Optional

from noxrunner import NoxRunnerClient

from atloop.config.models import SandboxConfig


class SandboxAdapter:
    """Adapter for noxrunner sandbox execution."""

    def __init__(self, config: SandboxConfig, session_id: str):
        """
        Initialize sandbox adapter.

        Args:
            config: Sandbox configuration
            session_id: Unique session identifier
        """
        self.config = config
        self.session_id = session_id
        self.client = NoxRunnerClient(
            base_url=config.base_url,
            timeout=config.timeout,
            local_test=config.local_test,
        )
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize sandbox (create if needed).

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            # Create sandbox
            self.client.create_sandbox(
                session_id=self.session_id,
                ttl_seconds=self.config.session_ttl_seconds,
                image=self.config.image,
                cpu_limit=self.config.cpu_limit,
                memory_limit=self.config.memory_limit,
                ephemeral_storage_limit=self.config.ephemeral_storage_limit,
            )
            self._initialized = True
            return True
        except Exception as e:
            print(f"Failed to create sandbox: {e}")
            return False

    def upload_workspace(self, workspace_path: str) -> bool:
        """
        Upload workspace to sandbox.

        Args:
            workspace_path: Local workspace path

        Returns:
            True if successful
        """
        if not self._initialized:
            if not self.initialize():
                return False

        workspace = Path(workspace_path)
        if not workspace.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        try:
            # Upload all files in workspace
            files = {}
            for file_path in workspace.rglob("*"):
                if file_path.is_file():
                    # Skip .git directory
                    if ".git" in file_path.parts:
                        continue
                    # Get relative path
                    rel_path = file_path.relative_to(workspace)
                    # Read file content
                    with open(file_path, "rb") as f:
                        files[str(rel_path)] = f.read()

            if files:
                return self.client.upload_files(
                    session_id=self.session_id,
                    files=files,
                    dest="/workspace",
                )
            return True
        except Exception as e:
            print(f"Failed to upload workspace: {e}")
            return False

    def initialize_git(self) -> bool:
        """
        Initialize git repository in sandbox if not exists.

        Returns:
            True if successful
        """
        if not self._initialized:
            if not self.initialize():
                return False

        try:
            # Check if git exists
            result = self.client.exec_shell(
                self.session_id,
                "git rev-parse --git-dir 2>/dev/null || echo 'not-git'",
                workdir="/workspace",
            )

            if result["exitCode"] == 0 and "not-git" not in result["stdout"]:
                # Git already initialized
                return True

            # Initialize git
            result = self.client.exec_shell(
                self.session_id,
                "git init",
                workdir="/workspace",
            )
            if result["exitCode"] != 0:
                return False

            # Add all files
            result = self.client.exec_shell(
                self.session_id,
                "git add .",
                workdir="/workspace",
            )
            if result["exitCode"] != 0:
                return False

            # Create initial commit
            result = self.client.exec_shell(
                self.session_id,
                "git commit -m 'Initial commit' || git config user.email 'agent@atloop' && git config user.name 'atloop Agent' && git commit -m 'Initial commit'",
                workdir="/workspace",
            )

            return result["exitCode"] == 0
        except Exception as e:
            print(f"Failed to initialize git: {e}")
            return False

    def exec_shell(
        self,
        command: str,
        workdir: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
    ) -> Dict:
        """
        Execute shell command in sandbox.

        Args:
            command: Shell command to execute
            workdir: Working directory
            env: Environment variables
            timeout_seconds: Command timeout

        Returns:
            Dict with exitCode, stdout, stderr, durationMs
        """
        if not self._initialized:
            if not self.initialize():
                return {
                    "exitCode": 1,
                    "stdout": "",
                    "stderr": "Sandbox not initialized",
                    "durationMs": 0,
                }

        return self.client.exec_shell(
            session_id=self.session_id,
            command=command,
            workdir=workdir,
            env=env,
            timeout_seconds=timeout_seconds,
        )

    def exec(
        self,
        cmd: List[str],
        workdir: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
    ) -> Dict:
        """
        Execute a command in the sandbox (using exec, not exec_shell).
        This returns the correct exit code from the command itself, not from sh.

        Args:
            cmd: Command to execute (list of strings)
            workdir: Working directory
            env: Environment variables
            timeout_seconds: Command timeout

        Returns:
            Dict with exitCode, stdout, stderr, durationMs
        """
        if not self._initialized:
            if not self.initialize():
                return {
                    "exitCode": 1,
                    "stdout": "",
                    "stderr": "Sandbox not initialized",
                    "durationMs": 0,
                }

        return self.client.exec(
            session_id=self.session_id,
            cmd=cmd,
            workdir=workdir,
            env=env,
            timeout_seconds=timeout_seconds,
        )

    def download_workspace(self, workspace_path: str) -> bool:
        """
        Download workspace from sandbox to local directory.

        This method delegates to noxrunner's download_workspace method,
        which handles all the details of downloading and extracting files
        regardless of the backend type (local or remote).

        Args:
            workspace_path: Local workspace path to download to

        Returns:
            True if successful
        """
        if not self._initialized:
            # If sandbox was never initialized, nothing to download
            import logging

            logger = logging.getLogger(__name__)
            logger.debug("Sandbox not initialized, skipping download")
            return True

        try:
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Downloading workspace from sandbox session {self.session_id}")

            # Use noxrunner's download_workspace method
            # This handles both local and remote backends transparently
            success = self.client.download_workspace(
                session_id=self.session_id,
                local_dir=workspace_path,
                src="/workspace",
            )

            if success:
                logger.info(f"Downloaded workspace from sandbox to {workspace_path}")
            else:
                logger.warning("Failed to download workspace from sandbox")

            return success

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to download workspace: {e}")
            logger.debug(f"Exception details: {type(e).__name__}: {e}", exc_info=True)
            return False
