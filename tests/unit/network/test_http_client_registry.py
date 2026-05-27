from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister.network.http_client_registry import (
    HTTPClientRegistry,
    get_http_client_registry,
)
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def configured_test_config(test_config: AppConfig) -> AppConfig:
    """Configure mock-specific endpoint limits on the isolated configuration
    boundary."""
    test_config.crossref_api_email = "user@test.com"
    test_config.crossref_api_delay = 1.5
    test_config.crossref_api_max_retry = 5
    test_config.crossref_api_timeout = 45.0
    test_config.doi_api_delay = 0.5
    test_config.doi_api_max_retry = 2
    test_config.doi_api_timeout = 15.0
    return test_config


def test_registry_creates_and_caches_client(configured_test_config: AppConfig) -> None:
    """Verify that a client is cached and reused upon subsequent requests."""
    registry = get_http_client_registry()
    registry.config = configured_test_config

    with patch(
        "manuscript_reference_lister.network.http_client_registry.HTTPClientWrapper"
    ) as mock_wrapper_cls:
        client_first = registry.get_client("crossref")
        client_second = registry.get_client("crossref")

        assert client_first == client_second
        assert mock_wrapper_cls.call_count == 1


@pytest.mark.parametrize(
    "domain, expected_kwargs",
    [
        (
            "crossref",
            {"email": "user@test.com", "delay": 1.5, "max_retries": 5, "timeout": 45.0},
        ),
        (
            "doi",
            {"email": "user@test.com", "delay": 0.5, "max_retries": 2, "timeout": 15.0},
        ),
        (
            "unknown_domain",
            {"email": "user@test.com"},
        ),
    ],
)
def test_registry_applies_correct_domain_configurations(
    configured_test_config: AppConfig, domain: str, expected_kwargs: dict[str, Any]
) -> None:
    """Verify that distinct domains receive their expected initialization parameters."""
    registry = HTTPClientRegistry(config=configured_test_config)

    with patch(
        "manuscript_reference_lister.network.http_client_registry.HTTPClientWrapper"
    ) as mock_wrapper_cls:
        registry.get_client(domain)
        mock_wrapper_cls.assert_called_with(**expected_kwargs)


def test_registry_close_all_clears_and_closes_resources(
    configured_test_config: AppConfig,
) -> None:
    """Verify that close_all calls close on every wrapper and empties the registry."""
    registry = HTTPClientRegistry(config=configured_test_config)

    with patch(
        "manuscript_reference_lister.network.http_client_registry.HTTPClientWrapper"
    ) as mock_wrapper_cls:
        mock_crossref = MagicMock()
        mock_doi = MagicMock()
        mock_wrapper_cls.side_effect = [mock_crossref, mock_doi]

        registry.get_client("crossref")
        registry.get_client("doi")

        registry.close_all()

        mock_crossref.close.assert_called_once()
        mock_doi.close.assert_called_once()
        assert len(registry._registry) == 0
