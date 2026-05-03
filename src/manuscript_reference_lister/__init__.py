from . import config_loader
from .base_repository import BaseRepository
from .citation_parser import CitationParser
from .data_loader import DataLoader
from .doi_repository import DoiRepository
from .journal_parser import JournalParser
from .journal_repository import JournalRepository
from .requests_wrapper import RequestsWrapper
from .schemas.citation_metadata import CitationMetadata
from .schemas.journal_metadata import JournalMetadata
from .schemas.work_metadata import WorkMetadata
from .style_repository import StyleRepository
from .work_repository import WorkRepository

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "BaseRepository",
    "config_loader",
    "CitationMetadata",
    "CitationParser",
    "DataLoader",
    "DoiRepository",
    "JournalMetadata",
    "JournalRepository",
    "JournalParser",
    "RequestsWrapper",
    "StyleRepository",
    "WorkMetadata",
    "WorkRepository",
]
