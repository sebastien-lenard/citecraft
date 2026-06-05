# src/citecraft/repositories/doi_repository.py
import json
import logging
from http import HTTPStatus
from typing import Any

import httpx

from citecraft.network import (
    HTTPClientRegistry,
    HTTPClientWrapper,
    get_http_client_registry,
)
from citecraft.schemas import DoiType
from citecraft.utils import AppConfig, get_config

logger = logging.getLogger(__name__)


class DoiRepository:
    """Handles metadata extraction and processing specific to DOI resources."""

    def __init__(
        self,
        config: AppConfig | None = None,
        registry: HTTPClientRegistry | None = None,
    ) -> None:
        self.config: AppConfig = config or get_config()
        registry = registry or get_http_client_registry()
        self.http_client_wrapper: HTTPClientWrapper = registry.get_client("doi")

    def get_metadata(self, doi: DoiType) -> dict[str, Any]:
        """Retrieve CSL-JSON metadata via DOI content negotiation.
        Ensures that metadata contains an attribute id or DOI, necessary for
        CSLReference validation.
        """
        headers = {"Accept": "application/vnd.citationstyles.csl+json"}
        url = self.config.doi_api_url.replace("{object_name}", str(doi))

        try:
            res, _ = self.http_client_wrapper.get(url, headers=headers)
            res.raise_for_status()
            csl_metadata = res.json()

            if (
                "id" not in csl_metadata
                and "DOI" not in csl_metadata
                and "doi" not in csl_metadata
            ):
                logger.debug(
                    "Invalid CSL-JSON content: %s",
                    json.dumps(csl_metadata, separators=(",", ":")),
                    extra={
                        "status": "KO",
                        "event": "doi_csl_json_dump",
                        "doi": doi,
                    },
                )
                logger.warning(
                    (
                        "CSL-JSON metadata invalid (missing 'id' and 'DOI'/'doi' field) for"
                        " DOI:%s"
                    ),
                    doi,
                    extra={
                        "status": "KO",
                        "event": "doi_csl_json_invalid_id_and_doi",
                        "doi": doi,
                    },
                )
                return {}

            # Purge configured blacklisted fields
            work_blacklist_fields = self.config.work_crossref_schema_blacklist_fields
            for field in work_blacklist_fields:
                csl_metadata.pop(field, None)

            author_blacklist_fields = (
                self.config.author_crossref_schema_blacklist_fields
            )
            if (
                author_blacklist_fields
                and "author" in csl_metadata
                and isinstance(csl_metadata["author"], list)
            ):
                for author_entry in csl_metadata["author"]:
                    if isinstance(author_entry, dict):
                        for sub_field in author_blacklist_fields:
                            author_entry.pop(sub_field, None)

            logger.debug(
                "Successfully resolved CSL-JSON metadata for DOI: %s",
                doi,
                extra={
                    "status": "OK",
                    "event": "doi_csl_json_success",
                    "doi": doi,
                },
            )
            return csl_metadata

        except json.JSONDecodeError:
            logger.warning(
                "Invalid format for CSL-JSON: %s",
                doi,
                extra={
                    "status": "KO",
                    "event": "doi_csl_json_invalid_format",
                    "doi": doi,
                },
            )
            return {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                logger.warning(
                    "DOI not found (%d) for CSL-JSON: %s",
                    HTTPStatus.NOT_FOUND,
                    doi,
                    extra={
                        "status": "KO",
                        "event": "doi_csl_json_not_found",
                        "doi": doi,
                        "status_code": HTTPStatus.NOT_FOUND,
                    },
                )
                return {}
            raise e
