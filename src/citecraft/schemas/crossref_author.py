# src/citecraft/schemas/crossref_author.py
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
