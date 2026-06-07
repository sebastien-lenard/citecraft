# src/citecraft/schemas/csl_reference.py
import logging
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .csl_date import CSLDate
from .csl_name import CSLName

logger = logging.getLogger(__name__)


class CSLReference(BaseModel):
    """Main schema representing a CSL-JSON reference item."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        validate_by_name=True,
        validate_by_alias=True,
    )

    # Required structural roots
    id: str
    type: str = Field(..., description="A valid CSL-JSON entry type category")

    # Contributor arrays
    author: list[CSLName] | None = None
    editor: list[CSLName] | None = None
    translator: list[CSLName] | None = None
    container_author: list[CSLName] | None = Field(None, alias="container-author")
    collection_editor: list[CSLName] | None = Field(None, alias="collection-editor")

    # Date profiles
    issued: CSLDate | None = None
    accessed: CSLDate | None = None
    submitted: CSLDate | None = None

    # Structural Titles & Locations
    title: str | None = None
    title_short: str | None = Field(None, alias="title-short")
    container_title: str | None = Field(None, alias="container-title")
    container_title_short: str | None = Field(None, alias="container-title-short")
    collection_title: str | None = Field(None, alias="collection-title")
    publisher: str | None = None
    publisher_place: str | None = Field(None, alias="publisher-place")

    # Info for book chapters and proceedings
    event_title: str | None = Field(None, alias="event-title")
    event_place: str | None = Field(None, alias="event-place")
    collection_number: int | str | None = Field(None, alias="collection-number")
    volume_title: str | None = Field(None, alias="volume-title")

    # Locators, Index numbers & Registry IDs
    volume: int | str | None = None
    issue: int | str | None = None
    number: int | str | None = None
    page: str | None = None
    page_first: str | None = Field(None, alias="page-first")
    edition: int | str | None = None
    doi: str | None = Field(default=None, validation_alias=AliasChoices("DOI", "doi"))
    URL: str | None = None
    ISBN: str | None = None
    issn: str | None = Field(
        default=None, validation_alias=AliasChoices("ISSN", "issn"),
    )

    # Miscellaneous Metadata
    abstract: str | None = None
    note: str | None = None
    language: str | None = None

    @field_validator("issn", mode="before")
    @classmethod
    def handle_crossref_issn_array(cls, value: Any) -> str | None:
        """Intercept the incoming ISSN data and extract the first element if a list."""
        if isinstance(value, list):
            return str(value[0]) if value else None
        return value

    @model_validator(mode="before")
    @classmethod
    def clean_crossref_metadata(cls, data: Any) -> Any:
        """Run sanitize routine to assign ID from DOI if missing."""
        if isinstance(data, dict):
            if "id" not in data and "DOI" in data:
                data["id"] = data["DOI"]
            if "id" not in data and "doi" in data:
                data["id"] = data["doi"]
        return data

    @model_validator(mode="before")
    @classmethod
    def validate_type_against_config(cls, data: Any, info: ValidationInfo) -> Any:
        """Validate standard CSL types via context, logging unknown categories."""
        if not isinstance(data, dict):
            return data

        csl_type = data.get("type")
        if not isinstance(csl_type, str):
            return data

        context = info.context or {}
        config = context.get("config")

        if config and hasattr(config, "work_csl_schema_types"):
            allowed_types = set(config.work_csl_schema_types)

            if csl_type not in allowed_types:
                ref_id = (
                    data.get("id") or data.get("DOI") or data.get("doi") or "unknown"
                )
                logger.warning(
                    "Unknown CSL reference type encountered: '%s' for ID: %s",
                    csl_type,
                    ref_id,
                    extra={
                        "status": "WARN",
                        "event": "unknown_csl_reference_type",
                        "csl_type": csl_type,
                        "reference_id": ref_id,
                    },
                )
        return data
