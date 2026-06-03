import pytest

from citecraft.schemas.work_metadata import WorkMetadata


def test_work_metadata_instantiation_defaults() -> None:
    """Verify that WorkMetadata structures load correct defaults on initialization."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_ISSNs=["1752-0894"],
    )

    assert work.input_ISSNs == ["1752-0894"]
    assert work.DOI is None
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
        input_ISSNs=["1234-5678"],
        DOI=None,
    )

    expected_key = ("Smith", "2022", None)
    assert work.identity_key == expected_key


def test_work_metadata_identity_key_with_none_input_issn_and_doi() -> None:
    """Verify that identity signatures ignore missing ISSN coordinates."""
    work = WorkMetadata(
        input_first_authors_txt="Smith",
        input_year_and_suffix="2022",
        input_ISSNs=None,
        DOI=None,
    )

    expected_key = ("Smith", "2022", None)
    assert work.identity_key == expected_key


def test_work_metadata_identity_key_with_actual_doi() -> None:
    """Verify identifier key variation matches distinct assigned DOI strings."""
    work_a = WorkMetadata(
        input_first_authors_txt="Guns and Vanacker",
        input_year_and_suffix="2021",
        input_ISSNs=["0016-7606"],
        DOI="10.1130/g49244.1",
    )

    work_b = WorkMetadata(
        input_first_authors_txt="Guns and Vanacker",
        input_year_and_suffix="2021",
        input_ISSNs=["0016-7606"],
        DOI="10.1130/DIFFERENT_DOI",
    )

    assert work_a.identity_key != work_b.identity_key
    assert work_a.identity_key[2] == "10.1130/g49244.1"
    assert work_b.identity_key[2] == "10.1130/different_doi"


def test_work_metadata_to_dict_includes_none() -> None:
    """Ensure None value parameters are preserved correctly in schema outputs."""
    work = WorkMetadata(
        input_first_authors_txt="Test",
        input_year_and_suffix="2024",
        input_ISSNs=["0000-0000"],
        DOI=None,
    )

    data = work.model_dump()

    assert data["DOI"] is None


def test_work_metadata_doi_normalization() -> None:
    """Verify automated lowercase conversion of DOI identifiers on setup."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard",
        input_year_and_suffix="2020",
        DOI="10.1038/NATURE123",
    )

    assert work.DOI == "10.1038/nature123"
    assert work.identity_key[2] == "10.1038/nature123"


@pytest.mark.parametrize(
    "doi, reference, expected_status",
    [
        ("10.1038/s41561-020-0585-2", "Lenard, S. J. P. (2020)...", "OK"),
        (None, "Lenard, S. J. P. (2020)...", "Missing DOI"),
        ("10.1038/s41561-020-0585-2", None, "Missing reference"),
        (None, None, "Missing DOI"),
    ],
)
def test_work_metadata_status_property(
    doi: str | None, reference: str | None, expected_status: str
) -> None:
    """Verify evaluation transitions of WorkMetadata status states."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020",
        DOI=doi,
        reference=reference,
    )

    assert work.status == expected_status
