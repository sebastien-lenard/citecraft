# src/citecraft/schemas/journal_metadata.py
from datetime import date
from typing import Self, override

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from .base_schema import BaseSchema
from .issn_type import IssnType


class JournalMetadata(BaseSchema):
    """Represents validated metadata for a scientific journal."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    input_title: str  # e.g. Nature Geoscience
    true_title: str | None = None  # e.g. Nature Geoscience
    publisher: str | None = None  # e.g. Nature Portfolio / Springer Nature
    issn: IssnType | None = Field(
        default=None, validation_alias=AliasChoices("ISSN", "issn")
    )  # e.g. 1752-0894
    start_year: int | None = Field(default=None, ge=1600, le=2099)  # e.g. 2008
    end_year: int | None = Field(default=None, ge=1600, le=2099)  # e.g. 2026
    similar_titles: list[str] | None = (
        None  # Titles in the remote repository (crossref) similar to input_title
    )
    update: str = Field(
        default_factory=lambda: str(date.today())
    )  # ISO format: YYYY-MM-DD

    @override
    @property
    def identity_key(self) -> tuple[str, str | None]:
        """Return the unique tuple identifier used for deduplication."""
        return (self.input_title, self.issn)

    @property
    def is_complete(self) -> bool:
        """Check if all core metadata fields are populated."""
        excluded_fields = {"similar_titles", "update"}
        return all(
            getattr(self, field_name) is not None
            for field_name in self.__class__.model_fields
            if field_name not in excluded_fields
        )

    @property
    def status(self) -> str:
        """Deduce the synchronization status of the journal record."""
        if self.issn is None and self.true_title is not None:
            return "Found without ISSN"
        if self.issn is not None and (self.start_year is None or self.end_year is None):
            return "Found without work"
        if not self.is_complete:
            return "Not found"
        return "OK"

    @model_validator(mode="after")
    def validate_year_range(self) -> Self:
        """Assert that start year is chronologically before end year."""
        if self.start_year and self.end_year:
            if self.start_year > self.end_year:
                raise ValueError(
                    f"start_year ({self.start_year}) should be lower than end_year"
                    f" ({self.end_year})"
                )
            return self
        return self
