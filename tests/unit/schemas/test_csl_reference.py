import json

import pytest
from pydantic import ValidationError

from manuscript_reference_lister.schemas.csl_reference import CSLReference


def test_valid_minimal_reference() -> None:
    """Verify that a standard CSL-JSON payload passes base validation rules."""
    raw_data = {
        "id": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "title": "Steady erosion rates in the Himalayas",
    }

    validated = CSLReference.model_validate(raw_data)

    assert validated.id == "10.1038/s41561-020-0585-2"
    assert validated.type == "article-journal"
    assert validated.title == "Steady erosion rates in the Himalayas"


def test_missing_id_fallback_to_doi() -> None:
    """Verify fallback mapping of DOI onto missing primary identifier keys."""
    raw_data = {
        "DOI": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
    }

    validated = CSLReference.model_validate(raw_data)

    assert validated.id == "10.1038/s41561-020-0585-2"
    assert validated.DOI == "10.1038/s41561-020-0585-2"


def test_validation_error_when_both_id_and_doi_missing() -> None:
    """Verify validation failure if both id and DOI fields are completely absent."""
    raw_data = {
        "type": "article-journal",
        "title": "A paper without identifiers",
    }

    with pytest.raises(ValidationError) as exc_info:
        CSLReference.model_validate(raw_data)

    assert "id" in str(exc_info.value)


def test_issn_array_extraction() -> None:
    """Verify selection of the primary entry when the ISSN contains list elements."""
    json_metadata = (
        '{"id":"10.13039/100010665","type":"journal-article","ISSN":["1991-9603", '
        '"1758-0471"]}'
    )
    csl_metadata = json.loads(json_metadata)

    validated = CSLReference.model_validate(csl_metadata)

    assert validated.ISSN == "1991-9603"


def test_issn_single_string_remains_unchanged() -> None:
    """Verify that pre-formatted singular string ISSNs pass through untouched."""
    raw_data = {"id": "some_id", "type": "book", "ISSN": "1234-567X"}

    validated = CSLReference.model_validate(raw_data)

    assert validated.ISSN == "1234-567X"


def test_extra_fields_ignored_automatically() -> None:
    """Verify schema ignores unmapped keys when converting back to dictionary layouts."""
    raw_data = {
        "id": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "extra_garbage_field": "should be ignored",
    }

    validated = CSLReference.model_validate(raw_data)
    exported_dict = validated.model_dump()

    assert "extra_garbage_field" not in exported_dict
