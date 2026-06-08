# src/citecraft/repositories/crossref_work_repository.py
"""Repository for managing academic work lookups via the Crossref API."""

import logging
from typing import override

from citecraft.schemas import (
    WorkMetadata,
)
from citecraft.utils import AppConfig

from .work_repository import WorkRepository

logger = logging.getLogger(__name__)


class CrossrefWorkRepository(WorkRepository):
    """Manages local storage and Crossref resolution for published academic works."""

    def __init__(
        self,
        local_filename: str = "work_records.json",
        config: AppConfig | None = None,
        api: str = "crossref",
    ) -> None:
        super().__init__(local_filename, config=config, api=api)

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
                extra={"event": "crossref_work_api_no_issn"},
            )
            return []
        if len(input_issns) != 1:
            logger.warning(
                "%s only accepts one ISSN but several are provided: %s.",
                type(self).__qualname__,
                ", ".join(input_issns),
                extra={
                    "event": "crossref_work_api_several_issns",
                    "issns": ", ".join(input_issns),
                },
            )
            return []

        get_limit = (
            int(get_limit)
            if get_limit is not None
            else self.config.crossref_api_works_get_limit
        )

        issn_filter = input_issns[0]
        filter_str = (
            f"from-pub-date:{year_int},until-pub-date:{year_int},issn:{issn_filter}"
        )
        params = {
            "query": f"{input_first_authors_txt} {keywords}",
            "rows": get_limit,
            "filter": filter_str,
        }

        response, _ = self.http_client_wrapper.get(
            str(self.config.crossref_api_works_url),
            headers=self.headers,
            params=params,
        )
        if response is None:
            return []

        response.raise_for_status()
        data = response.json()

        return data["message"].get("items", [])

    @override
    def _get_authors_from_api_item(self, item: dict) -> list[dict] | None:
        """Get authors of an item returned by the api."""
        return item.get("author")

    @override
    def _get_doi_from_api_item(self, item: dict) -> str | None:
        """Get doi of an item returned by the api."""
        return item.get("DOI")

    @override
    def _get_issns_groups_for_api(self, issns: list[str]) -> list[list[str]]:
        """Split ISSNs in groups that can be used as filters by API."""
        return [[issn] for issn in issns]

    @override
    def _get_type_from_api_item(self, item: dict) -> str | None:
        """Get type of an item returned by the api."""
        return item.get("type")

    @override
    def _set_metadata_attribute(
        self,
        work_metadata: WorkMetadata,
        item: dict,
    ) -> WorkMetadata:
        """Clean and update the metadata attribute and returns object."""
        work_metadata.crossref_metadata = self._clean_metadata(
            item,
            self.config.work_crossref_schema_blacklist_fields,
            "author",
            self.config.author_crossref_schema_blacklist_fields,
        )
        return work_metadata

    @override
    def _validate_author(self, input_author: str, api_author: dict) -> bool:
        """Verify that input input and api authors are similar.

        Warning: For crossref, strict comparison, case insensitive. If name slightly
        differs (e.g. VanDijk vs Van Dijk, comparison returns False)
        """
        if not input_author:
            return False
        if "family" in api_author:
            api_author_name = api_author["family"]
        elif "given" in api_author:
            api_author_name = api_author["given"]
        elif "name" in api_author:
            api_author_name = api_author["name"]
        else:
            return False
        return self._normalize_string(input_author) == self._normalize_string(
            api_author_name,
        )
