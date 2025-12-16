from types import SimpleNamespace

import pytest

from infrastructure.clients.aws import sso as sso_module


class FakeSSOClient:
    def create_account_assignment(self, **kwargs):
        return {"AccountAssignmentCreationStatus": {"Status": "SUCCEEDED"}}

    def delete_account_assignment(self, **kwargs):
        return {"AccountAssignmentDeletionStatus": {"Status": "SUCCEEDED"}}

    def list_account_assignments(self, **kwargs):
        return {"AccountAssignments": [{"PrincipalId": kwargs.get("PrincipalId")}]}


def test_create_account_assignment(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeSSOClient(),
    )

    res = sso_module.create_account_assignment(
        user_id="u-1",
        account_id="111",
        permission_set_arn="arn:ps",
        instance_arn="inst-1",
    )
    assert res.is_success


def test_list_account_assignments(monkeypatch):
    monkeypatch.setattr(
        "infrastructure.clients.aws.client.get_boto3_client",
        lambda service_name, **kw: FakeSSOClient(),
    )

    res = sso_module.list_account_assignments_for_principal(
        "u-1", instance_arn="inst-1"
    )
    assert res.is_success
    assert isinstance(res.data, dict) or isinstance(res.data, list)
