import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from manuscript_reference_lister.utils.config import AppConfig, create_config


@pytest.fixture(autouse=True)
def mock_env_file() -> Generator[None, None, None]:
    """Isolate testing pipelines from local disk configurations using mock variables."""
    with patch.dict(os.environ, clear=True):
        os.environ["CROSSREF_API_EMAIL"] = "test@example.com"
        os.environ["CROSSREF_API_JOURNALS_URL"] = "https://example.com"
        os.environ["CROSSREF_API_JOURNALS_ISSN_URL"] = "https://example.com/{issn}"
        os.environ["CROSSREF_API_STYLES_URL"] = "https://example.com"
        os.environ["CROSSREF_API_WORKS_URL"] = "https://example.com"
        os.environ["DOI_API_URL"] = "https://example.com/{doi}"
        os.environ["STYLE_REPO_URL"] = "https://example.com/{style}"
        os.environ["ALL_STYLES_REPO_URL"] = "https://example.com"
        os.environ["CHILD_STYLE_REPO_URL"] = "https://example.com/{style}"
        os.environ["CSL_XML_NAMESPACES"] = '{"cs": "http://citationstyles.org/ns/"}'
        yield


def _create_test_config() -> AppConfig:
    """Helper to safely instantiate configurations, explicitly bypassing local file
    loads."""
    return create_config(_env_file=None)


def test_valid_https_urls_pass() -> None:
    """Ensure that already valid https:// locations are preserved during validation."""
    with patch.dict(os.environ, {"DOI_API_URL": "https://crossref.org/{doi}"}):
        config = _create_test_config()
        assert config.doi_api_url == "https://crossref.org/{doi}"


def test_http_url_upgrades_to_https() -> None:
    """Verify that http:// endpoint declarations automatically upgrade to secure
    https:// layouts."""
    with patch.dict(
        os.environ,
        {
            "DOI_API_URL": "http://crossref.org/{doi}",
            "CROSSREF_API_JOURNALS_URL": "http://crossref.org",
        },
    ):
        config = _create_test_config()
        assert config.doi_api_url == "https://crossref.org/{doi}"
        assert (
            str(config.crossref_api_journals_url).rstrip("/") == "https://crossref.org"
        )


def test_missing_scheme_prepends_https() -> None:
    """Verify that schemes absent from input strings are safely coerced to https://."""
    with patch.dict(os.environ, {"STYLE_REPO_URL": "://github.com/{style}"}):
        config = _create_test_config()
        assert config.style_repo_url == "https://github.com/{style}"

    with patch.dict(os.environ, {"STYLE_REPO_URL": "github.com/{style}"}):
        config = _create_test_config()
        assert config.style_repo_url == "https://github.com/{style}"


def test_invalid_scheme_raises_validation_error() -> None:
    """Verify that non-standard protocols like ftp:// fail configuration parsing."""
    with patch.dict(os.environ, {"DOI_API_URL": "ftp://api.crossref.org/{doi}"}):
        with pytest.raises(ValidationError) as exc_info:
            _create_test_config()

        assert "must use 'https://' scheme" in str(exc_info.value)


def test_missing_template_placeholder_raises_error() -> None:
    """Verify that omission of expected URL interpolation parameters breaks loading."""
    with patch.dict(
        os.environ, {"CROSSREF_API_JOURNALS_ISSN_URL": "https://invalid-url.org"}
    ):
        with pytest.raises(ValidationError) as exc_info:
            _create_test_config()
        assert "mandatory '{issn}' placeholder" in str(exc_info.value)


def test_case_insensitivity_works() -> None:
    """Ensure parsing and enforcement rules apply regardless of environment key case."""
    with patch.dict(os.environ, {"doi_api_url": "http://crossref.org/{doi}"}):
        config = _create_test_config()
        assert config.doi_api_url == "https://crossref.org/{doi}"
