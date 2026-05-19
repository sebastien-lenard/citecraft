import logging
from datetime import date, timedelta
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister.repositories import JournalRepository
from manuscript_reference_lister.schemas import JournalMetadata


@pytest.fixture
def repo() -> JournalRepository:
    """Provides a fresh instance of JournalRepository for each test."""
    return JournalRepository()


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

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [mock_main, mock_year, mock_year]

        results = repo.get_journal_metadata("Geology")

        assert len(results) == 1
        assert results[0].ISSN == "0091-7613"
        assert results[0].start_year == 1973
        assert results[0].end_year == 1995


def test_get_journal_metadata_not_found_behavior(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify fallback to template and warning log when absolutely no matching journal
    or similar titles are found.."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_resp):
        with caplog.at_level(logging.WARNING):
            results = repo.get_journal_metadata("Unknown Journal")

            assert "Journal Unknown Journal not found." in caplog.text
            assert "similar titles found" not in caplog.text
            assert len(results) == 1
            assert results[0].ISSN is None
            assert results[0].similar_titles is None
            assert results[0].input_title == "Unknown Journal"


def test_get_journal_metadata_similar_matches_found(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify normalization rules detect potential matches, filter duplicates, and "
    "set similar_titles, and follow up by collecting their ISSNs, query their publication years, and enrich records with metadata."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Nature Geoscience",
                    "publisher": "Springer Nature",
                    "ISSN": ["1752-0894"],
                },
                {
                    "title": "Nature-Geosciences",
                    "publisher": "Springer Nature",
                    "ISSN": ["1752-0894", "1752-0908"],  # Includes a unique one
                },
                {
                    "title": "Nature Geoscience",
                    "publisher": "Springer Nature",
                    "ISSN": ["1752-0894"],
                },  # Duplicate item
                {
                    "title": "Science Journal",
                    "publisher": "Other",
                    "ISSN": ["0000-0000"],
                },  # Out of scope
            ]
        }
    }

    mock_year = MagicMock(status_code=200)
    mock_year.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[2008]]},
                    "published-online": {"date-parts": [[2026]]},
                }
            ]
        }
    }

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        # 1 call for main query + 2 endpoints per unique ISSN found
        # (2 unique ISSNs = 4 calls)
        mock_get.side_effect = [mock_main, mock_year, mock_year, mock_year, mock_year]

        with caplog.at_level(logging.WARNING):
            results = repo.get_journal_metadata("nature geoscience")

            # Check for updated warning log string
            assert (
                "Journal nature geoscience not found. Use similar titles to fill"
                " metadata: Nature Geoscience, Nature-Geosciences" in caplog.text
            )
            # 2 valid unique ISSNs across similar titles generate 2 metadata entries
            assert len(results) == 2

            # Assert first entry values
            assert results[0].input_title == "nature geoscience"
            assert results[0].true_title == "Nature Geoscience"
            assert results[0].ISSN == "1752-0894"
            assert results[0].start_year == 2008
            assert results[0].end_year == 2026
            assert results[0].similar_titles == [
                "Nature Geoscience",
                "Nature-Geosciences",
            ]

            # Assert second entry values (resolved from the structural variant item)
            assert results[1].input_title == "nature geoscience"
            assert results[1].true_title == "Nature-Geosciences"
            assert results[1].ISSN == "1752-0908"
            assert results[1].similar_titles == [
                "Nature Geoscience",
                "Nature-Geosciences",
            ]

            assert mock_get.call_count == 5


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

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [
            mock_main,
            year_mock(1869),
            year_mock(2023),  # ISSN 1
            year_mock(1997),
            year_mock(2023),  # ISSN 2
        ]

        results = repo.get_journal_metadata("Nature")

        assert len(results) == 2
        assert results[0].ISSN == "0028-0836"
        assert results[1].ISSN == "1476-4687"
        assert mock_get.call_count == 5


def test_get_journal_metadata_missing_issn_handling(repo: JournalRepository) -> None:
    """Verify that journals found without an ISSN are preserved in the results
    with ISSN and years set to None, without calling year endpoints.
    """
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Natural Hazards and Earth System Sciences",
                    "publisher": "Copernicus Publications",
                }
            ]
        }
    }

    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_main
    ) as mock_get:
        results = repo.get_journal_metadata("Natural Hazards and Earth System Sciences")

        assert len(results) == 1
        assert results[0].true_title == "Natural Hazards and Earth System Sciences"
        assert results[0].ISSN is None
        assert results[0].start_year is None
        assert results[0].end_year is None
        assert mock_get.call_count == 1


def test_get_journal_metadata_empty_publication_years(repo: JournalRepository) -> None:
    """Verify that journals with a valid ISSN but no published works are preserved
    with their metadata intact and dates set to None.
    """
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Empty Journal",
                    "publisher": "Silent Publisher",
                    "ISSN": ["9999-999X"],
                }
            ]
        }
    }

    mock_year_empty = MagicMock(status_code=200)
    mock_year_empty.json.return_value = {"message": {"items": []}}

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [mock_main, mock_year_empty, mock_year_empty]

        results = repo.get_journal_metadata("Empty Journal")

        assert len(results) == 1
        assert results[0].true_title == "Empty Journal"
        assert results[0].ISSN == "9999-999X"
        assert results[0].start_year is None
        assert results[0].end_year is None
        assert mock_get.call_count == 3


def test_get_issns_by_input_title(repo: JournalRepository) -> None:
    """Verify that get_issns_by_input_title extracts unique and clean ISSNs
    for a specific input_title, ignoring duplicates and None values.
    """
    repo.records = [
        JournalMetadata(
            input_title="Journal A", ISSN="1111-1111", start_year=2000, end_year=2010
        ),
        JournalMetadata(
            input_title="Journal A", ISSN="2222-2222", start_year=2005, end_year=2015
        ),
        JournalMetadata(input_title="Journal A", ISSN=None),  # Must be ignored
        JournalMetadata(
            input_title="Journal B", ISSN="3333-3333", start_year=2000, end_year=2020
        ),
    ]

    issns = repo.get_issns_by_input_title("Journal A")
    assert issns == ["1111-1111", "2222-2222"]

    assert repo.get_issns_by_input_title("Non Existent") == []


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
        repo.http_client_wrapper, "get", return_value=mock_response
    ) as mock_get:
        result = repo.get_issn_year_endpoint("1234-5678", order)
        assert result == expected_year
        # Verify the API was called with the correct sort/order params
        mock_get.assert_called_with(
            repo.config.crossref_api_journals_issn_url.replace("{issn}", "1234-5678"),
            params={
                "sort": "published",
                "order": order,
                "rows": 1,
                "mailto": repo.config.crossref_api_email,
            },
            headers=repo.headers,
        )
        mock_get.assert_called_once()


def test_get_issn_year_endpoint_no_items(repo: JournalRepository) -> None:
    """Test the 'guard clause' when the API returns no items."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"items": []}}
    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_response
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
        repo.http_client_wrapper, "get", return_value=mock_response
    ) as mock_get:
        assert repo.get_issn_year_endpoint("1111-2222", "asc") == 2010
        mock_get.assert_called_once()


def test_get_sync_status_isolated(repo: JournalRepository) -> None:
    """Verify get_sync_status accurately categorizes different records state without
    running update_all."""
    repo.config = repo.config.model_copy(update={"journal_update_days": 30})
    today = date.today()
    old_date = str(today - timedelta(days=45))  # Expired threshold
    recent_date = str(today - timedelta(days=5))  # Valid threshold

    repo.records = [
        # Valid
        JournalMetadata(
            input_title="Valid J",
            true_title="T",
            publisher="P",
            ISSN="1-1",
            start_year=2000,
            end_year=2026,
            update=recent_date,
        ),
        # Expired
        JournalMetadata(
            input_title="Expired J",
            true_title="T",
            publisher="P",
            ISSN="2-2",
            start_year=2000,
            end_year=2026,
            update=old_date,
        ),
        # Missing (Incomplete)
        JournalMetadata(
            input_title="Missing J",
            true_title=None,
            publisher=None,
            ISSN=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
    ]

    repo.has_pending_updates = True

    status = repo.get_sync_status()

    assert status["is_fully_synchronized"] is False
    assert status["missing_metadata_count"] == 1
    assert status["expired_metadata_count"] == 1
    assert status["has_pending_updates"] is True


def test_get_sync_status_fully_synchronized(repo: JournalRepository) -> None:
    """Verify status report when all elements are complete and up to date."""
    repo.config = repo.config.model_copy(update={"journal_update_days": 30})
    recent_date = str(date.today() - timedelta(days=5))

    repo.records = [
        JournalMetadata(
            input_title="Valid J",
            true_title="T",
            publisher="P",
            ISSN="1-1",
            start_year=2000,
            end_year=2026,
            update=recent_date,
        )
    ]
    repo.has_pending_updates = False

    status = repo.get_sync_status()

    assert status["is_fully_synchronized"] is True
    assert status["missing_metadata_count"] == 0
    assert status["expired_metadata_count"] == 0
    assert status["has_pending_updates"] is False


def test_merge_new_titles(repo: JournalRepository) -> None:
    """Verify that new titles are deduplicated and merged as templates without
    affecting existing data."""
    repo.records = [JournalMetadata(input_title="Existing", ISSN="0000-0000")]
    repo.merge_new_titles(input_titles=["Existing", "Geology", "Geology"])

    assert len(repo) == 2
    assert any(
        r.input_title == "Existing" and r.ISSN == "0000-0000" for r in repo.records
    )

    new_entries = [r for r in repo.records if r.input_title == "Geology"]
    assert len(new_entries) == 1
    assert new_entries[0].ISSN is None
    assert new_entries[0].update == str(date.today())


def test_update_all_priority_and_limit(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that updates prioritize missing info and respect the max update limit."""
    caplog.set_level(logging.INFO)
    repo.config = repo.config.model_copy(
        update={"journal_update_limit": 1, "journal_update_days": 30}
    )
    today = date.today()
    old_date = str(today - timedelta(days=45))
    recent_date = str(today - timedelta(days=5))

    repo.records = [
        # This one is EXPIRED (all fields filled, date is old)
        JournalMetadata(
            input_title="Old",
            true_title="Old Journal",
            publisher="Pub",
            ISSN="1234-5678",
            start_year=2000,
            end_year=2024,
            update=old_date,
        ),
        # This one is MISSING (ISSN is None)
        JournalMetadata(
            input_title="Missing",
            true_title=None,
            publisher=None,
            ISSN=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
        # This one is VALID (all fields filled, date is recent)
        JournalMetadata(
            input_title="Recent",
            true_title="Recent Journal",
            publisher="Pub",
            ISSN="9012-3456",
            start_year=2020,
            end_year=2024,
            update=recent_date,
        ),
    ]

    updated_data = [
        JournalMetadata(
            input_title="Missing",
            true_title="Missing Journal",
            publisher="Pub",
            ISSN="1111-2222",
            start_year=2000,
            end_year=2024,
            update=str(today),
        )
    ]

    with patch.object(
        JournalRepository, "get_journal_metadata", return_value=updated_data
    ) as mock_get:
        repo.update_all()

        assert (
            "Journal categorization completed. Missing: 1, Expired: 1, Valid: 1"
            in caplog.text
        )

        # Ensure 'Missing' was the one updated due to limit=1
        assert mock_get.call_count == 1
        mock_get.assert_called_with("Missing")
        assert repo.has_pending_updates is True

        # All records are now complete ("Missing" was updated by the API, "Old" and
        # "Recent" already had data)
        # They are all sorted alphabetically by input_title: "Missing" (M) ->
        # "Old" (O) -> "Recent" (R)
        assert repo.records[0].input_title == "Missing"
        assert (
            repo.records[0].ISSN == "1111-2222"
        )  # Verifies the API update took effect

        assert repo.records[1].input_title == "Old"

        assert repo.records[2].input_title == "Recent"

        # Test the design pattern: fetch status through the inspector method
        status = repo.get_sync_status()
        assert status["is_fully_synchronized"] is False
        assert status["missing_metadata_count"] == 0
        assert status["expired_metadata_count"] == 1
        assert status["has_pending_updates"] is True


def test_update_all_sorting_logic_strict(repo: JournalRepository) -> None:
    """Verify that records are strictly partitioned (complete first, then incomplete)
    and that each subgroup is sorted alphabetically by input_title.
    """
    repo.config = repo.config.model_copy(
        update={"journal_update_limit": 0, "journal_update_days": 30}
    )
    today = date.today()
    recent_date = str(today - timedelta(days=5))

    repo.records = [
        # INCOMPLETE (Missing fields) - Title starts with 'A'
        JournalMetadata(
            input_title="Alpha Missing",
            true_title=None,
            publisher=None,
            ISSN=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
        # COMPLETE - Title starts with 'Z'
        JournalMetadata(
            input_title="Zulu Complete",
            true_title="Zulu Journal",
            publisher="Pub",
            ISSN="9999-9999",
            start_year=2020,
            end_year=2026,
            update=recent_date,
        ),
        # INCOMPLETE (Missing fields) - Title starts with 'M'
        JournalMetadata(
            input_title="Mike Missing",
            true_title=None,
            publisher=None,
            ISSN=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
        # COMPLETE - Title starts with 'B'
        JournalMetadata(
            input_title="Bravo Complete",
            true_title="Bravo Journal",
            publisher="Pub",
            ISSN="1111-1111",
            start_year=2010,
            end_year=2026,
            update=recent_date,
        ),
    ]

    # update_limit=0 forces the repository to keep records untouched but still
    # categorizes and sorts them
    with patch.object(JournalRepository, "get_journal_metadata", return_value=None):
        repo.update_all()

    # Expected order:
    # Group 1 (Complete): "Bravo Complete" -> "Zulu Complete"
    # Group 2 (Incomplete): "Alpha Missing" -> "Mike Missing"
    assert repo.records[0].input_title == "Bravo Complete"
    assert repo.records[1].input_title == "Zulu Complete"
    assert repo.records[2].input_title == "Alpha Missing"
    assert repo.records[3].input_title == "Mike Missing"
