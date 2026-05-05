from .citation_metadata import (
    CitationMetadata,
    create_citation_metadata,
    is_citation_metadata,
)
from .crossref_author import CrossrefAuthor
from .journal_metadata import (
    JournalMetadata,
    create_journal_metadata,
    is_journal_metadata,
)
from .work_metadata import WorkMetadata, create_work_metadata, is_work_metadata

__all__ = [
    "CitationMetadata",
    "create_citation_metadata",
    "create_journal_metadata",
    "create_work_metadata",
    "CrossrefAuthor",
    "is_citation_metadata",
    "is_journal_metadata",
    "is_work_metadata",
    "JournalMetadata",
    "WorkMetadata",
]
