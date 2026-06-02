# tests/test_db.py
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from manuscript_reference_lister.schemas.journal_metadata import JournalMetadata
from manuscript_reference_lister.schemas.work_metadata import WorkMetadata
from manuscript_reference_lister.storage.db import (
    _get_sqlite_type,
    _is_collection_type,
    load_records,
    save_records,
)


class SimpleMockModel(BaseModel):
    """Simple model for testing database serialization and schemas."""

    id: int
    name: str
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, int] = Field(default_factory=dict)
    is_active: bool = True


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
    """Verify that a write failure triggers a clean rollback of state."""
    db_path = tmp_path / "test_rollback.db"

    records = [SimpleMockModel(id=1, name="Original", tags=[])]
    save_records(db_path, "mock_table", records, SimpleMockModel)

    # Intentionally pass invalid collection item to force serialization crash
    bad_records = [
        SimpleMockModel(id=2, name="Failure", tags=["ok"]),
        "not_a_model",  # type: ignore[list-item]
    ]

    with pytest.raises(Exception):
        save_records(
            db_path,
            "mock_table",
            bad_records,
            SimpleMockModel,  # type: ignore[arg-type]
        )

    # Verify table maintains original records (not empty, not corrupted)
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
        ISSN="1752-0894",
        start_year=2008,
        end_year=2026,
        similar_titles=["Nature Geosciences"],
    )

    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_ISSNs=["1752-0894"],
        looked_up_ISSNs=["1752-0894"],
        raw_reference="Raw reference text",
        reference="Clean reference text",
        style="apa",
        DOI="10.1038/s41561-020-0585-2",
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
    assert loaded_works[0].DOI == "10.1038/s41561-020-0585-2"
    assert loaded_works[0].crossref_metadata == {"indexed": {"date-parts": [[2020]]}}
    assert loaded_works[0].openalex_metadata == {"id": "https://openalex.org/W1234"}
