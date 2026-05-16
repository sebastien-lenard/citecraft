from .cli import main

# Warning: don't include packages that can call themselves in a circular way
__all__ = [
    "main",
]
