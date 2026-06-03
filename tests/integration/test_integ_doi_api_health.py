import pytest

from citecraft.repositories import DoiRepository


@pytest.mark.integration
@pytest.mark.vcr  # Activates VCR interception and automated YAML cassette management
def test_doi_api_service_health() -> None:
    """Verify the health of the doi.org content negotiation service and CSL-JSON
    payload format."""
    repo = DoiRepository()

    # DOI: Steady erosion rates in the Himalayas through late Cenozoic climatic changes
    test_doi = "10.1038/s41561-020-0585-2"

    # Extract raw metadata via the live API
    metadata = repo.get_metadata(test_doi)

    # --- Structural validations for CSL-JSON format ---
    assert isinstance(metadata, dict), (
        "The DOI service should return a dictionary payload."
    )
    assert len(metadata) > 0, "The resolved metadata dictionary should not be empty."

    # Mandatory pivot identifiers required for CSLReference validation
    assert any(k in metadata for k in ("id", "DOI")), (
        "The retrieved CSL-JSON payload must contain either an 'id' or a 'DOI' field."
    )

    # --- Domain content validation (Publication attributes) ---
    assert metadata.get("DOI") == test_doi, (
        "The returned DOI field does not match the target query."
    )
    assert "container-title" in metadata, (
        "The container journal title field is missing."
    )
    assert "Nature Geoscience" in metadata["container-title"], (
        f"Expected journal title 'Nature Geoscience' was not found in:"
        f" {metadata.get('container-title')}"
    )

    # --- Sanitization pipeline validation (Configuration blacklists) ---
    # Root level structural fields sanitization (e.g., 'URL', 'reference' blacklisted)
    assert "URL" not in metadata, (
        "The root level 'URL' field should have been removed by the blacklist."
    )
    assert "reference" not in metadata, (
        "The root level 'reference' field should have been removed by the blacklist."
    )

    # Nested author metadata sanitization (e.g., 'ORCID', 'affiliation' blacklisted)
    if "author" in metadata and isinstance(metadata["author"], list):
        for author in metadata["author"]:
            if isinstance(author, dict):
                assert "ORCID" not in author, (
                    "The nested 'ORCID' field for authors should have been removed."
                )
                assert "affiliation" not in author, (
                    "The nested 'affiliation' field for authors should have been"
                    " removed."
                )


@pytest.mark.integration
@pytest.mark.vcr
def test_doi_api_service_not_found() -> None:
    """Verify elegant fallback behavior (empty dict return) when encountering a
    HTTP 404 error."""
    repo = DoiRepository()
    invalid_doi = "10.1000/xyz123_non_existent_doi"

    metadata = repo.get_metadata(invalid_doi)

    assert metadata == {}, (
        "A 404 response on an invalid DOI must gracefully return an empty dictionary."
    )
