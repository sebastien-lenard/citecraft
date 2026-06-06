# tests/unit/services/test_bibliography_service.py
import csv
import logging
from pathlib import Path

import pytest

from citecraft.schemas import CitationMetadata, WorkMetadata
from citecraft.services.bibliography_service import (
    BibliographyService,
)
from citecraft.utils import AppConfig


@pytest.mark.parametrize(
    "citations, works, expected_rows, expected_logs",
    [
        # Scenario 1: Standard Multi-Match Sorting and Status Determination
        (
            [
                CitationMetadata(
                    first_authors_txt="Lenard et al.", year_and_suffix="2020"
                ),
                CitationMetadata(first_authors_txt="Smith", year_and_suffix="2021"),
                CitationMetadata(first_authors_txt="Alpha", year_and_suffix="2019"),
            ],
            [
                WorkMetadata(
                    input_first_authors_txt="Lenard et al.",
                    input_year_and_suffix="2020",
                    doi="10.1000/xyz.b",
                    reference="Lenard Ref B",
                ),
                WorkMetadata(
                    input_first_authors_txt="Lenard et al.",
                    input_year_and_suffix="2020",
                    doi="10.1000/xyz.a",
                    reference="Lenard Ref A",
                ),
                WorkMetadata(
                    input_first_authors_txt="Smith",
                    input_year_and_suffix="2021",
                    doi="10.1000/smith",
                    reference="Smith Ref",
                ),
            ],
            [
                {
                    "Citation": "Alpha, 2019",
                    "Status": "Warning: No doi or reference found for the citation",
                    "Reference": "",
                },
                {
                    "Citation": "Lenard et al., 2020",
                    "Status": "Warning: select the right reference",
                    "Reference": "Lenard Ref A",
                },
                {
                    "Citation": "Lenard et al., 2020",
                    "Status": "Warning: select the right reference",
                    "Reference": "Lenard Ref B",
                },
                {
                    "Citation": "Smith, 2021",
                    "Status": "OK",
                    "Reference": "Smith Ref",
                },
            ],
            [
                ("WARNING", "No metadata or DOI found for citation: Alpha, 2019"),
                ("INFO", "Several references found for citation: Lenard et al., 2020"),
                ("INFO", "Generated and saved bibliography with 4 rows"),
            ],
        ),
        # Scenario 2: Exclusion of Invalid Work Records (Missing DOI or Missing
        # Reference String)
        (
            [
                CitationMetadata(
                    first_authors_txt="MissingDOI", year_and_suffix="2024"
                ),
                CitationMetadata(
                    first_authors_txt="MissingRef", year_and_suffix="2025"
                ),
            ],
            [
                WorkMetadata(
                    input_first_authors_txt="MissingDOI",
                    input_year_and_suffix="2024",
                    doi=None,
                    reference="Some orphan reference string",
                ),
                WorkMetadata(
                    input_first_authors_txt="MissingRef",
                    input_year_and_suffix="2025",
                    doi="10.1016/j.isprsjprs.2025.101",
                    reference=None,
                ),
            ],
            [
                {
                    "Citation": "MissingDOI, 2024",
                    "Status": "Warning: No doi or reference found for the citation",
                    "Reference": "",
                },
                {
                    "Citation": "MissingRef, 2025",
                    "Status": "Warning: No doi or reference found for the citation",
                    "Reference": "",
                },
            ],
            [
                ("WARNING", "No metadata or DOI found for citation: MissingDOI, 2024"),
                ("WARNING", "No metadata or DOI found for citation: MissingRef, 2025"),
                ("INFO", "Generated and saved bibliography with 2 rows"),
            ],
        ),
    ],
)
def test_export_to_csv_computes_statuses_and_sorts_correctly(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    test_config: AppConfig,
    citations: list[CitationMetadata],
    works: list[WorkMetadata],
    expected_rows: list[dict[str, str]],
    expected_logs: list[tuple[str, str]],
) -> None:
    """Verify standard status assignment, record exclusion boundaries, and multi-key
    sorting."""
    caplog.set_level(logging.INFO)
    output_csv = tmp_path / "output.csv"

    biblio_service = BibliographyService(config=test_config)
    biblio_service.export_to_csv(citations, works, output_csv)

    # Dynamic logging verification to prevent test scenario bleeding
    for level, pattern in expected_logs:
        assert any(
            pattern in record.message and record.levelname == level
            for record in caplog.records
        )

    # Read written rows back for assertion checking
    with open(output_csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == len(expected_rows)
    for index, expected in enumerate(expected_rows):
        assert rows[index]["Citation"] == expected["Citation"]
        assert rows[index]["Status"] == expected["Status"]
        assert rows[index]["Reference"] == expected["Reference"]


def test_export_to_csv_emits_structured_logs_and_returns_valid_result(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, test_config: AppConfig
) -> None:
    """Verify export processes populate structured result schemas with precise
    statistics."""
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
            doi="10.1000/ref1",
            reference="Lenard Ref B",
        ),
        WorkMetadata(
            input_first_authors_txt="Lenard et al.",
            input_year_and_suffix="2020",
            doi="10.1000/ref2",
            reference="Lenard Ref A",
        ),
        # Unique (are OK)
        WorkMetadata(
            input_first_authors_txt="Smith",
            input_year_and_suffix="2021",
            doi="10.1000/smith",
            reference="Smith Ref",
        ),
        # Alpha without corresponding record (Warning: No doi or reference...)
    ]

    biblio_service = BibliographyService(config=test_config)
    result = biblio_service.export_to_csv(citations, works, output_csv)

    # Validation of return structures
    assert result.total_rows == 4
    assert result.output_filepath == output_csv
    assert result.export_format == "CSV"
    assert result.ok_count == 1
    assert result.missing_count == 1
    assert result.duplicate_count == 2

    # Verify alphabetical sample sorting priorities
    assert result.sample_ok is not None
    assert result.sample_ok["Citation"] == "Smith, 2021"
    assert result.sample_ok["Status"] == "OK"

    assert result.sample_missing is not None
    assert result.sample_missing["Citation"] == "Alpha, 2019"
    assert result.sample_missing["Reference"] is None

    assert len(result.samples_duplicate) == 2
    assert result.samples_duplicate[0]["Reference"] == "Lenard Ref A"
    assert result.samples_duplicate[1]["Reference"] == "Lenard Ref B"
    assert result.samples_duplicate[0]["Citation"] == "Lenard et al., 2020"
    assert result.samples_duplicate[1]["Citation"] == "Lenard et al., 2020"

    log_messages = [record.message for record in caplog.records]
    log_levels = [record.levelname for record in caplog.records]
    assert "No metadata or DOI found for citation: Alpha, 2019" in log_messages
    assert "WARNING" in log_levels
    assert "Several references found for citation: Lenard et al., 2020" in log_messages


def test_export_to_csv_strips_only_preserved_tags(
    tmp_path: Path, test_config: AppConfig
) -> None:
    """Verify that only configured preserved HTML tags are stripped from references."""
    output_csv = tmp_path / "output.csv"
    test_config = test_config.model_copy(update={"preserved_html_tags": {"sub", "sup"}})

    citations = [
        CitationMetadata(first_authors_txt="Test", year_and_suffix="2026"),
    ]
    works = [
        WorkMetadata(
            input_first_authors_txt="Test",
            input_year_and_suffix="2026",
            doi="10.1000/tags-test",
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
