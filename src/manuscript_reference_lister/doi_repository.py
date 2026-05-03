import logging

import requests

from . import config_loader
from .requests_wrapper import RequestsWrapper


class DoiRepository:
    """Handles calls to doi.org, to get full formatted references.
    Done using DOI Content Negotiation Service."""

    def __init__(self):
        self.base_url = config_loader.DOI_API_URL
        self.requests_wrapper = RequestsWrapper(
            config_loader.CROSSREF_API_EMAIL,
            timeout=config_loader.DOI_API_TIMEOUT,
            max_retries=config_loader.DOI_API_MAX_RETRY,
            delay=config_loader.DOI_API_DELAY,
        )

    def get_formatted_reference(self, doi, style):
        """Requests the reference version formatted to a specific style via content
        negotiation."""
        headers = {"Accept": f"text/x-bibliography; style={style}"}

        try:
            res = self.requests_wrapper.get(
                self.base_url.replace("{doi}", str(doi)), headers=headers
            )
            return res.text.strip()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.warning("DOI not found (404): %s", doi)
                return "Reference unavailable in doi.org."
            # raise for HTTP error other than (500, 403, etc.)
            raise e
