from .citation_metadata import CitationMetadata, is_citation_metadata
from .crossref_author import CrossrefAuthor
from .journal_metadata import JournalMetadata, is_journal_metadata
from .work_metadata import WorkMetadata, is_work_metadata

__all__ = [
    "CitationMetadata",
    "CrossrefAuthor",
    "is_citation_metadata",
    "is_journal_metadata",
    "is_work_metadata",
    "JournalMetadata",
    "WorkMetadata",
]
