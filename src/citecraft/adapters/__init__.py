# src/citecraft/adapters/__init__.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
from .citeproc_adapter import CiteprocAdapter

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "CiteprocAdapter",
]
