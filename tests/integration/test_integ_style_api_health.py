import pytest

from manuscript_reference_lister.repositories import StyleRepository


@pytest.mark.integration
@pytest.mark.vcr
def test_style_repository_integration() -> None:
    """Verify real CSL file extraction from the remote repository and structure
    compliance."""
    repo = StyleRepository("apa")

    # 1. Fetch metadata from the real repository endpoint
    repo.fetch_style_metadata()
    assert repo.csl_content is not None, (
        "Failed to download the remote CSL filecontent."
    )

    # 2. Validate structural constraints on real data
    repo.validate_favored_style()
    assert repo.favored_style_is_valid is True, (
        f"The downloaded CSL for '{repo.favored_style}' did not meet structure"
        f"boundaries."
    )
