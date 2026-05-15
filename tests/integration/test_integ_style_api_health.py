import sys
import traceback

import pytest
import requests

from manuscript_reference_lister.repositories import StyleRepository


@pytest.mark.integration
def test_style_api_health() -> None:
    print("Checking Crossref Style API health via RequestsWrapper...")

    # 'apa' is a standard style that should always exist
    repo = StyleRepository("apa")
    headers = {
        "User-Agent": f"ManuscriptRefLister/1.0 (mailto:{repo.config.crossref_api_email})"
    }

    try:
        repo.validate_favored_style()

        if repo.favored_style_is_valid is True:
            print("[OK] Style API is reachable and 'apa' was found.")
        elif repo.favored_style_is_valid is False:
            print("[FAIL] API reachable, but 'apa' style was not found in the list.")
            sys.exit(1)
        else:
            print("[FAIL] API call failed (status code was not 200).")
            sys.exit(1)

        # Check for Polite Pool headers for extra safety
        response = repo.http_client_wrapper.get(
            repo.config.crossref_api_styles_url, headers=headers, max_retries=1
        )

        limit = response.headers.get("X-Rate-Limit-Limit")
        if limit:
            print(f"[OK] Rate limiting recognized (Limit: {limit}).")
        else:
            print("[WARNING] X-Rate-Limit-Limit header missing.")

        print("--- STYLE HEALTH CHECK PASSED ---")

    except requests.exceptions.HTTPError as e:
        print("\n[FAIL] HTTP Error detected!")
        print(f"Status Code: {e.response.status_code}")
        print(f"URL: {e.response.url}")
        print(f"Response Body: {e.response.text[:200]}...")
        sys.exit(1)

    except KeyError as e:
        print("\n[FAIL] Data Structure Error (JSON Schema mismatch)!")
        print(f"Missing key in JSON: {e}")
        traceback.print_exc(limit=1)
        sys.exit(1)

    except Exception as e:
        print(f"\n[FAIL] Unexpected Exception of type {type(e).__name__}:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_style_api_health()
