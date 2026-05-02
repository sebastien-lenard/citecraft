import unittest

from manuscript_reference_lister import CitationParser


class TestCitationParser(unittest.TestCase):
    def setUp(self):
        self.parser = CitationParser()

    def test_basic_and_coauthor_formats(self):
        """Test standard Author, Author and Author, and Author et al."""
        text = "Hovius (1997), Parker and Smith (2011), and Larsen et al. (2012)."
        res = self.parser.extract_citations(text)
        authors = [r["author"] for r in res]
        self.assertIn("Hovius", authors)
        self.assertIn("Parker and Smith", authors)
        self.assertIn("Larsen et al.", authors)

    def test_french_et_support(self):
        """Verify that 'et' is recognized as a coordinator between authors."""
        text = "L'étude de Dupont et Dupond (1945) est une référence."
        res = self.parser.extract_citations(text)
        self.assertEqual(res[0]["author"], "Dupont et Dupond")

    def test_multiple_years_narrative(self):
        """Verify: Author (Year1a, Year2b) -> Two distinct results with suffixes."""
        text = "Croissant et al. (2017a, 2019b) found specific patterns."
        res = self.parser.extract_citations(text)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["year"], "2017a")
        self.assertEqual(res[1]["year"], "2019b")

    def test_year_suffixes(self):
        """Test that years followed by letters (a, b, c) are correctly captured."""
        text = "As noted by Lupker et al. (2011a) and again (Lupker et al., 2011b)."
        res = self.parser.extract_citations(text)
        years = [r["year"] for r in res]
        self.assertIn("2011a", years)
        self.assertIn("2011b", years)

    def test_complex_initials(self):
        """Test multi-part initials like J.S. or S.J-P."""
        text = "J.S. Bach (1720) and (S.J-P. Lénard et al., 2024)."
        res = self.parser.extract_citations(text)
        authors = [r["author"] for r in res]
        self.assertIn("J.S. Bach", authors)
        self.assertIn("S.J-P. Lénard et al.", authors)

    def test_particles_van_der_and_de(self):
        """Test specific particles: van der, Van Der, and De."""
        text = "Van Der Beek (2026), van der Beek (2026), and De Castro (2010)."
        res = self.parser.extract_citations(text)
        authors = [r["author"] for r in res]
        self.assertIn("Van Der Beek", authors)
        self.assertIn("van der Beek", authors)
        self.assertIn("De Castro", authors)

    def test_false_positive_prevention(self):
        """Ensure (2020) or (in 2020) are NOT captured as citations if authorless."""
        text = "This was resolved recently (2020) and also (in 2021)."
        res = self.parser.extract_citations(text)
        self.assertEqual(len(res), 0)

    def test_blacklist_and_noise(self):
        """Test that Fig. or Table are ignored but similar names are kept."""
        text = "(Fig. 5; Hovius, 1997). Figueroa (2020) is not Fig."
        res = self.parser.extract_citations(text)
        authors = [r["author"] for r in res]
        self.assertIn("Hovius", authors)
        self.assertIn("Figueroa", authors)
        self.assertNotIn("Fig.", authors)

    def test_nested_and_parenthetical_blocks(self):
        """Test semicolon-separated groups and text inside double parens."""
        text = "((Larsen and Montgomery, 2012)). See also (Smith, 2003; Brown, 2005)."
        res = self.parser.extract_citations(text)
        self.assertEqual(len(res), 3)
        authors = [r["author"] for r in res]
        self.assertIn("Larsen and Montgomery", authors)
        self.assertIn("Smith", authors)
        self.assertIn("Brown", authors)

    def test_accents_and_hyphens(self):
        """Verify names like Lyon-Caen or Lénard."""
        text = "Lyon-Caen and Molnar (1985) and Lénard (2020)."
        res = self.parser.extract_citations(text)
        authors = [r["author"] for r in res]
        self.assertIn("Lyon-Caen and Molnar", authors)
        self.assertIn("Lénard", authors)

    def test_hyphenated_and_unicode_names(self):
        """Test names with various types of dashes and language coordinators."""
        # Note: the hyphen in Lyon‐Caen below is the Unicode U+2010
        text = "Work by Lyon‐Caen and Molnar (1985) and Lyon‐Caen et Molnar (1985)."
        citations = self.parser.extract_citations(text)

        # We expect two distinct entries
        self.assertEqual(len(citations), 2)

        # Check first citation (English coordinator)
        self.assertEqual(citations[0]["author"], "Lyon‐Caen and Molnar")
        self.assertEqual(citations[0]["year"], "1985")

        # Check second citation (French coordinator)
        self.assertEqual(citations[1]["author"], "Lyon‐Caen et Molnar")
        self.assertEqual(citations[1]["year"], "1985")

    def test_complex_initials_with_dashes(self):
        """Test that initials with dashes (S.J-P.) are fully captured."""
        text = "S.J-P. Lénard et al. (2020) demonstrated this."
        citations = self.parser.extract_citations(text)

        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["author"], "S.J-P. Lénard et al.")

    def test_exclude_full_references(self):
        """Test that full APA references are not parsed."""
        text = (
            "Bernard, T., G., Lague, D., and Philippe Steer, P. (2021). Beyond 2D "
            "Landslide Inventories and Their Rollover: Synoptic 3D . Earth Surface "
            " Dynamics 9 (4), 1013–44. "
            "https://doi.org/10.5194/esurf-9-1013-2021"
        )
        citations = self.parser.extract_citations(text)
        self.assertEqual(len(citations), 0)

    def test_exclude_dates(self):
        """Test that dates are not parsed."""
        text = "When this happened (August 31, 2020), everyboy was impressed."
        citations = self.parser.extract_citations(text)
        self.assertEqual(len(citations), 0)


if __name__ == "__main__":
    unittest.main()
