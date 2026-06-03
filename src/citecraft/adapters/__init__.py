# src/citecraft/adapters/__init__.py
from .citeproc_adapter import CiteprocAdapter

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "CiteprocAdapter",
]
