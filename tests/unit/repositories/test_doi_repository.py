from unittest.mock import MagicMock, patch

import httpx
import pytest

from manuscript_reference_lister.repositories import DoiRepository


@pytest.fixture
def repo() -> DoiRepository:
    """Provides a fresh instance of DoiRepository for each test."""
    return DoiRepository()


def test_get_metadata_success(repo: DoiRepository) -> None:
    """Verify that CSL-JSON metadata is returned correctly as a dictionary."""
    mock_json_data = {
        "id": "10.1000/182",
        "type": "article-journal",
        "title": "Title of the Paper",
        "author": [{"family": "Doe", "given": "J."}],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_json_data

    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_response
    ) as mock_get:
        doi = "10.1000/182"
        result = repo.get_metadata(doi)

        assert result == mock_json_data
        assert isinstance(result, dict)

        _, kwargs = mock_get.call_args
        assert "headers" in kwargs
        assert kwargs["headers"]["Accept"] == "application/vnd.citationstyles.csl+json"


def test_get_metadata_not_found(repo: DoiRepository) -> None:
    """Verify an empty dictionary is returned when a 404 error occurs for CSL-JSON."""
    mock_request = httpx.Request("GET", "https://doi.org/invalid/doi")
    mock_response = httpx.Response(status_code=404, request=mock_request)

    error = httpx.HTTPStatusError(
        message="Client Error: 404 Not Found",
        request=mock_request,
        response=mock_response,
    )
    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        result = repo.get_metadata("invalid/doi")
        assert result == {}


def test_get_reference_success(repo: DoiRepository) -> None:
    """Verify formatted reference is returned correctly with proper headers."""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Doe, J. (2023). Title of the Paper. Journal of Science."

    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_response
    ) as mock_get:
        doi = "10.1000/182"
        style = "apa"
        result = repo.get_reference(doi, style)

        assert result == "Doe, J. (2023). Title of the Paper. Journal of Science."

        _, kwargs = mock_get.call_args
        assert "headers" in kwargs
        assert kwargs["headers"]["Accept"] == f"text/x-bibliography; style={style}"


def test_get_reference_not_found(repo: DoiRepository) -> None:
    """Verify fallback string is returned when a 404 error occurs."""
    mock_request = httpx.Request("GET", "https://doi.org/invalid/doi")
    mock_response = httpx.Response(status_code=404, request=mock_request)

    error = httpx.HTTPStatusError(
        message="Client Error: 404 Not Found",
        request=mock_request,
        response=mock_response,
    )
    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        result = repo.get_reference("invalid/doi", "apa")
        assert result == "Reference unavailable in doi.org."


def test_get_reference_utf8_encoding(repo: DoiRepository) -> None:
    """Verify that special characters (accented, dashes) are handled correctly."""
    # This string contains 'é' and an em-dash '—'
    utf8_text = "Lavé, J. (2020). Steady erosion — Himalayas."

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = utf8_text

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_response):
        result = repo.get_reference("10.1038/s41561-020-0585-2", "apa")

        assert result == utf8_text
        # Ensure the repo actually tried to set the encoding to utf-8
        assert mock_response.encoding == "utf-8"
