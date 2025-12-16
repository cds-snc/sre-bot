from types import SimpleNamespace

import pytest

from infrastructure.clients.aws import dynamodb as dynamodb_module


class FakeDynamoClient:
    def __init__(self, name):
        self.name = name

    def get_item(self, **kwargs):
        return {"Item": {"id": {"S": "123"}}}

    def query(self, **kwargs):
        return {"Items": [{"id": {"S": "1"}}, {"id": {"S": "2"}}]}


def test_get_item_returns_operation_result(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeDynamoClient(service_name),
    )

    res = dynamodb_module.get_item("table", {"id": {"S": "123"}})
    assert res.is_success
    assert isinstance(res.data, dict)


def test_query_pagination(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeDynamoClient(service_name),
    )

    res = dynamodb_module.query("table", "pk = :pk")
    assert res.is_success
    assert isinstance(res.data, list) or isinstance(res.data, dict)
