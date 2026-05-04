import json
from pathlib import Path

import pytest

from manuscript_reference_lister.repositories import BaseRepository


class MockRepository(BaseRepository[dict]):
    def __init__(self, local_filename: str, local_dir: str):
        # We pass a simple lambda as the validator
        super().__init__(
            local_filename, validator=lambda x: isinstance(x, dict) and "id" in x
        )
        self.local_repo_dir_path = local_dir


@pytest.fixture
def base_repo(tmp_path: Path) -> MockRepository:
    return MockRepository("test_base_records.json", str(tmp_path))


def test_load_all_success(base_repo: MockRepository) -> None:
    """Verify loading valid data into records."""
    path = Path(base_repo.local_repo_dir_path) / base_repo.local_filename
    valid_data = [{"id": 1}, {"id": 2}]
    path.write_text(json.dumps(valid_data))

    base_repo.load_all()

    assert base_repo.records == valid_data
    assert len(base_repo) == 2


def test_load_all_invalid_schema(base_repo: MockRepository) -> None:
    """Verify that records is empty if the file fails validation."""
    path = Path(base_repo.local_repo_dir_path) / base_repo.local_filename
    invalid_data = [{"id": 1}, {"wrong_key": 2}]
    path.write_text(json.dumps(invalid_data))

    base_repo.load_all()

    assert base_repo.records == []
    assert len(base_repo) == 0


def test_load_all_file_not_found(base_repo: MockRepository) -> None:
    """Verify that a missing file results in empty records without crashing."""
    base_repo.load_all()
    assert base_repo.records == []


def test_save_all_atomic_success(base_repo: MockRepository) -> None:
    """Verify that save_all creates the file and uses the correct data."""
    data = [{"id": 1, "content": "test"}]
    base_repo.records = data
    expected_path = Path(base_repo.local_repo_dir_path) / base_repo.local_filename

    base_repo.save_all()

    assert expected_path.exists()
    assert not expected_path.with_suffix(".tmp").exists()
    assert json.loads(expected_path.read_text()) == data


def test_save_all_overwrite_existing(base_repo: MockRepository) -> None:
    """Verify that save_all correctly overwrites an existing file."""
    path = Path(base_repo.local_repo_dir_path) / base_repo.local_filename
    path.write_text("old data")

    new_data = [{"new": "data"}]
    base_repo.records = new_data
    base_repo.save_all()

    assert json.loads(path.read_text()) == new_data
