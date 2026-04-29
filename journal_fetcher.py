import requests
import time
import warnings
from config_loader import CROSSREF_API_DELAY, CROSSREF_API_EMAIL, CROSSREF_API_TIMEOUT
from config_loader import CROSSREF_API_JOURNALS_URL, CROSSREF_API_JOURNALS_ISSN_URL

class JournalFetcher:
    """
    Handles API calls to Crossref about journals.
    """
    def __init__(self):
        self.email = CROSSREF_API_EMAIL
        self.headers = {'User-Agent': f'ManuscriptRefLister/1.0 (mailto:{self.email})'}
        self.base_url = CROSSREF_API_JOURNALS_URL
        self.issn_url = CROSSREF_API_JOURNALS_ISSN_URL
        self.delay = CROSSREF_API_DELAY
        self.timeout = CROSSREF_API_TIMEOUT

    def get_issns_and_dates_by_name(self, journal_name):
        """
        Retrieves the first match from Crossref, get min/max publication dates and returns a list of dictionaries,
        one for each ISSN associated with that journal.
        """
        time.sleep(self.delay)
        params = {
            "query": journal_name,
            "rows": 200, # Pull a large enough batch to find all matches
            "mailto": self.email
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            items = response.json().get('message', {}).get('items', [])

            if items:
                exact_matches = [
                    item for item in items 
                    if item.get('title', '').strip() == journal_name
                ]
                items = exact_matches
                item = items[0]
                title = item.get('title', "")
                publisher = item.get('publisher', "")
                issns = item.get('ISSN', [])
                issns = list(dict.fromkeys(item.get('ISSN', []))) # remove duplicates
                
                # Create a list of dicts, one per ISSN
                record_list = []
                for issn in issns:
                    # For each ISSN, try to find its specific publication range
                    dates = {"min_year": self.get_year_endpoint(issn, "asc"), 
                        "max_year": self.get_year_endpoint(issn, "desc")}

                    record_list.append({
                        "requested_title": journal_name,
                        "title": title,
                        "publisher": publisher,
                        "issn": issn,
                        "start_year": dates["min_year"],
                        "end_year": dates["max_year"]
                    })
            else:
                record_list.append({
                            "requested_title": journal_name,
                            "title": "",
                            "publisher": "",
                            "issn": 0,
                            "start_year": 1600,
                            "end_year": 2099
                        })
                warnings.warn(f"[WARNING] Journal {journal_name} not found.")
            return record_list

        except Exception:
            return None

    def get_year_endpoint(self, issn, order):
        """Helper to fetch the oldest or newest work year for an ISSN.
        order: asc or desc."""
        params = {
            "sort": "published",
            "order": order,
            "rows": 1,
            "mailto": self.email
        }
        time.sleep(self.delay)
        try:
            response = requests.get(self.issn_url.replace("{issn}", str(issn)), 
                                    params=params, timeout=self.timeout)
            response.raise_for_status()
            items = response.json().get('message', {}).get('items', [])
            if not items:
                return None
            
            # Crossref works use 'published-print' or 'published-online'
            work = items[0]
            p_date = work.get('published-print', {}).get('date-parts', [[None]])[0][0]
            o_date = work.get('published-online', {}).get('date-parts', [[None]])[0][0]
            
            # Return the earliest or latest year found between print/online
            years = [y for y in [p_date, o_date] if y is not None]
            return min(years) if order == "asc" and years else max(years) if years else None
        except:
            return None
