"""Tests for standalone module launchers and selftest modes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_mobile_bridge_selftest():
    """Verify python -m cache_vault.modules.mobile_bridge --selftest returns 0."""
    result = subprocess.run(
        [sys.executable, "-m", "cache_vault.modules.mobile_bridge", "--selftest"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "mobile_bridge selftest OK" in result.stdout


def test_image_viewer_selftest():
    """Verify python -m cache_vault.modules.image_viewer --selftest returns 0."""
    result = subprocess.run(
        [sys.executable, "-m", "cache_vault.modules.image_viewer", "--selftest"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "image_viewer selftest OK" in result.stdout


def test_mobile_bridge_launcher_output():
    """Verify standalone mobile bridge launcher output (non-selftest)."""
    result = subprocess.run(
        [sys.executable, "-m", "cache_vault.modules.mobile_bridge"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Mobile Bridge Doctor" in result.stdout
    assert "Connection Doctor" in result.stdout


def test_image_viewer_launcher_output():
    """Verify standalone image viewer launcher output (non-selftest)."""
    result = subprocess.run(
        [sys.executable, "-m", "cache_vault.modules.image_viewer"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Image Viewer" in result.stdout
    assert "Storage path" in result.stdout
