import unittest
import os
from docx import Document
from text_loader import TextLoader

class TestTextLoader(unittest.TestCase):
    def setUp(self):
        """Create a dummy docx file for testing."""
        self.test_filename = "test_sample.docx"
        self.test_content = ["Hello World", "This is a test paragraph.", "End of doc."]
        
        # Create and save a real .docx file
        doc = Document()
        for line in self.test_content:
            doc.add_paragraph(line)
        doc.save(self.test_filename)

    def tearDown(self):
        """Remove the dummy file after the test."""
        if os.path.exists(self.test_filename):
            os.remove(self.test_filename)

    def test_extract_text_matches_input(self):
        """Check if extracted text matches what we wrote."""
        loader = TextLoader(self.test_filename)
        extracted_text = loader.extract_text_from_docx()
        
        # Join our original list with newlines to match your loader's output
        expected_text = '\n'.join(self.test_content)
        
        self.assertEqual(extracted_text, expected_text)

    def test_file_not_found_raises_error(self):
        """Ensure the class correctly raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            TextLoader("non_existent_file.docx")

if __name__ == '__main__':
    unittest.main()
