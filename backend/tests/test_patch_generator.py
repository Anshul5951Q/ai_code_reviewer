"""
Tests for unified diff generation, patch validation, and line substitution.
"""
import pytest
from app.remediation.patch_generator import (
    PatchValidationError,
    apply_code_change,
    generate_unified_diff,
    sanitize_relative_path,
    validate_patch_safety,
)


def test_sanitize_relative_path_valid():
    assert sanitize_relative_path("src/api/users.py") == "src/api/users.py"
    assert sanitize_relative_path("components\\ui\\button.tsx") == "components/ui/button.tsx"
    assert sanitize_relative_path("/src/api/users.py") == "src/api/users.py"


def test_sanitize_relative_path_rejects_traversal():
    with pytest.raises(PatchValidationError):
        sanitize_relative_path("../../../etc/passwd")

    with pytest.raises(PatchValidationError):
        sanitize_relative_path("src/../../secret.txt")

    with pytest.raises(PatchValidationError):
        sanitize_relative_path("..")


def test_apply_code_change_clean_substitution():
    orig = "def add(a, b):\n    return a + b\n"
    modified = apply_code_change(
        original_content=orig,
        start_line=2,
        end_line=2,
        original_code="    return a + b",
        replacement_code="    # Add numbers safely\n    return a + b",
    )
    assert "# Add numbers safely" in modified
    assert "def add(a, b):" in modified


def test_generate_unified_diff_format():
    orig = "line 1\nline 2\nline 3\n"
    mod = "line 1\nline 2 modified\nline 3\n"
    diff = generate_unified_diff("test.txt", orig, mod)

    assert "--- a/test.txt" in diff
    assert "+++ b/test.txt" in diff
    assert "-line 2" in diff
    assert "+line 2 modified" in diff


def test_validate_patch_safety_limits():
    valid_diff = "--- a/test.txt\n+++ b/test.txt\n@@ -1 +1 @@\n-old\n+new\n"
    assert validate_patch_safety(["test.txt"], valid_diff, max_files=2, max_lines=10)

    # Exceed file count
    with pytest.raises(PatchValidationError, match="modifies 3 files"):
        validate_patch_safety(["a.py", "b.py", "c.py"], valid_diff, max_files=2)

    # Exceed line count
    large_diff = "\n".join(["+added line" for _ in range(25)])
    with pytest.raises(PatchValidationError, match="modifies 25 lines"):
        validate_patch_safety(["test.py"], large_diff, max_lines=20)

    # Exceed byte size
    with pytest.raises(PatchValidationError, match="Patch size"):
        validate_patch_safety(["test.py"], "x" * 200, max_size_bytes=100)
