from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister.schemas import WorkMetadata
from manuscript_reference_lister.services.reference_service import ReferenceService
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def sample_csl_style() -> str:
    """Provide a minimal valid CSL XML layout for testing citation rendering."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" '
        'version="1.0">\n'
        "  <info><title>Mock Style</title><id>mock-id</id></info>\n"
        '  <macro name="author"><names variable="author"><name/></names></macro>\n'
        '  <citation><layout><text variable="title"/></layout></citation>\n'
        "  <bibliography><layout>\n"
        '    <text macro="author" suffix=" "/>\n'
        '    <date variable="issued" prefix="(" suffix="). "><date-part '
        'name="year"/></date>\n'
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


def test_fill_missing_references_success(
    mock_doi_repo: MagicMock, test_config: AppConfig, sample_csl_style: str
) -> None:
    """Verify that records are updated correctly on successful reference formatting."""
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

    expected_reference = (
        "Sebastien J. P. Lenard, Jérôme Lavé, Christian France-Lanord (2020)."
        " Steady erosion rates in the Himalayas through late Cenozoic climatic."
    )

    with (
        patch(
            "manuscript_reference_lister.services.reference_service.CiteprocAdapter.create_json_source"
        ) as mock_src,
        patch(
            "manuscript_reference_lister.services.reference_service.CiteprocAdapter.parse_csl_style"
        ) as mock_style,
        patch(
            "manuscript_reference_lister.services.reference_service.CiteprocAdapter.render_bibliography"
        ) as mock_render,
    ):
        mock_src.return_value = (MagicMock(), None)
        mock_style.return_value = (MagicMock(), None)
        mock_render.return_value = (expected_reference, None)

        reference_service = ReferenceService(config=test_config)
        reference_service.fill_missing_references(
            records,
            mock_doi_repo,
            csl_style_content=sample_csl_style,
            target_style="apa",
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
    mock_doi_repo.get_metadata.side_effect = Exception("API Connection Failed")
    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2020",
            DOI="10.5194/esurf-8-447-2020",
            reference=None,
        )
    ]
    reference_service = ReferenceService(config=test_config)

    with pytest.raises(Exception) as excinfo:
        reference_service.fill_missing_references(
            records,
            mock_doi_repo,
            csl_style_content=sample_csl_style,
            target_style="apa",
        )

    assert "API Connection Failed" in str(excinfo.value)


@pytest.mark.parametrize(
    "csl_metadata, doi, expected_result, should_mock_success",
    [
        # Happy path: Complete, valid CSL-JSON metadata
        (
            {
                "DOI": "10.1000/182",
                "id": "10.1000/182",
                "type": "article-journal",
                "title": "Title of the Paper",
                "author": [{"family": "Doe", "given": "J."}],
                "issued": {"date-parts": [[2023]]},
            },
            "10.1000/182",
            "J. Doe (2023). Title of the Paper.",
            True,
        ),
        # Empty metadata dict
        (
            {},
            "invalid/doi",
            "Reference unavailable in doi.org.",
            False,
        ),
        # Missing structural 'id' key
        (
            {
                "type": "article-journal",
                "title": "Title without id",
            },
            "10.1000/missing-id",
            "Reference unavailable in doi.org.",
            False,
        ),
        # Special Unicode characters (accents, em-dashes)
        (
            {
                "DOI": "10.1038/s41561-020-0585-2",
                "id": "10.1038/s41561-020-0585-2",
                "type": "article-journal",
                "title": "Steady erosion — Himalayas.",
                "author": [{"family": "Lavé", "given": "J."}],
                "issued": {"date-parts": [[2020]]},
            },
            "10.1038/s41561-020-0585-2",
            "J. Lavé (2020). Steady erosion — Himalayas..",
            True,
        ),
    ],
)
def test_get_reference_scenarios(
    test_config: AppConfig,
    sample_csl_style: str,
    csl_metadata: dict[str, Any],
    doi: str,
    expected_result: str,
    should_mock_success: bool,
) -> None:
    """Verify formatted reference outputs under standard metadata states."""
    reference_service = ReferenceService(config=test_config)

    with (
        patch(
            "manuscript_reference_lister.services.reference_service.CiteprocAdapter.create_json_source"
        ) as mock_src,
        patch(
            "manuscript_reference_lister.services.reference_service.CiteprocAdapter.parse_csl_style"
        ) as mock_style,
        patch(
            "manuscript_reference_lister.services.reference_service.CiteprocAdapter.render_bibliography"
        ) as mock_render,
    ):
        if should_mock_success:
            mock_src.return_value = (MagicMock(), None)
            mock_style.return_value = (MagicMock(), None)
            mock_render.side_effect = lambda *args, **kwargs: (expected_result, None)
        else:
            # If Pydantic fails, the adapter methods shouldn't even be called
            mock_src.return_value = (None, "Should not be reached")

        result = reference_service.get_reference(
            csl_metadata, sample_csl_style, doi=doi
        )

        assert result == expected_result
