"""End-to-end tests for real-world scenarios."""

import logging
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import Budget, TaskSpec
from atloop.orchestrator.coordinator import WorkflowCoordinator

pytestmark = pytest.mark.e2e

logger = logging.getLogger(__name__)


class TestE2ECalculatorBugfix:
    """E2E test for calculator bugfix scenario."""

    def test_e2e_calculator_bugfix_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E calculator bugfix scenario setup."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E calculator bugfix scenario")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create calculator with bug
        calc_file = temp_workspace / "calculator.py"
        calc_file.write_text(
            """def add(a, b):
    return a - b  # Bug: should be a + b

def subtract(a, b):
    return a + b  # Bug: should be a - b
"""
        )

        # Create failing test
        test_file = temp_workspace / "test_calculator.py"
        test_file.write_text(
            """from calculator import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
"""
        )

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-calc-bugfix",
            goal="Fix the bugs in calculator.py so all tests pass",
            workspace_root=str(temp_workspace),
            task_type="bugfix",
            constraints=["All tests must pass"],
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        assert coordinator.task_spec.task_id == "e2e-calc-bugfix"
        assert coordinator.state_manager.agent_state.phase == "DISCOVER"

        # Verify files exist
        assert calc_file.exists()
        assert test_file.exists()
        logger.info("Calculator bugfix scenario setup successful ✅")


class TestE2EPythonProjectSetup:
    """E2E test for Python project setup scenario."""

    def test_e2e_python_project_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E Python project setup scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E Python project setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create Python project structure
        (temp_workspace / "src" / "mypackage").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "tests").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "src" / "mypackage" / "__init__.py").write_text("")
        (temp_workspace / "src" / "mypackage" / "module.py").write_text(
            "def hello(): return 'world'\n"
        )
        (temp_workspace / "tests" / "test_module.py").write_text(
            "from src.mypackage.module import hello\ndef test_hello(): assert hello() == 'world'\n"
        )
        (temp_workspace / "pyproject.toml").write_text(
            "[project]\nname = 'mypackage'\nversion = '0.1.0'\n"
        )

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-python-setup",
            goal="Set up Python project structure",
            workspace_root=str(temp_workspace),
            task_type="feature",
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None

        # Verify project structure
        assert (temp_workspace / "src" / "mypackage" / "__init__.py").exists()
        assert (temp_workspace / "src" / "mypackage" / "module.py").exists()
        assert (temp_workspace / "tests" / "test_module.py").exists()
        assert (temp_workspace / "pyproject.toml").exists()
        logger.info("Python project setup scenario successful ✅")


class TestE2ENodeJSProjectSetup:
    """E2E test for Node.js project setup scenario."""

    def test_e2e_nodejs_project_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E Node.js project setup scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E Node.js project setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create Node.js project structure
        (temp_workspace / "src").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "src" / "index.js").write_text(
            "function add(a, b) { return a + b; }\nmodule.exports = { add };\n"
        )
        (temp_workspace / "package.json").write_text('{"name": "myapp", "version": "1.0.0"}\n')

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-nodejs-setup",
            goal="Set up Node.js project structure",
            workspace_root=str(temp_workspace),
            task_type="feature",
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None

        # Verify project structure
        assert (temp_workspace / "src" / "index.js").exists()
        assert (temp_workspace / "package.json").exists()
        logger.info("Node.js project setup scenario successful ✅")


class TestE2EGoProjectSetup:
    """E2E test for Go project setup scenario."""

    def test_e2e_go_project_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E Go project setup scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E Go project setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create Go project structure
        (temp_workspace / "cmd" / "myapp").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "cmd" / "myapp" / "main.go").write_text(
            "package main\n\nfunc main() {}\n"
        )
        (temp_workspace / "go.mod").write_text("module myapp\n\ngo 1.21\n")

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-go-setup",
            goal="Set up Go project structure",
            workspace_root=str(temp_workspace),
            task_type="feature",
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None

        # Verify project structure
        assert (temp_workspace / "cmd" / "myapp" / "main.go").exists()
        assert (temp_workspace / "go.mod").exists()
        logger.info("Go project setup scenario successful ✅")


class TestE2EMultiLanguageProject:
    """E2E test for multi-language project scenario."""

    def test_e2e_multi_language_project(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E multi-language project scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E multi-language project")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create multi-language project
        (temp_workspace / "python").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "javascript").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "go").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "python" / "app.py").write_text("print('Hello')\n")
        (temp_workspace / "javascript" / "app.js").write_text("console.log('Hello');\n")
        (temp_workspace / "go" / "app.go").write_text("package main\n\nfunc main() {}\n")

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-multi-lang",
            goal="Work with multi-language project",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None

        # Verify files exist
        assert (temp_workspace / "python" / "app.py").exists()
        assert (temp_workspace / "javascript" / "app.js").exists()
        assert (temp_workspace / "go" / "app.go").exists()
        logger.info("Multi-language project scenario successful ✅")


class TestE2ELargeCodebase:
    """E2E test for large codebase scenario."""

    def test_e2e_large_codebase(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E large codebase scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E large codebase")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create large codebase (many files)
        for i in range(20):
            (temp_workspace / f"module_{i}.py").write_text(f"def func_{i}(): return {i}\n")

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-large-codebase",
            goal="Work with large codebase",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None

        # Verify files exist
        files = list(temp_workspace.glob("module_*.py"))
        assert len(files) == 20
        logger.info("Large codebase scenario successful ✅")


class TestE2EComplexRefactoring:
    """E2E test for complex refactoring scenario."""

    def test_e2e_complex_refactoring(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E complex refactoring scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E complex refactoring")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create complex codebase with dependencies
        (temp_workspace / "old_module.py").write_text(
            """class OldClass:
    def old_method(self):
        return "old"

def old_function():
    return "old"
"""
        )
        (temp_workspace / "consumer.py").write_text(
            """from old_module import OldClass, old_function

obj = OldClass()
result = old_function()
"""
        )

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-refactor",
            goal="Refactor old_module.py to new_module.py",
            workspace_root=str(temp_workspace),
            task_type="refactor",
            constraints=["Maintain backward compatibility"],
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        assert coordinator.task_spec.task_type == "refactor"

        # Verify files exist
        assert (temp_workspace / "old_module.py").exists()
        assert (temp_workspace / "consumer.py").exists()
        logger.info("Complex refactoring scenario successful ✅")
