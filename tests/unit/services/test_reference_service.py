from unittest.mock import MagicMock

import pytest

from manuscript_reference_lister.schemas import WorkMetadata
from manuscript_reference_lister.services.reference_service import ReferenceService


@pytest.fixture
def mock_doi_repo():
    repo = MagicMock()
    repo.get_reference.return_value = "Formatted Author (2020). Title..."
    return repo


def test_fill_missing_references_success(mock_doi_repo):
    """Verify that records are updated correctly on success."""
    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2020",
            DOI="doi_a",
            reference=None,
        ),
        WorkMetadata(
            input_first_authors_txt="B",
            input_year_and_suffix="2021",
            DOI="doi_b",
            reference="Old",
            style="bibtex",
        ),
    ]

    ReferenceService.fill_missing_references(records, mock_doi_repo, target_style="apa")

    assert records[0].reference == "Formatted Author (2020). Title..."
    assert records[1].style == "apa"
    assert mock_doi_repo.get_reference.call_count == 2


def test_fill_missing_references_raises_on_api_error(mock_doi_repo):
    """Verify that an exception in the repository stops the service."""
    # Simulate an API failure (e.g., 500 Server Error)
    mock_doi_repo.get_reference.side_effect = Exception("API Connection Failed")

    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2020",
            DOI="doi_a",
            reference=None,
        )
    ]

    # The service should NOT catch the exception; it should bubble up to core.py
    with pytest.raises(Exception) as excinfo:
        ReferenceService.fill_missing_references(
            records, mock_doi_repo, target_style="apa"
        )

    assert "API Connection Failed" in str(excinfo.value)
