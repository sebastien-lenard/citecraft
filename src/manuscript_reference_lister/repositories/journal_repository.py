import logging
import time
from datetime import date, datetime, timedelta
from typing import Literal

from manuscript_reference_lister.schemas import JournalMetadata
from manuscript_reference_lister.utils import AppConfig

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class JournalRepository(BaseRepository[JournalMetadata]):
    """Handles journal metadata records."""

    def __init__(
        self,
        local_filename: str = "journal_records.json",
        config: AppConfig | None = None,
    ):
        super().__init__(local_filename, model_class=JournalMetadata, config=config)
        self.has_pending_updates = False

    def _log_heartbeat_if_needed(
        self, processed: int, total: int, last_time: float
    ) -> float:
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
                    "event": "journal_update_heartbeat",
                    "remaining_count": remaining,
                    "total_count": total,
                },
            )
            return current_time
        return last_time

    def _normalize_title(self, title: str) -> str:
        """Normalize title for fuzzy matching (case, plurals, and delimiters)."""
        if not title:
            return ""
        t = title.strip().lower()
        t = t.replace("-", " ").replace(":", " ").replace(",", " ")
        words = [w[:-1] if w.endswith("s") else w for w in t.split()]
        return " ".join(words)

    def get_journal_metadata(self, input_title: str) -> list[JournalMetadata]:
        """
        Get journal metadata filtered on the exact match or similar matches of the title
        (input_title). A title can correspond to several
        records or none, each of them identified by a unique ISSN.
        - Case exact match: Returns a list of JournalMetadata corresponding to
            the first exact title found (one by distinct ISSN).
        - Case no exact match but similar titles found: Resolves ISSNs for all similar
            titles, queries their publication ranges, and returns JournalMetadata
            records mapped to the original input_title and the similar_titles list.
        - Case no exact match: Returns a list of one incomplete JournalMetadata only.
        """
        logger.info(
            "Retrieving journal %s metadata from Crossref...",
            input_title,
            extra={
                "status": "OK",
                "event": "crossref_journal_query_start",
                "input_title": input_title,
            },
        )
        # Retrieval of records with titles similar to input_title from Crossref API
        params = {
            "query": input_title,
            "rows": 200,  # Large batch to find all matches
            "mailto": self.config.crossref_api_email,
        }

        journal_records = []
        response = self.http_client_wrapper.get(
            self.config.crossref_api_journals_url, params=params, headers=self.headers
        )
        response.raise_for_status()

        items = response.json().get("message", {}).get("items", [])

        # Identify exact matches
        exact_matches = [
            item for item in items if item.get("title", "").strip() == input_title
        ]

        working_items = []
        similar_titles = None

        if exact_matches:
            # Discard exact matches other than the 1st one
            if len(exact_matches) > 1:
                logger.warning(
                    "Discarded %d duplicate titles in the repo for journal: %s",
                    len(exact_matches),
                    input_title,
                    extra={
                        "status": "WARNING",
                        "event": "crossref_duplicate_titles_discarded",
                        "discarded_count": len(exact_matches),
                        "input_title": input_title,
                    },
                )
            working_items = [exact_matches[0]]
        else:
            # Look for potential matches based on flexible business rules
            target_norm = self._normalize_title(input_title)
            similar_items = []
            raw_similar_titles = []

            for item in items:
                raw_title = item.get("title", "").strip()
                if raw_title and self._normalize_title(raw_title) == target_norm:
                    similar_items.append(item)
                    raw_similar_titles.append(raw_title)

            if similar_items:
                # Deduplicate titles keeping order
                similar_titles = list(dict.fromkeys(raw_similar_titles))
                logger.warning(
                    "Journal %s not found. Use similar titles to fill metadata: %s",
                    input_title,
                    ", ".join(similar_titles),
                    extra={
                        "status": "WARNING",
                        "event": "crossref_journal_similar_found",
                        "input_title": input_title,
                        "similar_titles": similar_titles,
                    },
                )
                working_items = similar_items
            else:
                # Absolute fallback: No match and no similar titles found
                logger.warning(
                    "Journal %s not found.",
                    input_title,
                    extra={
                        "status": "KO",
                        "event": "crossref_journal_not_found",
                        "input_title": input_title,
                    },
                )
                return [JournalMetadata(input_title=input_title)]

        # Process all validated items (either the exact match or set of similar matches)
        processed_issns = set()  # Follow-up to avoid duplicates returned by crossref
        for item in working_items:
            true_title = item.get("title", "")
            publisher = item.get("publisher", "")
            issns = list(dict.fromkeys(item.get("ISSN", [])))  # remove duplicate ISSNs
            if not issns:
                logger.warning(
                    "Journal %s found but contains no ISSN metadata.",
                    true_title,
                    extra={
                        "status": "WARNING",
                        "event": "crossref_journal_missing_issn",
                        "input_title": input_title,
                        "true_title": true_title,
                    },
                )
                journal_records.append(
                    JournalMetadata(
                        input_title=input_title,
                        true_title=true_title,
                        publisher=publisher,
                        ISSN=None,
                        start_year=None,
                        end_year=None,
                        similar_titles=similar_titles,
                    )
                )
                continue

            for issn in issns:
                if issn in processed_issns:
                    logger.debug(
                        "ISSN %s already processed in this batch. Skipping.",
                        issn,
                    )
                    continue

                processed_issns.add(issn)

                logger.info(
                    "Retrieving %s / %s publication range...",
                    input_title,
                    issn,
                    extra={
                        "status": "OK",
                        "event": "crossref_issn_range_query_start",
                        "input_title": input_title,
                        "issn": issn,
                    },
                )
                # Publication range
                dates = {
                    "min_year": self.get_issn_year_endpoint(issn, "asc"),
                    "max_year": self.get_issn_year_endpoint(issn, "desc"),
                }

                # Keep records without published work
                if not dates["min_year"] or not dates["max_year"]:
                    logger.warning(
                        "Journal %s / %s has no published work found. Keeping record"
                        " with empty dates.",
                        input_title,
                        issn,
                        extra={
                            "status": "WARNING",
                            "event": "crossref_journal_no_works_found",
                            "input_title": input_title,
                            "issn": issn,
                        },
                    )
                    dates["min_year"] = None
                    dates["max_year"] = None

                journal_records.append(
                    JournalMetadata(
                        input_title=input_title,
                        true_title=true_title,
                        publisher=publisher,
                        ISSN=issn,
                        start_year=dates["min_year"],
                        end_year=dates["max_year"],
                        similar_titles=similar_titles,
                    )
                )

        return journal_records

    def get_issn_year_endpoint(
        self, issn: str, order: Literal["asc", "desc"]
    ) -> int | None:
        """Get the year of the oldest (order: asc) or the newest (order: desc) published
        work (no distinction print or online) for the ISSN."""
        params = {
            "sort": "published",
            "order": order,
            "rows": 1,
            "mailto": self.config.crossref_api_email,
        }
        response = self.http_client_wrapper.get(
            self.config.crossref_api_journals_issn_url.replace("{issn}", str(issn)),
            params=params,
            headers=self.headers,
        )

        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        if not items:
            return None

        work = items[0]
        p_date = work.get("published-print", {}).get("date-parts", [[None]])[0][0]
        o_date = work.get("published-online", {}).get("date-parts", [[None]])[0][0]

        # Earliest or latest year found between print/online
        years = [y for y in [p_date, o_date] if y is not None]
        return min(years) if order == "asc" and years else max(years) if years else None

    def get_sync_status(self) -> dict[str, int | bool]:
        """Analyze the current state of records to determine sync problems.
        Returns a status dictionary useful for control flow in core.py.
        TODO: Check if we still need this method (after the development of catching
        metadata from similar titles)
        """
        expiration_date = date.today() - timedelta(days=self.config.journal_update_days)
        missing_count = 0
        expired_count = 0

        for record in self.records:
            if not record.is_complete:
                missing_count += 1
            else:
                last_update = datetime.strptime(record.update, "%Y-%m-%d").date()
                if last_update < expiration_date:
                    expired_count += 1

        return {
            "is_fully_synchronized": missing_count == 0 and expired_count == 0,
            "missing_metadata_count": missing_count,
            "expired_metadata_count": expired_count,
            "has_pending_updates": self.has_pending_updates,
        }

    def update_all(self) -> None:
        """Update the records missing metadata (Priority 1) and records with expired
        metadata (Priority 2) with up-to-date metatata from the remote repo.
        Warning: Update restricted to a max number of journals, doesn't include
        regular local saving of the updates."""

        expiration_date = date.today() - timedelta(days=self.config.journal_update_days)
        logger.info(
            "Updating journals without metadata or metadata older than: %s",
            expiration_date,
            extra={
                "status": "OK",
                "event": "journal_update_process_started",
                "expiration_threshold": str(expiration_date),
            },
        )
        missing_metadata: list[JournalMetadata] = []
        expired_metadata: list[JournalMetadata] = []
        valid_metadata: list[JournalMetadata] = []

        for record in self.records:
            last_update = datetime.strptime(record.update, "%Y-%m-%d").date()

            if not record.is_complete:
                missing_metadata.append(record)
            elif last_update < expiration_date:
                expired_metadata.append(record)
            else:
                valid_metadata.append(record)

        logger.info(
            "Journal categorization completed. Missing: %d, Expired: %d, Valid: %d",
            len(missing_metadata),
            len(expired_metadata),
            len(valid_metadata),
            extra={
                "status": "OK",
                "event": "journal_update_categorization",
                "missing_count": len(missing_metadata),
                "expired_count": len(expired_metadata),
                "valid_count": len(valid_metadata),
            },
        )

        update_count = 0
        last_display_time = time.time()

        total_initial_targets = len(missing_metadata) + len(expired_metadata)
        processed_so_far = 0

        # Temporary collection for the new state of our repository records
        new_records: list[JournalMetadata] = []
        new_records.extend(valid_metadata)

        # Process Missing Metadata (Priority 1)
        for record in missing_metadata:
            print(f"missing:{record.input_title}.")
            if update_count < self.config.journal_update_limit:
                new_data = self.get_journal_metadata(record.input_title)
                if new_data:
                    new_records.extend(new_data)
                else:
                    # Should not occur
                    new_records.append(record)
                update_count += 1
            else:
                new_records.append(record)

            processed_so_far += 1
            last_display_time = self._log_heartbeat_if_needed(
                processed_so_far, total_initial_targets, last_display_time
            )

        # Process Expired Metadata (Priority 2)
        for record in expired_metadata:
            if update_count < self.config.journal_update_limit:
                new_data = self.get_journal_metadata(record.input_title)
                if new_data:
                    new_records.extend(new_data)
                else:
                    new_records.append(record)
                update_count += 1
            else:
                new_records.append(record)

            processed_so_far += 1
            last_display_time = self._log_heartbeat_if_needed(
                processed_so_far, total_initial_targets, last_display_time
            )

        # Compute if any record that required update got skipped due to limit
        skipped_count = total_initial_targets - update_count
        self.has_pending_updates = skipped_count > 0

        if self.has_pending_updates:
            logger.warning(
                "Journal update limit reached. %d records still need updating or "
                "refreshing.",
                skipped_count,
                extra={
                    "status": "WARNING",
                    "event": "journal_update_limit_reached",
                    "remaining_count": skipped_count,
                    "limit_configured": self.config.journal_update_limit,
                },
            )

        # Sort records: 1. Core metadata complete first, then incomplete.
        # 2. Alphabetical by input_title
        new_records.sort(key=lambda r: (not r.is_complete, r.input_title.lower()))

        self.records = new_records

        logger.info(
            "Journal metadata sync finalized. Updated %d journals",
            len(self.records),
            extra={
                "status": "OK",
                "event": "journal_update_completed",
                "total_records": len(self.records),
            },
        )

    def merge_new_titles(self, input_titles: list[str]) -> None:
        """Merge new titles into the existing records as empty templates.
        No duplication of titles."""
        input_titles = list(dict.fromkeys(input_titles))  # unique titles
        # Set for fast lookup
        existing_titles = {info.input_title for info in self.records}

        new_entries = [
            JournalMetadata(input_title=title)
            for title in input_titles
            if title not in existing_titles
        ]

        self.records.extend(new_entries)
        logger.info(
            "Merged %d new journal records into the local repository list",
            len(new_entries),
            extra={
                "status": "OK",
                "event": "journal_records_merged",
                "new_entries_count": len(new_entries),
            },
        )
