from pydantic import BaseModel, ConfigDict, Field


class CSLDate(BaseModel):
    """CSL Schema for structured historical or academic dates."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    date_parts: list[list[int | str]] = Field(..., alias="date-parts")
    season: int | str | None = None
    circa: int | str | None = None
    literal: str | None = None
