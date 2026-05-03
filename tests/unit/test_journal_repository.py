import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister import JournalRepository


@pytest.fixture
def repo(tmp_path: Path) -> JournalRepository:
    """Provides a fresh instance of JournalRepository for each test."""
    repo = JournalRepository()
    repo.local_repo_dir_path = str(tmp_path)
    return repo


def test_get_journal_metadata_success(repo: JournalRepository) -> None:
    """Verify successful retrieval of ISSNs and years from multiple API endpoints."""
    # 1. Main search response
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {"items": [{"title": "Geology", "ISSN": ["0091-7613"]}]}
    }

    # 2. Year endpoint response (reused for min/max)
    mock_year = MagicMock(status_code=200)
    mock_year.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[1973]]},
                    "published-online": {"date-parts": [[1995]]},
                }
            ]
        }
    }

    with patch.object(repo.requests_wrapper, "get") as mock_get:
        mock_get.side_effect = [mock_main, mock_year, mock_year]

        results = repo.get_journal_metadata("Geology")

        assert len(results) == 1
        assert results[0]["ISSN"] == "0091-7613"
        assert results[0]["start_year"] == 1973
        assert results[0]["end_year"] == 1995


def test_get_journal_metadata_not_found_behavior(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify fallback to template and warning log when no journal is found."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}

    with patch.object(repo.requests_wrapper, "get", return_value=mock_resp):
        with caplog.at_level(logging.WARNING):
            results = repo.get_journal_metadata("Unknown Journal")

            assert "Journal Unknown Journal not found." in caplog.text
            assert len(results) == 1
            assert results[0]["ISSN"] is None
            assert results[0]["input_title"] == "Unknown Journal"


@pytest.mark.parametrize(
    "order, expected_year",
    [
        ("asc", 1990),  # Test oldest
        ("desc", 2024),  # Test newest
    ],
)
def test_get_issn_year_endpoint_success(
    repo: JournalRepository, order: Literal["asc", "desc"], expected_year: int
) -> None:
    """Test retrieving years when both print and online dates are present."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[1990, 1, 1]]},
                    "published-online": {"date-parts": [[2024, 5, 12]]},
                }
            ]
        }
    }

    with patch.object(
        repo.requests_wrapper, "get", return_value=mock_response
    ) as mock_get:
        result = repo.get_issn_year_endpoint("1234-5678", order)
        assert result == expected_year
        # Verify the API was called with the correct sort/order params
        mock_get.assert_called_with(
            repo.issn_url.replace("{issn}", "1234-5678"),
            params={
                "sort": "published",
                "order": order,
                "rows": 1,
                "mailto": repo.email,
            },
            headers=repo.headers,
        )
        mock_get.assert_called_once()


def test_get_issn_year_endpoint_no_items(repo: JournalRepository) -> None:
    """Test the 'guard clause' when the API returns no items."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"items": []}}
    with patch.object(
        repo.requests_wrapper, "get", return_value=mock_response
    ) as mock_get:
        result = repo.get_issn_year_endpoint("0000-0000", "asc")
        assert result is None
        mock_get.assert_called_once()


def test_get_issn_year_endpoint_partial_dates(repo: JournalRepository) -> None:
    """Test behavior when only one type of date (e.g. online) is available."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[None]]},
                    "published-online": {"date-parts": [[2010, 1, 1]]},
                }
            ]
        }
    }
    with patch.object(
        repo.requests_wrapper, "get", return_value=mock_response
    ) as mock_get:
        assert repo.get_issn_year_endpoint("1111-2222", "asc") == 2010
        mock_get.assert_called_once()


def test_get_journal_metadata_multiple_issns(repo: JournalRepository) -> None:
    """Verify that journals with multiple ISSNs return distinct records."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Nature",  # Must contain the exact string
                    "ISSN": ["0028-0836", "1476-4687"],
                }
            ]
        }
    }

    def year_mock(year: int):
        m = MagicMock(status_code=200)
        m.json.return_value = {
            "message": {"items": [{"published-print": {"date-parts": [[year]]}}]}
        }
        return m

    with patch.object(repo.requests_wrapper, "get") as mock_get:
        mock_get.side_effect = [
            mock_main,
            year_mock(1869),
            year_mock(2023),  # ISSN 1
            year_mock(1997),
            year_mock(2023),  # ISSN 2
        ]

        results = repo.get_journal_metadata("Nature")

        assert len(results) == 2
        assert results[0]["ISSN"] == "0028-0836"
        assert results[1]["ISSN"] == "1476-4687"
        assert mock_get.call_count == 5


def test_merge_new_titles(repo: JournalRepository) -> None:
    """Verify that new titles are merged as templates without affecting existing data."""
    repo.records = [{"input_title": "Existing", "ISSN": "0000-0000"}]
    repo.merge_new_titles(input_titles=["Existing", "New"])

    assert len(repo) == 2
    assert any(
        r["input_title"] == "Existing" and r["ISSN"] == "0000-0000"
        for r in repo.records
    )

    new_entry = next(r for r in repo.records if r["input_title"] == "New")
    assert new_entry["ISSN"] is None
    assert new_entry["update"] == str(date.today())


def test_save_all(repo: JournalRepository) -> None:
    """Verify that the journal list is saved correctly to the work directory."""
    initial_records = [{"input_title": "Test", "ISSN": "1234"}]
    repo.records = initial_records
    expected_path = Path(repo.local_repo_dir_path) / repo.local_filename

    repo.save_all()

    assert expected_path.exists()
    saved_records = json.loads(expected_path.read_text())
    assert saved_records == initial_records


def test_update_all_priority_and_limit(repo: JournalRepository) -> None:
    """Verify that updates prioritize missing info and respect the max update limit."""
    repo.update_limit = 1
    today = date.today()
    old_date = str(today - timedelta(days=45))
    recent_date = str(today - timedelta(days=5))

    repo.records = [
        {"input_title": "Old", "update": old_date, "ISSN": "1234-5678"},
        {"input_title": "Missing", "update": recent_date, "ISSN": None},  # Priority
        {"input_title": "Recent", "update": recent_date, "ISSN": "9012-3456"},
    ]

    updated_data = [
        {"input_title": "Missing", "ISSN": "1111-2222", "update": str(today)}
    ]

    with patch.object(
        JournalRepository, "get_journal_metadata", return_value=updated_data
    ) as mock_get:
        repo.update_all()

        assert mock_get.call_count == 1
        assert repo.has_pending_updates is True
        # Ensure 'Missing' was the one updated
        assert any(j["ISSN"] == "1111-2222" for j in repo.records)
