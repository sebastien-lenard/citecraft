# src/citecraft/schemas/issn_type.py
import logging
import re
from typing import Annotated

from pydantic import TypeAdapter, ValidationError
from pydantic.functional_validators import AfterValidator

logger = logging.getLogger(__name__)

ISSN_REGEX = re.compile(r"^\d{4}-\d{3}[\dX]$", re.IGNORECASE)


def validate_issn(issn: str) -> str:
    """Validates an ISSN string format and its Modulus 11 checksum."""
    if not ISSN_REGEX.match(issn):
        logger.warning(
            "ISSN Validation Failed (Format): %s",
            issn,
            extra={"event": "invalid_issn_format", "issn": issn},
        )
        raise ValueError("Invalid ISSN format. Must be 'YYYY-YYYY' (e.g. 2049-3630).")

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
        expected_check = "X" if calc_check == 10 else str(calc_check)

    # Compare with the actual 8th character
    actual_check = clean_issn[7]

    if actual_check != expected_check:
        logger.warning(
            "ISSN Validation Failed (Checksum): %s",
            issn,
            extra={"event": "invalid_issn_checksum", "issn": issn},
        )
        raise ValueError("Invalid ISSN checksum. The number is fabricated or mistyped.")

    return issn


ISSNType = Annotated[str, AfterValidator(validate_issn)]

issn_adapter = TypeAdapter(ISSNType)


def check_standalone_issn(issn: str) -> bool:
    """Validates a standalone string against the ISSN Annotated type rules."""
    try:
        issn_adapter.validate_python(issn)
        return True
    except ValidationError:
        return False
