import io
import logging
import time

import citeproc
from citeproc import (
    Citation,
    CitationItem,
    CitationStylesBibliography,
    CitationStylesStyle,
)
from citeproc.source.json import CiteProcJSON
from pydantic import ValidationError

from manuscript_reference_lister.parsers import HtmlCleaner
from manuscript_reference_lister.repositories import DoiRepository
from manuscript_reference_lister.schemas import WorkMetadata
from manuscript_reference_lister.schemas.csl_reference import CSLReference
from manuscript_reference_lister.utils import (
    AppConfig,
    get_config,
)

logger = logging.getLogger(__name__)


class ReferenceService:
    """Coordinates metadata enrichment and bibliography rendering."""

    def __init__(
        self,
        config: AppConfig | None = None,
    ):
        self.config = config or get_config()

    @staticmethod
    def _log_heartbeat_if_needed(processed: int, total: int, last_time: float) -> float:
        """Helper to log heartbeat every 10 seconds."""
        current_time = time.time()
        if current_time - last_time > 10:
            remaining = total - processed
            logger.info(
                "Batch update status: %d updates remaining out of %d",
                remaining,
                total,
                extra={
                    "status": "OK",
                    "event": "reference_update_heartbeat",
                    "remaining_count": remaining,
                    "total_count": total,
                },
            )
            return current_time
        return last_time

    def fill_missing_references(
        self,
        records: list[WorkMetadata],
        doi_repo: DoiRepository,
        csl_style_content: str,
        target_style: str,
    ) -> None:
        """
        Enriches WorkMetadata records with formatted references.
        Updates in-place if style is mismatched or reference is missing.

        Note: If get_reference raises an exception, the execution
        will stop to ensure the error is handled and analyzed.
        """
        html_cleaner = HtmlCleaner(config=self.config)
        records_to_process = [
            r
            for r in records
            if r.DOI and (r.reference is None or r.style != target_style)
        ]
        logger.info(
            "Starting generating %s references...",
            len(records_to_process),
            extra={
                "status": "OK",
                "event": "reference_generation_start",
                "records_to_process_count": len(records_to_process),
            },
        )
        processed_record_count = 0
        last_display_time = time.time()

        for record in records_to_process:
            if not record.csl_metadata:
                record.csl_metadata = doi_repo.get_metadata(record.DOI)
            raw_reference = self.get_reference(
                record.csl_metadata, csl_style_content, record.DOI
            )

            cleaned_reference = html_cleaner.clean_to_plain_text(raw_reference)

            record.reference = cleaned_reference
            record.raw_reference = raw_reference
            record.style = target_style
            processed_record_count += 1
            last_display_time = ReferenceService._log_heartbeat_if_needed(
                processed_record_count,
                len(records_to_process),
                last_display_time,
            )

        logger.info(
            "Reference retrieval completed. Updated: %d",
            processed_record_count,
            extra={
                "event": "reference_update_completed",
                "updated_count": processed_record_count,
            },
        )

    def get_reference(
        self, csl_metadata: dict[str, any], csl_style_content: str, doi: str
    ) -> str:
        """Renders a single CSL-JSON metadata dictionary into a plain text bibliography
        reference.
        Warning: the metadata must contain an id attribute."""
        if not csl_metadata:
            logger.warning(
                "Missing CSL-JSON metadata for DOI: %s",
                doi,
                extra={
                    "status": "KO",
                    "event": "reference_generation_failed_missing_metadata",
                    "doi": doi,
                },
            )
            return "Reference unavailable in doi.org."

        try:
            validated_csl = CSLReference.model_validate(csl_metadata)
            clean_csl_dict = validated_csl.model_dump(by_alias=True, exclude_none=True)

        except ValidationError as e:
            logger.warning(
                "CSL-JSON metadata validation failed for DOI: %s. Details: %s",
                doi,
                e.errors(
                    include_url=False
                ),  # Donne un résumé propre des champs en faute
                extra={
                    "status": "KO",
                    "event": "reference_generation_failed_invalid_structure",
                    "doi": doi,
                },
            )
            return "Reference unavailable in doi.org."
        bib_source = CiteProcJSON([clean_csl_dict])
        style_bytes = csl_style_content.encode("utf-8")
        style_file = io.BytesIO(style_bytes)

        # CitationStylesStyle handles the CSL file parsing. validate=False disables
        # strict XSD check.
        bib_style = CitationStylesStyle(style_file, validate=False)
        bibliography = CitationStylesBibliography(
            bib_style, bib_source, citeproc.formatter.plain
        )

        item_id = csl_metadata["id"]
        citation = Citation([CitationItem(item_id)])
        bibliography.register(citation)

        render_output = bibliography.bibliography()
        if render_output:
            reference_text = "".join(str(token) for token in render_output[0]).strip()
            logger.debug(
                "Successfully resolved bibliography reference generation for DOI: %s",
                doi,
                extra={
                    "status": "OK",
                    "event": "doi_local_resolution_success",
                    "doi": doi,
                },
            )
            return reference_text

        return "Reference unavailable in doi.org."
