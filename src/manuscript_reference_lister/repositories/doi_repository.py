import json
import logging

import httpx

from manuscript_reference_lister.network import (
    HTTPClientWrapper,
    get_http_client_registry,
)
from manuscript_reference_lister.utils import AppConfig, get_config

logger = logging.getLogger(__name__)


class DoiRepository:
    """Handles information specific to the DOI of a work."""

    def __init__(
        self, config: AppConfig | None = None, registry: HTTPClientWrapper | None = None
    ):
        self.config = config or get_config()
        registry = registry or get_http_client_registry()
        self.http_client_wrapper = registry.get_client("doi")

    def get_metadata(self, doi: str) -> dict[str, any]:
        """Gets the metadata of a work in CSL-JSON format via content negotiation.
        Ensures that metadata contains an attribute id, necessary to get a reference
        using ReferenceService::get_reference() and not supplied by default using
        DOI negotiation.
        """
        headers = {"Accept": "application/vnd.citationstyles.csl+json"}

        try:
            res = self.http_client_wrapper.get(
                self.config.doi_api_url.replace("{doi}", str(doi)), headers=headers
            )
            res.raise_for_status()
            csl_metadata = res.json()

            if "id" not in csl_metadata:
                if "DOI" in csl_metadata:
                    csl_metadata["id"] = csl_metadata["DOI"]
                else:
                    compact_json = json.dumps(csl_metadata, separators=(",", ":"))
                    logger.debug(
                        "Invalid CSL-JSON content: %s",
                        compact_json,
                        extra={
                            "status": "KO",
                            "event": "doi_csl_json_dump",
                            "doi": doi,
                        },
                    )
                    logger.warning(
                        (
                            "CSL-JSON metadata invalid (missing 'id' and 'DOI' field) for"
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

            work_blacklist_fields = getattr(
                self.config, "work_cls_schema_blacklist_fields", []
            )
            for field in work_blacklist_fields:
                csl_metadata.pop(field, None)

            author_blacklist_fields = getattr(
                self.config, "author_cls_schema_blacklist_fields", []
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
            if e.response.status_code == 404:
                logger.warning(
                    "DOI not found (404) for CSL-JSON: %s",
                    doi,
                    extra={
                        "status": "KO",
                        "event": "doi_csl_json_not_found",
                        "doi": doi,
                        "status_code": 404,
                    },
                )
                return {}
            raise e
