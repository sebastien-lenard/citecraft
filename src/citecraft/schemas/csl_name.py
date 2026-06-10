# src/citecraft/schemas/csl_name.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic schemas mirroring Citation Style Language (CSL) contributor names."""

from pydantic import BaseModel, ConfigDict


class CSLName(BaseModel):
    """CSL Schema for individual contributors and organizations."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    family: str | None = None
    given: str | None = None
    literal: str | None = None  # Used for institutional/organizational names
