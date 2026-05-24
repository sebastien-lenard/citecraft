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
        """Gets the metadata of a work in CSL-JSON format via content negotiation."""
        headers = {"Accept": "application/vnd.citationstyles.csl+json"}

        try:
            res = self.http_client_wrapper.get(
                self.config.doi_api_url.replace("{doi}", str(doi)), headers=headers
            )
            csl_data = res.json()
            logger.debug(
                "Successfully resolved CSL-JSON metadata for DOI: %s",
                doi,
                extra={
                    "status": "OK",
                    "event": "doi_csl_json_success",
                    "doi": doi,
                },
            )
            return csl_data
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

    def get_reference(self, doi: str, style: str = "apa") -> str:
        """Gets the reference formatted to a style and ready to include in a
        bibliography.
        Examples of styles:
        apa (AGU, Wiley), copernicus-publications (EGU), elsevier-harvard (Elsevier),
        chicago-author-date (Taylor & Francis), springer-basic-author-date (Springer),
        etc. Must have been validated using StyleRepository.
        Warning: doesn't handle the case when the style is not supported."""
        headers = {"Accept": f"text/x-bibliography; style={style}"}

        try:
            res = self.http_client_wrapper.get(
                self.config.doi_api_url.replace("{doi}", str(doi)), headers=headers
            )  # DOI Content Negotiation Service
            res.encoding = "utf-8"
            reference_text = res.text.strip()
            logger.debug(
                "Successfully resolved bibliographic reference for DOI: %s",
                doi,
                extra={
                    "status": "OK",
                    "event": "doi_resolution_success",
                    "doi": doi,
                    "style": style,
                },
            )
            return reference_text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "DOI not found (404) via content negotiation: %s",
                    doi,
                    extra={
                        "status": "KO",
                        "event": "doi_not_found",
                        "doi": doi,
                        "status_code": 404,
                    },
                )
                return "Reference unavailable in doi.org."
            raise e
