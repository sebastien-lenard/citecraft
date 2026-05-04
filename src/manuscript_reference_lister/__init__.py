from . import config_loader
from .base_repository import BaseRepository
from .data_loader import DataLoader
from .doi_repository import DoiRepository
from .journal_repository import JournalRepository
from .requests_wrapper import RequestsWrapper
from .style_repository import StyleRepository
from .work_repository import WorkRepository

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "BaseRepository",
    "config_loader",
    "CitationMetadata",
    "DataLoader",
    "DoiRepository",
    "JournalMetadata",
    "JournalRepository",
    "RequestsWrapper",
    "StyleRepository",
    "WorkMetadata",
    "WorkRepository",
]
