# tests/unit/repositories/test_doi_repository.py
"""Unit tests for validating DOI metadata resolution and filtering operations."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from citecraft.repositories import DoiRepository
from citecraft.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> DoiRepository:
    """Provide DoiRepository testing instance."""
    return DoiRepository(config=test_config)


def test_get_metadata_success(repo: DoiRepository) -> None:
    """Verify that valid CSL-JSON metadata is mapped and returned correctly."""
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
        repo.http_client_wrapper,
        "get",
        return_value=(mock_response, None),
    ) as mock_get:
        result = repo.get_metadata("10.1000/182")

        assert result == mock_json_data
        assert isinstance(result, dict)

        _, kwargs = mock_get.call_args
        assert "headers" in kwargs
        assert kwargs["headers"]["Accept"] == "application/vnd.citationstyles.csl+json"


@pytest.mark.parametrize(
    ("side_effect", "json_val", "expected_log_sub"),
    [
        # Case A: Missing required keys (id and DOI)
        (
            None,
            {"type": "article-journal", "title": "Orphan Title"},
            "metadata invalid",
        ),
        # Case B: JSONDecodeError simulation
        (
            json.JSONDecodeError("Expecting value", "", 0),
            None,
            "Invalid format for CSL-JSON",
        ),
        # Case C: HTTP 404 Status Error simulation
        (
            httpx.HTTPStatusError(
                "404 Not Found",
                request=httpx.Request("GET", "https://doi.org/invalid/doi"),
                response=httpx.Response(404),
            ),
            None,
            "not found",
        ),
    ],
)
def test_get_metadata_safe_fallbacks(
    repo: DoiRepository,
    side_effect: Exception | None,
    json_val: dict[str, Any] | None,
    expected_log_sub: str,
) -> None:
    """Verify that errors fall back to empty records."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    if json_val is not None:
        mock_response.json.return_value = json_val
    if isinstance(side_effect, json.JSONDecodeError):
        mock_response.json.side_effect = side_effect

    with (
        patch.object(repo.http_client_wrapper, "get") as mock_get,
        patch("citecraft.repositories.doi_repository.logger.warning") as mock_warn,
    ):
        if isinstance(side_effect, httpx.HTTPStatusError):
            mock_get.side_effect = side_effect
        else:
            mock_get.return_value = (mock_response, None)

        result = repo.get_metadata("10.1000/fallback-target")

        assert result == {}
        mock_warn.assert_called_once()

        log_content = " ".join(str(arg) for arg in mock_warn.call_args[0]).lower()
        assert expected_log_sub.lower() in log_content


def test_get_metadata_server_error_500_bubbles_up(repo: DoiRepository) -> None:
    """Verify that server-level errors (like 500) bubble up and raise immediately."""
    mock_request = httpx.Request("GET", "https://doi.org/10.1000/broken")
    mock_response = httpx.Response(status_code=500, request=mock_request)
    error = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=mock_request,
        response=mock_response,
    )

    with (
        patch.object(repo.http_client_wrapper, "get", side_effect=error),
        pytest.raises(httpx.HTTPStatusError),
    ):
        repo.get_metadata("10.1000/broken")


def test_get_metadata_applies_blacklists_successfully(test_config: AppConfig) -> None:
    """Verify that blacklists strip fields from work and author scopes."""
    test_config = test_config.model_copy(
        update={
            "work_crossref_schema_blacklist_fields": [
                "issns",
                "assertion",
                "is-referenced-by-count",
            ],
            "author_crossref_schema_blacklist_fields": [
                "ORCID",
                "authenticated-orcid",
                "role",
            ],
        },
    )
    repo = DoiRepository(config=test_config)

    mock_raw_csl = {
        "DOI": "10.1038/s41561-020-0585-2",
        "issns": ["1752-0894"],
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

    with patch.object(
        repo.http_client_wrapper,
        "get",
        return_value=(mock_response, None),
    ):
        filtered_result = repo.get_metadata("10.1038/s41561-020-0585-2")

        assert "DOI" in filtered_result
        assert "title" in filtered_result
        assert "issns" not in filtered_result
        assert "is-referenced-by-count" not in filtered_result
        assert "assertion" not in filtered_result

        assert "author" in filtered_result
        authors = filtered_result["author"]
        assert len(authors) == 2

        assert authors[0]["family"] == "Lenard"
        assert "ORCID" not in authors[0]
        assert "authenticated-orcid" not in authors[0]
        assert "role" not in authors[0]

        assert authors[1]["family"] == "Lavé"
        assert "role" not in authors[1]


def test_get_metadata_with_empty_or_missing_blacklists(test_config: AppConfig) -> None:
    """Verify that blacklisting logic passes through unchanged when scopes are empty."""
    test_config = test_config.model_copy(
        update={
            "work_crossref_schema_blacklist_fields": [],
            "author_crossref_schema_blacklist_fields": [],
        },
    )
    repo = DoiRepository(config=test_config)
    mock_json_data = {
        "id": "10.1000/182",
        "author": [{"family": "Doe", "ORCID": "0000-0001"}],
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_json_data

    with patch.object(
        repo.http_client_wrapper,
        "get",
        return_value=(mock_response, None),
    ):
        result = repo.get_metadata("10.1000/182")
        assert result == mock_json_data
        assert "ORCID" in result["author"][0]


def test_is_valid_csl_delegate(repo: DoiRepository) -> None:
    """Directly test the structural validation helper rule."""
    valid_record = {"id": "10.1234/test"}
    invalid_record = {"title": "Missing ID"}

    assert repo._is_valid_csl(valid_record, "10.1234/test") is True
    assert repo._is_valid_csl(invalid_record, "10.1234/test") is False


def test_apply_blacklists_delegate(repo: DoiRepository) -> None:
    """Directly test that internal blacklist manipulation strips keys safely."""
    repo.config = repo.config.model_copy(
        update={
            "work_crossref_schema_blacklist_fields": ["unwanted_work_key"],
            "author_crossref_schema_blacklist_fields": ["unwanted_author_key"],
        },
    )
    doi = "10.1111/test"
    payload = {
        "id": "10.1111/test",
        "unwanted_work_key": "delete_me",
        "author": [{"family": "Smith", "unwanted_author_key": "strip_me"}],
    }

    repo._apply_blacklists(doi, payload)

    assert "unwanted_work_key" not in payload
    assert "unwanted_author_key" not in payload["author"][0]
