# tests/unit/services/test_reference_service.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for CSL parsing, metadata validation, and citation adapter error rules."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from citecraft.schemas import WorkMetadata
from citecraft.services.reference_service import ReferenceService
from citecraft.utils import AppConfig


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
        "doi": "10.1038/s41561-020-0585-2",
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
    mock_doi_repo: MagicMock,
    test_config: AppConfig,
    sample_csl_style: str,
) -> None:
    """Verify that records are updated correctly on successful reference formatting."""
    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2023",
            doi="10.1000/182",
            reference=None,
        ),
        WorkMetadata(
            input_first_authors_txt="B",
            input_year_and_suffix="2021",
            doi="10.1000/183",
            reference="Old",
            style="bibtex",
        ),
        WorkMetadata(
            input_first_authors_txt="C",
            input_year_and_suffix="2021",
            doi=None,
            reference=None,
            style=None,
        ),
        WorkMetadata(
            input_first_authors_txt="D",
            input_year_and_suffix="2022",
            doi="10.1000/184",
            reference="Pre-existing Clean Reference",
            style="apa",
        ),
    ]

    expected_reference = (
        "Sebastien J. P. Lenard, Jérôme Lavé, Christian France-Lanord (2020)."
        " Steady erosion rates in the Himalayas through late Cenozoic climatic."
    )

    with (
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.create_json_source",
        ) as mock_src,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.parse_csl_style",
        ) as mock_style,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.render_bibliography",
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
    assert records[3].reference == "Pre-existing Clean Reference"
    assert records[3].style == "apa"
    assert mock_doi_repo.get_metadata.call_count == 2


def test_fill_missing_references_skips_repo_query_if_metadata_present(
    mock_doi_repo: MagicMock,
    test_config: AppConfig,
    sample_csl_style: str,
) -> None:
    """Verify fill_missing_references skips repo query when metadata is cached."""
    pre_existing_metadata = {
        "doi": "10.1000/cached",
        "id": "10.1000/cached",
        "type": "article-journal",
        "title": "Cached Metadata Title",
        "author": [{"family": "Doe", "given": "J."}],
        "issued": {"date-parts": [[2023]]},
    }

    records = [
        WorkMetadata(
            input_first_authors_txt="Cached",
            input_year_and_suffix="2023",
            doi="10.1000/cached",
            reference=None,
            crossref_metadata=pre_existing_metadata,
        ),
    ]

    expected_reference = "J. Doe (2023). Cached Metadata Title."

    with (
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.create_json_source",
        ) as mock_src,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.parse_csl_style",
        ) as mock_style,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.render_bibliography",
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
    assert records[0].style == "apa"
    # Metadata should be resolved from cache; repo query must be bypassed completely
    mock_doi_repo.get_metadata.assert_not_called()


def test_fill_missing_references_raises_on_repository_error(
    mock_doi_repo: MagicMock,
    test_config: AppConfig,
    sample_csl_style: str,
) -> None:
    """Verify that an exception in  metadata collection stops the service."""
    mock_doi_repo.get_metadata.side_effect = Exception("API Connection Failed")
    records = [
        WorkMetadata(
            input_first_authors_txt="A",
            input_year_and_suffix="2020",
            doi="10.5194/esurf-8-447-2020",
            reference=None,
        ),
    ]
    reference_service = ReferenceService(config=test_config)

    with pytest.raises(Exception, match="API Connection Failed") as excinfo:
        reference_service.fill_missing_references(
            records,
            mock_doi_repo,
            csl_style_content=sample_csl_style,
            target_style="apa",
        )

    assert "API Connection Failed" in str(excinfo.value)


@pytest.mark.parametrize(
    ("csl_metadata", "doi", "expected_result", "should_mock_success"),
    [
        # Happy path: Complete, valid CSL-JSON metadata
        (
            {
                "doi": "10.1000/182",
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
                "doi": "10.1038/s41561-020-0585-2",
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
            "citecraft.services.reference_service.CiteprocAdapter.create_json_source",
        ) as mock_src,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.parse_csl_style",
        ) as mock_style,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.render_bibliography",
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
            csl_metadata,
            sample_csl_style,
            doi=doi,
        )

        assert result == expected_result


@pytest.mark.parametrize(
    ("source_ret", "style_ret", "render_ret", "expected_substr"),
    [
        (
            (None, "Source error"),
            (MagicMock(), None),
            ("Rendered", None),
            "Source error",
        ),
        (
            (MagicMock(), "Source msg"),
            (MagicMock(), None),
            ("Rendered", None),
            "Source msg",
        ),
        (
            (MagicMock(), None),
            (None, "Style error"),
            ("Rendered", None),
            "Style error",
        ),
        (
            (MagicMock(), None),
            (MagicMock(), "Style msg"),
            ("Rendered", None),
            "Style msg",
        ),
        (
            (MagicMock(), None),
            (MagicMock(), None),
            (None, "Render error"),
            "Render error",
        ),
        (
            (MagicMock(), None),
            (MagicMock(), None),
            (MagicMock(), "Render msg"),
            "Render msg",
        ),
    ],
)
def test_get_reference_adapter_failures(
    test_config: AppConfig,
    sample_csl_style: str,
    source_ret: tuple[Any, Any],
    style_ret: tuple[Any, Any],
    render_ret: tuple[Any, Any],
    expected_substr: str,
) -> None:
    """Verify that get_reference handles all inner adapter failures gracefully."""
    reference_service = ReferenceService(config=test_config)
    csl_metadata = {
        "doi": "10.1000/182",
        "id": "10.1000/182",
        "type": "article-journal",
        "title": "Title",
        "issued": {"date-parts": [[2023]]},
    }

    with (
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.create_json_source",
        ) as mock_src,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.parse_csl_style",
        ) as mock_style,
        patch(
            "citecraft.services.reference_service.CiteprocAdapter.render_bibliography",
        ) as mock_render,
    ):
        mock_src.return_value = source_ret
        mock_style.return_value = style_ret
        mock_render.return_value = render_ret

        result = reference_service.get_reference(
            csl_metadata,
            sample_csl_style,
            doi="10.1000/182",
        )

        assert expected_substr in result
