import json

import pytest
from pydantic import ValidationError

from manuscript_reference_lister.schemas.csl_reference import CSLReference


def test_valid_minimal_reference():
    """Verify that a standard CSL-JSON dictionary with required roots passes
    validation."""
    raw_data = {
        "id": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "title": "Steady erosion rates in the Himalayas",
    }

    validated = CSLReference.model_validate(raw_data)

    assert validated.id == "10.1038/s41561-020-0585-2"
    assert validated.type == "article-journal"
    assert validated.title == "Steady erosion rates in the Himalayas"


def test_missing_id_fallback_to_doi():
    """Verify that if 'id' is missing but 'DOI' is present, 'id' is auto-populated."""
    raw_data = {
        "DOI": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
    }

    validated = CSLReference.model_validate(raw_data)

    assert validated.id == "10.1038/s41561-020-0585-2"
    assert validated.DOI == "10.1038/s41561-020-0585-2"


def test_validation_error_when_both_id_and_doi_missing():
    """Verify that validation fails if both 'id' and 'DOI' are missing entirely."""
    raw_data = {
        "type": "article-journal",
        "title": "A paper without identifiers",
    }

    with pytest.raises(ValidationError) as exc_info:
        CSLReference.model_validate(raw_data)

    assert "id" in str(exc_info.value)


def test_issn_array_extraction():
    """Verify that an ISSN array is handled by extracting only the first entry
    string."""
    json_metadata = (
        '{"id":"10.13039/100010665","type":"journal-article","ISSN":["1991-9603", '
        '"1758-0471"]}'
    )
    csl_metadata = json.loads(json_metadata)

    validated = CSLReference.model_validate(csl_metadata)

    # It must pull out only the first element, ignoring the rest
    assert validated.ISSN == "1991-9603"


def test_issn_single_string_remains_unchanged():
    """Verify that a single plain text ISSN string remains unaffected."""
    raw_data = {"id": "some_id", "type": "book", "ISSN": "1234-567X"}

    validated = CSLReference.model_validate(raw_data)
    assert validated.ISSN == "1234-567X"


def test_extra_fields_ignored_automatically():
    """Verify that unsupported keys (like CrossRef's 'sequence') are silently
    discarded."""
    raw_data = {
        "id": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "extra_garbage_field": "should be ignored",
    }

    validated = CSLReference.model_validate(raw_data)

    # Exporting back to JSON or a dict should reveal the field was discarded
    exported_dict = validated.model_dump()
    assert "extra_garbage_field" not in exported_dict
