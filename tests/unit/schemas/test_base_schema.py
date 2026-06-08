# tests/unit/schemas/test_base_schema.py
"""Unit tests verifying the base data schema configuration and behavior lifecycle."""

import pytest

from citecraft.schemas.base_schema import BaseSchema


class MockSchema(BaseSchema):
    """Simple schema implementation for validating base behaviors."""

    name: str
    value: int = 0

    @property
    def identity_key(self) -> str:
        """Provide a test mock implementation of an identity key."""
        return self.name


def test_base_schema_to_dict() -> None:
    """Verify clean dictionary export functionality."""
    obj = MockSchema(name="Test", value=10)
    expected = {"name": "Test", "value": 10}

    assert obj.model_dump() == expected


def test_base_schema_from_dict_ignores_extra_fields() -> None:
    """Ensure unregistered dictionary items are discarded during instantiation."""
    raw_data = {"name": "Test", "value": 42, "extra_garbage": "ignore_me"}

    obj = MockSchema(**raw_data)

    assert obj.name == "Test"
    assert obj.value == 42
    assert not hasattr(obj, "extra_garbage")


def test_base_schema_identity_key_requirement() -> None:
    """Ensure subclasses trigger NotImplementedError when identity_key is missing."""

    class BrokenSchema(BaseSchema):
        name: str

    obj = BrokenSchema(name="Fail")

    with pytest.raises(
        NotImplementedError,
        match="Subclasses must implement identity_key",
    ):
        _ = obj.identity_key
