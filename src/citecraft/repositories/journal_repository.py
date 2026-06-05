# src/citecraft/repositories/journal_repository.py
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from citecraft.parsers import JournalParser
from citecraft.schemas import JournalMetadata
from citecraft.utils import AppConfig

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UpdateBatchState:
    """Tracks operational state across batch execution segments."""

    total: int
    processed: int = 0
    update_count: int = 0
    last_heartbeat: float = 0.0


class JournalRepository(BaseRepository[JournalMetadata]):
    """Handles persistence and retrieval workflows for journal metadata records."""

    def __init__(
        self,
        local_filename: str = "journal_records.json",
        config: AppConfig | None = None,
        api: str = "crossref",
    ) -> None:
        super().__init__(
            local_filename, model_class=JournalMetadata, config=config, api=api
        )
        self.has_pending_updates: bool = False

    def _log_heartbeat_if_needed(
        self, processed: int, total: int, last_time: float
    ) -> float:
        """Log update batch progress status every 10 seconds of processing time."""
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
                    "event": "journal_update_heartbeat",
                    "remaining_count": remaining,
                    "total_count": total,
                },
            )
            return current_time
        return last_time

    def get_issns_by_input_title(self, input_title: str) -> list[str]:
        """Return unique, non-null ISSNs present in records for a specific title."""
        return sorted(
            {
                r.issn
                for r in self.records
                if r.input_title == input_title and r.issn is not None
            }
        )

    def get_unique_issns_for_titles(self, titles: list[str]) -> list[str]:
        """Extract unique, non-null ISSNs for a validated list of titles."""
        if not titles:
            return []

        # Normalize and put in a set (O(1) search)
        required_normalized = {JournalParser.normalize_title(t) for t in titles if t}

        # Cache filter (O(N))
        unique_issns: set[str] = set()

        for record in self.records:
            if (
                record.issn
                and JournalParser.normalize_title(record.input_title)
                in required_normalized
            ):
                unique_issns.add(record.issn)

        return sorted(unique_issns)

    def _fetch_crossref_items(self, input_title: str) -> list[dict[str, Any]] | None:
        """Fetch matching raw journal records from Crossref API."""
        params = {
            "query": input_title,
            "rows": 200,
            "mailto": self.config.user_email,
        }
        response, predicted_url = self.http_client_wrapper.get(
            str(self.config.crossref_api_journals_url),
            params=params,
            headers=self.headers,
        )
        if response is None:
            logger.warning(
                "Empty journal '%s' response from URL %s.",
                input_title,
                predicted_url,
                extra={
                    "status": "KO",
                    "event": "empty_journal_response_from_url",
                    "input_title": input_title,
                    "predicted_url": predicted_url,
                },
            )
            return None

        response.raise_for_status()
        return response.json().get("message", {}).get("items", [])

    def _filter_matches(
        self, input_title: str, items: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str] | None]:
        """Classify Crossref items into exact matches or similar matches."""
        # Filter exact title representations
        exact_matches = [
            item for item in items if item.get("title", "").strip() == input_title
        ]

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
            return [exact_matches[0]], None

        # Look for potential matches based on flexible business rules
        target_norm = JournalParser.normalize_title(input_title)
        similar_items = []
        raw_similar_titles = []

        for item in items:
            raw_title = item.get("title", "").strip()
            if raw_title and JournalParser.normalize_title(raw_title) == target_norm:
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
            return similar_items, similar_titles

        return [], None

    def _resolve_publication_years(self, issn: str) -> tuple[int | None, int | None]:
        """Resolve start and end publication years for a given ISSN."""
        min_year = self.get_issn_year_endpoint(issn, "asc")
        max_year = self.get_issn_year_endpoint(issn, "desc")
        return min_year, max_year

    def _build_metadata_records(
        self,
        input_title: str,
        working_items: list[dict[str, Any]],
        similar_titles: list[str] | None,
    ) -> list[JournalMetadata]:
        """Map working Crossref metadata items to list of JournalMetadata."""
        journal_records: list[JournalMetadata] = []
        processed_issns: set[str] = set()

        for item in working_items:
            true_title = item.get("title", "")
            publisher = item.get("publisher", "")
            # remove duplicate ISSNs, get MUST be on ISSN.
            raw_issns = item.get("ISSN") or item.get("issn") or []
            issns = list(dict.fromkeys(raw_issns))

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
                        issn=None,
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

                start_year, end_year = self._resolve_publication_years(issn)

                if start_year is None or end_year is None:
                    logger.warning(
                        "Journal %s / %s has no published work found. "
                        "Keeping record with empty dates.",
                        input_title,
                        issn,
                        extra={
                            "status": "WARNING",
                            "event": "crossref_journal_no_works_found",
                            "input_title": input_title,
                            "issn": issn,
                        },
                    )
                    start_year = None
                    end_year = None

                journal_records.append(
                    JournalMetadata(
                        input_title=input_title,
                        true_title=true_title,
                        publisher=publisher,
                        issn=issn,
                        start_year=start_year,
                        end_year=end_year,
                        similar_titles=similar_titles,
                    )
                )

        return journal_records

    def get_journal_metadata(self, input_title: str) -> list[JournalMetadata]:
        """Retrieve and process journal metadata maps from the remote Crossref API.
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
        items = self._fetch_crossref_items(input_title)
        if items is None:
            return [JournalMetadata(input_title=input_title)]

        working_items, similar_titles = self._filter_matches(input_title, items)
        if not working_items:
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

        return self._build_metadata_records(input_title, working_items, similar_titles)

    def get_issn_year_endpoint(
        self, issn: str, order: Literal["asc", "desc"]
    ) -> int | None:
        """Get publication endpoints based on print/online works for the ISSN.
        asc: oldest / desc: youngest.
        """
        params = {
            "sort": "published",
            "order": order,
            "rows": 1,
            "mailto": self.config.user_email,
        }
        url = self.config.crossref_api_journals_issn_url.replace(
            "{object_name}", str(issn)
        )

        response, predicted_url = self.http_client_wrapper.get(
            url,
            params=params,
            headers=self.headers,
        )

        if response is None:
            logger.warning(
                "Empty journal issn '%s' response from URL %s.",
                issn,
                predicted_url,
                extra={
                    "status": "KO",
                    "event": "empty_journal_response_from_url",
                    "issn": issn,
                    "predicted_url": predicted_url,
                },
            )
            return None

        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        if not items:
            return None

        work = items[0]
        p_date = work.get("published-print", {}).get("date-parts", [[None]])[0][0]
        o_date = work.get("published-online", {}).get("date-parts", [[None]])[0][0]

        # Earliest or latest year found between print/online
        years = [y for y in [p_date, o_date] if y is not None]
        if not years:
            return None
        return min(years) if order == "asc" else max(years)

    def get_sync_status(self) -> dict[str, int | bool]:
        """Analyze local records completeness and update status against thresholds.
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

    def _partition_records(
        self, expiration_date: date
    ) -> tuple[list[JournalMetadata], list[JournalMetadata], list[JournalMetadata]]:
        """Partition local records into missing, expired, and valid categories."""
        missing: list[JournalMetadata] = []
        expired: list[JournalMetadata] = []
        valid: list[JournalMetadata] = []

        for record in self.records:
            last_update = datetime.strptime(record.update, "%Y-%m-%d").date()

            if not record.is_complete:
                missing.append(record)
            elif last_update < expiration_date:
                expired.append(record)
            else:
                valid.append(record)

        return missing, expired, valid

    def _update_batch(
        self,
        targets: list[JournalMetadata],
        new_records: list[JournalMetadata],
        state: UpdateBatchState,
    ) -> None:
        """Process a collection of target records up to the configured limit."""
        for record in targets:
            if state.update_count < self.config.journal_update_limit:
                new_data = self.get_journal_metadata(record.input_title)
                if new_data:
                    new_records.extend(new_data)
                else:
                    new_records.append(record)
                state.update_count += 1
            else:
                new_records.append(record)

            state.processed += 1
            state.last_heartbeat = self._log_heartbeat_if_needed(
                state.processed, state.total, state.last_heartbeat
            )

    def update_all(self) -> None:
        """Sync and update outdated journal records up to configured limits.
        Update the records missing metadata (Priority 1) and records with expired
        metadata (Priority 2) with up-to-date metatata from the remote repo.
        Warning: Update restricted to a max number of journals, doesn't include
        regular local saving of the updates."""
        expiration_date = date.today() - timedelta(days=self.config.journal_update_days)
        logger.info(
            "Updating journals without metadata or metadata older than: %s",
            str(expiration_date),
            extra={
                "status": "OK",
                "event": "journal_update_process_started",
                "expiration_threshold": str(expiration_date),
            },
        )

        missing, expired, valid = self._partition_records(
            expiration_date
        )  # missing = missing metadata

        logger.info(
            "Journal categorization completed. Missing: %d, Expired: %d, Valid: %d",
            len(missing),
            len(expired),
            len(valid),
            extra={
                "status": "OK",
                "event": "journal_update_categorization",
                "missing_count": len(missing),
                "expired_count": len(expired),
                "valid_count": len(valid),
            },
        )

        new_records: list[JournalMetadata] = list(valid)
        total_initial_targets = len(missing) + len(expired)
        state = UpdateBatchState(
            total=total_initial_targets,
            last_heartbeat=time.time(),
        )

        # Process Missing Metadata (Priority 1)
        self._update_batch(missing, new_records, state)

        # Process Expired Metadata (Priority 2)
        self._update_batch(expired, new_records, state)

        # Compute if any record that required update got skipped due to limit
        skipped_count = total_initial_targets - state.update_count
        self.has_pending_updates = skipped_count > 0

        if self.has_pending_updates:
            logger.warning(
                "Journal update limit reached. %d records still need updating.",
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
        """Merge fresh titles as empty templates without introducing duplicates."""
        input_titles = list(dict.fromkeys(input_titles))
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
