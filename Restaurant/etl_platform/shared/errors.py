"""Shared platform error classes."""


class PlatformError(Exception):
    """Base exception for platform modules."""


class ValidationError(PlatformError):
    """Raised when input validation fails."""


class ConfigurationError(PlatformError):
    """Raised when tenant or module configuration is invalid."""

