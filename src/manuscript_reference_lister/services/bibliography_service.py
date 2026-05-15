import csv
import logging
from pathlib import Path
from typing import Any

from manuscript_reference_lister.schemas import CitationMetadata, WorkMetadata

logger = logging.getLogger(__name__)


class BibliographyService:
    """Handles bibliographies."""

    @staticmethod
    def export_to_csv(
        citations: list[CitationMetadata],
        works: list[WorkMetadata],
        output_path: Path,
    ) -> None:
        """Construct a bibliography by filtering works against citations, determining
        statuses, sorting, and saving to CSV."""
        works_by_citation: dict[tuple[str, str], list[WorkMetadata]] = {}
        for work in works:
            key = (work.input_first_authors_txt, work.input_year_and_suffix)
            works_by_citation.setdefault(key, []).append(work)

        unique_citations = {
            (c.first_authors_txt, c.year_and_suffix): c for c in citations
        }.values()

        rows: list[dict[str, Any]] = []

        for cite in unique_citations:
            citation_str = f"{cite.first_authors_txt}, {cite.year_and_suffix}"
            key = (cite.first_authors_txt, cite.year_and_suffix)
            matched_works = works_by_citation.get(key, [])

            if not matched_works:
                rows.append(
                    {
                        "Citation": citation_str,
                        "Status": "Error: No doi or reference found for the citation",
                        "Reference": None,
                    }
                )
                continue

            status = (
                "Warning: select the right reference"
                if len(matched_works) > 1
                else "OK"
            )

            for work in matched_works:
                rows.append(
                    {
                        "Citation": citation_str,
                        "Status": status,
                        "Reference": work.reference,
                    }
                )

        # Sort with fallback empty string to handle None references
        rows.sort(
            key=lambda r: (
                (r["Reference"] or "").lower(),
                r["Citation"].lower(),
            )
        )

        fieldnames = ["Citation", "Status", "Reference"]
        with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.info(
            f"Generated and saved bibliography with {len(rows)} rows in {output_path}."
        )
