# src/citecraft/schemas/crossref_author.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Type definitions representing author item payloads from the Crossref API."""

from typing import Any, TypedDict

CrossrefAuthor = TypedDict(
    "CrossrefAuthor",
    {
        "given": str,
        "family": str,
        "name": str,
        "sequence": str,
        "affiliation": list[dict[str, Any]],
        "ORCID": str,
        "authenticated-orcid": bool,
    },
    total=False,  # Keeps everything optional for unit tests clarity
)
