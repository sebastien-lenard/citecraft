# tests/integration/test_integ_crossref_work_api_health.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Integration tests on the real Crossref API to fetch work DOI and metadata."""

import _socket

import pytest

from citecraft.repositories import CrossrefWorkRepository
from citecraft.schemas import CitationMetadata
from citecraft.utils import AppConfig


@pytest.fixture(autouse=True)
def allow_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore native socket connect to bypass conftest network blocking."""
    monkeypatch.setattr("socket.socket.connect", _socket.socket.connect)


@pytest.mark.integration
@pytest.mark.vcr
def test_integ_crossref_works_api_health(test_config: AppConfig) -> None:
    """Check Crossref API Works health, limits, and dual-author parity logic."""
    repo = CrossrefWorkRepository(config=test_config)

    test_author = "Lenard et al."
    test_year = "2020"
    test_issns = ["1752-0894"]
    test_keywords = "erosion"
    requested_limit = 5

    candidates = repo.get_work_metadata(
        input_citation_metadata=CitationMetadata(
            first_authors_txt=test_author,
            year_and_suffix=test_year,
        ),
        input_issns=test_issns,
        keywords=test_keywords,
        get_limit=requested_limit,
    )

    assert len(candidates) > 0, (
        f"No candidates found for '{test_author}'. Author filter might be "
        "too strict or Crossref metadata structure has changed."
    )
    assert len(candidates) <= requested_limit, (
        f"max_results limit not respected: got {len(candidates)} records, "
        f"expected maximum of {requested_limit}."
    )
    first_candidate = candidates[0]
    assert first_candidate.doi is not None, "Fetched candidate is missing a DOI."
    assert first_candidate.doi.startswith("10.1038"), (
        f"DOI Formatting error: unexpected prefix in '{first_candidate.doi}'."
    )
    assert first_candidate.input_first_authors_txt == test_author, (
        f"Metadata persistence mismatch: original author '{test_author}' was "
        f"not preserved in candidate object."
    )

    test_author_2 = "Guns and Vanacker"
    test_year_2 = "2014"
    test_issn_2 = "2213-3054"

    candidates_2 = repo.get_work_metadata(
        input_citation_metadata=CitationMetadata(
            first_authors_txt=test_author_2,
            year_and_suffix=test_year_2,
        ),
        input_issns=[test_issn_2],
        keywords=test_keywords,
        get_limit=1,
    )

    assert len(candidates_2) > 0, (
        f"Strict dual-author match failed for '{test_author_2}'. "
        "Verify if Crossref metadata structure matches parser assumptions."
    )
