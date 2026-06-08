# tests/unit/repositories/test_work_repository.py
"""Unit tests for WorkRepository data integration and citation validation workflows."""

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from citecraft.repositories import WorkRepository
from citecraft.schemas import (
    CitationMetadata,
    WorkMetadata,
)
from citecraft.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> WorkRepository:
    """Provide WorkRepository instance with test configuration."""
    test_config = test_config.model_copy(
        update={
            "min_publication_year": 1800,
            "max_publication_year": 2100,
        },
    )
    return WorkRepository(config=test_config)


def test_abstract_methods_raise_not_implemented(repo: WorkRepository) -> None:
    """Verify that all abstract hook methods raise NotImplementedError."""
    with pytest.raises(NotImplementedError):
        repo._call_work_api("Author", 2020, [])
    with pytest.raises(NotImplementedError):
        repo._get_authors_from_api_item({})
    with pytest.raises(NotImplementedError):
        repo._get_doi_from_api_item({})
    with pytest.raises(NotImplementedError):
        repo._get_issns_groups_for_api([])
    with pytest.raises(NotImplementedError):
        repo._get_type_from_api_item({})
    with pytest.raises(NotImplementedError):
        repo._set_metadata_attribute(MagicMock(), {})


def test_get_input_first_authors_empty_input(repo: WorkRepository) -> None:
    """Verify empty first authors string returns (None, False)."""
    assert repo._get_input_first_authors_and_et_al("") == (None, False)


def test_get_work_metadata_raises_on_missing_issns(repo: WorkRepository) -> None:
    """Verify get_work_metadata raises ValueError if input_issns is empty."""
    with pytest.raises(ValueError, match="input_issn is an obligatory argument"):
        repo.get_work_metadata(
            CitationMetadata(first_authors_txt="Lenard", year_and_suffix="2020"),
            input_issns=[],
        )


@pytest.mark.parametrize("year", ["1799", "2101"])
def test_get_work_metadata_raises_on_invalid_year_range(
    repo: WorkRepository,
    year: str,
) -> None:
    """Verify get_work_metadata raises ValueError if year is out of range."""
    with pytest.raises(ValueError, match="must be in the"):
        repo.get_work_metadata(
            CitationMetadata(first_authors_txt="Lenard", year_and_suffix=year),
            input_issns=["1752-0894"],
        )


def test_get_work_metadata_skips_invalid_candidates(repo: WorkRepository) -> None:
    """Verify candidates with empty authors or failed validations are skipped."""
    items = [
        # Candidate 1: No api authors
        {"DOI": "10.1000/1", "type": "journal-article"},
        # Candidate 2: Authors validation fail
        {
            "DOI": "10.1000/2",
            "type": "journal-article",
            "author": [{"family": "Smith"}],
        },
    ]

    repo._call_work_api = MagicMock(return_value=items)
    repo._get_authors_from_api_item = MagicMock(
        side_effect=lambda item: item.get("author"),
    )
    repo._get_doi_from_api_item = MagicMock(side_effect=lambda item: item.get("DOI"))
    repo._get_type_from_api_item = MagicMock(side_effect=lambda item: item.get("type"))
    repo._validate_first_authors_count = MagicMock(return_value=True)
    repo._validate_first_authors = MagicMock(return_value=False)

    results = repo.get_work_metadata(
        CitationMetadata(first_authors_txt="Lenard", year_and_suffix="2020"),
        input_issns=["1752-0894"],
    )
    assert len(results) == 0


@pytest.mark.parametrize(
    ("inputs", "apis"),
    [
        ([], [{"family": "Lenard"}]),
        (["Lenard"], []),
        ([], []),
    ],
)
def test_validate_first_authors_empty_boundaries(
    repo: WorkRepository,
    inputs: list[str],
    apis: list[dict],
) -> None:
    """Verify that _validate_first_authors returns False if either array is empty."""
    assert repo._validate_first_authors(inputs, apis) is False


def test_validate_first_authors_mismatched_api_authors_length(
    repo: WorkRepository,
) -> None:
    """Verify returns False if input count matches limit but api results lack."""
    repo._validate_author = MagicMock(return_value=True)

    input_first_authors = ["Guns", "Vanacker"]
    api_authors = [{"family": "Guns"}]  # Only 1 author in API results

    assert repo._validate_first_authors(input_first_authors, api_authors) is False


def test_clean_metadata(repo: WorkRepository) -> None:
    """Verify that _clean_metadata filters blacklisted fields."""
    raw_metadata = {
        "title": "A Great Study",
        "indexed": "2026-05-31",
        "unwanted_field": "remove_me",
        "authors": [
            {
                "family": "Lenard",
                "given": "S. J. P.",
                "unwanted_author_field": "strip_me",
            },
            "NotADict",
        ],
    }

    work_blacklist = ["indexed", "unwanted_field", "non_existent_field"]
    author_blacklist = ["unwanted_author_field", "non_existent_author_field"]

    cleaned = repo._clean_metadata(
        metadata=raw_metadata,
        work_blacklist_fields=work_blacklist,
        author_key="authors",
        author_blacklist_fields=author_blacklist,
    )

    assert "title" in cleaned
    assert "indexed" not in cleaned
    assert "unwanted_field" not in cleaned

    authors = cleaned["authors"]
    assert isinstance(authors, list)
    assert len(authors) == 2

    assert authors[0]["family"] == "Lenard"
    assert "unwanted_author_field" not in authors[0]

    assert authors[1] == "NotADict"


@pytest.mark.parametrize(
    ("input_str", "expected_str"),
    [
        ("Van Dijk", "van dijk"),
        ("Lénárd", "lenard"),
        ("François", "francois"),
        ("Łukasiewicz", "lukasiewicz"),
        ("Peña", "pena"),
        ("Erdős", "erdos"),
        ("  Spaces  ", "spaces"),
    ],
)
def test_normalize_string(
    repo: WorkRepository,
    input_str: str,
    expected_str: str,
) -> None:
    """Verify string transliteration and casing normalization."""
    assert repo._normalize_string(input_str) == expected_str


@pytest.mark.parametrize(
    ("api_items", "expected_length", "expected_first_doi", "expected_first_type"),
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
                    "DOI": "10.1029/98jb00510",
                    "type": "proceedings-article",
                    "author": [
                        {"family": "Lenard", "sequence": "first"},
                        {"family": "Jones", "sequence": "additional"},
                        {"family": "Brown", "sequence": "additional"},
                    ],
                },
            ],
            2,
            "10.1038/s41561-020-0585-2",
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
    """Verify get_work_metadata parses raw API payloads into WorkMetadata."""
    repo._call_work_api = MagicMock(return_value=api_items)
    repo._get_authors_from_api_item = MagicMock(
        side_effect=lambda item: item.get("author", []),
    )
    repo._get_doi_from_api_item = MagicMock(side_effect=lambda item: item.get("DOI"))
    repo._get_type_from_api_item = MagicMock(side_effect=lambda item: item.get("type"))
    repo._set_metadata_attribute = MagicMock(side_effect=lambda work, item: work)
    repo._validate_author = MagicMock(return_value=True)

    results = repo.get_work_metadata(
        CitationMetadata(first_authors_txt="Lenard et al.", year_and_suffix="2020"),
        input_issns=["1752-0894"],
    )

    assert len(results) == expected_length
    if expected_length > 0:
        assert expected_first_doi == results[0].doi
        assert results[0].type == expected_first_type


def test_get_work_metadata_verifies_internal_calls(repo: WorkRepository) -> None:
    """Verify that all required hook methods are called during metadata extraction."""
    repo._get_input_first_authors_and_et_al = MagicMock(
        return_value=(["Lenard"], False),
    )
    repo._call_work_api = MagicMock(
        return_value=[{"DOI": "10.1029/98jb00510", "type": "journal-article"}],
    )
    repo._get_authors_from_api_item = MagicMock(
        return_value=[{"family": "Lenard", "sequence": "first"}],
    )
    repo._validate_first_authors_count = MagicMock(return_value=True)
    repo._validate_first_authors = MagicMock(return_value=True)
    repo._get_doi_from_api_item = MagicMock(return_value="10.1029/98jb00510")
    repo._get_type_from_api_item = MagicMock(return_value="journal-article")
    repo._set_metadata_attribute = MagicMock(side_effect=lambda work, item: work)

    results = repo.get_work_metadata(
        CitationMetadata(first_authors_txt="Lenard", year_and_suffix="2020"),
        input_issns=["0361-0160"],
    )

    assert len(results) == 1
    repo._get_input_first_authors_and_et_al.assert_called_once_with("Lenard")
    repo._call_work_api.assert_called_once_with(
        "Lenard",
        2020,
        ["0361-0160"],
        "",
        get_limit=20,
    )
    repo._get_authors_from_api_item.assert_called_once()
    repo._validate_first_authors_count.assert_called_once()
    repo._validate_first_authors.assert_called_once()
    repo._get_doi_from_api_item.assert_called_once()
    repo._set_metadata_attribute.assert_called_once()


def test_author_validation_filtering(repo: WorkRepository) -> None:
    """Verify that candidates with non-matching first authors are filtered out."""
    items = [
        {
            "DOI": "10.1029/98jb00510",
            "author": [
                {"family": "Guns", "sequence": "first"},
                {"family": "Alpha", "sequence": "additional"},
                {"family": "Beta", "sequence": "additional"},
            ],
        },
        {
            "DOI": "10.5194/esurf-8-447-2020",
            "author": [{"family": "Smith", "sequence": "first"}],
        },
        {
            "DOI": "10.5194/gmd-13-3863-2020",
            "author": [
                {"family": "Guns", "sequence": "first"},
                {"family": "Gamma", "sequence": "additional"},
                {"family": "Delta", "sequence": "additional"},
            ],
        },
    ]

    repo._call_work_api = MagicMock(return_value=items)
    repo._get_authors_from_api_item = MagicMock(
        side_effect=lambda item: item.get("author", []),
    )
    repo._get_doi_from_api_item = MagicMock(side_effect=lambda item: item.get("DOI"))
    repo._get_type_from_api_item = MagicMock(side_effect=lambda item: item.get("type"))
    repo._set_metadata_attribute = MagicMock(side_effect=lambda work, item: work)
    repo._validate_author = MagicMock(
        side_effect=lambda inp, api: inp == api.get("family"),
    )

    results = repo.get_work_metadata(
        CitationMetadata(
            first_authors_txt="Guns et al.",
            year_and_suffix="2014",
        ),
        input_issns=["0361-0160"],
    )
    assert len(results) == 2
    assert results[0].doi == "10.1029/98jb00510"
    assert results[1].doi == "10.5194/gmd-13-3863-2020"


@pytest.mark.parametrize(
    ("api_authors", "input_first_authors", "expected_result"),
    [
        ([{"family": "Lenard"}], ["Lenard"], True),
        ([{"family": "Zappa"}], ["Hendrix"], False),
        (
            [
                {"family": "Guns", "sequence": "first"},
                {"family": "Vanacker", "sequence": "additional"},
            ],
            ["Guns", "Vanacker"],
            True,
        ),
        (
            [
                {"family": "Guns", "sequence": "first"},
                {"family": "Dupont", "sequence": "additional"},
            ],
            ["Guns", "Vanacker"],
            False,
        ),
    ],
)
def test_validate_first_authors_logic(
    repo: WorkRepository,
    api_authors: list[dict],
    input_first_authors: list[str],
    expected_result: bool,
) -> None:
    """Directly test _validate_first_authors logic by mocking _validate_author."""
    repo._validate_author = MagicMock(
        side_effect=lambda input_auth, api_auth: input_auth == api_auth.get("family"),
    )
    assert (
        repo._validate_first_authors(input_first_authors, api_authors)
        == expected_result
    )


def test_validate_author_raises_not_implemented(repo: WorkRepository) -> None:
    """Verify that the base class _validate_author raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        repo._validate_author("Lenard", {"family": "Lenard"})


@pytest.mark.parametrize(
    ("input_count", "input_is_et_al", "api_count", "expected_result"),
    [
        (1, False, 1, True),
        (1, False, 2, False),
        (2, False, 2, True),
        (2, False, 3, False),
        (1, True, 3, True),
        (1, True, 1, False),
    ],
)
def test_validate_first_authors_count(
    repo: WorkRepository,
    input_count: int,
    input_is_et_al: bool,
    api_count: int,
    expected_result: bool,
) -> None:
    """Directly test author count validation logic."""
    assert (
        repo._validate_first_authors_count(
            input_count,
            api_count,
            input_is_et_al=input_is_et_al,
        )
        == expected_result
    )


@pytest.mark.parametrize(
    (
        "initial_records",
        "new_citations",
        "expected_final_count",
        "expected_first_doi",
        "expected_first_issn",
    ),
    [
        # Scenario A: Identical incoming citation targets are deduplicated onto a single
        # template record
        (
            [],
            [
                CitationMetadata(
                    first_authors_txt="Lenard et al.",
                    year_and_suffix="2020a",
                ),
                CitationMetadata(
                    first_authors_txt="Lenard et al.",
                    year_and_suffix="2020a",
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
                    input_issns=["1752-0894"],
                    doi="10.1038/s41561-020-0585-2",
                ),
            ],
            [
                CitationMetadata(
                    first_authors_txt="Lenard et al.",
                    year_and_suffix="2020a",
                ),
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
    """Verify deduplication, rich preservation, and insertion of merge_new_works."""
    repo.records = initial_records
    repo.merge_new_works(new_citations)

    assert len(repo) == expected_final_count
    if expected_final_count > 0:
        assert expected_first_doi == repo.records[0].doi
        expected_issns = [expected_first_issn] if expected_first_issn else None
        assert repo.records[0].input_issns == expected_issns


def test_update_all_replaces_template_with_rich_record(
    repo: WorkRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that a record without a DOI is updated when get_work_metadata returns."""
    caplog.set_level(logging.INFO)
    repo._get_issns_groups_for_api = MagicMock(side_effect=lambda issns: [issns])

    template = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
    )
    existing_rich = WorkMetadata(
        input_first_authors_txt="Other Author",
        input_year_and_suffix="2021",
        doi="10.5194/esurf-8-447-2020",
    )
    repo.records = [template, existing_rich]

    mock_rich_result = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_issns=["1752-0894"],
        doi="10.5194/esurf-8-447-2020",
        type="journal-article",
    )

    with patch.object(
        repo,
        "get_work_metadata",
        return_value=[mock_rich_result],
    ) as mock_get:
        repo.update_all(issns=["1752-0894"])

        assert "Work resolution completed. Updated: 1, Failed: 0" in caplog.text
        assert mock_get.call_count == 1
        assert len(repo.records) == 2

        titles = [r.input_first_authors_txt for r in repo.records]
        assert "Lenard et al." in titles
        assert "Other Author" in titles

        updated_record = next(
            r for r in repo.records if r.input_first_authors_txt == "Lenard et al."
        )
        assert updated_record.doi == "10.5194/esurf-8-447-2020"
        assert updated_record.input_issns == ["1752-0894"]


def test_update_all_skips_if_no_results_found(
    repo: WorkRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that if get_work_metadata returns nothing, template is untouched."""
    caplog.set_level(logging.INFO)
    repo._get_issns_groups_for_api = MagicMock(side_effect=lambda issns: [issns])

    template = WorkMetadata(
        input_first_authors_txt="Unknown",
        input_year_and_suffix="2024",
    )
    repo.records = [template]

    with patch.object(repo, "get_work_metadata", return_value=[]):
        repo.update_all(issns=["0361-0160"])

        assert "No work found for Unknown, 2024." in caplog.text
        assert "Work resolution completed. Updated: 0, Failed: 1" in caplog.text
        assert len(repo.records) == 1
        assert repo.records[0].doi is None


def test_update_all_filters_already_queried_issns(
    repo: WorkRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that update_all queries only the new ISSNs."""
    caplog.set_level(logging.INFO)
    repo._get_issns_groups_for_api = MagicMock(side_effect=lambda issns: [issns])

    template = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        looked_up_issns=["0361-0160"],
    )
    repo.records = [template]

    # Mock the return for the new ISSN "2222-2222"
    mock_rich_result = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        input_issns=["2222-2222"],
        doi="10.1038/s41561-020-0585-2",
        type="journal-article",
    )

    with patch.object(
        repo,
        "get_work_metadata",
        return_value=[mock_rich_result],
    ) as mock_get:
        # Call update_all with both old and new ISSNs
        repo.update_all(issns=["0361-0160", "1752-0894"])

        # Check that get_work_metadata was called exactly once, with the new ISSN
        mock_get.assert_called_once_with(
            input_citation_metadata=CitationMetadata(
                first_authors_txt="Lenard et al.",
                year_and_suffix="2020a",
            ),
            input_issns=["1752-0894"],
        )

        repo._get_issns_groups_for_api.assert_called_once_with(["1752-0894"])
        assert "on 1 new ISSNs" in caplog.text

        # Verify that both ISSNs are now marked as looked up on the resolved record
        updated_record = repo.records[0]
        assert updated_record.looked_up_issns == ["0361-0160", "1752-0894"]


def test_update_all_skips_when_all_issns_previously_queried(
    repo: WorkRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify update_all skips lookup if all ISSNs were already searched."""
    caplog.set_level(logging.WARNING)

    template = WorkMetadata(
        input_first_authors_txt="Lenard et al.",
        input_year_and_suffix="2020a",
        looked_up_issns=["0010-051x", "1752-0894"],
    )
    repo.records = [template]

    with patch.object(repo, "get_work_metadata") as mock_get:
        repo.update_all(issns=["0010-051x", "1752-0894"])

        # API should not be called at all
        mock_get.assert_not_called()

        # Check for specific warning log
        warning_msg = (
            "All provided ISSNs already searched for citation (Lenard et "
            "al., 2020a). Skipping lookup."
        )
        assert any(warning_msg in record.message for record in caplog.records)


def test_update_all_updates_history_on_failure(
    repo: WorkRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify queried ISSNs are appended to history on failure."""
    caplog.set_level(logging.INFO)
    repo._get_issns_groups_for_api = MagicMock(side_effect=lambda issns: [issns])

    template = WorkMetadata(
        input_first_authors_txt="Unresolvable et al.",
        input_year_and_suffix="2023",
        looked_up_issns=["0010-051x"],
    )
    repo.records = [template]

    with patch.object(repo, "get_work_metadata", return_value=[]):
        repo.update_all(issns=["0010-051x", "2049-3630"])

        assert len(repo.records) == 1
        # The template record is retained and its lookup list now includes the new ISSN
        assert repo.records[0].looked_up_issns == ["0010-051x", "2049-3630"]
