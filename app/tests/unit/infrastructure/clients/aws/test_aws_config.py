import pytest

from infrastructure.clients.aws.config import ConfigClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.fixture
def session_provider():
    return SessionProvider(region="us-east-1")


@pytest.mark.unit
@pytest.mark.skip(reason="Deprecated tests, marked for deletion")
def test_describe_aggregate_compliance_calls_execute(monkeypatch, session_provider):
    client = ConfigClient(session_provider=session_provider, role_arn=None)

    called = {}

    def fake_execute(service, method, **kwargs):
        called["service"] = service
        called["method"] = method
        return []

    monkeypatch.setattr(
        "infrastructure.clients.aws.executor.execute_aws_api_call", fake_execute
    )

    result = client.describe_aggregate_compliance_by_config_rules("agg", {})
    assert result is not None
