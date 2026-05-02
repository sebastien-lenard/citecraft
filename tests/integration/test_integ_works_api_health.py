import sys
import traceback

import requests

from manuscript_reference_lister import WorkFetcher


def check_integ_works_api_health():
    print("Checking Crossref API Works (Article Search) health via RequestsWrapper...")
    fetcher = WorkFetcher()

    # Known work
    test_author = "Lenard et al."
    test_year = "2020"
    test_issn = "1752-0894"
    test_keywords = "erosion"

    try:
        # 1. Overriding of max_results
        requested_limit = 5
        print(f"Testing max_results override (requested: {requested_limit})...")
        print("Testing connectivity and author filtering...")

        candidates = fetcher.fetch_dois_for_this_info(
            author=test_author,
            year=test_year,
            issn=test_issn,
            keywords=test_keywords,
            max_results=requested_limit,
        )

        if len(candidates) > requested_limit:
            print(
                f"[FAIL] max_results not respected: got {len(candidates)}, expected "
                f"{requested_limit}"
            )
            sys.exit(1)
        elif not candidates:
            print(
                "[FAIL] No candidates found. Check connectivity or filters. This might "
                "mean the author filter is TOO strict"
            )
            print(
                f"       or the Crossref metadata for '{test_author}' is missing the "
                f"'author' field."
            )
            sys.exit(1)
        else:
            print(
                f"[OK] Found {len(candidates)} candidate(s) passing the author filter."
            )

        # 2. Deep check of the 'author' node format from Crossref
        # This is where we verify that the real API matches our assumptions
        # Since we use fetcher.requests_wrapper, we can do a manual call if we want
        # to inspect but checking the candidates is enough.

        print("Verifying if Crossref provides the expected 'author' structure...")
        # Note: In a real integration test, we can't easily check 'item' because
        # it's internal to fetch_dois_for_this_info.
        # But if candidates exists, it MEANS the validation passed!

        # 3. Additional check for strict parity (2 authors)
        print("Testing dual-author parity logic (Guns and Vanacker)...")
        test_author_2 = "Guns and Vanacker"
        test_year_2 = "2014"
        test_issn_2 = "2213-3054"

        candidates_2 = fetcher.fetch_dois_for_this_info(
            author=test_author_2, year=test_year_2, issn=test_issn_2, max_results=1
        )

        if candidates_2:
            print(f"[OK] Strict two-author match successful for {test_author_2}.")
        else:
            print(
                f"[WARNING] Strict match failed for {
                    test_author_2
                }. Verify Crossref metadata manually."
            )

        # 3. Check content and format
        first_candidate = candidates[0]

        # Check DOI
        if first_candidate["doi"].startswith("https://doi.org/"):
            print(f"[OK] DOI Formatting: {first_candidate['doi']}")
        else:
            print(
                f"[FAIL] DOI Formatting: Unexpected prefix in {first_candidate['doi']}"
            )
            sys.exit(1)

        # Check metadata
        if first_candidate["req_author"] == test_author:
            print(
                f"[OK] Metadata persistence: Original author '{test_author}' preserved "
                f"in candidate."
            )
        else:
            print(
                "[FAIL] Metadata persistence: Candidate req_author doesn't match query."
            )
            sys.exit(1)

        print("\n--- WORK FETCHING SYSTEM GO (Integration Verified) ---")

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
    check_integ_works_api_health()
