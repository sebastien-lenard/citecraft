# tests/unit/schemas/test_issn_type.py
import logging

import pytest

from citecraft.schemas import check_standalone_issn


@pytest.mark.parametrize(
    "valid_issn",
    [
        "2049-3630",  # Standard numeric check digit
        "0010-051X",  # Uppercase 'X' check digit (value of 10)
        "0010-051x",  # Lowercase 'x' check digit (case insensitivity)
        "0036-8075",  # Science
        "1752-0894",  # Standard numeric check digit
        "0361-0160",  # Edge case: Remainder 0, check digit is exactly '0'
    ],
)
def test_check_standalone_issn_valid(valid_issn: str) -> None:
    """Ensure that valid ISSN values pass validation without warnings."""
    assert check_standalone_issn(valid_issn) is True


@pytest.mark.parametrize(
    "invalid_issn, expected_log_snippet",
    [
        ("2049-3631", "ISSN Validation Failed (Checksum)"),
        ("12345678", "ISSN Validation Failed (Format)"),
        ("abc-1234", "ISSN Validation Failed (Format)"),
    ],
)
def test_check_standalone_issn_invalid(
    caplog: pytest.LogCaptureFixture, invalid_issn: str, expected_log_snippet: str
) -> None:
    """Verify that invalid strings return False and trigger a structural warning log."""
    with caplog.at_level(logging.WARNING):
        result = check_standalone_issn(invalid_issn)

        assert result is False
        assert len(caplog.records) == 1
        assert expected_log_snippet in caplog.text
