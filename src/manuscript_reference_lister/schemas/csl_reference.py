from pydantic import BaseModel, ConfigDict, Field

from .csl_date import CSLDate
from .csl_name import CSLName

csl_config = ConfigDict(populate_by_name=True, extra="ignore")


class CSLReference(BaseModel):
    """Main schema representing a strict, valid CSL-JSON reference item."""

    model_config = csl_config

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

    # Locators, Index numbers & Registry IDs
    volume: int | str | None = None
    issue: int | str | None = None
    number: int | str | None = None
    page: str | None = None
    page_first: str | None = Field(None, alias="page-first")
    edition: int | str | None = None
    DOI: str | None = None
    URL: str | None = None
    ISBN: str | None = None
    ISSN: str | None = None

    # Miscellaneous Metadata
    abstract: str | None = None
    note: str | None = None
    language: str | None = None
