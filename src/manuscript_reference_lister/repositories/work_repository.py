from unidecode import unidecode

from manuscript_reference_lister.schemas import (
    CitationMetadata,
    CrossrefAuthor,
    WorkMetadata,
    create_work_metadata,
    is_work_metadata,
)
from manuscript_reference_lister.utils import AppConfig

from .base_repository import BaseRepository


class WorkRepository(BaseRepository[WorkMetadata]):
    """Handles published work metadata records (for articles, book chapters, etc.)."""

    def __init__(
        self, local_filename: str = "work_records.json", config: AppConfig | None = None
    ):
        super().__init__(local_filename, validator=is_work_metadata, config=config)

    def get_work_metadata(
        self,
        input_citation_metadata: CitationMetadata,
        input_ISSN: str,
        keywords: str = "",
        get_limit: int | None = None,
    ) -> list[WorkMetadata]:
        """
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
        input_first_authors_txt = input_citation_metadata["first_authors_txt"]
        input_year_and_suffix = input_citation_metadata["year_and_suffix"]
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

        response = self.requests_wrapper.get(
            self.config.crossref_api_works_url, headers=self.headers, params=params
        )
        response.raise_for_status()
        data = response.json()

        items = data["message"].get("items", [])
        candidates = []

        for item in items:
            if "author" not in item:
                continue

            if not self._validate_first_authors(
                item["author"], raw_authors, expected_count
            ):
                continue
            doi = item.get("DOI")
            if doi:
                candidates.append(
                    create_work_metadata(
                        input_first_authors_txt=input_first_authors_txt,
                        input_year_and_suffix=input_year_and_suffix,
                        input_ISSN=input_ISSN,
                        reference="",
                        style="",
                        doi=self.config.doi_api_url.replace("{doi}", str(doi)),
                        type=item.get("type", "unknown"),
                    )
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

    def _validate_first_authors(
        self,
        crossref_authors: list[CrossrefAuthor],
        input_first_authors: list[str],
        input_first_authors_count: int | None = None,
    ) -> bool:
        """
        Validates if the first crossref_authors match the input_first_authors, and if
        number of authors match too if 1 or 2 authors only.
        Warning: strict comparison, case insensitive. If name slightly differs (e.g.
        VanDijk vs Van Dijk, comparison returns False)
        """

        # 1. Strict count validation if not an "et al." citation
        if (
            input_first_authors_count is not None
            and len(crossref_authors) != input_first_authors_count
        ):
            return False

        norm_expected = [self._normalize_string(a) for a in input_first_authors]

        # 2. Validate the primary (first) author.
        # Fallback to the first element in the list if 'sequence' key is missing.
        first_author_obj = next(
            (a for a in crossref_authors if a.get("sequence") == "first"),
            crossref_authors[0],
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
        if input_first_authors_count == 2:
            # The second author is the one that is NOT the first_author_obj
            second_author_obj = [a for a in crossref_authors if a != first_author_obj][
                0
            ]
            norm_second_family = self._normalize_string(
                second_author_obj.get("family", second_author_obj.get("name", ""))
            )
            if norm_expected[1] != norm_second_family:
                return False

        return True
