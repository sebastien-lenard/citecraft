import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from manuscript_reference_lister.repositories import BaseRepository
from manuscript_reference_lister.schemas import BaseSchema
from manuscript_reference_lister.utils import AppConfig


class MockSchema(BaseSchema):
    """Simple schema for testing repository logic."""

    id: int
    content: str = "test"

    @property
    def identity_key(self) -> int:
        return self.id


class MockRepository(BaseRepository[MockSchema]):
    """Concrete repository implementation mapping MockSchema elements."""

    pass


@pytest.fixture
def base_repo(test_config: AppConfig) -> MockRepository:
    """Provide a MockRepository instance utilizing the isolated global test
    configuration."""
    return MockRepository("test_base_records.json", MockSchema, config=test_config)


def test_deduplicate_removes_repeats(base_repo: MockRepository) -> None:
    """Ensure records with identical identity_keys are removed, keeping the first."""
    base_repo.records = [
        MockSchema(id=1, content="first"),
        MockSchema(id=2, content="unique"),
        MockSchema(id=1, content="duplicate"),
    ]

    base_repo.deduplicate()

    assert len(base_repo) == 2
    assert base_repo.records[0].content == "first"
    assert [r.id for r in base_repo.records] == [1, 2]


@pytest.mark.parametrize(
    "file_content, expected_records_count, expected_load_failed",
    [
        # Case A: Valid JSON file loaded and verified
        ('[{"id": 1, "content": "A"}, {"id": 2, "content": "B"}]', 2, False),
        # Case B: Invalid JSON structure causes failure flag and clears entries
        ('[{"content": "broken"}]', 0, True),
        # Case C: Missing target repository file loads empty lists gracefully
        (None, 0, False),
    ],
)
def test_load_all_scenarios(
    base_repo: MockRepository,
    file_content: str | None,
    expected_records_count: int,
    expected_load_failed: bool,
) -> None:
    """Verify load_all behaviors under standard file-system and validation states."""
    path = Path(base_repo.config.local_repo_dir_path) / base_repo.local_filename

    if file_content is not None:
        path.write_text(file_content, encoding="utf-8")
    elif path.exists():
        path.unlink()

    base_repo.load_all()

    assert len(base_repo.records) == expected_records_count
    assert base_repo._load_failed is expected_load_failed


def test_save_all_atomic_success(base_repo: MockRepository, tmp_path: Path) -> None:
    """Verify save_all writes JSON and cleans up temporary swap files."""
    data = [MockSchema(id=1, content="saved")]
    base_repo.records = data
    target = tmp_path / base_repo.local_filename

    base_repo.save_all(output_filepath=target)

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8"))[0]["id"] == 1
    assert not target.with_suffix(".tmp").exists()


def test_save_all_overwrite_existing(base_repo: MockRepository) -> None:
    """Verify that save_all correctly overwrites existing contents via atomic swap."""
    path = Path(base_repo.config.local_repo_dir_path) / base_repo.local_filename
    path.write_text("initial junk data", encoding="utf-8")

    new_record = MockSchema(id=99, content="new")
    base_repo.records = [new_record]
    base_repo.save_all()

    saved_data = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved_data) == 1
    assert saved_data[0]["id"] == 99


def test_save_all_preserves_utf8(base_repo: MockRepository) -> None:
    """Ensure non-ASCII characters are saved as literal UTF-8 in the JSON file."""
    special_content = "Lavé & Keddadouche — 2020"
    base_repo.records = [MockSchema(id=1, content=special_content)]
    path = Path(base_repo.config.local_repo_dir_path) / base_repo.local_filename

    base_repo.save_all()
    raw_text = path.read_text(encoding="utf-8")

    assert "é" in raw_text
    assert "—" in raw_text

    base_repo.load_all()
    assert base_repo.records[0].content == special_content


def test_validation_error_handling() -> None:
    """Verify invalid schema instantiations raise ValidationErrors."""
    with pytest.raises(ValidationError):
        MockSchema(content="error")
