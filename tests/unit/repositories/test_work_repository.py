from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister.repositories import WorkRepository
from manuscript_reference_lister.schemas import CrossrefAuthor, create_citation_metadata


@pytest.fixture
def repo() -> WorkRepository:
    """Provides a fresh instance of WorkRepository for each test."""
    return WorkRepository()


def test_fetch_not_found(repo: WorkRepository) -> None:
    """Verify behavior when no results are found (returns empty list)."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}

    with patch.object(repo.requests_wrapper, "get", return_value=mock_resp):
        result = repo.get_work_metadata(
            create_citation_metadata(
                first_authors_txt="UnknownAuthor",
                year_and_suffix="2025",
            ),
            input_ISSN="1752-0894",
        )
        assert result == []


def test_returns_multiple_candidates(repo: WorkRepository) -> None:
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

    with patch.object(repo.requests_wrapper, "get", return_value=mock_resp):
        results = repo.get_work_metadata(
            create_citation_metadata(
                first_authors_txt="Lenard et al.", year_and_suffix="2020"
            ),
            input_ISSN="1752-0894",
        )
        assert len(results) == 2
        assert results[0]["type"] == "journal-article"
        assert results[0]["doi"] == "https://doi.org/10.1038/s41561-020-0585-2"
        assert results[1]["type"] == "proceedings-article"


def test_parameterized_keywords(repo: WorkRepository) -> None:
    """Verify that custom keywords are correctly injected into the API query."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}

    custom_kws = "Shifts in landslide frequency–area distribution"

    with patch.object(repo.requests_wrapper, "get", return_value=mock_resp) as mock_get:
        repo.get_work_metadata(
            create_citation_metadata(
                first_authors_txt="Guns and Vanacker",
                year_and_suffix="2014",
            ),
            input_ISSN="2213-3054",
            keywords=custom_kws,
        )

        _, kwargs = mock_get.call_args
        assert custom_kws in kwargs.get("params", {}).get("query", "")


def test_author_validation_filtering(repo: WorkRepository) -> None:
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

    with patch.object(repo.requests_wrapper, "get", return_value=mock_resp):
        results = repo.get_work_metadata(
            create_citation_metadata(
                first_authors_txt="Guns et al.",
                year_and_suffix="2014",
            ),
            input_ISSN="2213-3054",
        )
        assert len(results) == 2
        assert results[0]["doi"] == "https://doi.org/10.1/match"
        assert results[1]["doi"] == "https://doi.org/10.1/inverted"


@pytest.mark.parametrize(
    "crossref_authors, input_first_authors, input_first_authors_count, expected_result",
    [
        ([{"family": "Lenard", "sequence": "first"}], ["Lenard"], 1, True),
        ([{"name": "Lenard", "sequence": "first"}], ["Lenard"], 1, True),
        ([{"family": "Van Dijk", "sequence": "first"}], ["  van dijk  "], 1, True),
        ([{"family": "Zappa", "sequence": "first"}], ["Hendrix"], 1, False),
        ([{"family": "Lénárd", "sequence": "first"}], ["Lenard"], 1, True),
        ([{"family": "François", "sequence": "first"}], ["Francois"], 1, True),
        ([{"family": "Łukasiewicz", "sequence": "first"}], ["Lukasiewicz"], 1, True),
        ([{"family": "Peña", "sequence": "first"}], ["Pena"], 1, True),
        ([{"family": "Erdős", "sequence": "first"}], ["Erdos"], 1, True),
        # Testing count mismatch (expected 1, got 2)
        (
            [
                {"family": "Lenard", "sequence": "first"},
                {"family": "Smith", "sequence": "additional"},
            ],
            ["Lenard"],
            1,
            False,
        ),
        # Testing two authors match
        (
            [
                {"family": "Guns", "sequence": "first"},
                {"family": "Vanacker", "sequence": "additional"},
            ],
            ["guns", "vanacker"],
            2,
            True,
        ),
        # Testing two authors, second fails
        (
            [
                {"family": "Guns", "sequence": "first"},
                {"family": "Dupont", "sequence": "additional"},
            ],
            ["guns", "vanacker"],
            2,
            False,
        ),
        # Testing two authors, count is 2 but list has 3
        (
            [
                {"family": "Guns", "sequence": "first"},
                {"family": "V", "sequence": "additional"},
                {"family": "T", "sequence": "additional"},
            ],
            ["guns", "v"],
            2,
            False,
        ),
        # Testing et al. (expected_count is None)
        (
            [
                {"family": "Lenard", "sequence": "first"},
                {"family": "A", "sequence": "additional"},
                {"family": "B", "sequence": "additional"},
            ],
            ["lenard"],
            None,
            True,
        ),
    ],
)
def test_validate_first_authors_logic(
    repo: WorkRepository,
    crossref_authors: list[CrossrefAuthor],
    input_first_authors: list,
    input_first_authors_count: int,
    expected_result: bool,
) -> None:
    """Directly test author validation logic across naming and count scenarios."""
    assert (
        repo._validate_first_authors(
            crossref_authors, input_first_authors, input_first_authors_count
        )
        == expected_result
    )
