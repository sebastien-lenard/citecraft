import csv
import logging

from manuscript_reference_lister.schemas import CitationMetadata, WorkMetadata
from manuscript_reference_lister.services.bibliography_service import (
    BibliographyService,
)


def test_export_to_csv_computes_statuses_and_sorts_correctly(tmp_path, caplog):
    """Verify statuses mapping logic and correct primary/secondary sorting."""
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
            reference="Lenard Ref B",
        ),
        WorkMetadata(
            input_first_authors_txt="Lenard et al.",
            input_year_and_suffix="2020",
            reference="Lenard Ref A",
        ),
        # Single match case for Smith
        WorkMetadata(
            input_first_authors_txt="Smith",
            input_year_and_suffix="2021",
            reference="Smith Ref",
        ),
        # Alpha is intentionally omitted here to simulate a missing Reference/DOI error
    ]

    BibliographyService.export_to_csv(citations, works, output_csv)

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
