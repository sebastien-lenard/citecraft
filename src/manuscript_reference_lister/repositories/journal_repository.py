import logging
import time
from datetime import date, datetime, timedelta
from typing import Literal

from manuscript_reference_lister import config_loader
from manuscript_reference_lister.schemas import JournalMetadata, is_journal_metadata

from .base_repository import BaseRepository


class JournalRepository(BaseRepository[JournalMetadata]):
    """Handles journal metadata records."""

    def __init__(self, local_filename: str = "journal_records.json"):
        super().__init__(local_filename, validator=is_journal_metadata)

        self.base_url = config_loader.CROSSREF_API_JOURNALS_URL
        self.issn_url = config_loader.CROSSREF_API_JOURNALS_ISSN_URL
        self.update_days = config_loader.JOURNAL_UPDATE_DAYS
        self.update_limit = config_loader.JOURNAL_UPDATE_LIMIT
        self.has_pending_updates = False

    def get_journal_metadata(self, input_title: str) -> list[JournalMetadata]:
        """
        Get journal metadata filtered on the exact match of the title (input_title) that
        have published works. A title can correspond to several records or none, each of
        them identified by a unique ISSN.
        Warning: If more than 1 exact match is found, returns only the records for the
        first one found.
        """
        # Retrieval of records with titles similar to input_title from Crossref API
        params = {
            "query": input_title,
            "rows": 200,  # Large batch to find all matches
            "mailto": self.email,
        }

        journal_records = []
        response = self.requests_wrapper.get(
            self.base_url, params=params, headers=self.headers
        )
        response.raise_for_status()

        items = response.json().get("message", {}).get("items", [])

        # Discard records without exact title match
        exact_matches = [
            item for item in items if item.get("title", "").strip() == input_title
        ]

        if not exact_matches:
            logging.warning("Journal %s not found.", input_title)
            return [
                {
                    "input_title": input_title,
                    "true_title": None,
                    "publisher": None,
                    "ISSN": None,
                    "start_year": None,
                    "end_year": None,
                    "update": str(date.today()),
                }
            ]

        # Discard exact matches other than the 1st one
        if len(exact_matches) > 1:
            logging.warning(
                "Discarded duplicate titles in the repo for journal %s.", input_title
            )
        item = exact_matches[0]
        true_title = item.get("title", "")
        publisher = item.get("publisher", "")
        issns = item.get("ISSN", [])
        issns = list(dict.fromkeys(item.get("ISSN", [])))  # remove duplicate ISSNs

        for issn in issns:
            # Publication range
            dates = {
                "min_year": self.get_issn_year_endpoint(issn, "asc"),
                "max_year": self.get_issn_year_endpoint(issn, "desc"),
            }

            # Discard records without published work
            if not dates["min_year"] or not dates["max_year"]:
                logging.warning("Skip journal %s (no published work).", input_title)
                continue

            journal_records.append(
                {
                    "input_title": input_title,
                    "true_title": true_title,
                    "publisher": publisher,
                    "ISSN": issn,
                    "start_year": dates["min_year"],
                    "end_year": dates["max_year"],
                    "update": str(date.today()),
                }
            )
        return journal_records

    def get_issn_year_endpoint(
        self, issn: str, order: Literal["asc", "desc"]
    ) -> int | None:
        """Get the year of the oldest (order: asc) or the newest (order: desc) published
        work (no distinction print or online) for the ISSN."""
        params = {"sort": "published", "order": order, "rows": 1, "mailto": self.email}
        response = self.requests_wrapper.get(
            self.issn_url.replace("{issn}", str(issn)),
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

    def update_all(self) -> None:
        """Update the records missing metadata (Priority 1) and records with expired
        metadata (Priority 2) with up-to-date metatata from the remote repo.
        Warning: Update restricted to a max number of journals, doesn't include
        regular local saving of the updates."""

        expiration_date = date.today() - timedelta(days=self.update_days)
        missing_metadata = []
        expired_metadata = []
        valid_metadata = []

        for record in self.records:
            try:
                last_update = datetime.strptime(record["update"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                last_update = date.min

            if None in record.values():
                missing_metadata.append(record)
            elif last_update < expiration_date:
                expired_metadata.append(record)
            else:
                valid_metadata.append(record)

        records_to_update = missing_metadata + expired_metadata
        update_count = 0
        last_display_time = time.time()
        update_total = len(records_to_update)
        update_remaining = 0

        for i, record in enumerate(records_to_update):
            if update_count < self.update_limit:
                new_data = self.get_journal_metadata(record["input_title"])
                if new_data:
                    valid_metadata.extend(new_data)
                else:
                    valid_metadata.append(record)
                update_count += 1
            else:
                # We hit the limit; keep the old record and count it for the warning
                valid_metadata.append(record)
                update_remaining = len(records_to_update) - i
                break
            # Display update every 10 seconds
            if time.time() - last_display_time > 10:
                remaining = update_total - (i + 1)
                print(f"Status: {remaining} updates remaining out of {update_total}...")
                last_display_time = time.time()

        # 3. Handle Warning and Flag
        if update_remaining > 0:
            self.has_pending_updates = True
            logging.warning(
                "Journal update limit reached. %d records still need updating.",
                update_remaining,
            )

        self.records = valid_metadata

    def merge_new_titles(self, input_titles: list[str]) -> None:
        """Merge new titles into the existing records as empty templates.
        No duplication of titles."""
        # Set for fast lookup
        existing_titles = {info["input_title"] for info in self.records}

        new_entries = [
            {
                "input_title": title,
                "true_title": None,
                "publisher": None,
                "ISSN": None,
                "start_year": None,
                "end_year": None,
                "update": str(date.today()),
            }
            for title in input_titles
            if title not in existing_titles
        ]

        self.records.extend(new_entries)
