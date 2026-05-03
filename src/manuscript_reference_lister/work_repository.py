import logging
import time

from unidecode import unidecode

from . import config_loader
from .requests_wrapper import RequestsWrapper
from .work_metadata import WorkMetadata


class WorkRepository:
    """
    Handles API calls to Crossref about article references
    with multi-result support.
    """

    def __init__(self):
        self.email = config_loader.CROSSREF_API_EMAIL
        self.headers = {"User-Agent": f"ManuscriptRefLister/1.0 (mailto:{self.email})"}
        self.base_url = config_loader.CROSSREF_API_WORKS_URL
        self.doi_url = config_loader.DOI_API_URL
        self.max_results = config_loader.CROSSREF_API_MAX_RESULTS
        self.requests_wrapper = RequestsWrapper(
            config_loader.CROSSREF_API_EMAIL,
            timeout=config_loader.CROSSREF_API_TIMEOUT,
            max_retries=config_loader.CROSSREF_API_MAX_RETRY,
            delay=config_loader.CROSSREF_API_DELAY,
        )
        self.works = []

    def fetch_dois_for_this_info(
        self,
        author: str,
        year: str,
        issn: str | None = None,
        keywords: str = "",
        max_results: int | None = None,
    ) -> list[WorkMetadata]:
        """
        Searches for references and returns a list of potential matches.
        year: str (1600-2099), with possible suffix (a, b, etc.).
        issn: valid issn of a journal. Without it, crossref will have troubles
            retrieving relevant candidates.
        keywords: either a reference or some specific words of the title. Generic
            keywords not in the title (e.g. geosciences) will dilute crossref output.
        Warning: these remarks are because the project uses the crossref rest api, which
            is mostly based on article metadata, and doesn't work like google scholar,
            which is based more on content.
        """
        if not issn:
            raise ValueError("issn is an obligatory argument (valid issn of a journal)")
        year_int = int("".join(filter(str.isdigit, year)))
        if year_int < 1600 or year_int > 2099:
            raise ValueError(f"year {year_int} must be in the 1600-2099 range")
        max_results = int(max_results) if max_results else self.max_results

        # Clean author string and determine the expected number of authors
        # Logic:
        # 1. "A et al." -> Many authors (no upper limit check)
        # 2. "A and B" or "A & B" -> Exactly 2 authors
        # 3. "A" -> Exactly 1 author
        is_et_al = " et al." in author
        raw_authors = author.split(" et al.")[0].replace(" et ", " and ").split(" and ")
        expected_count = len(raw_authors) if not is_et_al else None

        params = {
            "query": f"{author} {keywords}",
            "rows": max_results,
            "filter": f"from-pub-date:{year_int},until-pub-date:{year_int},issn:{issn}",
        }

        response = self.requests_wrapper.get(
            self.base_url, headers=self.headers, params=params
        )
        response.raise_for_status()
        data = response.json()

        items = data["message"].get("items", [])
        candidates = []

        for item in items:
            if not self._validate_first_author(item, raw_authors, expected_count):
                continue
            doi = item.get("DOI")
            if doi:
                candidates.append(
                    {
                        "req_author": author,
                        "req_year": year,
                        "req_issn": issn,
                        "req_keywords": keywords,
                        "reference": "",
                        "style": "",
                        "doi": self.doi_url.replace("{doi}", str(doi)),
                        "type": item.get("type", "unknown"),
                    }
                )
        return candidates

    def _normalize_string(self, text: str) -> str:
        """
        Transliterates unicode string to its closest ASCII representation in lowercase.
        Example: 'Lénárd' becomes 'lenard', 'Łukasiewicz' becomes 'lukasiewicz'.
        Warning: ü becomes u and not ue (as sometimes found in bibliographies)
        """
        if not text:
            return ""
        return unidecode(text).lower().strip()

    def _validate_first_author(
        self, item: dict, expected_authors: list[str], expected_count: int | None = None
    ) -> bool:
        """
        Validates the authors based on the expected list and count.
        Validates if the first author of the Crossref item matches the expected author.
        Warning: strict comparison, case insensitive. If name slightly differs (e.g.
        VanDijk vs Van Dijk, comparison returns False)

        Args:
            item: The work item dictionary from Crossref.
            expected_author: The surname/name of the author to match.

        Returns:
            bool: True if a match is found, False otherwise.
        """
        authors = item.get("author", [])
        if not authors:
            return False

        # 1. Strict count validation if not an "et al." citation
        if expected_count is not None and len(authors) != expected_count:
            return False

        norm_expected = [self._normalize_string(a) for a in expected_authors]

        # 2. Validate the primary (first) author.
        # Fallback to the first element in the list if 'sequence' key is missing.
        first_author_obj = next(
            (a for a in authors if a.get("sequence") == "first"), authors[0]
        )
        norm_first_family = self._normalize_string(
            first_author_obj.get("family", first_author_obj.get("name", ""))
        )

        if norm_expected[0] != norm_first_family:
            # Fallback check on given name
            norm_first_given = self._normalize_string(first_author_obj.get("given", ""))
            if norm_expected[0] != norm_first_given:
                return False

        # 3. Validate second author if exactly two are expected
        if expected_count == 2:
            # The second author is the one that is NOT the first_author_obj
            second_author_obj = [a for a in authors if a != first_author_obj][0]
            norm_second_family = self._normalize_string(
                second_author_obj.get("family", second_author_obj.get("name", ""))
            )
            if norm_expected[1] != norm_second_family:
                return False

        return True

    def update(self):
        """Find works and sets doi in self.work_info_list.
        Update is restricted to a max number of works, and method doesnt save the
        list to a file."""

        # 1. Identify and categorize records needing attention
        needs_info = []  # Priority 1: Missing data (None)
        needs_refresh = []  # Priority 2: Old data (Date expired)
        complete = []  # No update needed

        for record in self.journal_info_list:
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
                    f"Status: {remaining} updates remaining out of {total_to_process}..."
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
