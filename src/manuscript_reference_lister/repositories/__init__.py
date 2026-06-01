from .base_repository import BaseRepository
from .crossref_work_repository import CrossrefWorkRepository
from .doi_repository import DoiRepository
from .journal_repository import JournalRepository
from .openalex_work_repository import OpenAlexWorkRepository
from .style_repository import StyleRepository
from .work_repository import WorkRepository

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "BaseRepository",
    "CrossrefWorkRepository",
    "DoiRepository",
    "JournalRepository",
    "OpenAlexWorkRepository",
    "StyleRepository",
    "WorkRepository",
]
