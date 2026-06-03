# tests/unit/schemas/test_types.py
import pytest
from pydantic import BaseModel, ValidationError

from citecraft.schemas import HttpsUrlStr, UrlWithObjectName


class MockUrlModel(BaseModel):
    url: HttpsUrlStr


class MockUrlWithObjectNameModel(BaseModel):
    url: UrlWithObjectName


def test_url_with_object_name_with_valid_placeholder():
    """Ensure UrlWithObjectName accepts a valid string containing the {object_name}
    placeholder."""
    valid_url = "https://crossref.org{object_name}"
    model = MockUrlWithObjectNameModel(url=valid_url)
    assert model.url == valid_url


def test_url_with_object_name_missing_placeholder():
    """Ensure UrlWithObjectName raises a ValidationError when the {object_name}
    placeholder is missing."""
    with pytest.raises(ValidationError) as exc_info:
        MockUrlWithObjectNameModel(url="https://crossref.org10.1000/xyz123")

    assert "URL must contain the mandatory '{object_name}' placeholder." in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    "incoming_input, expected_output",
    [
        ("https://example.com", "https://example.com"),
        ("http://example.com", "https://example.com"),
        ("://example.com", "https://example.com"),
        ("://://example.com", "https://example.com"),
        ("   https://example.com   ", "https://example.com"),
        ("", ""),
        ("/", "/"),
        ("./relative/path", "./relative/path"),
    ],
)
def test_https_url_str_successful_cases(incoming_input: str, expected_output: str):
    """Ensure that valid URLs are preserved, repaired, or safely bypassed."""
    model = MockUrlModel(url=incoming_input)
    assert model.url == expected_output


def test_https_url_str_unsupported_scheme():
    """Ensure that illegal network protocols trigger an explicit ValidationError."""

    # Case 1: Test a standard unsupported protocol
    with pytest.raises(ValidationError) as exc_info:
        MockUrlModel(url="ftp://example.com")
    assert "URL must use 'https://' scheme. Got unsupported: 'ftp'" in str(
        exc_info.value
    )

    # Case 2: Test a corrupted unsupported protocol
    with pytest.raises(ValidationError) as exc_info_corrupt:
        MockUrlModel(url="ws://://example.com")
    assert "URL must use 'https://' scheme. Got unsupported: 'ws'" in str(
        exc_info_corrupt.value
    )


def test_https_url_str_non_string_input():
    """Ensure that non-string objects do not crash the parser and rely on Pydantic's
    core limits."""
    with pytest.raises(ValidationError):
        MockUrlModel(url=12345)


def test_placeholder_validators_receive_coerced_https_string():
    """Ensure that the AfterValidators run AFTER the BeforeValidator protocol cleanup."""
    with pytest.raises(ValidationError) as exc_info:
        MockUrlWithObjectNameModel(url="ftp://://example.com{object_name}")
    assert "URL must use 'https://' scheme" in str(exc_info.value)

    model = MockUrlWithObjectNameModel(url="://://example.com{object_name}")
    assert model.url == "https://example.com{object_name}"
