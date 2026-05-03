from typing import TypedDict


class WorkMetadata(TypedDict):
    input_first_authors: str
    input_year_and_suffix: int
    input_ISSN: str
    reference: str
    style: str
    doi: str
    score: int
    type: str
