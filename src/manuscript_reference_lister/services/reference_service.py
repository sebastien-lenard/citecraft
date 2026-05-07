import logging

from manuscript_reference_lister.repositories import DoiRepository
from manuscript_reference_lister.schemas import WorkMetadata

logger = logging.getLogger(__name__)


class ReferenceService:
    """Coordinates metadata enrichment."""

    @staticmethod
    def fill_missing_references(
        records: list[WorkMetadata], doi_repo: DoiRepository, target_style: str
    ) -> None:
        """
        Enriches WorkMetadata records with formatted references.
        Updates in-place if style is mismatched or reference is missing.

        Note: If doi_repo.get_reference raises an exception, the execution
        will stop to ensure the error is handled and analyzed.
        """
        for record in records:
            if not record.DOI:
                continue

            needs_update = record.reference is None or record.style != target_style

            if needs_update:
                # No try/except: let HTTPError or ConnectionError bubble up
                formatted_ref = doi_repo.get_reference(record.DOI, style=target_style)

                record.reference = formatted_ref
                record.style = target_style
