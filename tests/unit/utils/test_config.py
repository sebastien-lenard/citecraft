import os
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from manuscript_reference_lister.utils.config import create_config


@pytest.fixture(autouse=True)
def mock_env_file():
    """Isolate the testing pipeline completely from local disk
    configurations."""
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


def _create_test_config() -> Any:
    """Helper to bypass local .env files explicitly during initialization."""
    return create_config(_env_file=None)


def test_valid_https_urls_pass() -> None:
    """Ensure that correct https:// URLs pass completely unchanged."""
    with patch.dict(os.environ, {"DOI_API_URL": "https://crossref.org/{doi}"}):
        config = _create_test_config()
        assert config.doi_api_url == "https://crossref.org/{doi}"


def test_http_url_upgrades_to_https():
    """Ensure that http:// is automatically upgraded to https://."""
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


def test_missing_scheme_prepends_https():
    """Ensure that a URL missing a scheme altogether gets https:// prepended
    correctly."""
    with patch.dict(os.environ, {"STYLE_REPO_URL": "://github.com/{style}"}):
        config = _create_test_config()
        assert config.style_repo_url == "https://github.com/{style}"

    with patch.dict(os.environ, {"STYLE_REPO_URL": "github.com/{style}"}):
        config = _create_test_config()
        assert config.style_repo_url == "https://github.com/{style}"


def test_invalid_scheme_raises_validation_error():
    """Ensure that an unsupported scheme like ftp:// causes an explicit validation
    error."""
    with patch.dict(os.environ, {"DOI_API_URL": "ftp://api.crossref.org/{doi}"}):
        with pytest.raises(ValidationError) as exc_info:
            _create_test_config()

        assert "must use 'https://' scheme" in str(exc_info.value)


def test_missing_template_placeholder_raises_error():
    """Ensure that omitting mandatory braces like {issn} triggers structural
    failures."""
    with patch.dict(
        os.environ, {"CROSSREF_API_JOURNALS_ISSN_URL": "https://invalid-url.org"}
    ):
        with pytest.raises(ValidationError) as exc_info:
            _create_test_config()
        assert "mandatory '{issn}' placeholder" in str(exc_info.value)


def test_case_insensitivity_works():
    """Ensure the validator catches fields even if the environment keys are
    lowercase."""
    with patch.dict(os.environ, {"doi_api_url": "http://crossref.org/{doi}"}):
        config = _create_test_config()
        assert config.doi_api_url == "https://crossref.org/{doi}"
