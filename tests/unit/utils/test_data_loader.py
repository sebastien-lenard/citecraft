# tests/unit/utils/test_data_loader.py
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import pytest
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from citecraft.utils import DataLoader


@dataclass(frozen=True)
class EnvPaths:
    """Environment configurations and file routes for DataLoader validation."""

    dir_path: Path
    docx_path: Path
    docx_content: list[str]
    json_path: Path
    json_data: dict[str, Any]


@pytest.fixture
def env(tmp_path: Path) -> EnvPaths:
    """Prepare standardized mock file structures on an isolated filesystem."""
    docx_path = tmp_path / "test.docx"
    content = ["Hello World", "Testing folders.", "End of file."]
    doc = Document()
    for line in content:
        doc.add_paragraph(line)
    doc.save(str(docx_path))

    json_path = tmp_path / "test.json"
    data = {"app": "DataLoader", "version": 1.0}
    json_path.write_text(json.dumps(data), encoding="utf-8")

    return EnvPaths(
        dir_path=tmp_path,
        docx_path=docx_path,
        docx_content=content,
        json_path=json_path,
        json_data=data,
    )


# --- DOCX TESTS ---


def test_extract_text_matches_input(env: EnvPaths) -> None:
    """Verify extracted document text matches the original layout perfectly."""
    loader = DataLoader(env.docx_path)
    assert loader.extract_text_from_docx() == "\n".join(env.docx_content)


def test_extract_text_corrupted_docx(
    env: EnvPaths, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify clean propagation or logging fallbacks for malformed zip archives."""
    corrupt_path = env.dir_path / "corrupt.docx"
    corrupt_path.write_bytes(b"Not a zip file")

    loader = DataLoader(corrupt_path, raise_exception=True)
    with pytest.raises((PackageNotFoundError, BadZipFile)):
        loader.extract_text_from_docx()

    loader_no_fail = DataLoader(corrupt_path, raise_exception=False)
    assert loader_no_fail.extract_text_from_docx() is None
    assert "Invalid or corrupted .docx" in caplog.text


# --- JSON TESTS ---


def test_load_json_success(env: EnvPaths) -> None:
    """Verify that validated JSON file load attempts succeed."""
    loader = DataLoader(env.json_path)
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
    """Ensure raw decoding failures either bubble up or fall back cleanly."""
    bad_json = env.dir_path / "bad.json"
    bad_json.write_text("{ 'wrong': True }", encoding="utf-8")

    loader = DataLoader(bad_json, raise_exception=raise_flag)

    if expected_behavior == "raise":
        with pytest.raises(json.JSONDecodeError):
            loader.load_json()
    else:
        assert loader.load_json() is expected_behavior
        assert "Invalid JSON format" in caplog.text


def test_load_json_with_validator_success(env: EnvPaths) -> None:
    """Ensure JSON arrays return correctly when all elements satisfy criteria."""
    list_path = env.dir_path / "list.json"
    list_data = [{"id": 1}, {"id": 2}]
    list_path.write_text(json.dumps(list_data), encoding="utf-8")

    loader = DataLoader(list_path)
    result = loader.load_json(validator=lambda x: "id" in x)

    assert result == list_data


@pytest.mark.parametrize("raise_flag", [True, False])
def test_load_json_with_validator_failure(
    env: EnvPaths, caplog: pytest.LogCaptureFixture, raise_flag: bool
) -> None:
    """Verify that validation schema exceptions or suppression logs execute safely."""
    list_path = env.dir_path / "invalid_list.json"
    list_data = [{"id": 1}, {"name": "missing_id"}]
    list_path.write_text(json.dumps(list_data), encoding="utf-8")

    loader = DataLoader(list_path, raise_exception=raise_flag)

    def validator(x: dict[str, Any]) -> bool:
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
    """Verify initialization boundaries block or warn on missing payloads."""
    missing_file = env.dir_path / "missing.txt"

    if expected_behavior == "raise":
        with pytest.raises(FileNotFoundError):
            DataLoader(missing_file, raise_exception=raise_flag)
    else:
        DataLoader(missing_file, raise_exception=raise_flag)
        assert "Input file not found" in caplog.text
