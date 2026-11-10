"""Focused execution of the real JavaScript editor without launching a browser."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_drive_time_editor_state_transitions():
    """feat-010/AC-108 feat-010/AC-109: stale previews cannot corrupt saved-area drafts."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for the editor state checks")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, "tests/drive_time_editor_checks.cjs"], cwd=root,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
