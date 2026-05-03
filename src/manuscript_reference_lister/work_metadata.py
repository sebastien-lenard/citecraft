from typing import TypedDict


class WorkMetadata(TypedDict):
    name: str
    role: str
    req_author: str
    req_year: int
    req_issn: str
    req_keywords: str
    reference: str
    style: str
    doi: str
    score: int
    type: str
