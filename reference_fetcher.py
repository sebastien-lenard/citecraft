import requests
import time
from config_loader import API_DELAY, CROSSREF_EMAIL, CONTEXT_KEYWORDS, MAX_RESULTS

class ReferenceFetcher:
    """
    Handles API calls to Crossref with multi-result support and scoring.
    """
    def __init__(self):
        self.email = CROSSREF_EMAIL
        self.headers = {'User-Agent': f'ManuscriptRefLister/1.0 (mailto:{self.email})'}
        self.base_url = "https://api.crossref.org/works"

    def fetch_apa_candidates(self, author, year, keywords=None):
        """
        Searches for references and returns a list of potential matches.
        'keywords' can be passed as a parameter (e.g., from a UI or CLI).
        """
        time.sleep(API_DELAY)
        
        # Use provided keywords or fallback to config
        search_context = keywords if keywords is not None else CONTEXT_KEYWORDS
        query = f"{author} {year} {search_context}"
        
        params = {
            'query': query,
            'rows': MAX_RESULTS,
            'filter': f'from-pub-date:{year},until-pub-date:{year}'
        }

        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            items = data['message'].get('items', [])
            candidates = []

            for item in items:
                doi = item.get('DOI')
                if doi:
                    apa_string = self._get_formatted_apa(doi)
                    candidates.append({
                        'apa': apa_string,
                        'doi': f"https://doi.org/{doi}",
                        'score': item.get('score', 0),
                        'type': item.get('type', 'unknown')
                    })
            return candidates
            
        except Exception as e:
            print(f"API Error for {query}: {e}")
            return []

    def _get_formatted_apa(self, doi):
        """Requests the formatted APA version via content negotiation."""
        url = f"https://doi.org/{doi}"
        headers = {'Accept': 'text/x-bibliography; style=apa'}
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                return res.text.strip()
        except:
            pass
        return "APA Format unavailable"