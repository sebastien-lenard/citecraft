from unittest.mock import MagicMock

import pytest

from manuscript_reference_lister.schemas import WorkMetadata
from manuscript_reference_lister.services.reference_service import ReferenceService
from manuscript_reference_lister.utils import AppConfig, get_config


@pytest.fixture
def sample_csl_style() -> str:
    """Provides a minimal valid CSL XML layout for testing citeproc."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">\n'
        "  <info><title>Mock Style</title><id>mock-id</id></info>\n"
        '  <macro name="author"><names variable="author"><name/></names></macro>\n'
        '  <citation><layout><text variable="title"/></layout></citation>\n'
        "  <bibliography><layout>\n"
        '    <text macro="author" suffix=" "/>\n'
        '    <date variable="issued" prefix="(" suffix="). "><date-part name="year"/></date>\n'
        '    <text variable="title" suffix="."/>\n'
        "  </layout></bibliography>\n"
        "</style>"
    )


@pytest.fixture
def mock_doi_repo() -> MagicMock:
    """Mock DoiRepository to return standard valid CSL-JSON metadata."""
    repo = MagicMock()
    repo.get_metadata.return_value = {
        "DOI": "10.1038/s41561-020-0585-2",
        "id": "10.1038/s41561-020-0585-2",
        "author": [
            {"family": "Lenard", "given": "Sebastien J. P.", "sequence": "first"},
            {"family": "Lavé", "given": "Jérôme", "sequence": "additional"},
            {"family": "France-Lanord", "given": "Christian", "sequence": "additional"},
        ],
        "container-title": "Nature Geoscience",
        "container-title-short": "Nat. Geosci.",
        "issue": "6",
        "language": "en",
        "page": "448-452",
        "issued": {"date-parts": [[2020, 6]]},
        "published": {"date-parts": [[2020, 6]]},
        "publisher": "Springer Science and Business Media LLC",
        "title": (
            "Steady erosion rates in the Himalayas through late Cenozoic climatic"
        ),
        "type": "journal-article",
        "volume": "13",
    }

    return repo


@pytest.fixture
def test_config() -> AppConfig:
    """Provides a safe copy of the application configuration for isolation."""
    return get_config().model_copy()


def test_fill_missing_references_success(
    mock_doi_repo: MagicMock, test_config: AppConfig, sample_csl_style: str
) -> None:
    """Verify that records are updated correctly on success."""
    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2023",
            DOI="10.1000/182",
            reference=None,
        ),
        WorkMetadata(
            input_first_authors_txt="B",
            input_year_and_suffix="2021",
            DOI="10.1000/183",
            reference="Old",
            style="bibtex",
        ),
        WorkMetadata(
            input_first_authors_txt="C",
            input_year_and_suffix="2021",
            DOI=None,
            reference=None,
            style=None,
        ),
    ]

    reference_service = ReferenceService(config=test_config)
    reference_service.fill_missing_references(
        records, mock_doi_repo, csl_style_content=sample_csl_style, target_style="apa"
    )

    expected_reference = (
        "Sebastien J. P. Lenard, Jérôme Lavé, Christian France-Lanord (2020)."
        " Steady erosion rates in the Himalayas through late Cenozoic climatic."
    )

    assert records[0].reference == expected_reference
    assert records[1].style == "apa"
    assert records[1].reference == expected_reference
    assert records[2].reference is None
    assert mock_doi_repo.get_metadata.call_count == 2


def test_fill_missing_references_raises_on_repository_error(
    mock_doi_repo: MagicMock, test_config: AppConfig, sample_csl_style: str
) -> None:
    """Verify that an exception in the repository metadata collection stops the
    service."""
    # Simulate an API failure (e.g., 500 Server Error)
    mock_doi_repo.get_metadata.side_effect = Exception("API Connection Failed")

    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2020",
            DOI="doi_a",
            reference=None,
        )
    ]
    reference_service = ReferenceService(config=test_config)

    # The service should NOT catch the exception; it should bubble up to core.py
    with pytest.raises(Exception) as excinfo:
        reference_service.fill_missing_references(
            records,
            mock_doi_repo,
            csl_style_content=sample_csl_style,
            target_style="apa",
        )

    assert "API Connection Failed" in str(excinfo.value)


def test_get_reference_success(test_config: AppConfig, sample_csl_style: str) -> None:
    """Verify formatted reference is returned correctly when CSL-JSON is valid."""
    reference_service = ReferenceService(config=test_config)

    csl_metadata = {
        "DOI": "10.1000/182",
        "id": "10.1000/182",
        "type": "article-journal",
        "title": "Title of the Paper",
        "author": [{"family": "Doe", "given": "J."}],
        "issued": {"date-parts": [[2023]]},
    }

    result = reference_service.get_reference(
        csl_metadata, sample_csl_style, doi="10.1000/182"
    )
    assert result == "J. Doe (2023). Title of the Paper."


def test_get_reference_missing_metadata(
    test_config: AppConfig, sample_csl_style: str
) -> None:
    """Verify fallback string is returned when metadata dictionary is empty."""
    reference_service = ReferenceService(config=test_config)

    result = reference_service.get_reference({}, sample_csl_style, doi="invalid/doi")
    assert result == "Reference unavailable in doi.org."


def test_get_reference_missing_id_field(
    test_config: AppConfig, sample_csl_style: str
) -> None:
    """Verify fallback string is returned when the required 'id' key is missing."""
    reference_service = ReferenceService(config=test_config)

    # Missing structural 'id' key
    csl_metadata = {
        "type": "article-journal",
        "title": "Title without id",
    }

    result = reference_service.get_reference(
        csl_metadata, sample_csl_style, doi="10.1000/missing-id"
    )
    assert result == "Reference unavailable in doi.org."


def test_get_reference_utf8_encoding(
    test_config: AppConfig, sample_csl_style: str
) -> None:
    """Verify that special characters (accented, dashes) are handled correctly."""
    reference_service = ReferenceService(config=test_config)
    # This string contains 'é' and an em-dash '—'
    utf8_title = "Steady erosion — Himalayas."
    csl_metadata = {
        "DOI": "10.1038/s41561-020-0585-2",
        "id": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "title": utf8_title,
        "author": [{"family": "Lavé", "given": "J."}],
        "issued": {"date-parts": [[2020]]},
    }

    result = reference_service.get_reference(
        csl_metadata, sample_csl_style, doi="10.1038/s41561-020-0585-2"
    )
    assert result == f"J. Lavé (2020). {utf8_title}."
