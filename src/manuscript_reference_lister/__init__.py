from . import config_loader
from .citation_parser import CitationParser
from .data_loader import DataLoader
from .doi_fetcher import DoiFetcher
from .journal_fetcher import JournalFetcher
from .journal_parser import JournalParser
from .requests_wrapper import RequestsWrapper
from .style_fetcher import StyleFetcher
from .work import Work

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "config_loader",
    "CitationParser",
    "DataLoader",
    "DoiFetcher",
    "JournalFetcher",
    "JournalParser",
    "RequestsWrapper",
    "StyleFetcher",
    "Work",
]
