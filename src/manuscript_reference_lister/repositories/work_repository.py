import logging
import time

from unidecode import unidecode

from manuscript_reference_lister.schemas import (
    CitationMetadata,
    WorkMetadata,
)
from manuscript_reference_lister.utils import AppConfig

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class WorkRepository(BaseRepository[WorkMetadata]):
    """Manages local storage and API resolution for published academic works."""

    def __init__(
        self,
        local_filename: str = "work_records.json",
        config: AppConfig | None = None,
        api: str = "crossref",
    ) -> None:
        super().__init__(
            local_filename, model_class=WorkMetadata, config=config, api=api
        )

    def _call_work_api(
        self,
        input_first_authors_txt: str,
        year_int: int,
        input_ISSNs: list[str],
        keywords: str = "",
        get_limit: int | None = None,
    ) -> list[dict] | None:
        """Return the list of items fetched by the api call."""
        raise NotImplementedError("Subclasses must implement call_work_api")

    def _get_authors_from_api_item(self, item: dict) -> list[dict] | None:
        """Get authors of an item returned by the api"""
        raise NotImplementedError(
            "Subclasses must implement _get_authors_from_api_item"
        )

    def _get_doi_from_api_item(self, item: dict) -> str | None:
        """Get doi of an item returned by the api"""
        raise NotImplementedError("Subclasses must implement _get_doi_from_api_item")

    def _get_ISSNs_groups_for_api(self, ISSNs: list[str]) -> list[list[str]]:
        """Split ISSNs in groups that can be used as filters by API."""
        raise NotImplementedError("Subclasses must implement _get_ISSNs_groups_for_api")

    def _get_type_from_api_item(self, item: dict) -> str | None:
        """Get type of an item returned by the api"""
        raise NotImplementedError("Subclasses must implement _get_type_from_api_item")

    def _get_input_first_authors_and_et_al(
        self,
        input_first_authors_txt: str,
    ) -> tuple[list[str] | None, bool]:
        """Extract first authors and detects presence of et al."""
        if not input_first_authors_txt:
            return (None, False)
        return (
            (
                input_first_authors_txt.split(" et al.")[0]
                .replace(" et ", " and ")
                .split(" and ")
            ),
            " et al." in input_first_authors_txt,
        )

    def add_work_metadata(self, input_DOI: str) -> WorkMetadata:
        """Fetch work metadata and create a new record"""

    def get_work_metadata(
        self,
        input_citation_metadata: CitationMetadata,
        input_ISSNs: list[str],
        keywords: str = "",
        get_limit: int | None = None,
    ) -> list[WorkMetadata]:
        """Query API to retrieve and validate metadata for a given citation.
        Get work metadata, including dois, from unstructured info combining the
        first_authors of input_citation_metadata and keywords, with results filtered on
        the year of input_citation_metadata and input_ISSNs. Number of results is capped
        by get_limit. Works without authors are excluded.
        Warning: This method uses the crossref or openalex api, mostly based on article
        metadata and giving irrelevant dois if words of the work title are not in
        keywords. The filter by valid input_ISSNs (issns of one or several journals)
        is essential to circumvent that effect.
        """
        if not input_ISSNs:
            raise ValueError(
                "input_ISSN is an obligatory argument (valid issn of a journal)"
            )
        input_first_authors_txt = input_citation_metadata.first_authors_txt
        input_year_and_suffix = input_citation_metadata.year_and_suffix
        year_int = int("".join(filter(str.isdigit, input_year_and_suffix)))
        if (
            year_int < self.config.min_publication_year
            or year_int > self.config.max_publication_year
        ):
            raise ValueError(
                f"year {year_int} must be in the "
                f"{self.config.min_publication_year}-"
                f"{self.config.max_publication_year} range"
            )
        get_limit = (
            int(get_limit)
            if get_limit is not None
            else self.config.crossref_api_works_get_limit
        )

        input_first_authors, input_is_et_al = self._get_input_first_authors_and_et_al(
            input_first_authors_txt
        )

        items = self._call_work_api(
            input_first_authors_txt,
            year_int,
            input_ISSNs,
            keywords,
            get_limit=get_limit,
        )
        candidates = []

        if items:
            for item in items:
                api_authors = self._get_authors_from_api_item(item)
                if not api_authors:
                    continue

                if not self._validate_first_authors_count(
                    len(input_first_authors) if input_first_authors else 0,
                    input_is_et_al,
                    len(api_authors),
                ):
                    continue

                if not self._validate_first_authors(
                    input_first_authors or [], api_authors
                ):
                    continue

                doi = self._get_doi_from_api_item(item)

                if doi:
                    work_metadata = WorkMetadata(
                        input_first_authors_txt=input_first_authors_txt,
                        input_year_and_suffix=input_year_and_suffix,
                        input_ISSNs=input_ISSNs,
                        DOI=doi,
                        type=self._get_type_from_api_item(item),
                    )

                    work_metadata = self._set_metadata_attribute(work_metadata, item)
                    candidates.append(work_metadata)
        return candidates

    def _log_heartbeat_if_needed(
        self, processed: int, total: int, last_time: float
    ) -> float:
        """Log progress status every 10 seconds of processing time."""
        current_time = time.time()
        if current_time - last_time > 10.0:
            remaining = total - processed
            logger.info(
                "Batch update status: %d updates remaining out of %d",
                remaining,
                total,
                extra={
                    "status": "OK",
                    "event": "work_update_heartbeat",
                    "remaining_count": remaining,
                    "total_count": total,
                },
            )
            return current_time
        return last_time

    def _normalize_string(self, text: str) -> str:
        """Transliterate Unicode strings to lowercase closest ASCII representation.
        Example: 'Lénárd' becomes 'lenard', 'Łukasiewicz' becomes 'lukasiewicz'.
        Warning: ü becomes u and not ue (as sometimes found in bibliographies)
        """
        if not text:
            return ""
        return unidecode(text).lower().strip()

    def _clean_metadata(
        self,
        metadata: dict,
        work_blacklist_fields: dict[str],
        author_key: str | None = None,
        author_blacklist_fields: list[str] | None = None,
    ) -> dict:
        """Remove unnecessary information from metadata."""
        for field in work_blacklist_fields:
            metadata.pop(field, None)
        if (
            author_blacklist_fields
            and author_key
            and author_key in metadata
            and isinstance(metadata[author_key], list)
        ):
            for author_entry in metadata[author_key]:
                if isinstance(author_entry, dict):
                    for sub_field in author_blacklist_fields:
                        author_entry.pop(sub_field, None)
        return metadata

    def _validate_first_authors_count(
        self,
        input_first_authors_count: int,
        input_is_et_al: bool,
        api_authors_count: int,
    ) -> bool:
        """Validates if the number of first authors are same for api result."""
        # Strict count validation if not an "et al." citation
        if input_first_authors_count and not input_is_et_al:
            if api_authors_count != input_first_authors_count:
                return False
        elif input_is_et_al and api_authors_count <= 2:
            # A citation "X et al." implies at least 3 authors
            return False
        return True

    def _validate_author(self, input_author: str, api_author: dict) -> bool:
        """Verify that input author name matches the api author name."""
        raise NotImplementedError("Subclasses must implement _validate_author")

    def _validate_first_authors(
        self,
        input_first_authors: list[str],
        api_authors: list[dict],
    ) -> bool:
        """Validate if api first authors and input first authors are similar."""
        if not input_first_authors or not api_authors:
            return False

        validate_first_author = self._validate_author(
            input_first_authors[0], api_authors[0]
        )

        if len(input_first_authors) == 2:
            if len(api_authors) < 2:
                return False
            validate_first_author = validate_first_author & self._validate_author(
                input_first_authors[1], api_authors[1]
            )
        return validate_first_author

    def merge_new_works(self, citations: list[CitationMetadata]) -> None:
        """Merge fresh citations into local records as template placeholders.
        (placeholders without doi and input_issn).
        Avoids adding a template if a record with the same author/year already exists,
        using a custom identity key.
        """
        # Deduplicate citations if necessary
        unique_citations = {
            (c.first_authors_txt, c.year_and_suffix): c for c in citations
        }.values()

        # Map existing records by (author, year)
        existing_keys = {
            (r.input_first_authors_txt, r.input_year_and_suffix) for r in self.records
        }

        new_entries = [
            WorkMetadata(
                input_first_authors_txt=cite.first_authors_txt,
                input_year_and_suffix=cite.year_and_suffix,
            )
            for cite in unique_citations
            if (cite.first_authors_txt, cite.year_and_suffix) not in existing_keys
        ]

        self.records.extend(new_entries)
        logger.info(
            "Merged %d new work record placeholders.",
            len(new_entries),
            extra={
                "event": "works_merged",
                "new_placeholders_count": len(new_entries),
            },
        )

    def _set_metadata_attribute(
        self, work_metadata: WorkMetadata, item: dict
    ) -> WorkMetadata:
        """Update the metadata correct attribute and returns object."""
        raise NotImplementedError("Subclasses must implement set_metadata_attribute")

    def update_all(self, ISSNs: list[str]) -> None:
        """Query API to find and commit DOIs for unpopulated works.
        ISSNs filter API results. Previously queried ISSNs are ignored.
        """
        # 1. Identify templates needing info
        templates_to_process = [r for r in self.records if not r.DOI]

        new_rich_records: list[WorkMetadata] = []
        processed_templates: list[WorkMetadata] = []
        failed_count = 0
        last_display_time = time.time()

        for record in templates_to_process:
            # Construct the search object expected by get_work_metadata
            citation_info = CitationMetadata(
                first_authors_txt=record.input_first_authors_txt,
                year_and_suffix=record.input_year_and_suffix,
            )

            already_looked_up = record.looked_up_ISSNs or []
            filtered_ISSNs = [issn for issn in ISSNs if issn not in already_looked_up]

            if not filtered_ISSNs:
                logger.warning(
                    (
                        "All provided ISSNs already searched for citation (%s, %s). "
                        "Skipping lookup."
                    ),
                    citation_info.first_authors_txt,
                    citation_info.year_and_suffix,
                    extra={
                        "event": "skip_all_issns_already_searched",
                        "author": citation_info.first_authors_txt,
                        "year": citation_info.year_and_suffix,
                        "looked_up_ISSNs": already_looked_up,
                    },
                )
                continue

            logger.info(
                (
                    "Retrieving citation (%s, %s) metadata from work API on %d new"
                    " ISSNs..."
                ),
                citation_info.first_authors_txt,
                citation_info.year_and_suffix,
                len(filtered_ISSNs),
                extra={
                    "status": "OK",
                    "event": "api_work_query_start",
                    "first_authors_txt": citation_info.first_authors_txt,
                    "year_and_suffix": citation_info.year_and_suffix,
                    "filtered_issns_count": len(filtered_ISSNs),
                },
            )

            found_for_this_record = False
            updated_lookups = list(already_looked_up)

            groups_of_ISSNs = self._get_ISSNs_groups_for_api(filtered_ISSNs)
            for grp_ISSNs in groups_of_ISSNs:
                results = self.get_work_metadata(
                    input_citation_metadata=citation_info, input_ISSNs=grp_ISSNs
                )

                if results:
                    new_rich_records.extend(results)
                    found_for_this_record = True

            looked_up_ISSNs = sorted(set(already_looked_up + filtered_ISSNs))
            record.looked_up_ISSNs = looked_up_ISSNs
            for r in new_rich_records:
                r.looked_up_ISSNs = looked_up_ISSNs

            if found_for_this_record:
                processed_templates.append(record)
            else:
                failed_count += 1
                logger.warning(
                    "No work found for %s, %s.",
                    citation_info.first_authors_txt,
                    citation_info.year_and_suffix,
                    extra={
                        "event": "work_resolution_failed",
                        "author": citation_info.first_authors_txt,
                        "year": citation_info.year_and_suffix,
                        "looked_up_ISSNs": updated_lookups,
                    },
                )

            last_display_time = self._log_heartbeat_if_needed(
                len(processed_templates) + failed_count,
                len(templates_to_process),
                last_display_time,
            )

        # 2. Swap templates for rich records
        for template in processed_templates:
            self.records.remove(template)

        self.records.extend(new_rich_records)
        self.deduplicate()

        logger.info(
            "Work resolution completed. Updated: %d, Failed: %d",
            len(new_rich_records),
            failed_count,
            extra={
                "event": "works_update_completed",
                "updated_count": len(new_rich_records),
                "failed_count": failed_count,
            },
        )
