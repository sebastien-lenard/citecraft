from unittest.mock import MagicMock, patch

import pytest
import requests

from manuscript_reference_lister import DoiRepository


@pytest.fixture
def repo() -> DoiRepository:
    """Provides a fresh instance of DoiRepository for each test."""
    return DoiRepository()


def test_get_reference_success(repo: DoiRepository) -> None:
    """Verify formatted reference is returned correctly with proper headers."""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Doe, J. (2023). Title of the Paper. Journal of Science."

    with patch.object(
        repo.requests_wrapper, "get", return_value=mock_response
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

    mock_response = MagicMock(status_code=404)
    error = requests.exceptions.HTTPError("404 Client Error", response=mock_response)

    with patch.object(repo.requests_wrapper, "get", side_effect=error):
        result = repo.get_reference("invalid/doi", "apa")
        assert result == "Reference unavailable in doi.org."
