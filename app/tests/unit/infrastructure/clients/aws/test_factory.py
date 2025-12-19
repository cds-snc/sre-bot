import pytest


@pytest.mark.unit
def test_aws_clients_facade_exists(aws_factory):
    # Basic smoke test that the facade is constructed by the fixture
    assert hasattr(aws_factory, "dynamodb")
    assert hasattr(aws_factory, "identitystore")
    assert hasattr(aws_factory, "organizations")
    assert hasattr(aws_factory, "sso_admin")
