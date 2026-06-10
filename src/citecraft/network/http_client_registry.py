# src/citecraft/network/http_client_registry.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Registry management container for caching and retrieving HTTP client wrappers."""

from functools import lru_cache

from citecraft.utils import AppConfig, get_config

from .http_client_wrapper import HTTPClientConfig, HTTPClientWrapper


class HTTPClientRegistry:
    """Registry to persistent domain-specific HTTPClientWrapper instances."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config: AppConfig = config or get_config()
        self._registry: dict[str, HTTPClientWrapper] = {}

    def get_client(self, domain_key: str) -> HTTPClientWrapper:
        """Return an existing HTTP client wrapper or initialize a new instance."""
        if domain_key not in self._registry:
            if domain_key in ("crossref"):
                client_options = HTTPClientConfig(
                    api_key=self.config.crossref_api_key,
                    delay=self.config.crossref_api_delay,
                    max_retries=self.config.crossref_api_max_retry,
                    timeout=self.config.crossref_api_timeout,
                    url_max_character_length=(
                        self.config.crossref_api_url_max_character_length
                    ),
                )
                self._registry[domain_key] = HTTPClientWrapper(
                    email=self.config.user_email,
                    client_config=client_options,
                    config=self.config,
                )
            elif domain_key == "openalex":
                client_options = HTTPClientConfig(
                    api_key=self.config.openalex_api_key,
                    delay=self.config.openalex_api_delay,
                    max_retries=self.config.openalex_api_max_retry,
                    timeout=self.config.openalex_api_timeout,
                    url_max_character_length=(
                        self.config.openalex_api_url_max_character_length
                    ),
                )
                self._registry[domain_key] = HTTPClientWrapper(
                    email=self.config.user_email,
                    client_config=client_options,
                    config=self.config,
                )
            else:
                self._registry[domain_key] = HTTPClientWrapper(
                    email=self.config.user_email,
                    config=self.config,
                )

        return self._registry[domain_key]

    def close_all(self) -> None:
        """Close all active registered HTTP clients and clear registry entries."""
        for wrapper in self._registry.values():
            wrapper.close()
        self._registry.clear()


@lru_cache(maxsize=1)
def get_http_client_registry() -> HTTPClientRegistry:
    """Get the globally cached HTTP client registry instance."""
    return HTTPClientRegistry()
