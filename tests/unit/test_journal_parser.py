import unittest

from manuscript_reference_lister import JournalParser


class TestJournalParser(unittest.TestCase):
    def setUp(self):
        """Initialize the parser before each test."""
        self.parser = JournalParser()

    def test_standard_case(self):
        """Test extraction from a typical formatted string."""
        text = """Intro text.
        
Journals
Geomorphology
Geology
Chemical Geology

End of file."""
        expected = ["Geomorphology", "Geology", "Chemical Geology"]
        self.assertEqual(self.parser.extract_journal_list(text), expected)

    def test_last_occurrence_only(self):
        """Ensure it only picks up the list after the LAST 'Journals' header."""
        text = """Journals
Old List

Intermediate text...

Journals
New List 1
New List 2

End."""
        expected = ["New List 1", "New List 2"]
        self.assertEqual(self.parser.extract_journal_list(text), expected)

    def test_no_journals_header(self):
        """Return empty list if 'Journals' line is missing."""
        text = "This text mentions journals but not as a header line."
        self.assertEqual(self.parser.extract_journal_list(text), [])

    def test_break_with_whitespace(self):
        """Ensure it stops at a double newline even if it contains spaces or tabs."""
        # Represents: Journals \n Item 1 \n [space][tab] \n Item 2
        text = "Journals\nJournal Alpha\n \t \nJournal Beta"
        expected = ["Journal Alpha"]
        self.assertEqual(self.parser.extract_journal_list(text), expected)

    def test_no_break_until_end_of_string(self):
        """Handle cases where the list goes until the very end of the string."""
        text = "Journals\nOnly Journal"
        expected = ["Only Journal"]
        self.assertEqual(self.parser.extract_journal_list(text), expected)

    def test_strict_match_only(self):
        """Ensure partial matches like 'Scientific Journals' are ignored."""
        text = """Scientific Journals
Physics

Journals
Chemistry

End"""
        expected = ["Chemistry"]
        self.assertEqual(self.parser.extract_journal_list(text), expected)


if __name__ == "__main__":
    unittest.main()
