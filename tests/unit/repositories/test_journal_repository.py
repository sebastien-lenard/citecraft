# tests/unit/repositories/test_journal_repository.py
import logging
import time
from datetime import date, timedelta
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest

from citecraft.repositories import JournalRepository
from citecraft.repositories.journal_repository import UpdateBatchState
from citecraft.schemas import JournalMetadata
from citecraft.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> JournalRepository:
    """Provide JournalRepository instance utilizing test config."""
    return JournalRepository(config=test_config)


def test_log_heartbeat_if_needed(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify heartbeat logger triggers periodically based on config threshold."""
    repo.config = repo.config.model_copy(
        update={"default_logging_frequency_for_batch_updates": 0.05},
    )
    with caplog.at_level(logging.INFO):
        t1 = time.time() - 0.1
        t2 = repo._log_heartbeat_if_needed(3, 10, t1)
        assert t2 > t1
        assert "Batch update status: 7 updates remaining" in caplog.text

        caplog.clear()
        t3 = repo._log_heartbeat_if_needed(4, 10, t2)
        assert t3 == t2
        assert "Batch update status" not in caplog.text


def test_get_journal_metadata_success(repo: JournalRepository) -> None:
    """Verify successful retrieval of ISSNs and years from endpoints."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {"items": [{"title": "Geology", "ISSN": ["0091-7613"]}]},
    }

    mock_year = MagicMock(status_code=200)
    mock_year.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[1973]]},
                    "published-online": {"date-parts": [[1995]]},
                },
            ],
        },
    }

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [
            (mock_main, None),
            (mock_year, None),
            (mock_year, None),
        ]

        results = repo.get_journal_metadata("Geology")

        assert len(results) == 1
        assert results[0].issn == "0091-7613"
        assert results[0].start_year == 1973
        assert results[0].end_year == 1995


def test_get_journal_metadata_not_found_behavior(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify fallback to template when no match is found."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}

    with (
        patch.object(repo.http_client_wrapper, "get", return_value=(mock_resp, None)),
        caplog.at_level(logging.WARNING),
    ):
        results = repo.get_journal_metadata("Unknown Journal")

        assert "Journal Unknown Journal not found." in caplog.text
        assert len(results) == 1
        assert results[0].issn is None


def test_get_journal_metadata_empty_response(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify fallback when network or API returns a null response."""
    with (
        patch.object(repo.http_client_wrapper, "get", return_value=(None, "mock_url")),
        caplog.at_level(logging.WARNING),
    ):
        results = repo.get_journal_metadata("Some Title")
        assert len(results) == 1
        assert results[0].input_title == "Some Title"
        assert results[0].issn is None
        assert "Empty journal 'Some Title' response from URL" in caplog.text


def test_get_journal_metadata_exact_matches_duplicate_discarded(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify multiple exact matches logs a warning and selects the first match."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {"title": "Duplicate", "ISSN": ["0028-0836"]},
                {"title": "Duplicate", "ISSN": ["8765-4321"]},
            ],
        },
    }
    mock_year = MagicMock(status_code=200)
    mock_year.json.return_value = {
        "message": {"items": [{"published-print": {"date-parts": [[2001]]}}]},
    }

    with (
        patch.object(repo.http_client_wrapper, "get") as mock_get,
        caplog.at_level(logging.WARNING),
    ):
        mock_get.side_effect = [
            (mock_main, None),
            (mock_year, None),
            (mock_year, None),
        ]
        results = repo.get_journal_metadata("Duplicate")
        assert len(results) == 1
        assert results[0].issn == "0028-0836"
        assert "Discarded 2 duplicate titles" in caplog.text


def test_get_journal_metadata_similar_matches_found(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify fuzzy title similarity, filtering, and mapping logic."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Nature Geoscience",
                    "publisher": "Springer Nature",
                    "issn": ["1752-0894"],
                },
                {
                    "title": "Nature-Geosciences",
                    "publisher": "Springer Nature",
                    "issn": ["1752-0894", "1752-0908"],
                },
                {
                    "title": "Nature Geoscience",
                    "publisher": "Springer Nature",
                    "issn": ["1752-0894"],
                },
            ],
        },
    }
    mock_year = MagicMock(status_code=200)
    mock_year.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[2008]]},
                    "published-online": {"date-parts": [[2026]]},
                },
            ],
        },
    }

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        mock_get.side_effect = [
            (mock_main, None),
            (mock_year, None),
            (mock_year, None),
            (mock_year, None),
            (mock_year, None),
        ]

        with caplog.at_level(logging.WARNING):
            results = repo.get_journal_metadata("nature geoscience")

            assert "Use similar titles to fill metadata" in caplog.text
            assert len(results) == 2
            assert results[0].issn == "1752-0894"
            assert results[1].issn == "1752-0908"


def test_get_journal_metadata_missing_issn_handling(repo: JournalRepository) -> None:
    """Verify journals without ISSN are logged and kept without range queries."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Natural Hazards",
                    "publisher": "Copernicus Publications",
                },
            ],
        },
    }

    with patch.object(
        repo.http_client_wrapper, "get", return_value=(mock_main, None),
    ) as mock_get:
        results = repo.get_journal_metadata("Natural Hazards")

        assert len(results) == 1
        assert results[0].issn is None
        assert mock_get.call_count == 1


def test_get_journal_metadata_empty_publication_years(repo: JournalRepository) -> None:
    """Verify default empty year ranges when no published works are detected."""
    mock_main = MagicMock(status_code=200)
    mock_main.json.return_value = {
        "message": {
            "items": [
                {
                    "title": "Empty Journal",
                    "publisher": "Silent Publisher",
                    "issn": ["0010-051x"],
                },
            ],
        },
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
        assert results[0].start_year is None
        assert results[0].end_year is None
        assert mock_get.call_count == 3


def test_get_issns_by_input_title(repo: JournalRepository) -> None:
    """Verify unicity and extraction of valid ISSNs."""
    repo.records = [
        JournalMetadata(
            input_title="Journal A", issn="0010-051x", start_year=2000, end_year=2010,
        ),
        JournalMetadata(
            input_title="Journal A", issn="2049-3630", start_year=2005, end_year=2015,
        ),
        JournalMetadata(input_title="Journal A", issn=None),
    ]

    assert repo.get_issns_by_input_title("Journal A") == ["0010-051x", "2049-3630"]
    assert repo.get_issns_by_input_title("Non Existent") == []


def test_get_unique_issns_for_titles(repo: JournalRepository) -> None:
    """Verify unique sorting and extraction of ISSNs with normalization rules."""
    repo.records = [
        JournalMetadata(
            input_title="Nature Geoscience",
            issn="1752-0894",
            start_year=2008,
            end_year=2026,
        ),
        JournalMetadata(
            input_title="Journal of Climate",
            issn="2049-3630",
            start_year=2000,
            end_year=2010,
        ),
    ]

    assert repo.get_unique_issns_for_titles([]) == []
    assert repo.get_unique_issns_for_titles(["Unknown"]) == []
    assert repo.get_unique_issns_for_titles(
        ["Nature Geoscience", "Journal of Climate"],
    ) == ["1752-0894", "2049-3630"]


@pytest.mark.parametrize(
    "order, mock_items, expected_year",
    [
        (
            "asc",
            [
                {
                    "published-print": {"date-parts": [[1990]]},
                    "published-online": {"date-parts": [[2024]]},
                },
            ],
            1990,
        ),
        (
            "desc",
            [
                {
                    "published-print": {"date-parts": [[1990]]},
                    "published-online": {"date-parts": [[2024]]},
                },
            ],
            2024,
        ),
        ("asc", [], None),
        (
            "asc",
            [
                {
                    "published-print": {"date-parts": [[None]]},
                    "published-online": {"date-parts": [[2010]]},
                },
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
    """Verify endpoint resolution behaves correctly under different scenarios."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"items": mock_items}}

    with patch.object(
        repo.http_client_wrapper, "get", return_value=(mock_response, None),
    ) as mock_get:
        assert repo.get_issn_year_endpoint("2049-3630", order) == expected_year
        mock_get.assert_called_once()


def test_get_issn_year_endpoint_empty_response(repo: JournalRepository) -> None:
    """Verify endpoint recovery when response resolves to None."""
    with patch.object(
        repo.http_client_wrapper, "get", return_value=(None, "mock_url"),
    ) as mock_get:
        assert repo.get_issn_year_endpoint("1234-5678", "asc") is None
        mock_get.assert_called_once()


def test_get_issn_year_endpoint_no_valid_years(repo: JournalRepository) -> None:
    """Verify endpoint resolution when payload exists but contains only null dates."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "items": [
                {
                    "published-print": {"date-parts": [[None]]},
                    "published-online": {"date-parts": [[None]]},
                },
            ],
        },
    }
    with patch.object(
        repo.http_client_wrapper, "get", return_value=(mock_response, None),
    ):
        assert repo.get_issn_year_endpoint("2049-3630", "asc") is None


@pytest.mark.parametrize(
    (
        "records, pending_updates, expected_synchronized, expected_missing, "
        "expected_expired, expected_pending"
    ),
    [
        (
            [
                JournalMetadata(
                    input_title="Valid J",
                    true_title="T",
                    publisher="P",
                    issn="2049-3630",
                    start_year=2000,
                    end_year=2026,
                    update=str(date.today() - timedelta(days=5)),
                ),
                JournalMetadata(
                    input_title="Expired J",
                    true_title="T",
                    publisher="P",
                    issn="1752-0908",
                    start_year=2000,
                    end_year=2026,
                    update=str(date.today() - timedelta(days=45)),
                ),
                JournalMetadata(
                    input_title="Missing J",
                    true_title=None,
                    publisher=None,
                    issn=None,
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
        (
            [
                JournalMetadata(
                    input_title="Valid J",
                    true_title="T",
                    publisher="P",
                    issn="2049-3630",
                    start_year=2000,
                    end_year=2026,
                    update=str(date.today() - timedelta(days=5)),
                ),
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
    """Verify sync evaluation behaves correctly for combinations of states."""
    repo.config = repo.config.model_copy(update={"journal_update_days": 30})
    repo.records = records
    repo.has_pending_updates = pending_updates

    status = repo.get_sync_status()

    assert status["is_fully_synchronized"] is expected_synchronized
    assert status["missing_metadata_count"] == expected_missing
    assert status["expired_metadata_count"] == expected_expired
    assert status["has_pending_updates"] is expected_pending


def test_merge_new_titles(repo: JournalRepository) -> None:
    """Verify merge of clean input templates avoiding existing overrides."""
    repo.records = [JournalMetadata(input_title="Existing", issn="2049-3630")]
    repo.merge_new_titles(input_titles=["Existing", "Geology", "Geology"])

    assert len(repo) == 2
    assert any(
        r.input_title == "Existing" and r.issn == "2049-3630" for r in repo.records
    )

    new_entries = [r for r in repo.records if r.input_title == "Geology"]
    assert len(new_entries) == 1
    assert new_entries[0].issn is None


def test_update_all_priority_and_limit(
    repo: JournalRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify prioritizing missing metadata and enforcement of capacity limits."""
    caplog.set_level(logging.INFO)
    repo.config = repo.config.model_copy(
        update={"journal_update_limit": 1, "journal_update_days": 30},
    )
    today = date.today()
    old_date = str(today - timedelta(days=45))
    recent_date = str(today - timedelta(days=5))

    repo.records = [
        JournalMetadata(
            input_title="Old",
            true_title="Old Journal",
            publisher="Pub",
            issn="0036-8075",
            start_year=2000,
            end_year=2024,
            update=old_date,
        ),
        JournalMetadata(
            input_title="Missing",
            true_title=None,
            publisher=None,
            issn=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
        JournalMetadata(
            input_title="Recent",
            true_title="Recent Journal",
            publisher="Pub",
            issn="0010-051X",
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
            issn="2049-3630",
            start_year=2000,
            end_year=2024,
            update=str(today),
        ),
    ]

    with patch.object(
        JournalRepository, "get_journal_metadata", return_value=updated_data,
    ) as mock_get:
        repo.update_all()

        assert "Journal categorization completed" in caplog.text
        assert mock_get.call_count == 1
        mock_get.assert_called_with("Missing")
        assert repo.has_pending_updates is True


def test_update_all_sorting_logic_strict(repo: JournalRepository) -> None:
    """Verify completed records are prioritized over templates alphabetically."""
    repo.config = repo.config.model_copy(
        update={"journal_update_limit": 0, "journal_update_days": 30},
    )
    today = date.today()
    recent_date = str(today - timedelta(days=5))

    repo.records = [
        JournalMetadata(
            input_title="Alpha Missing",
            true_title=None,
            publisher=None,
            issn=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
        JournalMetadata(
            input_title="Zulu Complete",
            true_title="Zulu Journal",
            publisher="Pub",
            issn="1752-0894",
            start_year=2020,
            end_year=2026,
            update=recent_date,
        ),
        JournalMetadata(
            input_title="Mike Missing",
            true_title=None,
            publisher=None,
            issn=None,
            start_year=None,
            end_year=None,
            update=recent_date,
        ),
        JournalMetadata(
            input_title="Bravo Complete",
            true_title="Bravo Journal",
            publisher="Pub",
            issn="0361-0160",
            start_year=2010,
            end_year=2026,
            update=recent_date,
        ),
    ]

    with patch.object(JournalRepository, "get_journal_metadata", return_value=None):
        repo.update_all()

    assert repo.records[0].input_title == "Bravo Complete"
    assert repo.records[1].input_title == "Zulu Complete"
    assert repo.records[2].input_title == "Alpha Missing"
    assert repo.records[3].input_title == "Mike Missing"


def test_update_batch_empty_new_data_fallback(repo: JournalRepository) -> None:
    """Verify _update_batch retains original record when API returns empty list."""
    record = JournalMetadata(input_title="Empty Lookup J")
    new_records: list[JournalMetadata] = []
    state = UpdateBatchState(total=1)

    repo.config = repo.config.model_copy(update={"journal_update_limit": 1})

    with patch.object(repo, "get_journal_metadata", return_value=[]):
        repo._update_batch([record], new_records, state)

    assert len(new_records) == 1
    assert new_records[0].input_title == "Empty Lookup J"
    assert state.update_count == 1
    assert state.processed == 1
