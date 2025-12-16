import builtins
from types import SimpleNamespace

import pytest

from infrastructure.clients.aws.client import get_boto3_client, execute_aws_api_call


class FakeClient:
    def __init__(self, service_name):
        self._service = service_name

    def describe_foo(self, **kwargs):
        return {"Foo": "bar", "CalledWith": kwargs}


def test_get_boto3_client_assume_role(monkeypatch):
    # Monkeypatch boto3 to return session with client factory
    fake_session = SimpleNamespace()
    fake_session.client = lambda svc, **cfg: FakeClient(svc)

    monkeypatch.setattr(
        "infrastructure.clients.aws.client.boto3.Session", lambda **kwargs: fake_session
    )
    client = get_boto3_client("foo", session_config={"region_name": "us-east-1"})
    assert isinstance(client, FakeClient)


def test_execute_aws_api_call_success(monkeypatch):
    # Patch get_boto3_client to return a fake client with method
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeClient(service_name),
    )

    result = execute_aws_api_call("foo", "describe_foo")
    assert result.is_success
    assert result.data["Foo"] == "bar"
