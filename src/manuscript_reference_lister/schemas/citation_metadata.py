from typing import Literal, TypedDict


class CitationMetadata(TypedDict):
    first_authors_txt: str  # e.g. Lenard et al., Guns and Vanacker
    year_and_suffix: str  # e.g. 2020a
    type: Literal["narrative", "parenthetical"]


def is_citation_metadata(record: dict) -> bool:
    """Check if a dictionary contains ALL keys defined in CitationMetadata."""
    required_keys = set(CitationMetadata.__annotations__.keys())
    return isinstance(record, dict) and required_keys.issubset(record.keys())
