import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister.repositories import WorkRepository
from manuscript_reference_lister.schemas import (
    CitationMetadata,
    CrossrefAuthor,
    WorkMetadata,
)
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> WorkRepository:
    """Provide WorkRepository instance utilizing the isolated global test
    configuration."""
    return WorkRepository(config=test_config)


@pytest.mark.parametrize(
    "api_items, expected_length, expected_first_doi, expected_first_type",
    [
        # Case A: Empty item payloads return empty result sets
        ([], 0, None, None),
        # Case B: Multiple valid work records instantiated with correct metadata types
        (
            [
                {
                    "DOI": "10.1038/s41561-020-0585-2",
                    "type": "journal-article",
                    "author": [
                        {"family": "Lenard", "sequence": "first"},
                        {"family": "Smith", "sequence": "additional"},
                        {"family": "Doe", "sequence": "additional"},
                    ],
                },
                {
                    "DOI": "10.1/ref2",
                    "type": "proceedings-article",
                    "author": [
                        {"family": "Lenard", "sequence": "first"},
                        {"family": "Jones", "sequence": "additional"},
                        {"family": "Brown", "sequence": "additional"},
                    ],
                },
            ],
            2,
            "https://doi.org/10.1038/s41561-020-0585-2",
            "journal-article",
        ),
    ],
)
def test_get_work_metadata_parsing_scenarios(
    repo: WorkRepository,
    api_items: list[dict[str, Any]],
    expected_length: int,
    expected_first_doi: str | None,
    expected_first_type: str | None,
) -> None:
    """Verify get_work_metadata parses and maps raw API payloads to matching schema
    lists."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": api_items}}

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_resp):
        results = repo.get_work_metadata(
            CitationMetadata(first_authors_txt="Lenard et al.", year_and_suffix="2020"),
            input_ISSN="1752-0894",
        )

        assert len(results) == expected_length
        if expected_length > 0:
            assert results[0].DOI == expected_first_doi
            assert results[0].type == expected_first_type


def test_parameterized_keywords(repo: WorkRepository) -> None:
    """Verify that custom keywords are correctly injected into the API query."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"items": []}}
    custom_kws = "Shifts in landslide frequency–area distribution"

    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_resp
    ) as mock_get:
        repo.get_work_metadata(
            CitationMetadata(
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
                    "author": [
                        {"family": "Guns", "sequence": "first"},
                        {"family": "Alpha", "sequence": "additional"},
                        {"family": "Beta", "sequence": "additional"},
                    ],
                },
                {
                    "DOI": "10.1/wrong",
                    "author": [{"family": "Smith", "sequence": "first"}],
                },
                {
                    "DOI": "10.1/inverted",
                    "author": [
                        {"given": "Guns", "sequence": "first"},
                        {"family": "Gamma", "sequence": "additional"},
                        {"family": "Delta", "sequence": "additional"},
                    ],
                },
            ]
        }
    }

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_resp):
        results = repo.get_work_metadata(
            CitationMetadata(
                first_authors_txt="Guns et al.",
                year_and_suffix="2014",
            ),
            input_ISSN="2213-3054",
        )
        assert len(results) == 2
        assert results[0].DOI == "https://doi.org/10.1/match"
        assert results[1].DOI == "https://doi.org/10.1/inverted"


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
        # Testing "et al." with one Crossref author only
        (
            [{"family": "Lucas", "sequence": "first"}],
            ["Lucas"],
            None,
            False,
        ),
        # Testing inversion family/given name.
        (
            [{"given": "Lucas", "family": "Laursen", "sequence": "first"}],
            ["Lucas"],
            1,
            False,
        ),
        # Given name match accepted only if absent family in Crossref metadata
        ([{"given": "Lucas", "sequence": "first"}], ["Lucas"], 1, True),
    ],
)
def test_validate_first_authors_logic(
    repo: WorkRepository,
    crossref_authors: list[CrossrefAuthor],
    input_first_authors: list[str],
    input_first_authors_count: int | None,
    expected_result: bool,
) -> None:
    """Directly test author validation logic across naming and count scenarios."""
    is_et_al_flag = input_first_authors_count is None
    assert (
        repo._validate_first_authors(
            crossref_authors,
            input_first_authors,
            input_first_authors_count,
            is_et_al=is_et_al_flag,
        )
        == expected_result
    )


@pytest.mark.parametrize(
    (
        "initial_records, new_citations, expected_final_count, expected_first_doi, "
        "expected_first_issn"
    ),
    [
        # Scenario A: Identical incoming citation targets are deduplicated onto a single
        # template record
        (
            [],
            [
                CitationMetadata(
                    first_authors_txt="Lenard et al.", year_and_suffix="2020a"
                ),
                CitationMetadata(
                    first_authors_txt="Lenard et al.", year_and_suffix="2020a"
                ),
            ],
            1,
            None,
            None,
        ),
        # Scenario B: Avoid adding blank templates when matching rich records exist in
        # records
        (
            [
                WorkMetadata(
                    input_first_authors_txt="Lenard et al.",
                    input_year_and_suffix="2020a",
                    input_ISSN="1752-0894",
                    DOI="10.1038/s41561-020-0585-2",
                )
            ],
            [
                CitationMetadata(
                    first_authors_txt="Lenard et al.", year_and_suffix="2020a"
                )
            ],
            1,
            "10.1038/s41561-020-0585-2",
            "1752-0894",
        ),
        # Scenario C: Create fresh template record for entirely unvisited citations
        (
            [],
            [CitationMetadata(first_authors_txt="New Author", year_and_suffix="2024")],
            1,
            None,
            None,
        ),
    ],
)
def test_merge_new_works_scenarios(
    repo: WorkRepository,
    initial_records: list[WorkMetadata],
    new_citations: list[CitationMetadata],
    expected_final_count: int,
    expected_first_doi: str | None,
    expected_first_issn: str | None,
) -> None:
    """Verify deduplication, rich preservation, and insertion behaviors of
    merge_new_works."""
    repo.records = initial_records
    repo.merge_new_works(new_citations)

    assert len(repo) == expected_final_count
    if expected_final_count > 0:
        assert repo.records[0].DOI == expected_first_doi
        assert repo.records[0].input_ISSN == expected_first_issn


def test_update_all_replaces_template_with_rich_record(
    repo: WorkRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that a record without a DOI is updated when get_work_metadata returns a
    result."""
    caplog.set_level(logging.INFO)
    template = WorkMetadata(
        input_first_authors_txt="Lenard et al.", input_year_and_suffix="2020a"
    )
    existing_rich = WorkMetadata(
        input_first_authors_txt="Other Author",
        input_year_and_suffix="2021",
        DOI="https://doi.org",
    )
    repo.records = [template, existing_rich]

    mock_rich_result = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_ISSN="1752-0894",
        DOI="https://doi.org",
        type="journal-article",
    )

    with patch.object(
        repo, "get_work_metadata", return_value=[mock_rich_result]
    ) as mock_get:
        repo.update_all(ISSNs=["1752-0894"])

        assert "Work resolution completed. Updated: 1, Failed: 0" in caplog.text
        assert mock_get.call_count == 1
        assert len(repo.records) == 2

        titles = [r.input_first_authors_txt for r in repo.records]
        assert "Lenard et al." in titles
        assert "Other Author" in titles

        updated_record = next(
            r for r in repo.records if r.input_first_authors_txt == "Lenard et al."
        )
        assert updated_record.DOI == "https://doi.org"
        assert updated_record.input_ISSN == "1752-0894"


def test_update_all_skips_if_no_results_found(
    repo: WorkRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that if get_work_metadata returns nothing, the template remains
    untouched."""
    caplog.set_level(logging.INFO)
    template = WorkMetadata(
        input_first_authors_txt="Unknown", input_year_and_suffix="2024"
    )
    repo.records = [template]

    with patch.object(repo, "get_work_metadata", return_value=[]):
        repo.update_all(ISSNs=["0000-0000"])

        assert "No work found for Unknown, 2024." in caplog.text
        assert "Work resolution completed. Updated: 0, Failed: 1" in caplog.text
        assert len(repo.records) == 1
        assert repo.records[0].DOI is None
