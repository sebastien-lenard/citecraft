# tests/unit/parsers/test_journal_parser.py
import pytest

from citecraft.parsers import JournalParser


@pytest.fixture
def parser() -> JournalParser:
    """Provide a fresh instance of JournalParser for isolated testing."""
    return JournalParser()


@pytest.mark.parametrize(
    "text, expected",
    [
        # Standard parsing case with introductory headers and footers
        (
            (
                "Intro text.\n\nJournals\nGeomorphology\nGeology\nChemical Geology"
                "\n\nEnd of file."
            ),
            ["Geomorphology", "Geology", "Chemical Geology"],
        ),
        # Last occurrence logic (only picking up list following the final "Journals"
        # header)
        (
            (
                "Journals\nOld List\n\nIntermediate text...\n\nJournals\nNew List 1"
                "\nNew List 2\n\nEnd."
            ),
            ["New List 1", "New List 2"],
        ),
        # No matching header
        ("This text mentions journals but not as a header line.", []),
        # Break parsing on intermediate whitespace or blank lines
        ("Journals\nJournal Alpha\n \t \nJournal Beta", ["Journal Alpha"]),
        # End of stream reached before any terminal breaks
        ("Journals\nOnly Journal", ["Only Journal"]),
        # Strict word matching (ignoring compound titles like 'Scientific Journals')
        ("Scientific Journals\nPhysics\n\nJournals\nChemistry\n\nEnd", ["Chemistry"]),
        # Auto-deduplication of parsed titles
        ("Journals\nNature\nScience\nNature\n\nEnd", ["Nature", "Science"]),
    ],
)
def test_journal_parser_scenarios(
    parser: JournalParser, text: str, expected: list[str],
) -> None:
    """Verify structural extraction rules and boundary parsing edge cases."""
    assert parser.extract_all(text) == expected
