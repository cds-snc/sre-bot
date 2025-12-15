"""Fixtures for infrastructure models tests."""

import pytest


@pytest.fixture
def make_api_response():
    """Factory fixture for creating APIResponse instances."""

    def _make(success=True, data=None, message=None, error_code=None):
        from infrastructure.models import APIResponse

        return APIResponse(
            success=success,
            data=data,
            message=message,
            error_code=error_code,
        )

    return _make


@pytest.fixture
def make_error_response():
    """Factory fixture for creating ErrorResponse instances."""

    def _make(error="Error", error_code="ERROR", details=None):
        from infrastructure.models import ErrorResponse

        return ErrorResponse(
            error=error,
            error_code=error_code,
            details=details,
        )

    return _make
