import sys
from style_fetcher import StyleFetcher
from config_loader import CROSSREF_API_EMAIL

def check_style_api_health():
    print("Checking Crossref Style API health  via RequestsWrapper...")
    
    # 'apa' is a standard style that should always exist
    fetcher = StyleFetcher("apa")
    headers = {'User-Agent': f'ManuscriptRefLister/1.0 (mailto:{CROSSREF_API_EMAIL})'}
    
    try:
        fetcher.check_style_is_valid()
        
        if fetcher.style_is_valid is True:
            print("[OK] Style API is reachable and 'apa' was found.")
        elif fetcher.style_is_valid is False:
            print("[FAIL] API reachable, but 'apa' style was not found in the list.")
            sys.exit(1)
        else:
            print("[FAIL] API call failed (status code was not 200).")
            sys.exit(1)

        # Check for Polite Pool headers for extra safety
        response = fetcher.requests_wrapper.get(fetcher.base_url, headers=headers,
                                                max_retries=1)

        limit = response.headers.get('X-Rate-Limit-Limit')
        if limit:
            print(f"[OK] Rate limiting recognized (Limit: {limit}).")
        else:
            print("[WARNING] X-Rate-Limit-Limit header missing.")

        print("--- STYLE HEALTH CHECK PASSED ---")

    except Exception as e:
        print(f"[FAIL] An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_style_api_health()
