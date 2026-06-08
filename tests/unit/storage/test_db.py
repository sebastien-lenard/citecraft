# tests/unit/storage/test_db.py
"""Unit tests for Pydantic schema relational mapping and serialization."""

import sqlite3
from pathlib import Path
from typing import Union
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError

import citecraft.storage.db as db_module
from citecraft.schemas.journal_metadata import JournalMetadata
from citecraft.schemas.work_metadata import WorkMetadata
from citecraft.storage.db import (
    _get_sqlite_type,
    _is_collection_type,
    archive_database_cache,
    create_table_for_model,
    deserialize_row,
    load_records,
    save_records,
    serialize_model,
)
from citecraft.storage.db_client import DbClient


class SimpleMockModel(BaseModel):
    """Simple model for testing database serialization and schemas."""

    id: int
    name: str
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, int] = Field(default_factory=dict)
    is_active: bool = True


class MismatchedMockModel(BaseModel):
    """Mock schema simulating a mismatched structural change scenario."""

    id: int
    name: str
    non_existent_column: str


class PathMockModel(BaseModel):
    """Mock schema validating dynamic path conversion properties."""

    file_path: Path


class FlexibleCollectionModel(BaseModel):
    """Mock schema containing raw alternative processing parameters."""

    items: list[str] | str


def test_type_mappings() -> None:
    """Verify that Python/Pydantic types map correctly to SQLite columns."""
    assert _get_sqlite_type(int) == "INTEGER"
    assert _get_sqlite_type(bool) == "INTEGER"
    assert _get_sqlite_type(float) == "REAL"
    assert _get_sqlite_type(str) == "TEXT"
    assert _get_sqlite_type(list[str]) == "TEXT"
    assert _is_collection_type(list[str]) is True
    assert _is_collection_type(dict[str, int]) is True
    assert _is_collection_type(int) is False


def test_is_collection_type_edge_cases() -> None:
    """Verify collection checks for None types and inheritance subclasses."""
    assert _is_collection_type(None) is False

    class CustomList(list):
        pass

    assert _is_collection_type(CustomList) is True


def test_get_sqlite_type_edge_cases() -> None:
    """Verify SQLite type resolutions for None and blank Unions."""
    assert _get_sqlite_type(None) == "TEXT"

    # Verify Union containing only NoneType falls back to TEXT
    mock_type = MagicMock()
    with (
        patch("citecraft.storage.db.get_origin", return_value=Union),
        patch("citecraft.storage.db.get_args", return_value=[type(None)]),
    ):
        assert _get_sqlite_type(mock_type) == "TEXT"


def test_serialize_model_path_type(tmp_path: Path) -> None:
    """Verify serialize_model converts Path values to plain string types."""
    test_file = tmp_path / "test_dir" / "file.txt"
    model = PathMockModel(file_path=test_file)
    serialized = serialize_model(model)
    assert serialized["file_path"] == str(test_file)


def test_deserialize_row_coverage() -> None:
    """Verify various deserialize_row logic branches and fallbacks.

    Organically triggers the 'field is None' continue path via ghost_column.
    """
    # 1. JSONDecodeError fallback branch
    row_invalid_json = {"items": "invalid_json_string_value"}
    deserialized_fallback = deserialize_row(row_invalid_json, FlexibleCollectionModel)
    assert deserialized_fallback.items == "invalid_json_string_value"

    # 2. Inner else: Collection type with non-string value
    row_already_collection = {"tags": ["pre_parsed_value"], "name": "Test", "id": 1}
    deserialized_collection = deserialize_row(row_already_collection, SimpleMockModel)
    assert deserialized_collection.tags == ["pre_parsed_value"]

    # 3. Outer else: Missing field column (gets ignored) and None values
    row_with_none = {
        "tags": None,
        "name": "Item Name",
        "id": 123,
        "ghost_column": "ignore_me",
    }
    deserialized_none = deserialize_row(row_with_none, SimpleMockModel)
    assert deserialized_none.name == "Item Name"
    assert deserialized_none.tags == []  # default_factory triggers


def test_deserialize_row_validation_error_on_missing_required() -> None:
    """Verify required field validation fails correctly if database returns None.

    Triggers 'deserialized[key] = None' and the ensuing ValidationError.
    """
    row_with_none_required = {"tags": None, "name": None, "id": 123}
    with pytest.raises(ValidationError):
        deserialize_row(row_with_none_required, SimpleMockModel)


def test_load_records_missing_boundaries(tmp_path: Path) -> None:
    """Verify load_records handles nonexistent files and missing tables."""
    # 1. Nonexistent database file path
    nonexistent_path = tmp_path / "ghost_file.db"
    assert load_records(nonexistent_path, "table", SimpleMockModel) == []

    # 2. Nonexistent table name within a valid database file
    db_path = tmp_path / "real_file.db"
    save_records(
        db_path,
        "actual_table",
        [SimpleMockModel(id=1, name="A")],
        SimpleMockModel,
    )
    assert load_records(db_path, "nonexistent_table", SimpleMockModel) == []


def test_archive_database_cache_oserror(tmp_path: Path) -> None:
    """Verify database renaming errors trigger logged OSErrors."""
    db_path = tmp_path / "cache.db"
    db_path.touch()

    with (
        patch("pathlib.Path.rename", side_effect=OSError("Permission Denied")),
        pytest.raises(OSError, match="Permission Denied"),
    ):
        archive_database_cache(db_path)


def test_dynamic_schema_and_save_load(tmp_path: Path) -> None:
    """Verify dynamic schema creation and exact serialization roundtrip."""
    db_path = tmp_path / "test_cache.db"

    records = [
        SimpleMockModel(
            id=1,
            name="Item A",
            tags=["tag1", "tag2"],
            attributes={"score": 42},
            is_active=True,
        ),
        SimpleMockModel(
            id=2,
            name="Item B",
            tags=[],
            attributes={},
            is_active=False,
        ),
    ]

    save_records(db_path, "mock_table", records, SimpleMockModel)
    loaded = load_records(db_path, "mock_table", SimpleMockModel)

    assert len(loaded) == 2
    assert loaded[0].id == 1
    assert loaded[0].tags == ["tag1", "tag2"]
    assert loaded[0].attributes == {"score": 42}
    assert loaded[0].is_active is True
    assert loaded[1].id == 2
    assert loaded[1].is_active is False


def test_transaction_rollback_integrity(tmp_path: Path) -> None:
    """Verify that a database-level write failure triggers a clean rollback."""
    db_path = tmp_path / "test_rollback.db"

    # 1. Initialize the table with the original schema
    records = [SimpleMockModel(id=1, name="Original", tags=[])]
    save_records(db_path, "mock_table", records, SimpleMockModel)

    # 2. Try to insert with the mismatched schema.
    # We bypass schema creation by calling save_records with our mismatched model.
    # This forces SQLite to raise a real sqlite3.OperationalError (no such column).
    bad_records = [
        MismatchedMockModel(id=2, name="Failure", non_existent_column="test"),
    ]

    with pytest.raises(sqlite3.Error) as exc_info:
        save_records(db_path, "mock_table", bad_records, MismatchedMockModel)

    # Verify that a real SQLite error was raised
    assert "has no column named " in str(exc_info.value)

    # 3. Verify original database state remains uncorrupted and loaded successfully
    loaded = load_records(db_path, "mock_table", SimpleMockModel)
    assert len(loaded) == 1
    assert loaded[0].name == "Original"


def test_real_metadata_roundtrip(tmp_path: Path) -> None:
    """Verify that actual JournalMetadata and WorkMetadata can serialize fully."""
    db_path = tmp_path / "real_test.db"

    journal = JournalMetadata(
        input_title="Nature Geoscience",
        true_title="Nature Geoscience",
        publisher="Springer Nature",
        issn="1752-0894",
        start_year=2008,
        end_year=2026,
        similar_titles=["Nature Geosciences"],
    )

    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_issns=["1752-0894"],
        looked_up_issns=["1752-0894"],
        raw_reference="Raw reference text",
        reference="Clean reference text",
        style="apa",
        doi="10.1038/s41561-020-0585-2",
        crossref_metadata={"indexed": {"date-parts": [[2020]]}},
        openalex_metadata={"id": "https://openalex.org/W1234"},
        type="journal-article",
    )

    save_records(db_path, "journals", [journal], JournalMetadata)
    save_records(db_path, "works", [work], WorkMetadata)

    loaded_journals = load_records(db_path, "journals", JournalMetadata)
    loaded_works = load_records(db_path, "works", WorkMetadata)

    assert len(loaded_journals) == 1
    assert loaded_journals[0].input_title == "Nature Geoscience"
    assert loaded_journals[0].similar_titles == ["Nature Geosciences"]

    assert len(loaded_works) == 1
    assert loaded_works[0].doi == "10.1038/s41561-020-0585-2"
    assert loaded_works[0].crossref_metadata == {"indexed": {"date-parts": [[2020]]}}
    assert loaded_works[0].openalex_metadata == {"id": "https://openalex.org/W1234"}


def test_archive_database_cache_success(tmp_path: Path) -> None:
    """Verify database is safely renamed with timestamp backup suffix on archive."""
    db_path = tmp_path / "cache.db"
    records = [SimpleMockModel(id=1, name="Item", tags=[])]
    save_records(db_path, "mock_table", records, SimpleMockModel)

    backup_path = archive_database_cache(db_path)

    assert backup_path is not None
    assert backup_path.is_file()
    assert ".bak_" in backup_path.name
    assert not db_path.exists()

    # Verify backup data contains original elements
    loaded = load_records(backup_path, "mock_table", SimpleMockModel)
    assert len(loaded) == 1
    assert loaded[0].name == "Item"


def test_archive_database_cache_missing_returns_none(tmp_path: Path) -> None:
    """Verify archiving returns None if targeted database cache file is absent."""
    db_path = tmp_path / "absent_cache.db"
    backup_path = archive_database_cache(db_path)
    assert backup_path is None


# ============================================================================ #
# ARCHITECTURAL SHIELDS (REGRESSION PREVENTERS)                               #
# ============================================================================ #


def test_architectural_shield_sql_placeholders() -> None:
    """Ensure that only {table_name} is used as SQL placeholders, never {table}."""
    db_file_path = Path(__file__).parents[3] / "src" / "citecraft" / "storage" / "db.py"
    if not db_file_path.exists():
        db_file_path = Path(db_module.__file__)

    content = db_file_path.read_text("utf-8")
    assert "{table}" not in content.replace("{table_name}", "")


def test_architectural_shield_no_direct_connection_execute() -> None:
    """Ensure db.py never calls execute or executemany directly on sqlite3."""
    db_file_path = Path(__file__).parents[3] / "src" / "citecraft" / "storage" / "db.py"
    if not db_file_path.exists():
        db_file_path = Path(db_module.__file__)

    content = db_file_path.read_text("utf-8")
    assert ".execute(" not in content
    assert ".executemany(" not in content


def test_architectural_shield_db_client_dispatches() -> None:
    """Verify that DbClient classmethods are called during database operations."""
    with (
        patch.object(DbClient, "safe_create_table") as mock_create,
        patch.object(DbClient, "safe_execute") as mock_execute,
        patch.object(DbClient, "safe_execute_many") as mock_executemany,
        patch.object(DbClient, "safe_fetch_all", return_value=[]) as mock_fetchall,
        patch.object(DbClient, "table_exists", return_value=True) as mock_exists,
    ):
        mock_conn = MagicMock(spec=sqlite3.Connection)

        # 1. Test create_table_for_model dispatch

        create_table_for_model(mock_conn, "test_table", SimpleMockModel)
        mock_create.assert_called_once()

        # 2. Test save_records dispatch

        with (
            patch("sqlite3.connect") as mock_connect,
            patch("citecraft.storage.db.create_table_for_model"),
        ):
            mock_connect.return_value = mock_conn
            save_records(
                Path("dummy.db"),
                "test_table",
                [SimpleMockModel(id=1, name="A")],
                SimpleMockModel,
            )
            mock_execute.assert_called_once()
            mock_executemany.assert_called_once()

        # 3. Test load_records dispatch
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.return_value = mock_conn
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = True

            load_records(mock_path, "test_table", SimpleMockModel)
            mock_exists.assert_called_once()
            mock_fetchall.assert_called_once()
