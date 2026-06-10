# src/citecraft/schemas/types.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Custom Pydantic field types and structural validation rules for API URLs."""

import re
from typing import Annotated
from urllib.parse import urlparse, urlunparse

from pydantic import AfterValidator, BeforeValidator


def coerce_and_enforce_https(v: str) -> str:
    """Clean up, normalize, and enforce HTTPS on an incoming URL string."""
    if not isinstance(v, str):
        return v

    val_str = v.strip()

    # Bypass empty targets or typical filesystem indicators (/, .)
    if not val_str or val_str.startswith(("/", ".")):
        return val_str

    # Extract anything before a colon or double slash to check the scheme
    # e.g., matches 'ftp' out of 'ftp://://example.com' or 'ws://test'
    scheme_match = re.match(r"^([a-zA-Z0-9+-.]+)(?::|//)", val_str)

    if scheme_match:
        possible_scheme = scheme_match.group(1).lower()
        if possible_scheme in ("ftp", "sftp", "gopher", "ws", "wss"):
            err_msg = (
                f"URL must use 'https://' scheme. Got unsupported: '{possible_scheme}'"
            )
            raise ValueError(err_msg)

    # Strip any corrupt leading protocols/colons/slashes cleanly
    # Matches strings starting with http, https, colons, or slashes
    clean_str = re.sub(r"^(https?|://|:|/)+", "", val_str)

    # Rebuild uniformly into a valid URL structure
    parsed_final = urlparse(f"https://{clean_str}")

    return urlunparse(parsed_final)


def verify_object_name_placeholder(v: str) -> str:
    """Verify that the validated URL string contains the object template tag."""
    if "{object_name}" not in v:
        err_msg = (
            "URL must contain the mandatory '{object_name}' placeholder."  # No f""
        )
        raise ValueError(err_msg)
    return v


HttpsUrlStr = Annotated[str, BeforeValidator(coerce_and_enforce_https)]
UrlWithObjectName = Annotated[
    HttpsUrlStr,
    AfterValidator(verify_object_name_placeholder),
]
