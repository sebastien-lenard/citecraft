import json
import logging
from pathlib import Path
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError


class DataLoader:
    """Handles data loading and text extraction for DOCX and JSON files.

    Attributes:
        file_path: Path to the source file.
        raise_exception: If True, invalid files trigger errors;
            otherwise, logs a warning.
    """

    def __init__(self, file_path: str | Path, raise_exception: bool = True):
        self.file_path = Path(file_path)
        self.raise_exception = raise_exception
        if not self.file_path.is_file():
            msg = f"Input file not found: {self.file_path}"
            if self.raise_exception:
                raise FileNotFoundError(msg)
            logging.warning(msg)

    def extract_text_from_docx(self) -> str | None:
        """Parses a .docx file and joins paragraphs with newlines."""
        if not self.file_path.is_file():
            return None
        try:
            doc = Document(self.file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        except (PackageNotFoundError, BadZipFile):
            msg = f"Invalid or corrupted .docx: {self.file_path}"
            if self.raise_exception:
                raise
            logging.warning(msg)
            return None

    def load_json(self, validator=None) -> dict | list | None:
        """Loads and parses JSON data. Returns None if file corrupted and if a list not
        records not validated by the validator function."""
        if not self.file_path.is_file():
            return None
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            msg = f"Invalid JSON format: {self.file_path}"
            if self.raise_exception:
                raise
            logging.warning(msg)
            return None

        if data is None:
            return None

        if validator and isinstance(data, list):
            if not all(validator(item) for item in data):
                msg = (
                    f"Schema validation failed for one or more items in: "
                    f"{self.file_path}"
                )
                if self.raise_exception:
                    raise ValueError(msg)
                logging.warning(msg)
                return None

        return data
