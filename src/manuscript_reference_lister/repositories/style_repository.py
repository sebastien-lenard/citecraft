import logging

import httpx

from manuscript_reference_lister.network import (
    HTTPClientWrapper,
    get_http_client_registry,
)
from manuscript_reference_lister.utils import AppConfig, get_config

logger = logging.getLogger(__name__)


class StyleRepository:
    """Handles information about reference styles by fetching CSL files."""

    def __init__(
        self,
        favored_style: str = "apa",
        config: AppConfig | None = None,
        registry: HTTPClientWrapper | None = None,
    ):
        """Examples of styles:
        apa (AGU, Wiley), copernicus-publications (EGU), elsevier-harvard (Elsevier),
        chicago-author-date (Taylor & Francis), springer-basic-author-date (Springer),
        etc.
        """
        self.config = config or get_config()
        registry = registry or get_http_client_registry()
        self.http_client_wrapper = registry.get_client("github")
        self.headers = {"User-Agent": "ManuscriptRefLister/1.0"}
        self.favored_style = favored_style
        self.favored_style_is_valid: bool | None = None
        self.csl_content: str | None = None

    def fetch_style_metadata(self) -> None:
        """Fetches the CSL file content for the favored style from the repository."""
        url = self.config.style_repo_url.replace("{style}", str(self.favored_style))

        try:
            res = self.http_client_wrapper.get(url, headers=self.headers)
            res.raise_for_status()
            self.csl_content = res.text
            logger.debug(
                "Successfully fetched CSL metadata for style: %s", self.favored_style
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "CSL style file not found (404) at URL: %s",
                    url,
                    extra={
                        "status": "KO",
                        "event": "style_file_not_found",
                        "style": self.favored_style,
                        "status_code": 404,
                    },
                )
                self.csl_content = None
                return
            raise e

    def validate_favored_style(self) -> None:
        """Check if the favored reference style content is structurally valid."""
        if not self.csl_content:
            self.favored_style_is_valid = False
            logger.warning(
                "Cannot validate style %s: No CSL content loaded.", self.favored_style
            )
            return

        content = self.csl_content.strip()

        # TODO: schema validation
        start_valid = content.startswith(
            '<?xml version="1.0" encoding="utf-8"?>\n<style xmlns="http://purl.org/net/xbiblio/csl"'
        ) or content.startswith(
            '<?xml version="1.0" encoding="utf-8"?>\n\n<style xmlns="http://purl.org/net/xbiblio/csl"'
        )  # Accounts for flexible newline formatting

        # Standardizing strict check to match requirements precisely
        start_marker = '<?xml version="1.0" encoding="utf-8"?>\n<style xmlns="http://purl.org/net/xbiblio/csl"'
        end_marker = "</style>"

        if content.replace("\r\n", "\n").startswith(start_marker) and content.endswith(
            end_marker
        ):
            self.favored_style_is_valid = True
            logger.info(
                "Favored reference style validated successfully: %s",
                self.favored_style,
                extra={
                    "status": "OK",
                    "event": "style_validation_success",
                    "style": self.favored_style,
                },
            )
        else:
            self.favored_style_is_valid = False
            logger.warning(
                "Favored reference style content layout invalid: %s",
                self.favored_style,
                extra={
                    "status": "KO",
                    "event": "style_validation_failed",
                    "style": self.favored_style,
                },
            )
