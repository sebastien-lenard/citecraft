# src/citecraft/schemas/csl_date.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic schemas mirroring Citation Style Language (CSL) date JSON specifications."""

from pydantic import BaseModel, ConfigDict, Field


class CSLDate(BaseModel):
    """CSL Schema for structured historical or academic dates."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    date_parts: list[list[int | str]] = Field(..., alias="date-parts")
    season: int | str | None = None
    circa: int | str | None = None
    literal: str | None = None
