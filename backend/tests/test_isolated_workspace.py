"""
Tests for IsolatedWorkspace disk sandbox security, boundaries, and teardown.
"""
import pytest
from pathlib import Path
from app.remediation.workspace import IsolatedWorkspace
from app.remediation.patch_generator import PatchValidationError


def test_isolated_workspace_lifecycle(tmp_path: Path):
    ws = IsolatedWorkspace(
        review_id="rev-123",
        remediation_id="rem-456",
        base_dir=tmp_path,
    )

    with ws:
        assert ws.workspace_path.exists()
        ws.populate({"src/app.py": "print('hello')", "config/settings.json": "{}"})

        assert ws.file_exists("src/app.py")
        assert ws.read_file("src/app.py") == "print('hello')"

        # Check list files
        files = ws.list_files()
        assert "src/app.py" in files
        assert "config/settings.json" in files

        # Overwrite file
        ws.write_file("src/app.py", "print('modified')")
        assert ws.read_file("src/app.py") == "print('modified')"

    # After exit context manager, workspace should be deleted
    assert not ws.workspace_path.exists()


def test_isolated_workspace_blocks_path_escape(tmp_path: Path):
    ws = IsolatedWorkspace(
        review_id="rev-123",
        remediation_id="rem-456",
        base_dir=tmp_path,
    )

    with ws:
        with pytest.raises(PatchValidationError):
            ws.write_file("../../outside.txt", "malicious payload")

        with pytest.raises(PatchValidationError):
            ws.read_file("../../outside.txt")
