import pytest

from citecraft.repositories import JournalRepository


@pytest.mark.integration
@pytest.mark.vcr
def test_integ_journals_api_health() -> None:
    """Check Crossref API Journals health, schema, and Rate Limit status."""
    repo = JournalRepository()
    headers = {
        "User-Agent": f"ManuscriptRefLister/1.0 (mailto:{repo.config.user_email})"
    }
    input_title = "The Journal of Geology"

    response, _ = repo.http_client_wrapper.get(
        repo.config.crossref_api_journals_url,
        params={"query": input_title, "rows": 1},
        headers=headers,
    )

    limit = response.headers.get("X-Rate-Limit-Limit")
    assert limit is not None, "Rate limit headers (X-Rate-Limit-Limit) not found."

    data = response.json()
    items = data.get("message", {}).get("items", [])
    assert len(items) > 0, f"API reachable but returned no items for '{input_title}'."

    sample_item = items[0]
    assert "title" in sample_item, "Schema mismatch: 'title' field is missing."
    assert "ISSN" in sample_item, "Schema mismatch: 'ISSN' field is missing."

    results = repo.get_journal_metadata(input_title)
    assert len(results) > 0, f"No journal metadata extracted for '{input_title}'."
    assert isinstance(results[0].start_year, int), (
        f"Date extraction logic failed: expected int, got {type(results[0].start_year)}"
    )
