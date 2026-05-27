from datetime import date

import pytest
from pydantic import ValidationError

from manuscript_reference_lister.schemas import JournalMetadata


def test_journal_metadata_defaults() -> None:
    """Ensure optional fields default to None and update dates fallback to today."""
    journal = JournalMetadata(input_title="Science")

    assert journal.ISSN is None
    assert journal.similar_titles is None
    assert journal.update == str(date.today())


def test_journal_metadata_identity_key() -> None:
    """Ensure deduplication identity matches mapped title and ISSN coordinates."""
    journal = JournalMetadata(input_title="Nature", ISSN="1234-5678")

    assert journal.identity_key == ("Nature", "1234-5678")


def test_journal_metadata_issn_formatting() -> None:
    """Verify that ISSN structures are normalized to standardized hyphenated layouts."""
    journal = JournalMetadata(input_title="Test", ISSN="12345678")
    assert journal.ISSN == "1234-5678"

    journal_ok = JournalMetadata(input_title="Test", ISSN="1234-5678")
    assert journal_ok.ISSN == "1234-5678"


@pytest.mark.parametrize("invalid_year", [1599, 2101])
def test_journal_metadata_year_bounds(invalid_year: int) -> None:
    """Ensure year boundaries outside 1600-2099 raise ValidationErrors."""
    with pytest.raises(ValidationError) as excinfo:
        JournalMetadata(input_title="Test", start_year=invalid_year)

    errors = str(excinfo.value)
    assert (
        "greater than or equal to 1600" in errors
        or "less than or equal to 2099" in errors
    )


def test_journal_metadata_year_range_logic() -> None:
    """Ensure logical bounds guarantee start_year cannot exceed end_year limits."""
    with pytest.raises(ValidationError) as excinfo:
        JournalMetadata(input_title="Test", start_year=2025, end_year=2020)

    assert "start_year (2025) should be lower than end_year (2020)" in str(
        excinfo.value
    )


def test_journal_metadata_valid_year_range() -> None:
    """Ensure valid year spans parse and store correctly within range parameters."""
    journal = JournalMetadata(input_title="Test", start_year=2020, end_year=2025)

    assert journal.start_year == 2020
    assert journal.end_year == 2025


def test_journal_metadata_extra_fields_ignored() -> None:
    """Verify that unregistered JSON dictionary values are ignored."""
    data = {"input_title": "Nature", "extra_api_garbage": "should_not_exist"}

    journal = JournalMetadata(**data)

    assert journal.input_title == "Nature"
    assert not hasattr(journal, "extra_api_garbage")


def test_journal_metadata_completeness_logic() -> None:
    """Verify is_complete identifies incomplete core operational properties."""
    incomplete_journal = JournalMetadata(input_title="Nature")
    assert incomplete_journal.is_complete is False

    complete_journal = JournalMetadata(
        input_title="Nature Geoscience",
        true_title="Nature Geoscience",
        publisher="Nature Portfolio",
        ISSN="1752-0894",
        start_year=2008,
        end_year=2026,
    )
    assert complete_journal.is_complete

    complete_with_suggestions = JournalMetadata(
        input_title="Nature Geo",
        true_title="Nature Geoscience",
        publisher="Nature Portfolio",
        ISSN="1752-0894",
        start_year=2008,
        end_year=2026,
        similar_titles=["Nature Geoscience", "Nature Geography"],
    )
    assert complete_with_suggestions.is_complete


def test_journal_metadata_status_property() -> None:
    """Verify state classification matches property presence combinations."""
    j_not_found = JournalMetadata(input_title="Fake Journal")
    assert j_not_found.status == "Not found"

    j_no_issn = JournalMetadata(
        input_title="Nature Physics",
        true_title="Nature Physics",
        publisher="Springer",
        ISSN=None,
    )
    assert j_no_issn.status == "Found without ISSN"

    j_no_works = JournalMetadata(
        input_title="Empty Journal",
        true_title="Empty Journal",
        publisher="Silent Publisher",
        ISSN="1234-5678",
        start_year=None,
        end_year=None,
    )
    assert j_no_works.status == "Found without work"

    j_ok = JournalMetadata(
        input_title="Science",
        true_title="Science",
        publisher="AAAS",
        ISSN="0036-8075",
        start_year=1880,
        end_year=2026,
    )
    assert j_ok.status == "OK"
