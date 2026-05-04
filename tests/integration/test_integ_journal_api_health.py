import sys
import traceback

import requests

from manuscript_reference_lister import config_loader
from manuscript_reference_lister.repositories import JournalRepository


def check_integ_journals_api_health() -> None:
    print(
        "Checking Crossref API Journals health, schema, and Rate Limit status via "
        "RequestsWrapper..."
    )
    repo = JournalRepository()
    headers = {
        "User-Agent": f"ManuscriptRefLister/1.0 (mailto:{
            config_loader.CROSSREF_API_EMAIL
        })"
    }

    # Using a known journal
    input_title = "The Journal of Geology"

    try:
        # On utilise le wrapper du repo.
        # On force max_retries=1 pour un diagnostic "sec" sans répétition.
        response = repo.requests_wrapper.get(
            repo.base_url,
            params={"query": input_title, "rows": 1},
            headers=headers,
            max_retries=1,
        )

        headers = response.headers

        # 1. Rate Limit & Polite Pool Check
        limit = headers.get("X-Rate-Limit-Limit")

        if limit:
            print(
                f"[OK] Polite Pool Active (via Wrapper): Limit is {limit} requests "
                "per {interval}."
            )
        else:
            print(
                "[WARNING] Rate limit headers not found. Check if email is correctly "
                "passed by Wrapper."
            )

        # 2. Schema and Data Check
        data = response.json()
        items = data.get("message", {}).get("items", [])

        if not items:
            print("[FAIL] API reachable but returned no items for a known journal.")
            sys.exit(1)

        sample_item = items[0]
        true_title = sample_item.get("title", ["No title found"])
        issns = sample_item.get("ISSN", [])

        print(f"[OK] Schema OK: Found '{true_title}' with ISSNs: {issns}")

        # 3. Date Format Check
        print("Testing date extraction logic...")
        results = repo.get_journal_metadata(input_title)

        if results and isinstance(results[0].get("start_year"), int):
            print(
                f"[OK] Date Logic OK: Extracted year {results[0]['start_year']} as "
                "integer."
            )
        else:
            print("[FAIL] Could not extract integer years from API response.")
            sys.exit(1)

        print("\n--- ALL SYSTEMS GO ---")

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
    check_integ_journals_api_health()
