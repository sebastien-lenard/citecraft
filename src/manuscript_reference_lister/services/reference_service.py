import logging
import time

from manuscript_reference_lister.parsers import HtmlCleaner
from manuscript_reference_lister.repositories import DoiRepository
from manuscript_reference_lister.schemas import WorkMetadata
from manuscript_reference_lister.utils import (
    AppConfig,
    get_config,
)

logger = logging.getLogger(__name__)


class ReferenceService:
    """Coordinates metadata enrichment."""

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
        self, records: list[WorkMetadata], doi_repo: DoiRepository, target_style: str
    ) -> None:
        """
        Enriches WorkMetadata records with formatted references.
        Updates in-place if style is mismatched or reference is missing.

        Note: If doi_repo.get_reference raises an exception, the execution
        will stop to ensure the error is handled and analyzed.
        """
        html_cleaner = HtmlCleaner(config=self.config)
        records_to_process = [
            r
            for r in records
            if r.DOI and (r.reference is None or r.style != target_style)
        ]
        logger.info(
            "Starting retrieving %s references from DOI negotiation service...",
            len(records_to_process),
            extra={
                "status": "OK",
                "event": "doi_reference_query_start",
                "records_to_process_count": len(records_to_process),
            },
        )
        processed_record_count = 0
        last_display_time = time.time()

        for record in records_to_process:
            # No try/except: let HTTPError or ConnectionError bubble up
            raw_reference = doi_repo.get_reference(record.DOI, style=target_style)

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
