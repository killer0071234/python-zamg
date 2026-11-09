"""Tests for Python-version-specific request timeouts."""

import sys
from importlib import import_module

import pytest


@pytest.mark.parametrize("module", ["src.zamg.nwp", "src.zamg.zamg"])
def test_timeout_implementation(module: str) -> None:
    """Test both clients use the timeout implementation for this Python version."""
    expected_module = "asyncio" if sys.version_info >= (3, 11) else "async_timeout"

    assert import_module(module).timeout is import_module(expected_module).timeout
