from typing import TypedDict


class JournalMetadata(TypedDict):
    input_title: str
    true_title: str
    publisher: str
    ISSN: str
    start_year: int
    end_year: int
    update: str
