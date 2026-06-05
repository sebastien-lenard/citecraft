# tests/unit/repositories/test_crossref_work_repository.py
# filepath: tests/test_crossref_work_repository.py
import logging
from unittest.mock import MagicMock, patch

import pytest

from citecraft.repositories import CrossrefWorkRepository
from citecraft.schemas import WorkMetadata
from citecraft.utils import AppConfig


@pytest.fixture
def repo(test_config: AppConfig) -> CrossrefWorkRepository:
    """Provide CrossrefWorkRepository instance with test configuration."""
    test_config = test_config.model_copy(
        update={
            "crossref_api_works_url": "https://api.crossref.org/works",
            "crossref_api_works_get_limit": 20,
            "doi_api_url": "https://doi.org/{object_name}",
        }
    )
    return CrossrefWorkRepository(config=test_config)


def test_call_work_api_success(repo: CrossrefWorkRepository) -> None:
    """Verify that _call_work_api executes GET request with correct parameters."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"items": [{"DOI": "10.1038/s41561-020-0585-2"}]}
    }

    with patch.object(
        repo.http_client_wrapper, "get", return_value=(mock_response, 100)
    ) as mock_get:
        items = repo._call_work_api(
            input_first_authors_txt="Lenard",
            year_int=2020,
            input_issns=["1752-0894"],
        )

        assert items == [{"DOI": "10.1038/s41561-020-0585-2"}]
        mock_get.assert_called_once()
        called_args, called_kwargs = mock_get.call_args
        assert called_args[0] == "https://api.crossref.org/works"
        assert "issn:1752-0894" in called_kwargs["params"]["filter"]
        assert "from-pub-date:2020" in called_kwargs["params"]["filter"]


def test_call_work_api_multiple_issns_fails(
    repo: CrossrefWorkRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that providing several ISSNs logs warning and returns empty list."""
    caplog.set_level(logging.WARNING)

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        items = repo._call_work_api(
            input_first_authors_txt="Lenard",
            year_int=2020,
            input_issns=["1111-1111", "2222-2222"],
        )

        assert items == []
        mock_get.assert_not_called()
        assert any(
            "only accepts one ISSN but several are provided" in r.message
            for r in caplog.records
        )


def test_get_authors_from_api_item(repo: CrossrefWorkRepository) -> None:
    """Verify author extraction from raw crossref items."""
    item_with_author = {"author": [{"family": "Lenard"}]}
    assert repo._get_authors_from_api_item(item_with_author) == [{"family": "Lenard"}]

    item_without_author = {}
    assert repo._get_authors_from_api_item(item_without_author) is None


def test_get_doi_from_api_item(repo: CrossrefWorkRepository) -> None:
    """Verify DOI extraction from raw crossref items."""
    item_with_doi = {"DOI": "10.1001"}
    assert repo._get_doi_from_api_item(item_with_doi) == "10.1001"

    item_without_doi = {}
    assert repo._get_doi_from_api_item(item_without_doi) is None


def test_get_issns_groups_for_api(repo: CrossrefWorkRepository) -> None:
    """Verify that ISSNs are split into singleton lists for Crossref queries."""
    assert repo._get_issns_groups_for_api(["1111-1111", "2222-2222"]) == [
        ["1111-1111"],
        ["2222-2222"],
    ]


def test_get_type_from_api_item(repo: CrossrefWorkRepository) -> None:
    """Verify type extraction from raw crossref items."""
    item_with_type = {"type": "journal-article"}
    assert repo._get_type_from_api_item(item_with_type) == "journal-article"

    item_without_type = {}
    assert repo._get_type_from_api_item(item_without_type) is None


def test_set_metadata_attribute(repo: CrossrefWorkRepository) -> None:
    """Verify that crossref item is attached to crossref_metadata attribute."""
    work_metadata = WorkMetadata(
        input_first_authors_txt="Lenard", input_year_and_suffix="2020"
    )
    raw_item = {"DOI": "10.1001", "author": []}
    updated = repo._set_metadata_attribute(work_metadata, raw_item)

    assert updated.crossref_metadata == raw_item


@pytest.mark.parametrize(
    "input_author, api_author, expected_result",
    [
        ("Lenard", {"family": "Lenard"}, True),
        ("Lenard", {"given": "Lenard"}, True),
        ("Lenard", {"name": "Lenard"}, True),
        ("Lenard", {"family": "Smith"}, False),
        ("Lenard", {"other": "Lenard"}, False),
        ("", {"family": "Lenard"}, False),
        ("Lucas", {"family": "Laursen", "given": "Lucas"}, False),
        ("Laursen", {"family": "Laursen", "given": "Lucas"}, True),
    ],
)
def test_validate_author(
    repo: CrossrefWorkRepository,
    input_author: str,
    api_author: dict,
    expected_result: bool,
) -> None:
    """Verify author name validation logic against raw crossref shapes."""
    assert repo._validate_author(input_author, api_author) == expected_result
