import requests
import sys
from journal_fetcher import JournalFetcher

def check_integ_journals_api_health():
    print("Checking Crossref API Journals health, schema, and Rate Limit status...")
    fetcher = JournalFetcher()
    
    # Using a known journal
    test_journal = "The Journal of Geology"
    
    try:
        # Manually call requests to inspect headers
        params = {"query": test_journal, "rows": 1, "mailto": fetcher.email}
        response = requests.get(fetcher.base_url, params=params, timeout=10)
        response.raise_for_status()
        
        headers = response.headers
        
        # 1. Rate Limit & Polite Pool Check
        limit = headers.get('X-Rate-Limit-Limit')
        interval = headers.get('X-Rate-Limit-Interval')
        
        if limit:
            print(f"[OK] Polite Pool Active: Limit is {limit} requests per {interval}.")
        else:
            print("[WARNING] Rate limit headers not found. You might be in the 'Public' pool.")
            print("          Check if CROSSREF_API_EMAIL is correctly set.")

        # 2. Schema and Data Check
        data = response.json()
        items = data.get('message', {}).get('items', [])
        
        if not items:
            print("[FAIL] API reachable but returned no items for a known journal.")
            sys.exit(1)
            
        sample_item = items[0]
        title = sample_item.get('title', ["No title found"])
        issns = sample_item.get('ISSN', [])
        
        print(f"[OK] Schema OK: Found '{title}' with ISSNs: {issns}")

        # 3. Date Format Check
        print("Testing date extraction logic...")
        results = fetcher.get_issns_and_dates_by_name(test_journal)
        
        if results and isinstance(results[0].get('start_year'), int):
            print(f"[OK] Date Logic OK: Extracted year {results[0]['start_year']} as integer.")
        else:
            print("[FAIL] Could not extract integer years from API response.")
            sys.exit(1)

        print("\n--- ALL SYSTEMS GO ---")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("[FAIL] Rate limit exceeded (429 Too Many Requests).")
        else:
            print(f"[FAIL] HTTP Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_integ_journals_api_health()
