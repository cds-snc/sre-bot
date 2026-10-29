"""Unit tests for the required-dependency error a plugin raises from ``register_requirements``.

The error is built directly; the assertions read only its public surface: the
configuration setting it names and its message, which must carry no value.
"""

import pytest

from contracts.plugins.requirements import RequiredDependencyError

pytestmark = pytest.mark.unit


def test_required_dependency_error_names_the_setting_to_configure() -> None:
    error = RequiredDependencyError("openai.tenant")

    assert error.setting == "openai.tenant"
    assert "openai.tenant" in str(error)
