import logging

from . import config_loader
from .requests_wrapper import RequestsWrapper


class StyleRepository:
    """Handles information about reference styles."""

    def __init__(self, favored_style: str = "apa"):
        """
        Examples of styles:
        apa (AGU, Wiley), copernicus-publications (EGU), elsevier-harvard (Elsevier),
        chicago-author-date (Taylor & Francis), springer-basic-author-date (Springer),
        etc.
        """
        self.email = config_loader.CROSSREF_API_EMAIL
        self.headers = {"User-Agent": f"ManuscriptRefLister/1.0 (mailto:{self.email})"}
        self.base_url = config_loader.CROSSREF_API_STYLES_URL
        self.favored_style = favored_style
        self.favored_style_is_valid = None
        self.requests_wrapper = RequestsWrapper(
            config_loader.CROSSREF_API_EMAIL,
            timeout=config_loader.CROSSREF_API_TIMEOUT,
            max_retries=config_loader.CROSSREF_API_MAX_RETRY,
            delay=config_loader.CROSSREF_API_DELAY,
        )

    def validate_favored_style(self) -> None:
        """Check is the favored reference style is in the repository and supported."""
        response = self.requests_wrapper.get(self.base_url, headers=self.headers)
        valid_styles = response.json()["message"]["items"]
        if self.favored_style in valid_styles:
            self.favored_style_is_valid = True
        else:
            self.favored_style_is_valid = False
            logging.warning("Invalid style %s.", self.favored_style)
