from typing import Any, override

from pydantic import Field, field_validator

from .base_schema import BaseSchema


class WorkMetadata(BaseSchema):
    """Represents validated metadata for a published work."""

    input_first_authors_txt: str = Field(
        min_length=1
    )  # e.g. Lenard et al., Guns and Vanacker
    input_year_and_suffix: str = Field(min_length=1)  # e.g. 2020a
    input_ISSN: str | None = None  # e.g. 1752-0894
    looked_up_ISSNs: list[str] | None = None  # e.g. ["1752-0894", "1700-0894"]
    raw_reference: str | None = (
        None  # reference from doi service. e.g. Lenard, S. J. P., Lavé, J., France-Lanord, C., Aumaître, G., Bourlès, D. L., & Keddadouche, K. (2020). Steady erosion rates in the Himalayas through late Cenozoic climatic changes. Nature Geoscience, 13(6), 448–452. https://doi.org/10.1038/s41561-020-0585-2
    )
    reference: str | None = (
        None  # reference after html cleaning. e.g. Lenard, S. J. P., Lavé, J., France-Lanord, C., Aumaître, G., Bourlès, D. L., & Keddadouche, K. (2020). Steady erosion rates in the Himalayas through late Cenozoic climatic changes. Nature Geoscience, 13(6), 448–452. https://doi.org/10.1038/s41561-020-0585-2
    )
    style: str | None = None  # e.g. apa
    DOI: str | None = None  # e.g. 10.1038/s41561-020-0585-2
    # CSL-dict metadata of the work from DOI negotiation service / crossref
    csl_metadata: dict[str, Any] | None = None
    # OpenAlex dict metadata of the work
    alex_metadata: dict[str, Any] | None = None
    type: str | None = None  # e.g. journal-article

    @field_validator("DOI", mode="before")
    @classmethod
    def doi_to_lower(cls, v: str | None) -> str | None:
        """Ensure DOI is stored in lower case."""
        if isinstance(v, str):
            return v.lower()
        return v

    @override
    @property
    def identity_key(self) -> tuple[str, str, str | None]:
        """Return the unique tuple identifier used for deduplication."""
        return (
            self.input_first_authors_txt,
            self.input_year_and_suffix,
            self.DOI,
        )

    @property
    def status(self) -> str:
        """Deduce status based on the availability of essential attributes."""
        if not self.DOI:
            return "Missing DOI"
        if not self.reference:
            return "Missing reference"
        return "OK"
