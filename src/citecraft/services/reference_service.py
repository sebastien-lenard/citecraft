# src/citecraft/services/reference_service.py
import logging
import time
from typing import Any

from pydantic import ValidationError

from citecraft.adapters import CiteprocAdapter
from citecraft.parsers import HtmlCleaner
from citecraft.repositories import DoiRepository
from citecraft.schemas import WorkMetadata
from citecraft.schemas.csl_reference import CSLReference
from citecraft.utils import (
    AppConfig,
    get_config,
)

logger = logging.getLogger(__name__)


class ReferenceService:
    """Coordinates Citeproc reference parsing and WorkMetadata schema enrichment."""

    def __init__(
        self,
        config: AppConfig | None = None,
    ) -> None:
        self.config: AppConfig = config or get_config()

    def _log_heartbeat_if_needed(
        self, processed: int, total: int, last_time: float,
    ) -> float:
        """Log batch resolution progress every 10 seconds of processing time."""
        current_time = time.time()
        if (
            current_time - last_time
            > self.config.default_logging_frequency_for_batch_updates
        ):
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
        """Enrich unpopulated WorkMetadata records with generated references in-place.
        Updates in-place if style is mismatched or reference is missing.

        Note: If get_reference raises an exception, the execution
        will stop to ensure the error is handled and analyzed.
        """
        html_cleaner = HtmlCleaner(config=self.config)
        total_targets = sum(
            1
            for r in records
            if r.doi and (r.reference is None or r.style != target_style)
        )
        logger.info(
            "Starting generating %s references...",
            total_targets,
            extra={
                "status": "OK",
                "event": "reference_generation_start",
                "records_to_process_count": total_targets,
            },
        )
        processed_record_count = 0
        last_display_time = time.time()

        for record in records:
            doi = record.doi
            if doi is None:
                continue

            # Skip already up-to-date entries
            if record.reference is not None and record.style == target_style:
                continue

            if not record.crossref_metadata:
                record.crossref_metadata = doi_repo.get_metadata(doi)

            raw_reference = self.get_reference(
                record.crossref_metadata, csl_style_content, doi,
            )

            cleaned_reference = html_cleaner.clean_to_plain_text(raw_reference)

            record.reference = cleaned_reference
            record.raw_reference = raw_reference
            record.style = target_style
            processed_record_count += 1
            last_display_time = self._log_heartbeat_if_needed(
                processed_record_count,
                total_targets,
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
        self, csl_metadata: dict[str, Any] | None, csl_style_content: str, doi: str,
    ) -> str:
        """Render a CSL-JSON dictionary into a formatted plain-text bibliography entry.
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
            validated_csl = CSLReference.model_validate(
                csl_metadata, context={"config": self.config},
            )
            clean_csl_dict = validated_csl.model_dump(by_alias=True, exclude_none=True)
        except ValidationError as e:
            logger.warning(
                "CSL-JSON metadata validation failed for DOI: %s. Details: %s",
                doi,
                str(e.errors(include_url=False)),
                extra={
                    "status": "KO",
                    "event": "reference_generation_failed_invalid_structure",
                    "doi": doi,
                },
            )
            return "Reference unavailable in doi.org."

        bib_source, err_msg = CiteprocAdapter.create_json_source(
            clean_csl_dict, doi=doi,
        )

        if not bib_source or err_msg:
            return f"Reference unavailable in doi.org. {err_msg}"

        bib_style, err_msg = CiteprocAdapter.parse_csl_style(csl_style_content, doi=doi)
        if not bib_style or err_msg:
            return f"Reference unavailable in doi.org. {err_msg}"

        render_output, err_msg = CiteprocAdapter.render_bibliography(
            bib_style, bib_source, item_id=validated_csl.id, doi=doi,
        )
        if not render_output or err_msg:
            return f"Reference unavailable in doi.org. {err_msg}"

        logger.debug(
            "Successfully resolved bibliography reference generation for DOI: %s",
            doi,
            extra={
                "status": "OK",
                "event": "doi_local_resolution_success",
                "doi": doi,
            },
        )
        return render_output
