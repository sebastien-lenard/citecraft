# tests/unit/repositories/test_openalex_work_repository.py
import logging
from unittest.mock import MagicMock, patch

import pytest

from citecraft.repositories import OpenAlexWorkRepository
from citecraft.schemas import WorkMetadata
from citecraft.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> OpenAlexWorkRepository:
    """Provide OpenAlexWorkRepository instance with test configuration."""
    test_config = test_config.model_copy(
        update={
            "openalex_api_works_url": "https://api.openalex.org/works",
            "openalex_api_works_get_limit": 100,
            "doi_api_url": "https://doi.org/{object_name}",
        },
    )
    return OpenAlexWorkRepository(config=test_config)


def test_call_work_api_success(repo: OpenAlexWorkRepository) -> None:
    """Verify that _call_work_api executes GET request with correct parameters."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"doi": "https://doi.org/10.1001"}]}

    with patch.object(
        repo.http_client_wrapper, "get", return_value=(mock_response, 100),
    ) as mock_get:
        items = repo._call_work_api(
            input_first_authors_txt="Lenard",
            year_int=2020,
            input_issns=["1752-0894"],
        )

        assert items == [{"doi": "https://doi.org/10.1001"}]
        mock_get.assert_called_once()
        called_args, called_kwargs = mock_get.call_args
        assert called_args[0] == "https://api.openalex.org/works"
        params = called_kwargs["params"]
        assert "primary_location.source.issn:1752-0894" in params["filter"]


def test_call_work_api_no_issns_fails(
    repo: OpenAlexWorkRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that empty ISSNs return empty list and log a warning."""
    caplog.set_level(logging.WARNING)
    items = repo._call_work_api(
        input_first_authors_txt="Lenard",
        year_int=2020,
        input_issns=[],
    )
    assert items == []
    assert any("needs at least one ISSN" in r.message for r in caplog.records)


def test_call_work_api_too_many_issns_fails(
    repo: OpenAlexWorkRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that providing more than 100 ISSNs logs a warning."""
    caplog.set_level(logging.WARNING)
    many_issns = [f"0000-{i:04d}" for i in range(101)]

    items = repo._call_work_api(
        input_first_authors_txt="Lenard",
        year_int=2020,
        input_issns=many_issns,
    )
    assert items == []
    assert any("maximum of 100 ISSNs" in r.message for r in caplog.records)


def test_get_authors_from_api_item(repo: OpenAlexWorkRepository) -> None:
    """Verify author extraction from raw OpenAlex items."""
    item_with_author = {"authorships": [{"raw_author_name": "Lenard"}]}
    assert repo._get_authors_from_api_item(item_with_author) == [
        {"raw_author_name": "Lenard"},
    ]

    item_without_author = {}
    assert repo._get_authors_from_api_item(item_without_author) is None


def test_get_doi_from_api_item(repo: OpenAlexWorkRepository) -> None:
    """Verify DOI prefix removal from raw OpenAlex items."""
    item_with_doi = {"doi": "https://doi.org/10.1001"}
    assert repo._get_doi_from_api_item(item_with_doi) == "10.1001"

    item_without_doi = {}
    assert repo._get_doi_from_api_item(item_without_doi) is None


def test_get_issns_groups_for_api(repo: OpenAlexWorkRepository) -> None:
    """Verify grouping logic with configured length filters."""
    repo.config = repo.config.model_copy(
        update={
            "openalex_api_url_max_character_length_for_issns_filter": 20,
        },
    )
    issns = ["1111-1111", "2222-2222", "3333-3333"]
    # 1111-1111 (9 chars)
    # |2222-2222 (10 chars penalty) -> 19 chars (valid < 20)
    # |3333-3333 would exceed 20 limit.
    groups = repo._get_issns_groups_for_api(issns)
    assert groups == [["1111-1111", "2222-2222"], ["3333-3333"]]


@pytest.mark.parametrize(
    "item, expected_type",
    [
        # Case 1: Primary location raw_type is present (Takes highest priority)
        (
            {
                "primary_location": {"raw_type": "journal-article"},
                "type": "book-chapter",
            },
            "journal-article",
        ),
        # Case 2: Fallback to top-level type when missing primary_location or raw_type
        (
            {"primary_location": {}, "type": "dataset"},
            "dataset",
        ),
        (
            {"type": "book"},
            "book",
        ),
        # Case 3: Complete fallback when neither target keys are present
        (
            {"primary_location": {"source": "crossref"}},
            None,
        ),
        (
            {},
            None,
        ),
    ],
)
def test_get_type_from_api_item(
    repo: OpenAlexWorkRepository, item: dict, expected_type: str | None,
) -> None:
    """Verify raw type extraction branches correctly from OpenAlex API payloads."""
    assert repo._get_type_from_api_item(item) == expected_type


def test_set_metadata_attribute(repo: OpenAlexWorkRepository) -> None:
    """Verify that OpenAlex metadata resets openalex_metadata attribute to None."""
    work_metadata = WorkMetadata(
        input_first_authors_txt="Lenard", input_year_and_suffix="2020",
    )
    work_metadata.openalex_metadata = {"some": "data"}

    updated = repo._set_metadata_attribute(work_metadata, {"any": "item"})
    assert updated.openalex_metadata is None


@pytest.mark.parametrize(
    "input_author, api_author, expected_result, is_ambiguous",
    [
        ("Lenard", {"raw_author_name": "S. J. P. Lenard"}, True, False),
        ("Lenard", {"raw_author_name": "Lenard-Smith"}, False, True),
        (
            "Lenard",
            {"author": {"display_name": "S. J. P. Lenard"}},
            True,
            False,
        ),
        ("Lenard", {"raw_author_name": "Smith"}, False, False),
        ("", {"raw_author_name": "Lenard"}, False, False),
    ],
)
def test_validate_author(
    repo: OpenAlexWorkRepository,
    caplog: pytest.LogCaptureFixture,
    input_author: str,
    api_author: dict,
    expected_result: bool,
    is_ambiguous: bool,
) -> None:
    """Verify validation and logging behavior of OpenAlex name checking."""
    caplog.set_level(logging.INFO)
    result = repo._validate_author(input_author, api_author)
    assert result == expected_result

    if is_ambiguous:
        assert any("ambiguous family name" in r.message for r in caplog.records)


@pytest.mark.parametrize(
    "authors_txt, expected_filter",
    [
        ("Lenard", 'raw_author_name.search:"Lenard"'),
        (
            "Guns and Vanacker",
            'raw_author_name.search:"Guns",raw_author_name.search:"Vanacker"',
        ),
        ("Lenard et al.", 'raw_author_name.search:"Lenard"'),
        ("", None),
    ],
)
def test_build_author_api_filter(
    repo: OpenAlexWorkRepository, authors_txt: str, expected_filter: str | None,
) -> None:
    """Verify that author filter string is correctly formatted."""
    assert repo._build_author_api_filter(authors_txt) == expected_filter


def test_call_work_api_calls_build_author_api_filter(
    repo: OpenAlexWorkRepository, caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that _call_work_api calls _build_author_api_filter and validates."""
    caplog.set_level(logging.WARNING)
    repo._build_author_api_filter = MagicMock(return_value=None)

    items = repo._call_work_api(
        input_first_authors_txt="Too Many Authors et al.",
        year_int=2020,
        input_issns=["1752-0894"],
    )

    assert items == []
    repo._build_author_api_filter.assert_called_once_with("Too Many Authors et al.")
    assert any("does not seem to have parsable" in r.message for r in caplog.records)
