# tests/integration/test_integ_style_api_health.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Integration tests to fetch the real CSL style file and validate it."""

import pytest

from citecraft.repositories import StyleRepository


@pytest.mark.integration
@pytest.mark.vcr
def test_style_api_health() -> None:
    """Verify real CSL file extraction from the repository and validate it."""
    # --- Validate fetch csl metadata + xml structural constraints for a style name ---
    repo = StyleRepository(favored_style="apa")

    repo.fetch_style_metadata()
    assert repo.csl_content is not None, (
        "Failed to download the remote CSL filecontent."
    )

    repo.validate_favored_style()
    assert repo.favored_style_is_valid is True, (
        f"The downloaded CSL for '{repo.favored_style}' did not meet structure"
        f"boundaries."
    )

    # --- Validate fetch parent style for a journal title ---
    repo = StyleRepository(favored_journal_title="Nature Geoscience")
    repo.fetch_style_metadata()
    assert repo.csl_content is not None, (
        "Failed to download the remote CSL filecontent."
    )
