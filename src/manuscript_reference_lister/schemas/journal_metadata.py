from datetime import date
from typing import TypedDict


class JournalMetadata(TypedDict):
    input_title: str  # e.g. Nature Geoscience
    true_title: str | None  # e.g. Nature Geoscience
    publisher: str | None  # e.g. Nature Portfolio / Springer Nature
    ISSN: str | None  # e.g. 1752-0894
    start_year: int | None  # e.g. 2008
    end_year: int | None  # e.g. 2026
    update: str  # e.g. 2026-03-27


def is_journal_metadata(record: dict) -> bool:
    """Check if a dictionary contains ALL keys defined in JournalMetadata."""
    required_keys = set(JournalMetadata.__annotations__.keys())
    return isinstance(record, dict) and required_keys.issubset(record.keys())


def create_journal_metadata(**kwargs) -> JournalMetadata:
    """Creates a default JournalMetadata with values overridable by kwargs."""
    defaults: JournalMetadata = {
        "input_title": "Unknown",
        "true_title": None,
        "publisher": None,
        "ISSN": None,
        "start_year": None,
        "end_year": None,
        "update": str(date.today()),
    }
    defaults.update(kwargs)
    return defaults
