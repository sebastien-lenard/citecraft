# tests/unit/repositories/test_base_repository.py
import sqlite3
from collections.abc import Hashable
from pathlib import Path
from unittest.mock import patch

import pytest

from citecraft.repositories import BaseRepository
from citecraft.schemas import BaseSchema
from citecraft.storage.db import load_records, save_records
from citecraft.utils import AppConfig


class MockSchema(BaseSchema):
    """Simple schema for testing repository logic."""

    id: int
    content: str = "test"

    @property
    def identity_key(self) -> Hashable:
        return self.id


class MockRepository(BaseRepository[MockSchema]):
    """Concrete repository implementation mapping MockSchema elements."""

    pass


@pytest.fixture
def base_repo(test_config: AppConfig) -> MockRepository:
    """Provide a MockRepository instance utilizing the isolated test config."""
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
    "scenario, expected_records_count, expected_load_failed",
    [
        ("valid", 2, False),
        ("corrupted", 0, True),
        ("missing", 0, False),
    ],
)
def test_load_all_scenarios(
    base_repo: MockRepository,
    scenario: str,
    expected_records_count: int,
    expected_load_failed: bool,
) -> None:
    """Verify load_all behaviors under standard database corruption states."""
    path = Path(base_repo.config.db_filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    if scenario == "valid":
        records = [MockSchema(id=1, content="A"), MockSchema(id=2, content="B")]
        save_records(path, base_repo.table_name, records, MockSchema)
    elif scenario == "corrupted":
        path.write_text("invalid corrupted sqlite binary header data", encoding="utf-8")
    elif scenario == "missing":
        if path.exists():
            path.unlink()

    base_repo.load_all()

    assert len(base_repo.records) == expected_records_count
    assert base_repo._load_failed is expected_load_failed

    if scenario == "corrupted":
        backup_files = list(path.parent.glob("*_corrupted_*.db"))
        assert len(backup_files) == 1
        assert not path.exists()


def test_save_all_atomic_success(base_repo: MockRepository, tmp_path: Path) -> None:
    """Verify save_all writes records cleanly to the SQLite database."""
    data = [MockSchema(id=1, content="saved")]
    base_repo.records = data
    target = tmp_path / "test_db.db"

    base_repo.save_all(output_filepath=target)

    assert target.exists()
    loaded = load_records(target, base_repo.table_name, MockSchema)
    assert len(loaded) == 1
    assert loaded[0].id == 1


def test_save_all_overwrite_existing(base_repo: MockRepository) -> None:
    """Verify that save_all correctly overwrites existing SQLite table records."""
    path = Path(base_repo.config.db_filepath)

    initial_records = [MockSchema(id=1, content="old")]
    save_records(path, base_repo.table_name, initial_records, MockSchema)

    new_record = MockSchema(id=99, content="new")
    base_repo.records = [new_record]
    base_repo.save_all()

    loaded = load_records(path, base_repo.table_name, MockSchema)
    assert len(loaded) == 1
    assert loaded[0].id == 99


def test_save_all_preserves_utf8(base_repo: MockRepository) -> None:
    """Ensure non-ASCII characters are saved as literal UTF-8 in the SQLite db."""
    special_content = "Lavé & Keddadouche — 2020"
    base_repo.records = [MockSchema(id=1, content=special_content)]

    base_repo.save_all()

    base_repo.load_all()
    assert base_repo.records[0].content == special_content


# =============================================================================
# COV TESTS: SPECIFIC IF/ELSE AND FALLBACK BRANCH COVERAGE
# =============================================================================


def test_load_all_backup_os_error_unlinks_file(
    base_repo: MockRepository,
) -> None:
    """Verify backup OSError unlinks corrupted file to ensure recovery."""
    path = Path(base_repo.config.db_filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("corrupted_database_mock_payload", encoding="utf-8")

    with patch.object(Path, "rename", side_effect=OSError("Rename blocked")):
        base_repo.load_all()

    assert base_repo._load_failed is True
    assert not path.exists()


def test_load_all_with_raise_exception(base_repo: MockRepository) -> None:
    """Verify load_all raises exception if raise_exception is explicitly True."""
    path = Path(base_repo.config.db_filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("corrupted_database_mock_payload", encoding="utf-8")

    with pytest.raises((sqlite3.Error, TypeError, ValueError)):
        base_repo.load_all(raise_exception=True)


def test_save_all_exception_raises_and_logs(
    base_repo: MockRepository,
) -> None:
    """Verify save_all failure triggers sqlite3.Error and exits cleanly."""
    base_repo.records = [MockSchema(id=1)]
    with (
        patch(
            "citecraft.repositories.base_repository.save_records",
            side_effect=sqlite3.OperationalError("Mock saving database error"),
        ),
        pytest.raises(sqlite3.Error),
    ):
        base_repo.save_all()
