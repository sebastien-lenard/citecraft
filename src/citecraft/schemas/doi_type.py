# src/citecraft/schemas/doi_type.py
"""Custom validation types and utilities for Digital Object Identifiers (DOIs)."""

import logging
import re
from typing import Annotated

from pydantic import TypeAdapter, ValidationError
from pydantic.functional_validators import AfterValidator

logger = logging.getLogger(__name__)

# Doi starting format + any character except spaces (legacy DOIs), match () and <>
# blocks + no trailing punctuation
DOI_REGEX = re.compile(
    r"^10\.\d{4,9}/(?:[^\s()<>]+|\([^)]*\)|<[^>]*>)+(?<![.,;!?:\-])$",
    re.IGNORECASE,
)


def validate_doi(doi: str) -> str:
    """Validate the DOI string. Logs a warning and raises ValueError if invalid."""
    if not DOI_REGEX.match(doi):
        logger.warning(
            "DOI Validation Failed: %s",
            doi,
            extra={"event": "invalid_doi", "doi": doi},
        )
        err_msg = (
            "Invalid DOI format. Must start with '10.' "
            "followed by a valid suffix and"
            "no space within and no trailing punctuation."
        )
        raise ValueError(err_msg)
    return doi


DoiType = Annotated[str, AfterValidator(validate_doi)]

doi_adapter = TypeAdapter(DoiType)


def check_standalone_doi(doi: str) -> bool:
    """Validate a standalone string against the DOI Annotated type rules."""
    try:
        doi_adapter.validate_python(doi)

    except ValidationError:
        return False
    else:
        return True
