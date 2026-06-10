# tests/unit/schemas/test_citation_metadata.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests verifying citation field initialization and deduplication keys."""

from citecraft.schemas.citation_metadata import CitationMetadata


def test_citation_metadata_instantiation() -> None:
    """Verify initialization defaults of CitationMetadata entities."""
    citation = CitationMetadata(
        first_authors_txt="Lenard et al.",
        year_and_suffix="2020a",
    )

    assert citation.first_authors_txt == "Lenard et al."
    assert citation.year_and_suffix == "2020a"
    assert citation.type == "narrative"


def test_citation_metadata_identity_key() -> None:
    """Verify signature generation matching author and publication details."""
    citation = CitationMetadata(
        first_authors_txt="Guns and Vanacker",
        year_and_suffix="2021",
        type="parenthetical",
    )

    expected_key = ("Guns and Vanacker", "2021")
    assert citation.identity_key == expected_key


def test_citation_metadata_deduplication_logic() -> None:
    """Ensure signature key generation is independent of citation layout style."""
    cit1 = CitationMetadata(
        first_authors_txt="Lenard et al.",
        year_and_suffix="2020",
        type="narrative",
    )
    cit2 = CitationMetadata(
        first_authors_txt="Lenard et al.",
        year_and_suffix="2020",
        type="parenthetical",
    )

    assert cit1.identity_key == cit2.identity_key
