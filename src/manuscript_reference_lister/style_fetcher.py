from . import config_loader
from .requests_wrapper import RequestsWrapper


class StyleFetcher:
    """
    Handles API calls to Crossref about styles, e.g. style=apa.
    """

    def __init__(self, style):
        """
        style: reference style, e.g. apa"""
        self.email = config_loader.CROSSREF_API_EMAIL
        self.headers = {"User-Agent": f"ManuscriptRefLister/1.0 (mailto:{self.email})"}
        self.base_url = config_loader.CROSSREF_API_STYLES_URL
        self.style = style
        self.style_is_valid = None
        self.requests_wrapper = RequestsWrapper(
            config_loader.CROSSREF_API_EMAIL,
            timeout=config_loader.CROSSREF_API_TIMEOUT,
            max_retries=config_loader.CROSSREF_API_MAX_RETRY,
            delay=config_loader.CROSSREF_API_DELAY,
        )

    def check_style_is_valid(self):
        """Fetch the official list of supported styles and check the validity of the
        style
        """
        response = self.requests_wrapper.get(self.base_url, headers=self.headers)
        supported_styles = response.json()["message"]["items"]
        if self.style in supported_styles:
            self.style_is_valid = True
        else:
            self.style_is_valid = False
