import logging
from datetime import date, timedelta
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest

from citecraft.repositories import JournalRepository
from citecraft.schemas import JournalMetadata
from citecraft.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> JournalRepository:
    """Provide JournalRepository instance utilizing the isolated global test
    configuration."""
    return JournalRepository(config=test_config)


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
        mock_get.side_effect = [
            (mock_main, None),
            (mock_year, None),
            (mock_year, None),
        ]

        results = repo.get_journal_metadata("Geology")

        assert len(results) == 1
        assert results[0].ISSN == "0091-7613"
        assert results[0].start_year == 1973
        assert results[0].end_year == 1995


def test_get_journal_metadata_not_found_behavior(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify fallback to template and warning log when absolutely no matching journal
    is found."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}

    with patch.object(repo.http_client_wrapper, "get", return_value=(mock_resp, None)):
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
    """Verify normalization rules detect potential matches, filter duplicates, and set
    similar_titles."""
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
                    "ISSN": ["1752-0894", "1752-0908"],
                },
                {
                    "title": "Nature Geoscience",
                    "publisher": "Springer Nature",
                    "ISSN": ["1752-0894"],
                },
                {
                    "title": "Science Journal",
                    "publisher": "Other",
                    "ISSN": ["0091-7613"],
                },
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
        mock_get.side_effect = [
            (mock_main, None),
            (mock_year, None),
            (mock_year, None),
            (mock_year, None),
            (mock_year, None),
        ]

        with caplog.at_level(logging.WARNING):
            results = repo.get_journal_metadata("nature geoscience")

            assert (
                "Journal nature geoscience not found. Use similar titles to fill"
                " metadata: Nature Geoscience, Nature-Geosciences" in caplog.text
            )
            assert len(results) == 2

            assert results[0].input_title == "nature geoscience"
            assert results[0].true_title == "Nature Geoscience"
            assert results[0].ISSN == "1752-0894"
            assert results[0].start_year == 2008
            assert results[0].end_year == 2026
            assert results[0].similar_titles == [
                "Nature Geoscience",
                "Nature-Geosciences",
            ]

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
                    "title": "Nature",
                    "ISSN": ["0028-0836", "1476-4687"],
                }
            ]
        }
    }

    def year_mock(year: int) -> MagicMock:
        m = MagicMock(status_code=200)
        m.json.return_value = {
            "message": {"items": [{"published-print": {"date-parts": [[year]]}}]}
        }
        return m

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [
            (mock_main, None),
            (year_mock(1869), None),
            (year_mock(2023), None),
            (year_mock(1997), None),
            (year_mock(2023), None),
        ]

        results = repo.get_journal_metadata("Nature")

        assert len(results) == 2
        assert results[0].ISSN == "0028-0836"
        assert results[1].ISSN == "1476-4687"
        assert mock_get.call_count == 5


def test_get_journal_metadata_missing_issn_handling(repo: JournalRepository) -> None:
    """Verify that journals found without an ISSN are preserved without calling year
    endpoints."""
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
        repo.http_client_wrapper, "get", return_value=(mock_main, None)
    ) as mock_get:
        results = repo.get_journal_metadata("Natural Hazards and Earth System Sciences")

        assert len(results) == 1
        assert results[0].true_title == "Natural Hazards and Earth System Sciences"
        assert results[0].ISSN is None
        assert results[0].start_year is None
        assert results[0].end_year is None
        assert mock_get.call_count == 1


def test_get_journal_metadata_empty_publication_years(repo: JournalRepository) -> None:
    """Verify that journals with valid ISSN but no published works preserve metadata."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Empty Journal",
                    "publisher": "Silent Publisher",
                    "ISSN": ["0010-051x"],
                }
            ]
        }
    }
    mock_year_empty = MagicMock(status_code=200)
    mock_year_empty.json.return_value = {"message": {"items": []}}

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [
            (mock_main, None),
            (mock_year_empty, None),
            (mock_year_empty, None),
        ]

        results = repo.get_journal_metadata("Empty Journal")

        assert len(results) == 1
        assert results[0].true_title == "Empty Journal"
        assert results[0].ISSN == "0010-051x"
        assert results[0].start_year is None
        assert results[0].end_year is None
        assert mock_get.call_count == 3


def test_get_issns_by_input_title(repo: JournalRepository) -> None:
    """Verify that get_issns_by_input_title extracts unique and clean ISSNs, ignoring
    empty fields."""
    repo.records = [
        JournalMetadata(
            input_title="Journal A", ISSN="0010-051x", start_year=2000, end_year=2010
        ),
        JournalMetadata(
            input_title="Journal A", ISSN="2049-3630", start_year=2005, end_year=2015
        ),
        JournalMetadata(input_title="Journal A", ISSN=None),
        JournalMetadata(
            input_title="Journal B", ISSN="1752-0894", start_year=2000, end_year=2020
        ),
    ]

    issns = repo.get_issns_by_input_title("Journal A")
    assert issns == ["0010-051x", "2049-3630"]
    assert repo.get_issns_by_input_title("Non Existent") == []


def test_get_unique_issns_for_titles(repo: JournalRepository) -> None:
    """Verify unique sorted ISSN extraction across multiple titles with normalization
    logic."""
    repo.records = [
        JournalMetadata(
            input_title="Nature Geoscience",
            ISSN="1752-0894",
            start_year=2008,
            end_year=2026,
        ),
        JournalMetadata(
            input_title="Nature Geoscience",
            ISSN="1752-0908",
            start_year=2008,
            end_year=2026,
        ),
        JournalMetadata(
            input_title="Journal of Climate",
            ISSN="2049-3630",
            start_year=2000,
            end_year=2010,
        ),
        JournalMetadata(
            input_title="Remote Sensing",
            ISSN=None,
        ),
    ]

    # Validation of unicity and sort
    requested = ["Nature Geoscience", "Journal of Climate"]
    issns = repo.get_unique_issns_for_titles(requested)
    assert issns == ["1752-0894", "1752-0908", "2049-3630"]

    # Minimal check of normalization
    dirty_requested = ["  nature-geoscience  "]
    issns_dirty = repo.get_unique_issns_for_titles(dirty_requested)
    assert issns_dirty == ["1752-0894", "1752-0908"]

    # Boundaries
    assert repo.get_unique_issns_for_titles([]) == []
    assert repo.get_unique_issns_for_titles(["Unknown Journal"]) == []


@pytest.mark.parametrize(
    "order, mock_items, expected_year",
    [
        # Case A: Oldest year extracted via print/online properties
        (
            "asc",
            [
                {
                    "published-print": {"date-parts": [[1990, 1, 1]]},
                    "published-online": {"date-parts": [[2024, 5, 12]]},
                }
            ],
            1990,
        ),
        # Case B: Newest year extracted via online/print properties
        (
            "desc",
            [
                {
                    "published-print": {"date-parts": [[1990, 1, 1]]},
                    "published-online": {"date-parts": [[2024, 5, 12]]},
                }
            ],
            2024,
        ),
        # Case C: Empty API response guard condition
        ("asc", [], None),
        # Case D: Missing print years fall back to online equivalents
        (
            "asc",
            [
                {
                    "published-print": {"date-parts": [[None]]},
                    "published-online": {"date-parts": [[2010, 1, 1]]},
                }
            ],
            2010,
        ),
    ],
)
def test_get_issn_year_endpoint_scenarios(
    repo: JournalRepository,
    order: Literal["asc", "desc"],
    mock_items: list[dict[str, Any]],
    expected_year: int | None,
) -> None:
    """Verify endpoint date resolution behaves correctly across different payload
    conditions."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"items": mock_items}}

    with patch.object(
        repo.http_client_wrapper, "get", return_value=(mock_response, None)
    ) as mock_get:
        result = repo.get_issn_year_endpoint("2049-3630", order)
        assert result == expected_year
        if expected_year is not None or len(mock_items) == 0:
            mock_get.assert_called_with(
                repo.config.crossref_api_journals_issn_url.replace(
                    "{object_name}", "2049-3630"
                ),
                params={
                    "sort": "published",
                    "order": order,
                    "rows": 1,
                    "mailto": repo.config.user_email,
                },
                headers=repo.headers,
            )
        mock_get.assert_called_once()


@pytest.mark.parametrize(
    (
        "records, pending_updates, expected_synchronized, expected_missing, "
        "expected_expired, expected_pending"
    ),
    [
        # Mixed states: Contains expired, missing, and valid entries
        (
            [
                JournalMetadata(
                    input_title="Valid J",
                    true_title="T",
                    publisher="P",
                    ISSN="2049-3630",
                    start_year=2000,
                    end_year=2026,
                    update=str(date.today() - timedelta(days=5)),
                ),
                JournalMetadata(
                    input_title="Expired J",
                    true_title="T",
                    publisher="P",
                    ISSN="1752-0908",
                    start_year=2000,
                    end_year=2026,
                    update=str(date.today() - timedelta(days=45)),
                ),
                JournalMetadata(
                    input_title="Missing J",
                    true_title=None,
                    publisher=None,
                    ISSN=None,
                    start_year=None,
                    end_year=None,
                    update=str(date.today() - timedelta(days=5)),
                ),
            ],
            True,
            False,
            1,
            1,
            True,
        ),
        # Fully synchronized states
        (
            [
                JournalMetadata(
                    input_title="Valid J",
                    true_title="T",
                    publisher="P",
                    ISSN="2049-3630",
                    start_year=2000,
                    end_year=2026,
                    update=str(date.today() - timedelta(days=5)),
                )
            ],
            False,
            True,
            0,
            0,
            False,
        ),
    ],
)
def test_get_sync_status_scenarios(
    repo: JournalRepository,
    records: list[JournalMetadata],
    pending_updates: bool,
    expected_synchronized: bool,
    expected_missing: int,
    expected_expired: int,
    expected_pending: bool,
) -> None:
    """Verify get_sync_status mapping calculations across varying list parameters."""
    repo.config = repo.config.model_copy(update={"journal_update_days": 30})
    repo.records = records
    repo.has_pending_updates = pending_updates

    status = repo.get_sync_status()

    assert status["is_fully_synchronized"] is expected_synchronized
    assert status["missing_metadata_count"] == expected_missing
    assert status["expired_metadata_count"] == expected_expired
    assert status["has_pending_updates"] is expected_pending


def test_merge_new_titles(repo: JournalRepository) -> None:
    """Verify new titles merge as blank templates without overriding pre-existing
    records."""
    repo.records = [JournalMetadata(input_title="Existing", ISSN="2049-3630")]
    repo.merge_new_titles(input_titles=["Existing", "Geology", "Geology"])

    assert len(repo) == 2
    assert any(
        r.input_title == "Existing" and r.ISSN == "2049-3630" for r in repo.records
    )

    new_entries = [r for r in repo.records if r.input_title == "Geology"]
    assert len(new_entries) == 1
    assert new_entries[0].ISSN is None
    assert new_entries[0].update == str(date.today())


def test_update_all_priority_and_limit(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that update processes prioritize missing records and respect capacity
    limits."""
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
            ISSN="0036-8075",
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
            ISSN="0010-051X",
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
            ISSN="2049-3630",
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
            repo.records[0].ISSN == "2049-3630"
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
    """Verify record sorting groups completed journals before placing incomplete items
    alphabetically."""
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
            ISSN="1752-0894",
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
            ISSN="0361-0160",
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
