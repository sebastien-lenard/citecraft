import logging
import time

from unidecode import unidecode

from manuscript_reference_lister.schemas import (
    CitationMetadata,
    CrossrefAuthor,
    WorkMetadata,
)
from manuscript_reference_lister.utils import AppConfig

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class WorkRepository(BaseRepository[WorkMetadata]):
    """Manages local storage and Crossref resolution for published academic works."""

    def __init__(
        self, local_filename: str = "work_records.json", config: AppConfig | None = None
    ) -> None:
        super().__init__(local_filename, model_class=WorkMetadata, config=config)

    def get_work_metadata(
        self,
        input_citation_metadata: CitationMetadata,
        input_ISSN: str,
        keywords: str = "",
        get_limit: int | None = None,
    ) -> list[WorkMetadata]:
        """Query Crossref API to retrieve and validate metadata for a given citation.
        Get work metadata, including dois, from unstructured info combining the
        first_authors of input_citation_metadata and keywords, with results filtered on
        the year of input_citation_metadata and input_ISSN. Number of results is capped
        by get_limit. Works without authors are excluded.
        Warning: This method uses the crossref api, mostly based on article metadata
        and giving irrelevant dois if words of the work title are not in keywords. The
        filter by a valid input_ISSN (a issn of a journal) is essential to circumvent
        that effect.
        """
        if not input_ISSN:
            raise ValueError(
                "input_ISSN is an obligatory argument (valid issn of a journal)"
            )
        input_first_authors_txt = input_citation_metadata.first_authors_txt
        input_year_and_suffix = input_citation_metadata.year_and_suffix
        year_int = int("".join(filter(str.isdigit, input_year_and_suffix)))
        if year_int < 1600 or year_int > 2099:
            raise ValueError(f"year {year_int} must be in the 1600-2099 range")
        get_limit = (
            int(get_limit) if get_limit else self.config.crossref_api_works_get_limit
        )

        # Number of authors (1, 2, or > 2)
        is_et_al = " et al." in input_first_authors_txt
        raw_authors = (
            input_first_authors_txt.split(" et al.")[0]
            .replace(" et ", " and ")
            .split(" and ")
        )
        expected_count = len(raw_authors) if not is_et_al else None

        params = {
            "query": f"{input_first_authors_txt} {keywords}",
            "rows": get_limit,
            "filter": f"from-pub-date:{year_int},until-pub-date:{year_int},"
            f"issn:{input_ISSN}",
        }
        response = self.http_client_wrapper.get(
            str(self.config.crossref_api_works_url), headers=self.headers, params=params
        )
        response.raise_for_status()
        data = response.json()

        items = data["message"].get("items", [])
        candidates = []

        for item in items:
            if "author" not in item:
                continue

            if not self._validate_first_authors(
                item["author"], raw_authors, expected_count, is_et_al=is_et_al
            ):
                continue
            doi = item.get("DOI")
            if doi:
                candidates.append(
                    WorkMetadata(
                        input_first_authors_txt=input_first_authors_txt,
                        input_year_and_suffix=input_year_and_suffix,
                        input_ISSN=input_ISSN,
                        DOI=self.config.doi_api_url.replace("{doi}", str(doi)),
                        type=item.get("type"),
                    )
                )
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

    def _validate_first_authors(
        self,
        crossref_authors: list[CrossrefAuthor],
        input_first_authors: list[str],
        input_first_authors_count: int | None = None,
        *,
        is_et_al: bool = False,
    ) -> bool:
        """Validate if the parsed Crossref author metadata matches input criteria.
        Validates if the first crossref_authors match the input_first_authors, and if
        number of authors match too if 1 or 2 authors only. Filters out single-author
        works if citation is 'et al.', and prevents matching an expected family name
        against a Crossref given name when family name metadata is available.
        Warning: strict comparison, case insensitive. If name slightly differs (e.g.
        VanDijk vs Van Dijk, comparison returns False)
        """
        # 1. Strict count validation if not an "et al." citation
        if input_first_authors_count is not None:
            if len(crossref_authors) != input_first_authors_count:
                return False
        elif is_et_al and len(crossref_authors) <= 2:
            # A citation "X et al." implies at least 3 authors
            return False

        norm_expected = [self._normalize_string(a) for a in input_first_authors]

        # 2. Validate the primary (first) author.
        # Fallback to the first element in the list if 'sequence' key is missing.
        first_author_obj = next(
            (a for a in crossref_authors if a.get("sequence") == "first"),
            crossref_authors[0],
        )
        has_family = "family" in first_author_obj
        norm_first_family = self._normalize_string(
            first_author_obj.get("family", first_author_obj.get("name", ""))
        )

        if norm_expected[0] != norm_first_family:
            if has_family:
                return False
            # Fallback check on given name
            norm_first_given = self._normalize_string(first_author_obj.get("given", ""))
            if norm_expected[0] != norm_first_given:
                return False

        # 3. Validate second author if exactly two are expected
        if input_first_authors_count == 2:
            # The second author is the one that is NOT the first_author_obj
            second_author_obj = next(
                a for a in crossref_authors if a != first_author_obj
            )
            norm_second_family = self._normalize_string(
                second_author_obj.get("family", second_author_obj.get("name", ""))
            )
            if norm_expected[1] != norm_second_family:
                return False

        return True

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

    def update_all(self, ISSNs: list[str]) -> None:
        """Query Crossref API to find and commit DOIs for unpopulated works.
        ISSNs filter Crossref API results. Previously queried ISSNs are ignored.
        """
        # 1. Identify templates needing info
        templates_to_process = [r for r in self.records if not r.DOI]

        new_rich_records = []
        processed_templates = []
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
                    "Retrieving citation (%s, %s) metadata from Crossref on %d new"
                    " ISSNs..."
                ),
                citation_info.first_authors_txt,
                citation_info.year_and_suffix,
                len(filtered_ISSNs),
                extra={
                    "status": "OK",
                    "event": "crossref_journal_query_start",
                    "first_authors_txt": citation_info.first_authors_txt,
                    "year_and_suffix": citation_info.year_and_suffix,
                    "filtered_issns_count": len(filtered_ISSNs),
                },
            )

            found_for_this_record = False
            updated_lookups = list(already_looked_up)

            for issn in filtered_ISSNs:
                if issn not in updated_lookups:
                    updated_lookups.append(issn)

                results = self.get_work_metadata(
                    input_citation_metadata=citation_info, input_ISSN=issn
                )

                if results:
                    for r in results:
                        r.looked_up_ISSNs = updated_lookups
                    new_rich_records.extend(results)
                    found_for_this_record = True

            record.looked_up_ISSNs = updated_lookups

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
