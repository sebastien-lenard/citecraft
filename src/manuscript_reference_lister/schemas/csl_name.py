from pydantic import BaseModel, ConfigDict

csl_config = ConfigDict(populate_by_name=True, extra="ignore")


class CSLName(BaseModel):
    """CSL Schema for individual contributors (authors, editors, translators, etc.)."""

    model_config = csl_config

    family: str | None = None
    given: str | None = None
    literal: str | None = None  # Used for institutional/organizational names
