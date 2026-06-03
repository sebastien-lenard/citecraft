# tests/unit/network/test_http_client_registry.py
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from citecraft.network.http_client_registry import (
    HTTPClientRegistry,
    get_http_client_registry,
)
from citecraft.utils import AppConfig


@pytest.fixture
def configured_test_config(test_config: AppConfig) -> AppConfig:
    """Configure mock-specific endpoint limits on the configuration boundary."""
    return test_config.model_copy(
        update={
            "user_email": "user@test.com",
            "crossref_api_key": None,
            "crossref_api_delay": 1.0,
            "crossref_api_max_retry": 3,
            "crossref_api_timeout": 30.0,
            "crossref_api_url_max_character_length": 3000,
            "openalex_api_key": "toto",
            "openalex_api_delay": 1.5,
            "openalex_api_max_retry": 5,
            "openalex_api_timeout": 45.0,
            "openalex_api_url_max_character_length": 4000,
            "default_api_key": None,
            "default_api_delay": 0.5,
            "default_api_max_retry": 2,
            "default_api_timeout": 15.0,
            "default_api_url_max_character_length": 2048,
        }
    )


def test_registry_creates_and_caches_client(
    configured_test_config: AppConfig,
) -> None:
    """Verify that a client is cached and reused upon subsequent requests."""
    registry = get_http_client_registry()
    registry.config = configured_test_config

    with patch(
        "citecraft.network.http_client_registry.HTTPClientWrapper"
    ) as mock_wrapper_cls:
        client_first = registry.get_client("openalex")
        client_second = registry.get_client("openalex")

        assert client_first == client_second
        assert mock_wrapper_cls.call_count == 1


@pytest.mark.parametrize(
    "domain, expected_keys_and_values",
    [
        (
            "openalex",
            {
                "api_key": "toto",
                "delay": 1.5,
                "email": "user@test.com",
                "max_retries": 5,
                "timeout": 45.0,
                "url_max_character_length": 4000,
            },
        ),
        (
            "crossref",
            {
                "api_key": None,
                "delay": 1.0,
                "email": "user@test.com",
                "max_retries": 3,
                "timeout": 30.0,
                "url_max_character_length": 3000,
            },
        ),
        (
            "unknown_domain",
            {
                "email": "user@test.com",
            },
        ),
    ],
)
def test_registry_applies_correct_domain_configurations(
    configured_test_config: AppConfig,
    domain: str,
    expected_keys_and_values: dict[str, Any],
) -> None:
    """Verify that distinct domains receive their expected initialization parameters."""
    registry = HTTPClientRegistry(config=configured_test_config)

    with patch(
        "citecraft.network.http_client_registry.HTTPClientWrapper"
    ) as mock_wrapper_cls:
        registry.get_client(domain)

        expected_kwargs = {
            **expected_keys_and_values,
            "config": configured_test_config,
        }
        mock_wrapper_cls.assert_called_with(**expected_kwargs)


def test_registry_close_all_clears_and_closes_resources(
    configured_test_config: AppConfig,
) -> None:
    """Verify that close_all calls close on every wrapper and empties the registry."""
    registry = HTTPClientRegistry(config=configured_test_config)

    with patch(
        "citecraft.network.http_client_registry.HTTPClientWrapper"
    ) as mock_wrapper_cls:
        mock_openalex = MagicMock()
        mock_default = MagicMock()
        mock_wrapper_cls.side_effect = [mock_openalex, mock_default]

        registry.get_client("openalex")
        registry.get_client("default")

        registry.close_all()

        mock_openalex.close.assert_called_once()
        mock_default.close.assert_called_once()
        assert len(registry._registry) == 0
