import sys
import traceback

import requests

from manuscript_reference_lister import DoiFetcher


def test_doi_service_health():
    print("Checking DOI Content Negotiation Service  via RequestsWrapper...")
    fetcher = DoiFetcher()

    # DOI for
    # Steady erosion rates in the Himalayas through late Cenozoic climatic changes
    test_doi = "10.1038/s41561-020-0585-2"
    test_style = "apa"

    try:
        reference = fetcher.get_reference(test_doi, test_style)
        print(reference)
        if reference != "Reference unavailable in doi.org." and len(reference) > 10:
            print("[OK] DOI service reachable and returned formatted reference.")
            print(f"Sample: {reference[:60]}...")
        else:
            print(
                "[FAIL] DOI service returned unexpected 'unavailable' message or "
                "empty string."
            )
            sys.exit(1)

        # Check for specific expected content in the APA citation
        if "Nature Geoscience" in reference:
            print("[OK] Citation content looks accurate.")
        else:
            print("[WARNING] Citation content did not contain expected publisher name.")

        print("--- DOI HEALTH CHECK PASSED ---")

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
    test_doi_service_health()
