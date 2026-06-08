# src/citecraft/schemas/base_schema.py
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
