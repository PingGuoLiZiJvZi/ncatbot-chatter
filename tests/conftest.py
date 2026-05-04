import os
import sys
import tempfile
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary SQLite database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory."""
    return str(tmp_path)
