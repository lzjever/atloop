"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Use real config from user's home directory
REAL_CONFIG_DIR = Path.home() / ".titan" / "config"
REAL_CONFIG_FILE = REAL_CONFIG_DIR / "titan.yaml"


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
def temp_titan_dir() -> Generator[Path, None, None]:
    """Fixture providing temporary Titan directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        titan_dir = Path(tmpdir) / ".titan"
        titan_dir.mkdir(parents=True, exist_ok=True)
        config_dir = titan_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        yield titan_dir
