# tests/unit/schemas/test_work_metadata.py
"""Unit tests verifying bibliographic work metadata parsing, states, and DOI mapping."""

import pytest

from citecraft.schemas.work_metadata import WorkMetadata


def test_work_metadata_instantiation_defaults() -> None:
    """Verify that WorkMetadata structures load correct defaults on initialization."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_issns=["1752-0894"],
    )

    assert work.input_issns == ["1752-0894"]
    assert work.doi is None
    assert work.raw_reference is None
    assert work.reference is None
    assert work.style is None
    assert work.type is None
    assert work.crossref_metadata is None
    assert work.openalex_metadata is None


def test_work_metadata_identity_key_with_none_doi() -> None:
    """Verify fallback behavior of the identity key in unresolved DOI states."""
    work = WorkMetadata(
        input_first_authors_txt="Smith",
        input_year_and_suffix="2022",
        input_issns=["1234-5678"],
        doi=None,
    )

    expected_key = ("Smith", "2022", None)
    assert work.identity_key == expected_key


def test_work_metadata_identity_key_with_none_input_issn_and_doi() -> None:
    """Verify that identity signatures ignore missing ISSN coordinates."""
    work = WorkMetadata(
        input_first_authors_txt="Smith",
        input_year_and_suffix="2022",
        input_issns=None,
        doi=None,
    )

    expected_key = ("Smith", "2022", None)
    assert work.identity_key == expected_key


def test_work_metadata_identity_key_with_actual_doi() -> None:
    """Verify identifier key variation matches distinct assigned DOI strings."""
    work_a = WorkMetadata(
        input_first_authors_txt="Guns and Vanacker",
        input_year_and_suffix="2021",
        input_issns=["0016-7606"],
        doi="10.1130/g49244.1",
    )

    work_b = WorkMetadata(
        input_first_authors_txt="Guns and Vanacker",
        input_year_and_suffix="2021",
        input_issns=["0016-7606"],
        doi="10.1130/DIFFERENT_DOI",
    )

    assert work_a.identity_key != work_b.identity_key
    assert work_a.identity_key[2] == "10.1130/g49244.1"
    assert work_b.identity_key[2] == "10.1130/different_doi"


def test_work_metadata_to_dict_includes_none() -> None:
    """Ensure None value parameters are preserved correctly in schema outputs."""
    work = WorkMetadata(
        input_first_authors_txt="Test",
        input_year_and_suffix="2024",
        input_issns=["0000-0000"],
        doi=None,
    )

    data = work.model_dump()

    assert data["doi"] is None


def test_work_metadata_doi_normalization() -> None:
    """Verify automated lowercase conversion of DOI identifiers on setup."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard",
        input_year_and_suffix="2020",
        doi="10.1038/NATURE123",
    )

    assert work.doi == "10.1038/nature123"
    assert work.identity_key[2] == "10.1038/nature123"


@pytest.mark.parametrize(
    ("doi", "reference", "expected_status"),
    [
        ("10.1038/s41561-020-0585-2", "Lenard, S. J. P. (2020)...", "OK"),
        (None, "Lenard, S. J. P. (2020)...", "Missing DOI"),
        ("10.1038/s41561-020-0585-2", None, "Missing reference"),
        (None, None, "Missing DOI"),
    ],
)
def test_work_metadata_status_property(
    doi: str | None,
    reference: str | None,
    expected_status: str,
) -> None:
    """Verify evaluation transitions of WorkMetadata status states."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020",
        doi=doi,
        reference=reference,
    )

    assert work.status == expected_status
