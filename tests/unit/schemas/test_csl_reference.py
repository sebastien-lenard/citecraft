import logging

import pytest
from pydantic import ValidationError

from citecraft.schemas.csl_reference import CSLReference
from citecraft.utils import AppConfig


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


@pytest.mark.parametrize(
    ("issn_input", "expected_issn"),
    [
        (["1991-9603", "1758-0471"], "1991-9603"),
        ("1234-567X", "1234-567X"),
        ([], None),
    ],
)
def test_issn_parsing_variants(
    issn_input: list[str] | str, expected_issn: str | None
) -> None:
    """Verify raw ISSN data input variants map onto a singular identifier string."""
    raw_data = {"id": "test_id", "type": "book", "ISSN": issn_input}
    validated = CSLReference.model_validate(raw_data)
    assert validated.ISSN == expected_issn


def test_extra_fields_not_ignored_automatically() -> None:
    """Verify schema keeps unmapped keys when converting back to dictionary
    layouts."""
    raw_data = {
        "id": "10.1038/s41561-020-0585-2",
        "type": "article-journal",
        "extra_garbage_field": "should be ignored",
    }

    validated = CSLReference.model_validate(raw_data)
    exported_dict = validated.model_dump()

    assert "extra_garbage_field" in exported_dict


def test_validate_csl_type_matching_config(test_config: AppConfig) -> None:
    """Verify type validation succeeds without warnings when listed in configuration."""
    test_config = test_config.model_copy(
        update={
            "work_csl_schema_types": ["article-journal", "book"],
        }
    )
    raw_data = {
        "id": "valid-id-1",
        "type": "article-journal",
    }

    validated = CSLReference.model_validate(raw_data, context={"config": test_config})

    assert validated.type == "article-journal"


def test_validate_csl_type_unknown_triggers_structured_log(
    test_config: AppConfig, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that an unlisted type logs a warning with explicit context metadata."""
    test_config = test_config.model_copy(
        update={
            "work_csl_schema_types": ["article-journal"],
        }
    )
    raw_data = {
        "id": "10.1234/test-doi",
        "type": "custom-fallback-type",
    }

    with caplog.at_level(logging.WARNING):
        validated = CSLReference.model_validate(
            raw_data, context={"config": test_config}
        )

    assert validated.type == "custom-fallback-type"
    assert len(caplog.records) == 1

    log_record = caplog.records[0]
    assert log_record.levelname == "WARNING"
    assert "Unknown CSL reference type encountered" in log_record.message
    assert log_record.csl_type == "custom-fallback-type"
    assert log_record.reference_id == "10.1234/test-doi"


def test_validate_csl_type_missing_context_silence() -> None:
    """Verify that validation passes silently if no execution context is passed."""
    raw_data = {
        "id": "no-context-id",
        "type": "unregistered-type",
    }

    validated = CSLReference.model_validate(raw_data, context=None)
    assert validated.type == "unregistered-type"
