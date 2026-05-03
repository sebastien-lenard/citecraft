from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister import WorkRepository


@pytest.fixture
def repo() -> WorkRepository:
    """Provides a fresh instance of WorkRepository for each test."""
    return WorkRepository()


@patch("manuscript_reference_lister.work_repository.RequestsWrapper.get")
def test_fetch_not_found(mock_get: MagicMock, repo: WorkRepository) -> None:
    """Verify behavior when no results are found (returns empty list)."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}
    mock_get.return_value = mock_resp

    result = repo.fetch_dois_for_this_info("UnknownAuthor", "2025", issn="1752-0894")
    assert result == []


@patch("manuscript_reference_lister.work_repository.RequestsWrapper.get")
def test_returns_multiple_candidates(mock_get: MagicMock, repo: WorkRepository) -> None:
    """Verify that the repo identifies and returns multiple valid candidates."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "message": {
            "items": [
                {
                    "DOI": "10.1038/s41561-020-0585-2",
                    "type": "journal-article",
                    "author": [{"family": "Lenard", "sequence": "first"}],
                },
                {
                    "DOI": "10.1/ref2",
                    "type": "proceedings-article",
                    "author": [{"family": "Lenard", "sequence": "first"}],
                },
            ]
        }
    }
    mock_get.return_value = mock_resp
    repo._get_formatted_full_reference = MagicMock(return_value="APA String")

    results = repo.fetch_dois_for_this_info("Lenard et al.", "2020", issn="1752-0894")

    assert len(results) == 2
    assert results[0]["type"] == "journal-article"
    # Fixed: Match the full constructed DOI URL
    assert results[0]["doi"] == "https://doi.org/10.1038/s41561-020-0585-2"
    assert results[1]["type"] == "proceedings-article"


@patch("manuscript_reference_lister.work_repository.RequestsWrapper.get")
def test_parameterized_keywords(mock_get: MagicMock, repo: WorkRepository) -> None:
    """Verify that custom keywords are correctly injected into the API query."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}
    mock_get.return_value = mock_resp

    custom_kws = "Shifts in landslide frequency–area distribution"
    repo.fetch_dois_for_this_info(
        "Guns and Vanacker", "2014", issn="2213-3054", keywords=custom_kws
    )

    _, kwargs = mock_get.call_args
    assert custom_kws in kwargs.get("params", {}).get("query", "")


@patch("manuscript_reference_lister.work_repository.RequestsWrapper.get")
def test_author_validation_filtering(mock_get: MagicMock, repo: WorkRepository) -> None:
    """Verify that candidates with non-matching first authors are filtered out."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "message": {
            "items": [
                {
                    "DOI": "10.1/match",
                    "author": [{"family": "Guns", "sequence": "first"}],
                },
                {
                    "DOI": "10.1/wrong",
                    "author": [{"family": "Smith", "sequence": "first"}],
                },
                {
                    "DOI": "10.1/inverted",
                    "author": [{"given": "Guns", "family": "M.", "sequence": "first"}],
                },
            ]
        }
    }
    mock_get.return_value = mock_resp

    results = repo.fetch_dois_for_this_info("Guns et al.", "2014", issn="2213-3054")

    assert len(results) == 2
    assert results[0]["doi"] == "https://doi.org/10.1/match"
    assert results[1]["doi"] == "https://doi.org/10.1/inverted"


@pytest.mark.parametrize(
    "item, search_authors, expected_count, expected_result",
    [
        ({"author": [{"family": "Lenard", "sequence": "first"}]}, ["Lenard"], 1, True),
        ({"author": [{"name": "Lenard"}]}, ["Lenard"], 1, True),
        ({"author": [{"family": "Van Dijk"}]}, ["  van dijk  "], 1, True),
        ({"author": [{"family": "Zappa"}]}, ["Hendrix"], 1, False),
        ({"author": [{"family": "Lénárd"}]}, ["Lenard"], 1, True),
        ({"author": [{"family": "François"}]}, ["Francois"], 1, True),
        ({"author": [{"family": "Łukasiewicz"}]}, ["Lukasiewicz"], 1, True),
        ({"author": [{"family": "Peña"}]}, ["Pena"], 1, True),
        ({"author": [{"family": "Erdős"}]}, ["Erdos"], 1, True),
        ({"author": [{"family": "Lenard"}, {"family": "Smith"}]}, ["Lenard"], 1, False),
        (
            {"author": [{"family": "Guns"}, {"family": "Vanacker"}]},
            ["guns", "vanacker"],
            2,
            True,
        ),
        (
            {"author": [{"family": "Guns"}, {"family": "Dupont"}]},
            ["guns", "vanacker"],
            2,
            False,
        ),
        (
            {"author": [{"family": "Guns"}, {"family": "V"}, {"family": "T"}]},
            ["guns", "v"],
            2,
            False,
        ),
        (
            {"author": [{"family": "Lenard"}, {"family": "A"}, {"family": "B"}]},
            ["lenard"],
            None,
            True,
        ),
    ],
)
def test_validate_first_author_logic(
    repo: WorkRepository,
    item: dict,
    search_authors: list,
    expected_count: int,
    expected_result: bool,
) -> None:
    """Directly test author validation logic across naming and count scenarios."""
    assert (
        repo._validate_first_author(item, search_authors, expected_count)
        == expected_result
    )
