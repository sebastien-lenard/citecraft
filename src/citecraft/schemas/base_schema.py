# src/citecraft/schemas/base_schema.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Base validation schema configuration for core domain metadata models."""

from collections.abc import Hashable

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base class providing common configuration for all metadata models."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )

    @property
    def identity_key(self) -> Hashable:
        """Return a unique identifier for deduplication."""
        err_msg = "Subclasses must implement identity_key"
        raise NotImplementedError(err_msg)
