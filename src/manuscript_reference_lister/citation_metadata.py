from typing import Literal, TypedDict


class CitationMetadata(TypedDict):
    first_authors: str  # e.g. Lenard et al., Guns and Vanacker
    year_and_suffix: str  # e.g. 2020a
    type: Literal["narrative", "parenthetical"]
