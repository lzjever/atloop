"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import AtloopConfig

# Use real config from user's home directory
REAL_CONFIG_DIR = Path.home() / ".atloop" / "config"
REAL_CONFIG_FILE = REAL_CONFIG_DIR / "atloop.yaml"


@pytest.fixture
def real_config_dir() -> Path:
    """Fixture providing real config directory."""
    return REAL_CONFIG_DIR


@pytest.fixture
def real_config_file() -> Path:
    """Fixture providing real config file path."""
    return REAL_CONFIG_FILE


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Fixture providing temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        yield workspace


@pytest.fixture
def temp_atloop_dir() -> Generator[Path, None, None]:
    """Fixture providing temporary atloop directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        atloop_dir = Path(tmpdir) / ".atloop"
        atloop_dir.mkdir(parents=True, exist_ok=True)
        config_dir = atloop_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        yield atloop_dir


@pytest.fixture(autouse=True)
def setup_config(temp_atloop_dir: Path) -> Generator[AtloopConfig, None, None]:
    """
    Auto-setup ConfigLoader for all tests.

    Creates a minimal test config if no real config exists.
    This fixture is automatically used by all tests (autouse=True).
    """
    # Try to use real config first
    if REAL_CONFIG_FILE.exists():
        ConfigLoader.setup()
    else:
        # Create minimal test config
        config_file = temp_atloop_dir / "config" / "atloop.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("""
ai:
  completion:
    model: test-model
    api_base: https://test.api.com
    api_key: test-key
  performance:
    max_tokens_input: 32000
    max_tokens_output: 4000
sandbox:
  base_url: http://test:8080
  local_test: true
runtime:
  default_budget:
    max_llm_calls: 10
    max_tool_calls: 50
    max_wall_time_sec: 3600
""")
        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))

    config = ConfigLoader.get()
    yield config

    # Cleanup (if needed)
    # ConfigLoader doesn't need explicit cleanup
