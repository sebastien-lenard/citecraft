import json
from collections import namedtuple
from pathlib import Path
from zipfile import BadZipFile

import pytest
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from manuscript_reference_lister import DataLoader

# Container for paths and expected data to keep tests readable
EnvPaths = namedtuple("EnvPaths", ["dir", "docx", "docx_content", "json", "json_data"])


@pytest.fixture
def env(tmp_path: Path) -> EnvPaths:
    """Fixture to set up a temporary filesystem using pytest's tmp_path."""
    # 1. Setup DOCX
    docx_path = tmp_path / "test.docx"
    content = ["Hello World", "Testing folders.", "End of file."]
    doc = Document()
    for line in content:
        doc.add_paragraph(line)
    doc.save(str(docx_path))

    # 2. Setup JSON
    json_path = tmp_path / "test.json"
    data = {"app": "DataLoader", "version": 1.0}
    json_path.write_text(json.dumps(data), encoding="utf-8")

    return EnvPaths(tmp_path, docx_path, content, json_path, data)


# --- DOCX TESTS ---


def test_extract_text_matches_input(env: EnvPaths) -> None:
    """Verify extracted text matches the seeded document content."""
    loader = DataLoader(env.docx)
    assert loader.extract_text_from_docx() == "\n".join(env.docx_content)


def test_extract_text_corrupted_docx(
    env: EnvPaths, caplog: pytest.LogCaptureFixture
) -> None:
    """Check error handling for non-zip files disguised as .docx."""
    corrupt_path = env.dir / "corrupt.docx"
    corrupt_path.write_bytes(b"Not a zip file")

    # Case 1: Exception raised
    loader = DataLoader(corrupt_path, raise_exception=True)
    with pytest.raises((PackageNotFoundError, BadZipFile)):
        loader.extract_text_from_docx()

    # Case 2: Silent failure with logging
    loader_no_fail = DataLoader(corrupt_path, raise_exception=False)
    assert loader_no_fail.extract_text_from_docx() is None
    assert "Invalid or corrupted .docx" in caplog.text


# --- JSON TESTS ---


def test_load_json_success(env: EnvPaths) -> None:
    """Verify loading from a valid .json file."""
    loader = DataLoader(env.json)
    assert loader.load_json() == env.json_data


@pytest.mark.parametrize(
    "raise_flag, expected_behavior", [(True, "raise"), (False, None)]
)
def test_load_json_invalid_format(
    env: EnvPaths,
    caplog: pytest.LogCaptureFixture,
    raise_flag: bool,
    expected_behavior: str | None,
) -> None:
    """Ensure malformed JSON triggers correct exception or warning."""
    bad_json = env.dir / "bad.json"
    bad_json.write_text("{ 'wrong': True }")

    loader = DataLoader(bad_json, raise_exception=raise_flag)

    if expected_behavior == "raise":
        with pytest.raises(json.JSONDecodeError):
            loader.load_json()
    else:
        assert loader.load_json() is expected_behavior
        assert "Invalid JSON format" in caplog.text


def test_load_json_with_validator_success(env: EnvPaths) -> None:
    """Verify that load_json returns data when all items pass validation."""
    # Setup a list of items
    list_path = env.dir / "list.json"
    list_data = [{"id": 1}, {"id": 2}]
    list_path.write_text(json.dumps(list_data))

    loader = DataLoader(list_path)
    # Validator checks if 'id' key exists
    result = loader.load_json(validator=lambda x: "id" in x)

    assert result == list_data


@pytest.mark.parametrize("raise_flag", [True, False])
def test_load_json_with_validator_failure(
    env: EnvPaths, caplog: pytest.LogCaptureFixture, raise_flag: bool
) -> None:
    """Verify that load_json returns None/raises when validation fails."""
    list_path = env.dir / "invalid_list.json"
    # Second item is missing 'id'
    list_data = [{"id": 1}, {"name": "missing_id"}]
    list_path.write_text(json.dumps(list_data))

    loader = DataLoader(list_path, raise_exception=raise_flag)

    def validator(x):
        return "id" in x

    if raise_flag:
        with pytest.raises(ValueError, match="Schema validation failed"):
            loader.load_json(validator=validator)
    else:
        assert loader.load_json(validator=validator) is None
        assert "Schema validation failed" in caplog.text


# --- GENERAL TESTS ---


@pytest.mark.parametrize(
    "raise_flag, expected_behavior", [(True, "raise"), (False, "log")]
)
def test_file_not_found_behavior(
    env: EnvPaths,
    caplog: pytest.LogCaptureFixture,
    raise_flag: bool,
    expected_behavior: str,
) -> None:
    """Verify FileNotFoundError handling and logging."""
    missing_file = env.dir / "missing.txt"

    if expected_behavior == "raise":
        with pytest.raises(FileNotFoundError):
            DataLoader(missing_file, raise_exception=raise_flag)
    else:
        # Check that initialization logs a warning instead of crashing
        DataLoader(missing_file, raise_exception=raise_flag)
        assert "Input file not found" in caplog.text
