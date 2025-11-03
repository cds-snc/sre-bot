import types

from modules.groups.errors import IntegrationError
import pytest


@pytest.mark.legacy
def test_integration_error_has_response_field():
    # Create a lightweight stand-in for IntegrationResponse
    fake_response = types.SimpleNamespace(
        success=False, data={"error": "boom"}, meta={"code": 500}
    )

    err = IntegrationError("integration failed", response=fake_response)

    assert isinstance(err, Exception)
    assert hasattr(err, "response")
    assert err.response is fake_response
    assert err.response.success is False
