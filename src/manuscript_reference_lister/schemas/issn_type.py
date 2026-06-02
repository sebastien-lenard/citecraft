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

    total = sum(int(clean_issn[i]) * (8 - i) for i in range(7))

    check_char = clean_issn[7]
    total += 10 if check_char == "X" else int(check_char)

    if total % 11 != 0:
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
