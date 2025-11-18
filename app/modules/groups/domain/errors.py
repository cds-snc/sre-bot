"""Errors for the groups module."""

from typing import Any


class IntegrationError(Exception):
    """Raised by provider adapters when their underlying integration reports an error.

    Attributes:
        message: human-friendly message
        response: the original IntegrationResponse object returned by the integration
    """

    def __init__(self, message: str, response: Any = None):
        super().__init__(message)
        self.response = response
