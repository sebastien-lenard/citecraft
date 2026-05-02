import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config_loader
from .requests_wrapper import RequestsWrapper


class JournalFetcher:
    """
    Handles API calls to Crossref about journals.
    """

    def __init__(self):
        self.email = config_loader.CROSSREF_API_EMAIL
        self.headers = {"User-Agent": f"ManuscriptRefLister/1.0 (mailto:{self.email})"}
        self.base_url = config_loader.CROSSREF_API_JOURNALS_URL
        self.issn_url = config_loader.CROSSREF_API_JOURNALS_ISSN_URL
        self.work_dir_path = config_loader.WORK_DIR_PATH
        self.journal_info_list = []
        self.update_days = config_loader.JOURNAL_UPDATE_DAYS
        self.update_max = config_loader.JOURNAL_UPDATE_MAX
        self.has_pending_updates = False
        self.requests_wrapper = RequestsWrapper(
            config_loader.CROSSREF_API_EMAIL,
            timeout=config_loader.CROSSREF_API_TIMEOUT,
            max_retries=config_loader.CROSSREF_API_MAX_RETRY,
            delay=config_loader.CROSSREF_API_DELAY,
        )

    def get_issns_and_dates_by_name(self, requested_title):
        """
        Retrieves the first match from Crossref, get min/max publication dates and
        returns a list of dictionaries,
        one for each ISSN associated with that journal.
        """
        params = {
            "query": requested_title,
            "rows": 200,  # Pull a large enough batch to find all matches
            "mailto": self.email,
        }

        record_list = []
        try:
            response = self.requests_wrapper.get(
                self.base_url, params=params, headers=self.headers
            )
            response.raise_for_status()

            items = response.json().get("message", {}).get("items", [])
            exact_matches = [
                item
                for item in items
                if item.get("title", "").strip() == requested_title
            ]

            # We only proceed if we found at least one exact match
            if exact_matches:
                item = exact_matches[0]
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                issns = item.get("ISSN", [])
                issns = list(dict.fromkeys(item.get("ISSN", [])))  # remove duplicates

                # Create a list of dicts, one per ISSN
                for issn in issns:
                    # For each ISSN, try to find its specific publication range
                    dates = {
                        "min_year": self.get_year_endpoint(issn, "asc"),
                        "max_year": self.get_year_endpoint(issn, "desc"),
                    }

                    record_list.append(
                        {
                            "requested_title": requested_title,
                            "title": title,
                            "publisher": publisher,
                            "issn": issn,
                            "start_year": dates["min_year"],
                            "end_year": dates["max_year"],
                            "update": str(date.today()),
                        }
                    )
            else:
                record_list.append(
                    {
                        "requested_title": requested_title,
                        "title": None,
                        "publisher": None,
                        "issn": None,
                        "start_year": None,
                        "end_year": None,
                        "update": str(date.today()),
                    }
                )
                logging.warning("Journal %s not found.", requested_title)
            return record_list

        except Exception as e:
            raise e
            return []

    def get_year_endpoint(self, issn, order):
        """Helper to fetch the oldest or newest work year for an ISSN.
        order: asc or desc."""
        params = {"sort": "published", "order": order, "rows": 1, "mailto": self.email}
        try:
            response = self.requests_wrapper.get(
                self.issn_url.replace("{issn}", str(issn)),
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
            if not items:
                return None

            # Crossref works use 'published-print' or 'published-online'
            work = items[0]
            p_date = work.get("published-print", {}).get("date-parts", [[None]])[0][0]
            o_date = work.get("published-online", {}).get("date-parts", [[None]])[0][0]

            # Return the earliest or latest year found between print/online
            years = [y for y in [p_date, o_date] if y is not None]
            return (
                min(years)
                if order == "asc" and years
                else max(years)
                if years
                else None
            )
        except:
            return None

    def update_journal_info(self):
        """Set or update issn/dates in self.journal_info_list. Should work ok if list
        has less than 100k items.
        Update is restricted to a max number of journals, and methode doesnt save the
        list to a file."""

        cutoff_date = date.today() - timedelta(days=self.update_days)
        # 1. Identify and categorize records needing attention
        needs_info = []  # Priority 1: Missing data (None)
        needs_refresh = []  # Priority 2: Old data (Date expired)
        complete = []  # No update needed

        for record in self.journal_info_list:
            try:
                last_update = datetime.strptime(record["update"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                last_update = date.min

            if None in record.values():
                needs_info.append(record)
            elif last_update < cutoff_date:
                needs_refresh.append(record)
            else:
                complete.append(record)

        # 2. Process updates with a limit
        final_list = complete
        to_process = needs_info + needs_refresh  # Missing info comes first
        calls_made = 0
        last_display_time = time.time()
        total_to_process = len(to_process)
        remaining_updates = 0

        for i, record in enumerate(to_process):
            if calls_made < self.update_max:
                new_data = self.get_issns_and_dates_by_name(record["requested_title"])
                if new_data:
                    final_list.extend(new_data)
                else:
                    final_list.append(record)
                calls_made += 1
            else:
                # We hit the limit; keep the old record and count it for the warning
                final_list.append(record)
                remaining_updates = len(to_process) - i
                break
            # Display update every 10 seconds
            if time.time() - last_display_time > 10:
                remaining = total_to_process - (i + 1)
                print(
                    f"Status: {remaining} updates remaining out of "
                    f"{total_to_process}..."
                )
                last_display_time = time.time()

        # 3. Handle Warning and Flag
        if remaining_updates > 0:
            self.has_pending_updates = True
            logging.warning(
                "Journal update limit reached. %d records still need updating.",
                remaining_updates,
            )

        self.journal_info_list = final_list

    def load_and_merge_journal_info_list(
        self, journal_title_list=[], input_filepath=None
    ):
        """Load the list."""
        if not input_filepath:
            input_filepath = Path(self.work_dir_path) / "journal_info_list.json"

        try:
            with open(input_filepath) as f:
                self.journal_info_list = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.journal_info_list = []

        # 1. Get a set of titles already in journal_info_list for fast lookup
        existing_titles = {info["requested_title"] for info in self.journal_info_list}

        # 2. Filter journal_title_list and create formatted dicts for the new ones
        new_entries = [
            {
                "requested_title": requested_title,
                "title": None,
                "publisher": None,
                "issn": None,
                "start_year": None,
                "end_year": None,
                "update": str(date.today()),
            }
            for requested_title in journal_title_list
            if requested_title not in existing_titles
        ]

        # 3. Merge the two lists
        self.journal_info_list = self.journal_info_list + new_entries

    def save_journal_info_list(self, output_filepath=None):
        """Save the list."""
        if not output_filepath:
            output_filepath = Path(self.work_dir_path) / "journal_info_list.json"
        with open(output_filepath, "w") as f:
            json.dump(self.journal_info_list, f, indent=4)
