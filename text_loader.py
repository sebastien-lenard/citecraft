from pathlib import Path
from docx import Document

class TextLoader:
    """
    Responsible for extracting text from a document file (only .docx right now).
    """
    def __init__(self, file_path):
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")
        self.file_path = file_path
        self.text = ""

    def extract_text_from_docx(self):
        doc = Document(self.file_path)
        # Collect text from every paragraph
        paragraphs = [p.text for p in doc.paragraphs]
        return '\n'.join(paragraphs)


