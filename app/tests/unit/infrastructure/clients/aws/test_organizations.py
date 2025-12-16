from types import SimpleNamespace

import pytest

from infrastructure.clients.aws import organizations as org_module


class FakeOrgClient:
    def list_accounts(self, **kwargs):
        return {
            "Accounts": [{"Id": "111", "Name": "one"}, {"Id": "222", "Name": "two"}]
        }

    def describe_account(self, **kwargs):
        return {"Account": {"Id": kwargs.get("AccountId"), "Name": "one"}}


def test_list_organization_accounts(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeOrgClient(),
    )

    res = org_module.list_organization_accounts()
    assert res.is_success
    assert isinstance(res.data, list) or isinstance(res.data, dict)


def test_get_account_details(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeOrgClient(),
    )

    res = org_module.get_account_details("111")
    assert res.is_success
    assert res.data.get("Account")
