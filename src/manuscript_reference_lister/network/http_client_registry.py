from functools import lru_cache

from manuscript_reference_lister.utils import AppConfig, get_config

from .http_client_wrapper import HTTPClientWrapper


class HTTPClientRegistry:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or get_config()
        self._registry: dict[str, HTTPClientWrapper] = {}

    def get_client(self, domain_key: str) -> HTTPClientWrapper:
        """Return an existing wrapper or create a new one for domain_key."""
        if domain_key not in self._registry:
            if domain_key in ["crossref", "github"]:
                self._registry[domain_key] = HTTPClientWrapper(
                    delay=self.config.crossref_api_delay,
                    email=self.config.crossref_api_email,
                    max_retries=self.config.crossref_api_max_retry,
                    timeout=self.config.crossref_api_timeout,
                )
            elif domain_key == "doi":
                self._registry[domain_key] = HTTPClientWrapper(
                    delay=self.config.doi_api_delay,
                    email=self.config.crossref_api_email,
                    max_retries=self.config.doi_api_max_retry,
                    timeout=self.config.doi_api_timeout,
                )
            else:
                self._registry[domain_key] = HTTPClientWrapper(
                    email=self.config.crossref_api_email
                )

        return self._registry[domain_key]

    def close_all(self) -> None:
        """Close all open HTTP clients and clear the registry."""
        for wrapper in self._registry.values():
            wrapper.close()
        self._registry.clear()


@lru_cache(maxsize=1)
def get_http_client_registry() -> HTTPClientRegistry:
    """Gets the single, cached HTTPClientRegistry instance for the application."""
    return HTTPClientRegistry()
