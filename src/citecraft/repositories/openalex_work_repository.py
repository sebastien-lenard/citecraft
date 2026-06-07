# src/citecraft/repositories/openalex_work_repository.py
import logging
from typing import override

from citecraft.schemas import (
    WorkMetadata,
)
from citecraft.utils import AppConfig

from .work_repository import WorkRepository

logger = logging.getLogger(__name__)


class OpenAlexWorkRepository(WorkRepository):
    """Manages local storage and OpenAlex resolution for published academic works."""

    def __init__(
        self,
        local_filename: str = "work_records.json",
        config: AppConfig | None = None,
        api: str = "openalex",
    ) -> None:
        super().__init__(local_filename, config=config, api=api)

    def _build_author_api_filter(self, input_authors_txt: str) -> str | None:
        """Builds a filter from author string."""
        authors, _ = self._get_input_first_authors_and_et_al(input_authors_txt)

        if not authors:
            return None
        match len(authors):
            case 1 | 2:
                return ",".join(
                    f'raw_author_name.search:"{author}"' for author in authors
                )

    @override
    def _call_work_api(
        self,
        input_first_authors_txt: str,
        year_int: int,
        input_issns: list[str],
        keywords: str = "",
        get_limit: int | None = None,
    ) -> list[dict] | None:
        """Return the list of items fetched by the api call."""
        if not input_issns:
            logger.warning(
                "%s needs at least one ISSN.",
                type(self).__qualname__,
                extra={
                    "event": "openalex_work_api_no_issn",
                },
            )
            return []

        if len(input_issns) > self.config.openalex_api_max_piped_filters:
            logger.warning(
                (
                    "OpenAlex API accepts a maximum of 100 ISSNs for a filter"
                    " parameter: %d provided."
                ),
                len(input_issns),
                extra={
                    "event": "openalex_work_api_too_many_issns",
                    "issns": ", ".join(input_issns),
                    "count_of_issns": len(input_issns),
                },
            )
            return []

        raw_author_name_filter = self._build_author_api_filter(input_first_authors_txt)

        if raw_author_name_filter is None:
            logger.warning(
                ("Citation does not seem to have parsable first authors: '%s'."),
                input_first_authors_txt,
                extra={
                    "event": "openalex_work_api_no_parsable_authors",
                    "input_first_authors_txt": input_first_authors_txt,
                },
            )
            return []

        get_limit = (
            int(get_limit)
            if get_limit is not None
            else self.config.openalex_api_works_get_limit
        )

        issn_filter_str = "|".join(input_issns)
        filters = (
            f"publication_year:{year_int},"
            f"primary_location.source.issn:{issn_filter_str},"
            f"{raw_author_name_filter}"
        )
        params = {
            "filter": filters,
            "api_key": self.config.openalex_api_key,
            "per_page": get_limit,
        }

        response, _ = self.http_client_wrapper.get(
            str(self.config.openalex_api_works_url),
            headers=self.headers,
            params=params,
        )

        if response is None:
            return []
        response.raise_for_status()
        data = response.json()

        return data.get("results", [])

    @override
    def _get_authors_from_api_item(self, item: dict) -> list[dict] | None:
        """Get authors of an item returned by the api"""
        return item.get("authorships")

    @override
    def _get_doi_from_api_item(self, item: dict) -> str | None:
        """Get doi of an item returned by the api"""
        doi = item.get("doi")
        if doi and isinstance(doi, str):
            return doi.removeprefix("https://doi.org/")
        return None

    @override
    def _get_issns_groups_for_api(self, issns: list[str]) -> list[list[str]]:
        """Split ISSNs in groups that can be used as filters (OR) by API."""
        issns_groups = []
        current_group = []
        current_length = 0

        for issn in issns:
            # Calculate length with the "|" delimiter included (if not the first item)
            delimiter_penalty = 1 if current_group else 0
            potential_length = current_length + len(issn) + delimiter_penalty
            if (
                potential_length
                < self.config.openalex_api_url_max_character_length_for_issns_filter
            ):
                current_group.append(issn)
                current_length = potential_length
            else:
                if current_group:
                    issns_groups.append(current_group)
                current_group = [issn]
                current_length = len(issn)

        # Append the final remaining group
        if current_group:
            issns_groups.append(current_group)

        return issns_groups

    @override
    def _get_type_from_api_item(self, item: dict) -> str | None:
        """Get type of an item returned by the api"""
        if "primary_location" in item and "raw_type" in item["primary_location"]:
            return item["primary_location"]["raw_type"]
        return item.get("type")

    @override
    def _set_metadata_attribute(
        self, work_metadata: WorkMetadata, item: dict,
    ) -> WorkMetadata:
        """Clean and update the metadata attribute and returns object."""
        logger.debug(
            "Application does not yet accept OpenAlex metadata.",
            extra={
                "method": type(self).__qualname__,
                "event": "openalex_work_repo_metadata_rejection",
            },
        )
        work_metadata.openalex_metadata = None
        return work_metadata

    @override
    def _validate_author(self, input_author: str, api_author: dict) -> bool:
        """Verify that input input and api authors are similar.
        WARNING: Comparison lacks of accuracy because OpenAlex API only provides
        full names rather than given/family names."""
        if not input_author:
            return False
        if "raw_author_name" in api_author:
            api_author_name = api_author["raw_author_name"]
        elif "author" in api_author and "display_name" in api_author["author"]:
            api_author_name = api_author["author"]["display_name"]
        else:
            return False
        norm_input_author = self._normalize_string(input_author)
        norm_api_author = self._normalize_string(api_author_name)
        if norm_input_author in norm_api_author and not norm_api_author.endswith(
            norm_input_author,
        ):
            logger.info(
                (
                    "Invalidate input author family name %s: ambiguous family name"
                    "matching with OpenAlex API full name '%s'."
                ),
                input_author,
                api_author_name,
                extra={
                    "event": "openalex_work_invalidate_ambiguous_author_names",
                    "input_author": input_author,
                    "api_author": api_author_name,
                },
            )
            return False
        return norm_api_author.endswith(norm_input_author)
