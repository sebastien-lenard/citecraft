from . import config_loader
from .citation_parser import CitationParser
from .data_loader import DataLoader
from .doi_repository import DoiRepository
from .journal_parser import JournalParser
from .journal_repository import JournalRepository
from .requests_wrapper import RequestsWrapper
from .style_repository import StyleRepository
from .work_metadata import WorkMetadata
from .work_repository import WorkRepository

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "config_loader",
    "CitationParser",
    "DataLoader",
    "DoiRepository",
    "JournalRepository",
    "JournalParser",
    "RequestsWrapper",
    "StyleRepository",
    "WorkMetadata",
    "WorkRepository",
]
