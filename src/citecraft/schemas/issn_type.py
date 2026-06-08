# src/citecraft/schemas/issn_type.py
"""Custom validation types and Modulus 11 checksum verification for ISSN fields."""

import logging
import re
from typing import Annotated

from pydantic import TypeAdapter, ValidationError
from pydantic.functional_validators import AfterValidator

logger = logging.getLogger(__name__)

ISSN_REGEX = re.compile(r"^\d{4}-\d{3}[\dX]$", re.IGNORECASE)


def validate_issn(issn: str) -> str:
    """Validate an ISSN string format and its Modulus 11 checksum."""
    if not ISSN_REGEX.match(issn):
        logger.warning(
            "ISSN Validation Failed (Format): %s",
            issn,
            extra={"event": "invalid_issn_format", "issn": issn},
        )
        err_msg = "Invalid ISSN format. Must be 'YYYY-YYYY' (e.g. 2049-3630)."
        raise ValueError(err_msg)

    # --- Modulus 11 Checksum Verification ---
    clean_issn = issn.replace("-", "").upper()

    # Calculate weighted sum for the first 7 digits (weights from 8 down to 2)
    total = sum(int(clean_issn[i]) * (8 - i) for i in range(7))

    # Calculate the expected check digit
    remainder = total % 11
    if remainder == 0:
        expected_check = "0"
    else:
        calc_check = 11 - remainder
        expected_check = "X" if calc_check == 10 else str(calc_check)  # noqa: PLR2004

    # Compare with the actual 8th character
    actual_check = clean_issn[7]

    if actual_check != expected_check:
        logger.warning(
            "ISSN Validation Failed (Checksum): %s",
            issn,
            extra={"event": "invalid_issn_checksum", "issn": issn},
        )
        err_msg = "Invalid ISSN checksum. The number is fabricated or mistyped."
        raise ValueError(err_msg)

    return issn


IssnType = Annotated[str, AfterValidator(validate_issn)]

issn_adapter = TypeAdapter(IssnType)


def check_standalone_issn(issn: str) -> bool:
    """Validate a standalone string against the ISSN Annotated type rules."""
    try:
        issn_adapter.validate_python(issn)
    except ValidationError:
        return False
    else:
        return True
