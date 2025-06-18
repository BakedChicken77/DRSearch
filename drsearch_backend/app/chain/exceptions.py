# file: app/chain/exceptions.py

from __future__ import annotations


class ConfigurationError(RuntimeError):
    """Raised when an expected index configuration is missing or malformed."""
