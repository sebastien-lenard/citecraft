from .base_repository import BaseRepository
from .crossref_work_repository import WorkRepository
from .doi_repository import DoiRepository
from .journal_repository import JournalRepository
from .style_repository import StyleRepository

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "BaseRepository",
    "DoiRepository",
    "JournalRepository",
    "StyleRepository",
    "WorkRepository",
]
