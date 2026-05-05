from typing import Literal, TypedDict


class CitationMetadata(TypedDict):
    first_authors_txt: str  # e.g. Lenard et al., Guns and Vanacker
    year_and_suffix: str  # e.g. 2020a
    type: Literal["narrative", "parenthetical"]


def is_citation_metadata(record: dict) -> bool:
    """Check if a dictionary contains ALL keys defined in CitationMetadata."""
    required_keys = set(CitationMetadata.__annotations__.keys())
    return isinstance(record, dict) and required_keys.issubset(record.keys())


def create_citation_metadata(**kwargs) -> CitationMetadata:
    """Creates a default CitationMetadata with values overridable by kwargs."""
    defaults: CitationMetadata = {
        "first_authors_txt": "Unknown",
        "year_and_suffix": "2010",
        "type": "narrative",
    }
    defaults.update(kwargs)
    return defaults
