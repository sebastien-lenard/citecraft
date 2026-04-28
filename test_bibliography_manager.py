import unittest
import os
import csv
from unittest.mock import patch, mock_open
from bibliography_manager import BibliographyManager
from config_loader import TEST_OUTPUT_DIR

class TestBibliographyManager(unittest.TestCase):
    def setUp(self):
        """Initialize the manager with a dummy file path."""
        self.input_file = "dummy_manuscript.txt"
        # Create the file physically to silence the "File not found" error
        with open(self.input_file, 'w', encoding='utf-8') as f:
            f.write("Dummy content")
        self.manager = BibliographyManager(self.input_file)
    
    def tearDown(self):
        """Clean up by removing the dummy file after each test."""
        if os.path.exists(self.input_file):
            os.remove(self.input_file)

    @patch('bibliography_manager.ReferenceFetcher.fetch_apa_candidates')
    def test_build_bibliography_logic(self, mock_fetch):
        """Checks if build_bibliography correctly handles multiple candidates."""
        # 1. Setup mock data (Aligning with ReferenceFetcher actual output format)
        mock_fetch.return_value = [
            {'apa': 'Lénard (2020) Best', 'doi': 'https://doi.org/10.1/best', 'score': 100, 'type': 'article'},
            {'apa': 'Lénard (2020) Alt', 'doi': 'https://doi.org/10.1/alt', 'score': 80, 'type': 'article'}
        ]
        self.manager.citations = [{'author': 'Lénard', 'year': '2020'}]
        
        # 2. Run logic
        results = self.manager.build_bibliography()
        
        # 3. Verify
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['Score'], 100)
        self.assertEqual(results[1]['DOI'], 'https://doi.org/10.1/alt')

    def test_line_range_logic(self):
        """
        Verify that the 1-indexed line range (n to p) 
        is correctly converted to 0-indexed slicing.
        """
        mock_data = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch.object(self.manager.parser, 'extract_citations') as mock_parser:
                    # Request lines 2 to 4 (should be 'Line 2\nLine 3\nLine 4\n')
                    self.manager.load_and_parse(start_line=2, end_line=4)
                    mock_parser.assert_called_once_with("Line 2\nLine 3\nLine 4\n")

    def test_full_file_loading(self):
        """Verify that the manager loads the entire content if no range is specified."""
        mock_data = "Hovius et al. (1997)\nParker and Smith (2011)"
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                self.manager.load_and_parse()
                # Check if sorted unique citations are stored
                self.assertEqual(len(self.manager.citations), 2)
                self.assertEqual(self.manager.citations[0]['author'], "Hovius et al.")

    def test_sorting_logic(self):
        """Verify that citations are sorted alphabetically by author then year."""
        # We use 'et al.' to satisfy the parser's regex
        mock_data = "Z-Author et al. (2020)\nA-Author et al. (2010)\nA-Author et al. (1995b)\nA-Author et al. (1995a)"
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                self.manager.load_and_parse()
                # Get author and year for comparison
                authors = [(c['author'], c['year']) for c in self.manager.citations]
                
                # Expected order: A 1995a, A 1995b, A 2010, Z 2020
                expected = [
                    ('A-Author et al.', '1995a'), 
                    ('A-Author et al.', '1995b'), 
                    ('A-Author et al.', '2010'), 
                    ('Z-Author et al.', '2020')
                ]
                self.assertEqual(authors, expected)

    def test_physical_csv_creation(self):
        """
        Verify that the CSV is physically created in the 
        TEST_OUTPUT_DIR and contains correct data.
        """
        test_filename = "physical_test.csv"
        # Pre-populate with controlled data
        self.manager.citations = [
            {'author': 'Lénard et al.', 'year': '2020'}
        ]
        
        # Target the test directory specifically
        self.manager.export_to_csv(test_filename, target_dir=TEST_OUTPUT_DIR)
        
        expected_path = os.path.join(TEST_OUTPUT_DIR, test_filename)
        
        # Check existence and content (before populating with API results)
        self.assertTrue(os.path.exists(expected_path))
        with open(expected_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['Author'], 'Lénard et al.')
            self.assertEqual(rows[0]['Year'], '2020')
            self.assertEqual(rows[0]['APA_Reference'], 'PENDING_API')
            self.assertEqual(rows[0]['Type'], 'PENDING')

    @patch('bibliography_manager.ReferenceFetcher.fetch_apa_candidates')
    def test_csv_content_with_api_results(self, mock_fetch):
        """
        Verify that the CSV is correctly populated with multiple 
        candidates returned by the API.
        """
        from config_loader import TEST_OUTPUT_DIR
        test_filename = "api_content_test.csv"
        
        # 1. Simulate 2 candidates returned by the API for one citation
        mock_fetch.return_value = [
            {'apa': 'Hovius (1997) A', 'doi': '10.1/A', 'score': 95.0, 'type': 'journal-article'},
            {'apa': 'Hovius (1997) B', 'doi': '10.1/B', 'score': 70.0, 'type': 'book-chapter'}
        ]
        
        # 2. Setup manager and run orchestration
        self.manager.citations = [{'author': 'Hovius', 'year': '1997'}]
        results = self.manager.build_bibliography()
        self.manager.export_to_csv(test_filename, api_results=results, target_dir=TEST_OUTPUT_DIR)
        
        # 3. Physical verification of the file content
        expected_path = os.path.join(TEST_OUTPUT_DIR, test_filename)
        with open(expected_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            self.assertEqual(len(rows), 2)
            # Verify the first row (highest score)
            self.assertEqual(rows[0]['DOI'], '10.1/A')
            self.assertEqual(float(rows[0]['Score']), 95.0)
            # Verify the second row
            self.assertEqual(rows[1]['DOI'], '10.1/B')
            self.assertEqual(rows[1]['Type'], 'book-chapter')
            
    def test_file_not_found_handling(self):
        """Verify that the manager handles missing input files gracefully."""
        with patch("os.path.exists", return_value=False):
            # Should not raise an exception, just print error
            # .Error: File 'dummy_manuscript.txt' not found
            self.manager.load_and_parse()
            self.assertEqual(self.manager.citations, [])

if __name__ == '__main__':
    unittest.main()