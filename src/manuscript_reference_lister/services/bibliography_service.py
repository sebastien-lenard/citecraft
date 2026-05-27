import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from manuscript_reference_lister.schemas import CitationMetadata, WorkMetadata
from manuscript_reference_lister.utils import (
    AppConfig,
    get_config,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportResult:
    """Data carrier representing metric aggregations and structural outputs of bibliography exports."""

    total_rows: int
    output_filepath: Path
    export_format: str = "CSV"

    # Metrics
    ok_count: int = 0
    missing_count: int = 0
    duplicate_count: int = 0

    # Row examples
    sample_ok: dict[str, Any] | None = None
    sample_missing: dict[str, Any] | None = None
    samples_duplicate: list[dict[str, Any]] = field(default_factory=list)


class BibliographyService:
    """Coordinates clean reference resolution and automated file export of bibliographies."""

    def __init__(
        self,
        config: AppConfig | None = None,
    ) -> None:
        self.config: AppConfig = config or get_config()

    def export_to_csv(
        self,
        citations: list[CitationMetadata],
        works: list[WorkMetadata],
        output_path: Path,
    ) -> ExportResult:
        """Construct, validate, sort, and serialize a manuscript bibliography to a
        CSV file."""
        works_by_citation: dict[tuple[str, str], list[WorkMetadata]] = {}
        for work in works:
            if work.status == "OK":
                key = (work.input_first_authors_txt, work.input_year_and_suffix)
                works_by_citation.setdefault(key, []).append(work)

        unique_citations = {
            (c.first_authors_txt, c.year_and_suffix): c for c in citations
        }.values()

        rows: list[dict[str, Any]] = []

        preserved_tags_regex = None
        if self.config.preserved_html_tags:
            tags_pattern = "|".join(
                re.escape(tag) for tag in self.config.preserved_html_tags
            )
            preserved_tags_regex = re.compile(rf"<(/)?({tags_pattern})(?:>|\s[^>]*>)")

        for cite in unique_citations:
            citation_str = f"{cite.first_authors_txt}, {cite.year_and_suffix}"
            key = (cite.first_authors_txt, cite.year_and_suffix)
            matched_works = works_by_citation.get(key, [])

            if not matched_works:
                logger.warning(
                    "No metadata or DOI found for citation: %s",
                    citation_str,
                    extra={
                        "status": "KO",
                        "event": "bibliography_missing_reference",
                        "citation": citation_str,
                    },
                )
                rows.append(
                    {
                        "Citation": citation_str,
                        "Status": "Warning: No doi or reference found for the citation",
                        "Reference": None,
                    }
                )
                continue

            if len(matched_works) > 1:
                logger.info(
                    "Several references found for citation: %s",
                    citation_str,
                    extra={
                        "status": "KO",
                        "event": "bibliography_multiple_references",
                        "citation": citation_str,
                    },
                )
                status = "Warning: select the right reference"
            else:
                status = "OK"

            for work in matched_works:
                cleaned_ref = work.reference
                if cleaned_ref and preserved_tags_regex:
                    cleaned_ref = preserved_tags_regex.sub("", cleaned_ref)

                rows.append(
                    {
                        "Citation": citation_str,
                        "Status": status,
                        "Reference": cleaned_ref,
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.info(
            "Generated and saved bibliography with %d rows to %s",
            len(rows),
            str(output_path),
            extra={
                "status": "OK",
                "event": "bibliography_export_success",
                "output_filepath": str(output_path),
                "total_rows": len(rows),
            },
        )

        # ---- Statistics and samples for return ----
        status_missing = "Warning: No doi or reference found for the citation"
        status_duplicate = "Warning: select the right reference"

        ok_count = sum(1 for r in rows if r["Status"] == "OK")
        missing_count = sum(1 for r in rows if r["Status"] == status_missing)
        # Note : Number of rows (not of unique citations)
        duplicate_count = sum(1 for r in rows if r["Status"] == status_duplicate)

        sample_ok = next((r for r in rows if r["Status"] == "OK"), None)
        sample_missing = next((r for r in rows if r["Status"] == status_missing), None)

        samples_duplicate = [r for r in rows if r["Status"] == status_duplicate][:2]

        return ExportResult(
            total_rows=len(rows),
            output_filepath=output_path,
            export_format="CSV",
            ok_count=ok_count,
            missing_count=missing_count,
            duplicate_count=duplicate_count,
            sample_ok=sample_ok,
            sample_missing=sample_missing,
            samples_duplicate=samples_duplicate,
        )
