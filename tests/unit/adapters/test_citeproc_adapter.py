# tests/unit/adapters/test_citeproc_adapter.py
"""Unit tests for the citeproc adapter layer."""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from citecraft.adapters import CiteprocAdapter

# Dynamically load a minimalist valid XML CSL style mock derived from nature.csl
FIXTURE_DIR = Path(__file__).parent / "fixtures"
MOCK_CSL_STYLE = (FIXTURE_DIR / "mock_csl.xml").read_text(encoding="utf-8")


def test_create_json_source_success_with_unsupported_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify instantiation redirects citeproc internal warnings onto local logs."""
    csl_dict = {
        "id": "10.1000/xyz123",
        "type": "article-journal",
        "title": "Test Title",
        "published": "2026-01-01",  # Triggers citeproc unsupported variable warning
    }

    with caplog.at_level(logging.DEBUG):
        source, err = CiteprocAdapter.create_json_source(csl_dict, doi="10.1000/xyz123")

    assert source is not None
    assert err is None

    # Check warning redirection to debug log channel
    debug_records = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert len(debug_records) == 1
    assert "citeproc_unsupported_fields_filtered" in getattr(
        debug_records[0],
        "event",
        "",
    )


@pytest.mark.parametrize(
    "broken_csl_payload",
    [
        {"id": "10.1000/xyz123"},  # Missing entirely the required 'type'
        {"type": "article-journal"},  # Missing entirely the required 'id'
    ],
)
# WARNING: we don't the fields set to None, citeproc-py has another behavior that is
# inconsistent
def test_create_json_source_malformed_payloads(
    broken_csl_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify structural type and ID anomalies handle standard citeproc failures."""
    with caplog.at_level(logging.WARNING):
        source, err = CiteprocAdapter.create_json_source(
            broken_csl_payload,
            doi="10.1000/xyz123",
        )

    assert source is None
    assert err is not None
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"


def test_parse_csl_style_success() -> None:
    """Verify successful parsing logic transformation onto native citeproc elements."""
    style, err = CiteprocAdapter.parse_csl_style(MOCK_CSL_STYLE, doi="10.1000/xyz123")
    assert style is not None
    assert err is None


def test_parse_csl_style_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Verify broken layout XML code captures errors."""
    malformed_xml = "<style><invalid-unclosed-tag>"

    with caplog.at_level(logging.WARNING):
        style, err = CiteprocAdapter.parse_csl_style(
            malformed_xml,
            doi="10.1000/xyz123",
        )

    assert style is None
    assert err is not None
    assert len(caplog.records) == 1


def test_full_rendering_pipeline_success(caplog: pytest.LogCaptureFixture) -> None:
    """Verify end-to-end processing sequence through the adapter layers."""
    doi_key = "10.1000/xyz123"
    csl_dict = {
        "id": doi_key,
        "type": "article-journal",
        "title": "Glacier Melting Dynamics",
    }
    expected_test = (
        "1.Glacier Melting Dynamics.."  # WARNING Dependent on MOCK_CSL_STYLE
    )

    source, _ = CiteprocAdapter.create_json_source(csl_dict, doi=doi_key)
    style, _ = CiteprocAdapter.parse_csl_style(MOCK_CSL_STYLE, doi=doi_key)

    assert source is not None
    assert style is not None

    with caplog.at_level(logging.DEBUG):
        rendered_text, err = CiteprocAdapter.render_bibliography(
            style,
            source,
            item_id=doi_key,
            doi=doi_key,
        )

    assert err is None
    assert rendered_text == expected_test

    # Confirm final resolution tracing assertion
    ok_records = [
        r
        for r in caplog.records
        if r.levelname == "DEBUG"
        and "doi_local_resolution_success" in getattr(r, "event", "")
    ]
    assert len(ok_records) == 1


def test_render_bibliography_corrupted_github_style_handles_attribute_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that an AttributeError triggers a warning and fallback."""
    doi_key = "10.1000/xyz123"
    csl_dict = {
        "id": doi_key,
        "type": "article-journal",
        "title": "Glacier Melting Dynamics",
    }

    source, _ = CiteprocAdapter.create_json_source(csl_dict, doi=doi_key)
    style, _ = CiteprocAdapter.parse_csl_style(MOCK_CSL_STYLE, doi=doi_key)

    assert source is not None
    assert style is not None

    with (
        patch(
            "citeproc.CitationStylesBibliography.bibliography",
            side_effect=AttributeError("'NoneType' object has no attribute 'render'"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        rendered_text, err = CiteprocAdapter.render_bibliography(
            style,
            source,
            item_id=doi_key,
            doi=doi_key,
        )

    assert rendered_text is None
    assert err is not None
    assert "hosted on GitHub appears to be corrupted" in err
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "WARNING"
    assert getattr(record, "event", "") == "citeproc_github_style_file_corrupted"
    assert getattr(record, "doi", "") == doi_key
