import logging
import re
from typing import Annotated

from pydantic import TypeAdapter, ValidationError
from pydantic.functional_validators import AfterValidator

logger = logging.getLogger(__name__)

DOI_REGEX = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)


def validate_doi(doi: str) -> str:
    """Validates the DOI string. Logs a warning and raises ValueError if invalid."""
    if not DOI_REGEX.match(doi):
        logger.warning(
            "DOI Validation Failed: %s",
            doi,
            extra={"event": "invalid_doi", "doi": doi},
        )
        raise ValueError(
            "Invalid DOI format. Must start with '10.' followed by a valid suffix."
        )
    return doi


DOIType = Annotated[str, AfterValidator(validate_doi)]

doi_adapter = TypeAdapter(DOIType)


def check_standalone_doi(doi: str) -> bool:
    """Validates a standalone string against the DOI Annotated type rules."""
    try:
        doi_adapter.validate_python(doi)
        return True
    except ValidationError:
        return False
