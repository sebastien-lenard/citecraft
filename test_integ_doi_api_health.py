import sys
from doi_fetcher import DoiFetcher

def test_doi_service_health():
    print("Checking DOI Content Negotiation Service...")
    fetcher = DoiFetcher()
    
    # DOI for Steady erosion rates in the Himalayas through late Cenozoic climatic changes
    test_doi = "10.1038/s41561-020-0585-2"
    test_style = "apa"
    
    try:
        reference = fetcher.get_formatted_reference(test_doi, test_style)
        print(reference)
        if reference != "Reference unavailable in doi.org." and len(reference) > 10:
            print("[OK] DOI service reachable and returned formatted reference.")
            print(f"Sample: {reference[:60]}...")
        else:
            print("[FAIL] DOI service returned unexpected 'unavailable' message or empty string.")
            sys.exit(1)

        # Check for specific expected content in the APA citation
        if "Nature Geoscience" in reference:
            print("[OK] Citation content looks accurate.")
        else:
            print("[WARNING] Citation content did not contain expected publisher name.")

        print("--- DOI HEALTH CHECK PASSED ---")

    except Exception as e:
        print(f"[FAIL] An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_doi_service_health()
