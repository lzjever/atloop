"""Project profile detection."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from atloop.runtime import ToolRuntime


@dataclass
class ProjectProfile:
    """Project profile information."""

    language: Optional[str] = None  # python, node, go, rust, java
    package_manager: Optional[str] = None  # pip, npm, yarn, pnpm, cargo, go mod
    test_commands: List[str] = None  # List of test command candidates
    format_commands: List[str] = None  # List of format command candidates
    lint_commands: List[str] = None  # List of lint command candidates

    def __post_init__(self):
        """Initialize default values."""
        if self.test_commands is None:
            self.test_commands = []
        if self.format_commands is None:
            self.format_commands = []
        if self.lint_commands is None:
            self.lint_commands = []

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "language": self.language,
            "package_manager": self.package_manager,
            "test_commands": self.test_commands,
            "format_commands": self.format_commands,
            "lint_commands": self.lint_commands,
        }


class ProjectProfileDetector:
    """Detect project profile from workspace."""

    def __init__(self, tool_runtime: ToolRuntime):
        """
        Initialize project profile detector.

        Args:
            tool_runtime: Tool runtime instance
        """
        self.tool_runtime = tool_runtime

    def detect(self) -> ProjectProfile:
        """
        Detect project profile.

        Returns:
            ProjectProfile instance
        """
        profile = ProjectProfile()

        # Check for Python
        if (
            self._file_exists("pyproject.toml")
            or self._file_exists("requirements.txt")
            or self._file_exists("setup.py")
        ):
            profile.language = "python"
            profile.package_manager = "pip"
            profile.test_commands = ["pytest -q", "python -m pytest -q", "python -m unittest"]
            profile.format_commands = ["black .", "autopep8 --in-place --recursive ."]
            profile.lint_commands = ["ruff check .", "pylint .", "flake8 ."]
            return profile

        # Check for Node.js
        if self._file_exists("package.json"):
            profile.language = "node"
            # Check package manager
            package_json = self._read_file("package.json")
            if package_json:
                if '"pnpm"' in package_json or "pnpm-lock.yaml" in self._list_files():
                    profile.package_manager = "pnpm"
                    profile.test_commands = ["pnpm test", "pnpm run test"]
                elif '"yarn"' in package_json or "yarn.lock" in self._list_files():
                    profile.package_manager = "yarn"
                    profile.test_commands = ["yarn test", "yarn run test"]
                else:
                    profile.package_manager = "npm"
                    profile.test_commands = ["npm test", "npm run test"]
            else:
                profile.package_manager = "npm"
                profile.test_commands = ["npm test", "npm run test"]

            profile.format_commands = ["prettier --write .", "npx prettier --write ."]
            profile.lint_commands = ["eslint .", "npx eslint ."]
            return profile

        # Check for Go
        if self._file_exists("go.mod"):
            profile.language = "go"
            profile.package_manager = "go mod"
            profile.test_commands = ["go test ./...", "go test -v ./..."]
            profile.format_commands = ["gofmt -w .", "go fmt ./..."]
            profile.lint_commands = ["golangci-lint run", "golint ./..."]
            return profile

        # Check for Rust
        if self._file_exists("Cargo.toml"):
            profile.language = "rust"
            profile.package_manager = "cargo"
            profile.test_commands = ["cargo test", "cargo test --verbose"]
            profile.format_commands = ["cargo fmt"]
            profile.lint_commands = ["cargo clippy"]
            return profile

        # Check for Java
        if self._file_exists("pom.xml"):
            profile.language = "java"
            profile.package_manager = "maven"
            profile.test_commands = ["mvn test", "mvn verify"]
            profile.format_commands = []
            profile.lint_commands = ["mvn checkstyle:check"]
            return profile

        if self._file_exists("build.gradle") or self._file_exists("build.gradle.kts"):
            profile.language = "java"
            profile.package_manager = "gradle"
            profile.test_commands = ["gradle test", "./gradlew test"]
            profile.format_commands = []
            profile.lint_commands = []

        return profile

    def _file_exists(self, filename: str) -> bool:
        """Check if file exists."""
        import shlex

        filename_escaped = shlex.quote(filename)
        result = self.tool_runtime.run(
            f"test -f {filename_escaped} 2>/dev/null && echo 'exists' || echo 'not'", timeout_sec=5
        )
        return result.ok and "exists" in result.stdout

    def _read_file(self, filename: str) -> Optional[str]:
        """Read file content."""
        import shlex

        filename_escaped = shlex.quote(filename)
        result = self.tool_runtime.run(
            f"head -n 50 {filename_escaped} 2>/dev/null || cat {filename_escaped} 2>/dev/null",
            timeout_sec=5,
        )
        if result.ok:
            return result.stdout
        return None

    def _list_files(self) -> str:
        """List files in current directory."""
        result = self.tool_runtime.run("ls -a 2>/dev/null || echo ''", timeout_sec=5)
        if result.ok:
            return result.stdout
        return ""
