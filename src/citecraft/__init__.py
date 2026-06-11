# src/citecraft/__init__.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
from .cli import ProcessedArgs, cli

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "ProcessedArgs",
    "cli",
]
