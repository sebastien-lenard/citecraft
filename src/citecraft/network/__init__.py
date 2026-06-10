# src/citecraft/network/__init__.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
from .http_client_registry import HTTPClientRegistry, get_http_client_registry
from .http_client_wrapper import HTTPClientWrapper

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "HTTPClientRegistry",
    "HTTPClientWrapper",
    "get_http_client_registry",
]
