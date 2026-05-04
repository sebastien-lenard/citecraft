import pytest

from manuscript_reference_lister.parsers import JournalParser


@pytest.fixture
def parser() -> JournalParser:
    """Provides a fresh instance of JournalParser for each test."""
    return JournalParser()


def test_standard_case(parser: JournalParser) -> None:
    """Test extraction from a typical formatted string with headers and footers."""
    text = (
        "Intro text.\n"
        "\n"
        "Journals\n"
        "Geomorphology\n"
        "Geology\n"
        "Chemical Geology\n"
        "\n"
        "End of file."
    )
    expected = ["Geomorphology", "Geology", "Chemical Geology"]
    assert parser.extract_all(text) == expected


def test_last_occurrence_only(parser: JournalParser) -> None:
    """Ensure it only picks up the list after the LAST 'Journals' header."""
    text = (
        "Journals\n"
        "Old List\n"
        "\n"
        "Intermediate text...\n"
        "\n"
        "Journals\n"
        "New List 1\n"
        "New List 2\n"
        "\n"
        "End."
    )
    expected = ["New List 1", "New List 2"]
    assert parser.extract_all(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        # No header: Return empty list
        ("This text mentions journals but not as a header line.", []),
        # Break with whitespace: Stop at a double newline even if it contains spaces/tabs
        ("Journals\nJournal Alpha\n \t \nJournal Beta", ["Journal Alpha"]),
        # End of string: Handle cases where the list goes until the very end
        ("Journals\nOnly Journal", ["Only Journal"]),
        # Strict match: Ensure partial matches like 'Scientific Journals' are ignored
        ("Scientific Journals\nPhysics\n\nJournals\nChemistry\n\nEnd", ["Chemistry"]),
    ],
)
def test_parsing_edge_cases(
    parser: JournalParser, text: str, expected: list[str]
) -> None:
    """Verify various boundary conditions and strict header matching."""
    assert parser.extract_all(text) == expected
