import csv
import logging
from pathlib import Path

import pytest

from manuscript_reference_lister.schemas import CitationMetadata, WorkMetadata
from manuscript_reference_lister.services.bibliography_service import (
    BibliographyService,
)
from manuscript_reference_lister.utils import AppConfig, get_config


@pytest.fixture
def test_config() -> AppConfig:
    """Provides a safe copy of the application configuration for isolation with explicit
    preserved tags."""
    config = get_config().model_copy()
    config.preserved_html_tags = ["sub", "sup"]
    return config


def test_export_to_csv_computes_statuses_and_sorts_correctly(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, test_config: AppConfig
) -> None:
    """Verify standard status assignment (OK, Warning) and proper alphabetical multi-key
    sorting."""
    caplog.set_level(logging.INFO)
    output_csv = tmp_path / "output.csv"

    citations = [
        CitationMetadata(first_authors_txt="Lenard et al.", year_and_suffix="2020"),
        CitationMetadata(first_authors_txt="Smith", year_and_suffix="2021"),
        CitationMetadata(first_authors_txt="Alpha", year_and_suffix="2019"),
    ]

    works = [
        # Multi match case for Lenard
        WorkMetadata(
            input_first_authors_txt="Lenard et al.",
            input_year_and_suffix="2020",
            DOI="10.1000/xyz.b",
            reference="Lenard Ref B",
        ),
        WorkMetadata(
            input_first_authors_txt="Lenard et al.",
            input_year_and_suffix="2020",
            DOI="10.1000/xyz.a",
            reference="Lenard Ref A",
        ),
        # Single match case for Smith
        WorkMetadata(
            input_first_authors_txt="Smith",
            input_year_and_suffix="2021",
            DOI="10.1000/smith",
            reference="Smith Ref",
        ),
        # Alpha is intentionally omitted here to simulate a missing Reference/DOI error
    ]

    biblio_service = BibliographyService(config=test_config)
    biblio_service.export_to_csv(citations, works, output_csv)

    # Logging assertions
    assert any(
        "No metadata or DOI found for citation: Alpha, 2019" in record.message
        and record.levelname == "WARNING"
        for record in caplog.records
    )
    assert any(
        "Several references found for citation: Lenard et al., 2020" in record.message
        and record.levelname == "INFO"
        for record in caplog.records
    )
    assert any(
        "Generated and saved bibliography with 4 rows" in record.message
        and record.levelname == "INFO"
        for record in caplog.records
    )

    # Csv content assertions
    # Read written rows back for assertion checking
    with open(output_csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 4

    # First row should be Alpha because Reference is None/Empty String (Primary Sort)
    assert rows[0]["Citation"] == "Alpha, 2019"
    assert rows[0]["Status"] == "Warning: No doi or reference found for the citation"
    assert rows[0]["Reference"] == ""

    # Second row should be Lenard Ref A (Alphabetical sort priority over Lenard Ref B)
    assert rows[1]["Citation"] == "Lenard et al., 2020"
    assert rows[1]["Status"] == "Warning: select the right reference"
    assert rows[1]["Reference"] == "Lenard Ref A"

    # Third row should be Lenard Ref B
    assert rows[2]["Citation"] == "Lenard et al., 2020"
    assert rows[2]["Status"] == "Warning: select the right reference"
    assert rows[2]["Reference"] == "Lenard Ref B"

    # Fourth row should be Smith Ref
    assert rows[3]["Citation"] == "Smith, 2021"
    assert rows[3]["Status"] == "OK"
    assert rows[3]["Reference"] == "Smith Ref"


def test_export_to_csv_emits_structured_logs_and_returns_valid_result(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, test_config: AppConfig
) -> None:
    """Verify that execution lifecycle logs correctly and returns a structural
    ExportResult loaded with precise counters and sorted row samples.
    """
    caplog.set_level(logging.INFO)
    output_csv = tmp_path / "output.csv"

    citations = [
        CitationMetadata(first_authors_txt="Alpha", year_and_suffix="2019"),
        CitationMetadata(first_authors_txt="Lenard et al.", year_and_suffix="2020"),
        CitationMetadata(first_authors_txt="Smith", year_and_suffix="2021"),
    ]
    works = [
        # Duplicates (Warning: select the right reference)
        WorkMetadata(
            input_first_authors_txt="Lenard et al.",
            input_year_and_suffix="2020",
            DOI="10.1000/ref1",
            reference="Lenard Ref B",
        ),
        WorkMetadata(
            input_first_authors_txt="Lenard et al.",
            input_year_and_suffix="2020",
            DOI="10.1000/ref2",
            reference="Lenard Ref A",
        ),
        # Unique (OK)
        WorkMetadata(
            input_first_authors_txt="Smith",
            input_year_and_suffix="2021",
            DOI="10.1000/smith",
            reference="Smith Ref",
        ),
        # Alpha without corresponding record (Warning: No doi or reference...)
    ]

    biblio_service = BibliographyService(config=test_config)
    result = biblio_service.export_to_csv(citations, works, output_csv)

    # Validation of return type
    assert result.total_rows == 4
    assert result.output_filepath == output_csv
    assert result.export_format == "CSV"
    assert result.ok_count == 1
    assert result.missing_count == 1
    assert result.duplicate_count == 2

    # Sample validation (alphabetic sort)
    # Sample OK
    assert result.sample_ok is not None
    assert result.sample_ok["Citation"] == "Smith, 2021"
    assert result.sample_ok["Status"] == "OK"

    # Missing sample
    assert result.sample_missing is not None
    assert result.sample_missing["Citation"] == "Alpha, 2019"
    assert result.sample_missing["Reference"] is None

    # Duplicates, with sort
    assert len(result.samples_duplicate) == 2
    assert result.samples_duplicate[0]["Reference"] == "Lenard Ref A"
    assert result.samples_duplicate[1]["Reference"] == "Lenard Ref B"
    assert result.samples_duplicate[0]["Citation"] == "Lenard et al., 2020"
    assert result.samples_duplicate[1]["Citation"] == "Lenard et al., 2020"

    # Log validation
    log_messages = [record.message for record in caplog.records]
    log_levels = [record.levelname for record in caplog.records]

    assert "No metadata or DOI found for citation: Alpha, 2019" in log_messages
    assert "WARNING" in log_levels

    assert "Several references found for citation: Lenard et al., 2020" in log_messages


def test_export_to_csv_strips_only_preserved_tags(
    tmp_path: Path, test_config: AppConfig
) -> None:
    """Verify that only configured preserved HTML tags are stripped from references,
    leaving unknown tags intact to act as a visual artifact/warning.
    """
    output_csv = tmp_path / "output.csv"

    citations = [
        CitationMetadata(first_authors_txt="Test", year_and_suffix="2026"),
    ]
    works = [
        WorkMetadata(
            input_first_authors_txt="Test",
            input_year_and_suffix="2026",
            DOI="10.1000/tags-test",
            reference=(
                "Analysis of CO<sub>2</sub> within <unsupported-tag>text"
                "</unsupported-tag>."
            ),
        )
    ]

    biblio_service = BibliographyService(config=test_config)
    biblio_service.export_to_csv(citations, works, output_csv)

    with open(output_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    expected_reference = (
        "Analysis of CO2 within <unsupported-tag>text</unsupported-tag>."
    )
    assert rows[0]["Reference"] == expected_reference


def test_export_to_csv_excludes_invalid_work_records(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, test_config: AppConfig
) -> None:
    """Verify that works missing either a DOI or a reference are excluded from matching
    and trigger the appropriate warning statuses and console logs.
    """
    caplog.set_level(logging.WARNING)
    output_csv = tmp_path / "output.csv"

    citations = [
        CitationMetadata(first_authors_txt="MissingDOI", year_and_suffix="2024"),
        CitationMetadata(first_authors_txt="MissingRef", year_and_suffix="2025"),
    ]

    works = [
        # 1. Work exists locally but has no DOI
        WorkMetadata(
            input_first_authors_txt="MissingDOI",
            input_year_and_suffix="2024",
            DOI=None,
            reference="Some orphan reference string",
        ),
        # 2. Work exists locally but has no reference text
        WorkMetadata(
            input_first_authors_txt="MissingRef",
            input_year_and_suffix="2025",
            DOI="10.1016/j.isprsjprs.2025.101",
            reference=None,
        ),
    ]

    biblio_service = BibliographyService(config=test_config)
    biblio_service.export_to_csv(citations, works, output_csv)

    assert any("MissingDOI, 2024" in r.message for r in caplog.records)
    assert any("MissingRef, 2025" in r.message for r in caplog.records)

    with open(output_csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    for row in rows:
        assert row["Status"] == "Warning: No doi or reference found for the citation"
        assert row["Reference"] == ""
