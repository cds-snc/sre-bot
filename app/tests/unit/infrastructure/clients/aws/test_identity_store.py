from types import SimpleNamespace

import pytest

from infrastructure.clients.aws import identity_store as id_module


class FakeIdentityClient:
    def describe_user(self, **kwargs):
        return {"UserName": "alice", "UserId": kwargs.get("UserId")}

    def list_users(self, **kwargs):
        return {"Users": [{"UserName": "alice"}, {"UserName": "bob"}]}


def test_get_user(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeIdentityClient(),
    )

    res = id_module.get_user("u-123", identity_store_id="id-1")
    assert res.is_success
    assert res.data["UserName"] == "alice"


def test_list_users(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeIdentityClient(),
    )

    res = id_module.list_users(identity_store_id="id-1")
    assert res.is_success
    assert isinstance(res.data, dict)
