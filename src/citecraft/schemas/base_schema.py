# src/citecraft/schemas/base_schema.py
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base class providing common configuration for all metadata models."""

    model_config = ConfigDict(
        populate_by_name=True, from_attributes=True, extra="ignore"
    )

    @property
    def identity_key(self) -> str:
        """Return a unique identifier for deduplication."""
        raise NotImplementedError("Subclasses must implement identity_key")

    # TODO: add an abstract property get_update_status to be able to implement
    # different levels of update, like in JournalRepository::update_all(), rather
    # than using "if None in astuple(record)"
