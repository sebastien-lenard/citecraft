# tests/unit/adapters/test_citeproc_adapter.py
import logging
from typing import Any
from unittest.mock import patch

import pytest

from citecraft.adapters import CiteprocAdapter

# Minimalist valid XML CSL style mock derived from nature.csl for testing execution flow
# ruff: disable[E501]
# Not possible to cut this xml string.
# TODO: this xml should be in a dedicated ancillary tracked  test file?
MOCK_CSL_STYLE = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="sort-only" default-locale="en-GB">
  <info>
    <title>Nature</title>
    <id>http://www.zotero.org/styles/nature</id>
    <category citation-format="numeric"/>
    <category field="science"/>
    <category field="generic-base"/>
  </info>
  <macro name="title">
    <choose>
      <if type="bill book graphic legal_case legislation motion_picture report song" match="any">
        <text variable="title" font-style="italic" text-case="title"/>
      </if>
      <else>
        <text variable="title"/>
      </else>
    </choose>
  </macro>
  <macro name="author">
    <names variable="author">
      <name sort-separator=", " delimiter=", " and="symbol" initialize-with=". " delimiter-precedes-last="never" name-as-sort-order="all"/>
      <label form="short" prefix=", "/>
      <et-al font-style="italic"/>
    </names>
  </macro>
  <macro name="access">
    <choose>
      <if variable="volume" type="article dataset software" match="any"/>
      <else-if variable="DOI">
        <text variable="DOI" prefix="doi:"/>
      </else-if>
    </choose>
  </macro>
  <macro name="access-data">
    <choose>
      <if type="dataset software" match="any">
        <text variable="DOI" prefix="https://doi.org/"/>
      </if>
    </choose>
  </macro>
  <macro name="issuance">
    <choose>
      <if type="article">
        <group delimiter=" ">
          <choose>
            <if variable="genre" match="any">
              <text variable="genre" text-case="capitalize-first"/>
            </if>
            <else>
              <text term="preprint" text-case="capitalize-first"/>
            </else>
          </choose>
          <text term="at"/>
          <choose>
            <if variable="DOI" match="any">
              <text variable="DOI" prefix="https://doi.org/"/>
            </if>
            <else>
              <text variable="URL"/>
            </else>
          </choose>
          <date date-parts="year" form="text" variable="issued" prefix="(" suffix=")"/>
        </group>
      </if>
      <else>
        <date variable="issued" prefix="(" suffix=")">
          <date-part name="year"/>
        </date>
      </else>
    </choose>
  </macro>
  <macro name="container-title">
    <choose>
      <if type="article-journal">
        <text variable="container-title" font-style="italic" form="short"/>
      </if>
      <else>
        <text variable="container-title" font-style="italic"/>
      </else>
    </choose>
  </macro>
  <macro name="editor">
    <choose>
      <if type="chapter paper-conference" match="any">
        <names variable="editor" prefix="(" suffix=")">
          <label form="short" suffix=" "/>
          <name and="symbol" delimiter-precedes-last="never" initialize-with=". " name-as-sort-order="all"/>
        </names>
      </if>
    </choose>
  </macro>
  <macro name="volume">
    <choose>
      <if type="article-journal" match="any">
        <text variable="volume" font-weight="bold" suffix=","/>
      </if>
      <else>
        <group delimiter=" ">
          <label variable="volume" form="short"/>
          <text variable="volume"/>
        </group>
      </else>
    </choose>
  </macro>
  <citation collapse="citation-number">
    <sort>
      <key variable="citation-number"/>
    </sort>
    <layout vertical-align="sup" delimiter=",">
      <text variable="citation-number"/>
    </layout>
  </citation>
  <bibliography et-al-min="6" et-al-use-first="1" second-field-align="flush" entry-spacing="0" line-spacing="2">
    <layout suffix=".">
      <text variable="citation-number" suffix="."/>
      <group delimiter=" ">
        <text macro="author" suffix="."/>
        <text macro="title" suffix="."/>
        <choose>
          <if type="chapter paper-conference" match="any">
            <text term="in"/>
          </if>
        </choose>
        <text macro="container-title"/>
        <text macro="editor"/>
        <text macro="volume"/>
        <text variable="page"/>
        <text macro="issuance"/>
        <text macro="access"/>
      </group>
    </layout>
  </bibliography>
</style>"""
# ruff: enable[E501]


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
    assert "citeproc_unsupported_fields_filtered" in debug_records[0].event  # type: ignore


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
    broken_csl_payload: dict[str, Any], caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify structural type and ID anomalies handle standard citeproc failures
    gracefully via parameter variants."""
    with caplog.at_level(logging.WARNING):
        source, err = CiteprocAdapter.create_json_source(
            broken_csl_payload, doi="10.1000/xyz123",
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
    """Verify broken layout XML code captures errors cleanly without collapsing
    execution."""
    malformed_xml = "<style><invalid-unclosed-tag>"

    with caplog.at_level(logging.WARNING):
        style, err = CiteprocAdapter.parse_csl_style(
            malformed_xml, doi="10.1000/xyz123",
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
            style, source, item_id=doi_key, doi=doi_key,
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
    """Verify that an AttributeError from a corrupted layout structure triggers a
    clean warning and fallback."""
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
            style, source, item_id=doi_key, doi=doi_key,
        )

    assert rendered_text is None
    assert err is not None
    assert "hosted on GitHub appears to be corrupted" in err
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "WARNING"
    assert record.event == "citeproc_github_style_file_corrupted"
    assert record.doi == doi_key
