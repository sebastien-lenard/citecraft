import json
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


def test_get_metadata_success_with_id_injection(repo: DoiRepository) -> None:
    """Verify that 'id' is correctly inferred from 'DOI' if missing initially."""
    mock_json_data = {
        "DOI": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "title": "Title of the Paper",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_json_data

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_response):
        result = repo.get_metadata("10.1038/s41561-020-0585-2")

        # L'id doit avoir été injecté à partir du DOI
        assert result["id"] == "10.1038/s41561-020-0585-2"
        assert result["DOI"] == "10.1038/s41561-020-0585-2"


def test_get_metadata_missing_both_id_and_doi(repo: DoiRepository) -> None:
    """Verify that an empty dict is returned and warning logged if identity fields are
    absent."""
    mock_invalid_data = {"type": "article-journal", "title": "Orphan Title"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_invalid_data

    with (
        patch.object(repo.http_client_wrapper, "get", return_value=mock_response),
        patch(
            "manuscript_reference_lister.repositories.doi_repository.logger.warning"
        ) as mock_warn,
    ):
        result = repo.get_metadata("10.1000/orphan")
        assert result == {}
        mock_warn.assert_called_once()
        assert "metadata invalid" in mock_warn.call_args[0][0]


def test_get_metadata_invalid_json_format(repo: DoiRepository) -> None:
    """Verify that a JSONDecodeError returns an empty dict and triggers a warning."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    with (
        patch.object(repo.http_client_wrapper, "get", return_value=mock_response),
        patch(
            "manuscript_reference_lister.repositories.doi_repository.logger.warning"
        ) as mock_warn,
    ):
        result = repo.get_metadata("10.1000/corrupted")
        assert result == {}
        mock_warn.assert_called_once()
        assert "Invalid format for CSL-JSON" in mock_warn.call_args[0][0]


def test_get_metadata_not_found_404(repo: DoiRepository) -> None:
    """Verify an empty dictionary is returned and logged when a 404 error occurs for
    CSL-JSON."""
    mock_request = httpx.Request("GET", "https://doi.org/invalid/doi")
    mock_response = httpx.Response(status_code=404, request=mock_request)

    error = httpx.HTTPStatusError(
        message="Client Error: 404 Not Found",
        request=mock_request,
        response=mock_response,
    )
    with (
        patch.object(repo.http_client_wrapper, "get", side_effect=error),
        patch(
            "manuscript_reference_lister.repositories.doi_repository.logger.warning"
        ) as mock_warn,
    ):
        result = repo.get_metadata("invalid/doi")
        assert result == {}
        mock_warn.assert_called_once()


def test_get_metadata_server_error_500_bubbles_up(repo: DoiRepository) -> None:
    """Verify that any non-404 HTTP errors (like 500) are NOT caught and bubble up."""
    mock_request = httpx.Request("GET", "https://doi.org/10.1000/broken")
    mock_response = httpx.Response(status_code=500, request=mock_request)
    error = httpx.HTTPStatusError(
        "500 Internal Server Error", request=mock_request, response=mock_response
    )

    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        with pytest.raises(httpx.HTTPStatusError):
            repo.get_metadata("10.1000/broken")


def test_get_metadata_applies_blacklists_successfully(repo: DoiRepository) -> None:
    """Verify that root work fields and internal author sub-fields are properly removed."""
    repo.config.work_cls_schema_blacklist_fields = [
        "ISSN",
        "assertion",
        "is-referenced-by-count",
    ]
    repo.config.author_cls_schema_blacklist_fields = [
        "ORCID",
        "authenticated-orcid",
        "role",
    ]

    mock_raw_csl = {
        "DOI": "10.1038/s41561-020-0585-2",
        "ISSN": ["1752-0894"],
        "is-referenced-by-count": 79,
        "assertion": [{"label": "Received"}],
        "title": "Steady erosion rates in the Himalayas",
        "author": [
            {
                "family": "Lenard",
                "given": "Sebastien J. P.",
                "ORCID": "https://orcid.org/0000-0003-3358-7197",
                "authenticated-orcid": False,
                "role": [{"role": "author"}],
            },
            {"family": "Lavé", "given": "Jérôme", "role": [{"role": "author"}]},
        ],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_raw_csl

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_response):
        filtered_result = repo.get_metadata("10.1038/s41561-020-0585-2")

        # Verify cleaning of work root fields
        assert "DOI" in filtered_result
        assert "id" in filtered_result
        assert "title" in filtered_result
        assert "ISSN" not in filtered_result
        assert "is-referenced-by-count" not in filtered_result
        assert "assertion" not in filtered_result

        # # Verify cleaning of author fields
        assert "author" in filtered_result
        authors = filtered_result["author"]
        assert len(authors) == 2

        # Check authors and missing excluded fields
        assert authors[0]["family"] == "Lenard"
        assert "ORCID" not in authors[0]
        assert "authenticated-orcid" not in authors[0]
        assert "role" not in authors[0]

        assert authors[1]["family"] == "Lavé"
        assert "role" not in authors[1]


def test_get_metadata_with_empty_or_missing_blacklists(repo: DoiRepository) -> None:
    """Verify get_metadata functions normally if blacklists are missing or empty."""
    repo.config.work_cls_schema_blacklist_fields = []
    repo.config.author_cls_schema_blacklist_fields = []

    mock_json_data = {
        "id": "10.1000/182",
        "author": [{"family": "Doe", "ORCID": "0000-0001"}],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_json_data

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_response):
        result = repo.get_metadata("10.1000/182")
        # No alteration should be observed
        assert result == mock_json_data
        assert "ORCID" in result["author"][0]
