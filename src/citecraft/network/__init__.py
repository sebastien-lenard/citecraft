# src/citecraft/network/__init__.py
from .http_client_registry import HTTPClientRegistry, get_http_client_registry
from .http_client_wrapper import HTTPClientWrapper

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "HTTPClientRegistry",
    "HTTPClientWrapper",
    "get_http_client_registry",
]
