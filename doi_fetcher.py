import requests
import time
from config_loader import DOI_API_DELAY, DOI_API_TIMEOUT
from config_loader import DOI_API_URL

class DoiFetcher:
    """Handles calls to doi.org, to get full formatted references.
    Done using DOI Content Negotiation Service."""

    def __init__(self):
        self.base_url = DOI_API_URL
        self.delay = DOI_API_DELAY
        self.timeout = DOI_API_TIMEOUT

    def get_formatted_reference(self, doi, style):
        """Requests the reference version formatted to a specific style via content
        negotiation."""
        time.sleep(self.delay)
        headers = {'Accept': f"text/x-bibliography; style={style}"}

        try:
            res = requests.get(self.base_url.replace("{doi}", str(doi)),
                               headers=headers,
                               timeout=self.timeout)
            if res.status_code == 200:
                return res.text.strip()
        except:
            pass
        return "Reference unavailable in doi.org."
