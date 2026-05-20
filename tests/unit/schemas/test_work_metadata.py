from manuscript_reference_lister.schemas.work_metadata import WorkMetadata


def test_work_metadata_instantiation_defaults():
    """Verify that WorkMetadata defaults DOI to None and strings to empty."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_ISSN="1752-0894",
    )

    # Required fields
    assert work.input_ISSN == "1752-0894"

    # Other fields should be None by default
    assert work.DOI is None
    assert work.raw_reference is None
    assert work.reference is None
    assert work.style is None
    assert work.type is None


def test_work_metadata_identity_key_with_none_doi():
    """Verify the key handles the 'unresolved' state (DOI=None)."""
    work = WorkMetadata(
        input_first_authors_txt="Smith",
        input_year_and_suffix="2022",
        input_ISSN="1234-5678",
        DOI=None,
    )

    expected_key = ("Smith", "2022", None)
    assert work.identity_key == expected_key


def test_work_metadata_identity_key_with_none_input_issn_and_doi():
    """Verify the key is consistent regardless of ISSN presence."""
    work = WorkMetadata(
        input_first_authors_txt="Smith",
        input_year_and_suffix="2022",
        input_ISSN=None,
        DOI=None,
    )

    expected_key = ("Smith", "2022", None)
    assert work.identity_key == expected_key


def test_work_metadata_identity_key_with_actual_doi():
    """Verify the key distinguishes between different DOIs for the same input."""
    work_a = WorkMetadata(
        input_first_authors_txt="Guns and Vanacker",
        input_year_and_suffix="2021",
        input_ISSN="0016-7606",
        DOI="10.1130/g49244.1",
    )

    work_b = WorkMetadata(
        input_first_authors_txt="Guns and Vanacker",
        input_year_and_suffix="2021",
        input_ISSN="0016-7606",
        DOI="10.1130/DIFFERENT_DOI",
    )

    # Keys must be unique despite identical inputs
    assert work_a.identity_key != work_b.identity_key
    assert work_a.identity_key[2] == "10.1130/g49244.1"
    assert work_b.identity_key[2] == "10.1130/different_doi"


def test_work_metadata_to_dict_includes_none():
    """Ensure None is preserved in serialization."""
    work = WorkMetadata(
        input_first_authors_txt="Test",
        input_year_and_suffix="2024",
        input_ISSN="0000-0000",
        DOI=None,
    )

    data = work.model_dump()
    assert data["DOI"] is None


def test_work_metadata_doi_normalization():
    """Verify that DOI is automatically converted to lower case at instantiation."""
    work = WorkMetadata(
        input_first_authors_txt="Lenard",
        input_year_and_suffix="2020",
        DOI="10.1038/NATURE123",
    )

    assert work.DOI == "10.1038/nature123"
    assert work.identity_key[2] == "10.1038/nature123"
