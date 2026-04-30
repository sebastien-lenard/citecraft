import sys
import requests, traceback
from journal_fetcher import JournalFetcher
from config_loader import CROSSREF_API_EMAIL

def check_integ_journals_api_health():
    print("Checking Crossref API Journals health, schema, and Rate Limit status via RequestsWrapper...")
    fetcher = JournalFetcher()
    headers = {'User-Agent': f'ManuscriptRefLister/1.0 (mailto:{CROSSREF_API_EMAIL})'}
    
    # Using a known journal
    test_journal = "The Journal of Geology"
    
    try:
        # On utilise le wrapper du fetcher. 
        # On force max_retries=1 pour un diagnostic "sec" sans répétition.
        response = fetcher.requests_wrapper.get(
            fetcher.base_url, 
            params={"query": test_journal, "rows": 1}, headers=headers,
            max_retries=1
        )
        
        headers = response.headers
        
        # 1. Rate Limit & Polite Pool Check
        limit = headers.get('X-Rate-Limit-Limit')
        interval = headers.get('X-Rate-Limit-Interval')
        
        if limit:
            print(f"[OK] Polite Pool Active (via Wrapper): Limit is {limit} requests per {interval}.")
        else:
            print("[WARNING] Rate limit headers not found. Check if email is correctly passed by Wrapper.")

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
        print(f"\n[FAIL] HTTP Error detected!")
        print(f"Status Code: {e.response.status_code}")
        print(f"URL: {e.response.url}")
        print(f"Response Body: {e.response.text[:200]}...")
        sys.exit(1)

    except KeyError as e:
        print(f"\n[FAIL] Data Structure Error (JSON Schema mismatch)!")
        print(f"Missing key in JSON: {e}")
        traceback.print_exc(limit=1) 
        sys.exit(1)

    except Exception as e:
        print(f"\n[FAIL] Unexpected Exception of type {type(e).__name__}:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_integ_journals_api_health()
