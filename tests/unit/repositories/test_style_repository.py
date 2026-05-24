from unittest.mock import MagicMock, patch

import httpx
import pytest

from manuscript_reference_lister.repositories import StyleRepository


@pytest.fixture
def valid_csl_content() -> str:
    """Provides a minimal valid CSL layout string."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://purl.org/net/xbiblio/csl"\n'
        '  class="in-text" version="1.0">\n'
        "  <info><title>Mock Style</title></info>\n"
        "</style>"
    )


def test_fetch_style_metadata_success(valid_csl_content: str) -> None:
    """Verify CSL content is successfully downloaded and stored."""
    repo = StyleRepository("apa")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = valid_csl_content

    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_response
    ) as mock_get:
        repo.fetch_style_metadata()
        assert repo.csl_content == valid_csl_content
        assert mock_get.call_count == 1


def test_fetch_style_metadata_not_found() -> None:
    """Verify fallback when CSL endpoint returns a 404 error."""
    repo = StyleRepository("invalid-style")
    mock_request = httpx.Request("GET", "https://raw.githubusercontent.com/invalid")
    mock_response = httpx.Response(status_code=404, request=mock_request)

    error = httpx.HTTPStatusError(
        message="404 Not Found", request=mock_request, response=mock_response
    )

    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        repo.fetch_style_metadata()
        assert repo.csl_content is None
        assert repo.favored_style_is_valid is None


def test_validate_favored_style_success(valid_csl_content: str) -> None:
    """Verify validation passes when XML boundaries are matching specifications."""
    repo = StyleRepository("apa")
    repo.csl_content = valid_csl_content

    repo.validate_favored_style()
    assert repo.favored_style_is_valid is True


def test_validate_favored_style_structure_failure() -> None:
    """Verify validation fails when structural XML markers are invalid or missing."""
    repo = StyleRepository("apa")
    repo.csl_content = "<style>Invalid Header structure</style>"

    repo.validate_favored_style()
    assert repo.favored_style_is_valid is False
