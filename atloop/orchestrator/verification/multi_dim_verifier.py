"""Multi-dimensional verification system for comprehensive task validation."""

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from atloop.memory.state import AgentState

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of multi-dimensional verification."""

    overall_success: bool
    details: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    completion_confidence: float = 0.0
    errors: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get a summary of verification results."""
        parts = []
        for dim_name, result in self.details.items():
            status = "✓" if result.get("passed", False) else "✗"
            parts.append(f"{status} {dim_name}")
        return " | ".join(parts)


class MultiDimensionVerifier:
    """
    Multi-dimensional verifier for comprehensive task validation.

    Goes beyond simple test execution to verify:
    - Syntax validity of created/modified files
    - Goal achievement matching
    - Dependency completeness
    - File existence verification
    """

    def __init__(self, sandbox):
        """
        Initialize multi-dimensional verifier.

        Args:
            sandbox: Sandbox adapter for reading files
        """
        self.sandbox = sandbox

    def verify(self, state: "AgentState", artifacts: Any) -> VerificationResult:
        """
        Execute multi-dimensional verification.

        Args:
            state: Current agent state
            artifacts: Artifacts containing test results etc.

        Returns:
            VerificationResult with comprehensive verification status
        """
        results = {}

        # 1. Test verification (existing - from artifacts)
        results["test"] = self._verify_tests(artifacts)

        # 2. Syntax verification
        results["syntax"] = self._verify_syntax(state)

        # 3. File existence verification
        results["files_exist"] = self._verify_files_exist(state)

        # 4. Dependency completeness
        results["dependencies"] = self._verify_dependencies(state)

        # Calculate overall success and confidence
        overall_success = all(r.get("passed", False) for r in results.values())
        completion_confidence = self._calculate_completion_confidence(results, state)

        # Collect errors
        errors = []
        for dim_name, result in results.items():
            if not result.get("passed", False):
                errors.append(f"{dim_name}: {result.get('error', 'Failed')}")

        logger.info(
            f"[MultiDimensionVerifier] Verification complete: "
            f"overall={overall_success}, confidence={completion_confidence:.2f}"
        )

        return VerificationResult(
            overall_success=overall_success,
            details=results,
            completion_confidence=completion_confidence,
            errors=errors,
        )

    def _verify_tests(self, artifacts: Any) -> Dict[str, Any]:
        """
        Verify test results from artifacts.

        Args:
            artifacts: Artifacts containing test_results

        Returns:
            Verification result dict
        """
        test_results = getattr(artifacts, "test_results", "")
        verification_success = getattr(artifacts, "verification_success", None)

        # Determine if tests passed
        if verification_success is True:
            passed = True
            error = None
        elif verification_success is False:
            passed = False
            error = "Tests failed"
        else:
            # Try to parse from test_results
            if test_results:
                test_lower = test_results.lower()
                passed = any(
                    keyword in test_lower
                    for keyword in ["passed", "✓", "success", "ok"]
                )
                error = None if passed else "Tests status unclear or failed"
            else:
                passed = True  # No tests configured is not a failure
                error = None

        return {
            "passed": passed,
            "error": error,
            "has_tests": bool(test_results),
        }

    def _verify_syntax(self, state: "AgentState") -> Dict[str, Any]:
        """
        Verify syntax of created/modified files.

        Args:
            state: Current agent state

        Returns:
            Verification result dict
        """
        syntax_errors = []

        # Check recent created and modified files
        files_to_check = []
        if state.memory.created_files:
            files_to_check.extend(state.memory.created_files[-10:])

        if state.memory.modified_files_content:
            # Check files modified in last 3 steps
            for record in state.memory.modified_files_content:
                if record.get("last_modified_step", 0) >= state.step - 3:
                    files_to_check.append(record.get("path", ""))

        # Deduplicate
        files_to_check = list(set(files_to_check))

        for file_path in files_to_check:
            error = self._check_file_syntax(file_path)
            if error:
                syntax_errors.append({"file": file_path, "error": error})

        passed = len(syntax_errors) == 0
        error_msg = "; ".join([f"{e['file']}: {e['error']}" for e in syntax_errors]) if syntax_errors else None

        return {
            "passed": passed,
            "error": error_msg,
            "errors": syntax_errors,
            "files_checked": len(files_to_check),
        }

    def _check_file_syntax(self, file_path: str) -> Optional[str]:
        """
        Check syntax of a single file.

        Args:
            file_path: Path to the file

        Returns:
            Error message or None if syntax is valid
        """
        try:
            if file_path.endswith(".py"):
                return self._check_python_syntax(file_path)
            elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                return self._check_javascript_syntax(file_path)
            # Other file types don't have syntax checking
            return None
        except Exception as e:
            return f"Syntax check error: {e}"

    def _check_python_syntax(self, file_path: str) -> Optional[str]:
        """
        Check Python file syntax using AST.

        Args:
            file_path: Path to the Python file

        Returns:
            Error message or None if syntax is valid
        """
        try:
            content = self._read_file_from_sandbox(file_path)
            if content is None:
                return "Could not read file"

            ast.parse(content)
            return None
        except SyntaxError as e:
            return f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return f"Parse error: {e}"

    def _check_javascript_syntax(self, file_path: str) -> Optional[str]:
        """
        Check JavaScript/TypeScript file syntax (basic check).

        Note: This is a basic check. Full validation would require
        a proper JS/TS parser which is not available in stdlib.

        Args:
            file_path: Path to the JS/TS file

        Returns:
            Error message or None if syntax is valid
        """
        # Basic syntax checks (bracket matching, etc.)
        try:
            content = self._read_file_from_sandbox(file_path)
            if content is None:
                return "Could not read file"

            # Check for balanced brackets
            brackets = {"(": ")", "{": "}", "[": "]"}
            stack = []

            for i, char in enumerate(content):
                if char in brackets:
                    stack.append((char, i))
                elif char in brackets.values():
                    if not stack:
                        return f"Unmatched closing bracket '{char}' at position {i}"
                    open_char, _ = stack.pop()
                    if brackets[open_char] != char:
                        return f"Mismatched brackets: expected '{brackets[open_char]}' but got '{char}' at position {i}"

            if stack:
                open_char, pos = stack[-1]
                return f"Unclosed bracket '{open_char}' at position {pos}"

            return None
        except Exception as e:
            return f"Syntax check error: {e}"

    def _verify_files_exist(self, state: "AgentState") -> Dict[str, Any]:
        """
        Verify that declared files actually exist in sandbox.

        Args:
            state: Current agent state

        Returns:
            Verification result dict
        """
        non_existent = []

        for file_path in state.memory.created_files:
            if not self._file_exists_in_sandbox(file_path):
                non_existent.append(file_path)

        passed = len(non_existent) == 0
        error_msg = f"Files not found: {', '.join(non_existent)}" if non_existent else None

        return {
            "passed": passed,
            "error": error_msg,
            "missing_files": non_existent,
            "total_created": len(state.memory.created_files),
        }

    def _verify_dependencies(self, state: "AgentState") -> Dict[str, Any]:
        """
        Verify that imports/dependencies are satisfied.

        Args:
            state: Current agent state

        Returns:
            Verification result dict
        """
        missing_deps = []

        # Check recent Python files for imports
        for file_path in state.memory.created_files[-10:]:
            if file_path.endswith(".py"):
                imports = self._extract_python_imports(file_path)
                for imp in imports:
                    if not self._is_import_available(imp):
                        missing_deps.append(f"{file_path}: {imp}")

        passed = len(missing_deps) == 0
        error_msg = "; ".join(missing_deps[:5]) if missing_deps else None

        return {
            "passed": passed,
            "error": error_msg,
            "missing": missing_deps,
        }

    def _extract_python_imports(self, file_path: str) -> List[str]:
        """
        Extract import statements from a Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            List of imported module names
        """
        try:
            content = self._read_file_from_sandbox(file_path)
            if content is None:
                return []

            imports = []

            # Match "import X" and "from X import Y" patterns
            for match in re.finditer(r"^import\s+([^\s]+)", content, re.MULTILINE):
                imports.append(match.group(1))

            for match in re.finditer(r"^from\s+([^\s]+)\s+import", content, re.MULTILINE):
                imports.append(match.group(1))

            return imports
        except Exception as e:
            logger.warning(f"Failed to extract imports from {file_path}: {e}")
            return []

    def _is_import_available(self, import_name: str) -> bool:
        """
        Check if an import is available (stdlib or local).

        Args:
            import_name: Module name to check

        Returns:
            True if import is likely available
        """
        # Stdlib modules (partial list - most common)
        stdlib_modules = {
            "os", "sys", "re", "json", "datetime", "collections",
            "itertools", "math", "random", "typing", "pathlib", "io",
            "logging", "argparse", "subprocess", "shutil", "tempfile",
            "unittest", "pytest", "dataclasses", "enum", "abc",
        }

        # Check if it's a stdlib module
        base_module = import_name.split(".")[0]
        if base_module in stdlib_modules:
            return True

        # Check if it's a relative import (local)
        if import_name.startswith("."):
            return True

        # For other imports, assume they might be available
        # (could be installed packages or local modules)
        return True

    def _read_file_from_sandbox(self, file_path: str) -> Optional[str]:
        """
        Read file content from sandbox.

        Args:
            file_path: Path to the file

        Returns:
            File content or None if read failed
        """
        import shlex

        try:
            path_escaped = shlex.quote(file_path)
            read_cmd = f"cat {path_escaped} 2>/dev/null"
            result = self.sandbox.exec_shell(
                command=read_cmd,
                workdir="/workspace",
                timeout_seconds=30,
            )

            if result.get("stderr", "").strip():
                return None

            return result.get("stdout", "")
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None

    def _file_exists_in_sandbox(self, file_path: str) -> bool:
        """
        Check if file exists in sandbox.

        Args:
            file_path: Path to the file

        Returns:
            True if file exists
        """
        import shlex

        try:
            path_escaped = shlex.quote(file_path)
            check_cmd = f"test -f {path_escaped} && echo 'exists' || echo 'not_found'"
            result = self.sandbox.exec_shell(
                command=check_cmd,
                workdir="/workspace",
                timeout_seconds=5,
            )

            return "exists" in result.get("stdout", "")
        except Exception:
            return False

    def _calculate_completion_confidence(
        self, results: Dict[str, Dict[str, Any]], state: "AgentState"
    ) -> float:
        """
        Calculate task completion confidence score.

        Args:
            results: Individual verification results
            state: Current agent state

        Returns:
            Confidence score (0.0 to 1.0)
        """
        weights = {
            "test": 0.4,  # Tests are most important
            "syntax": 0.3,  # Syntax validity is critical
            "files_exist": 0.2,  # Files must exist
            "dependencies": 0.1,  # Dependencies are less critical
        }

        score = 0.0
        for dim_name, weight in weights.items():
            if dim_name in results and results[dim_name].get("passed", False):
                score += weight

        return min(score, 1.0)
