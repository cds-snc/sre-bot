import pytest

from infrastructure.operations.result import OperationResult, OperationStatus


@pytest.mark.unit
@pytest.mark.skip(reason="Deprecated tests, marked for deletion")
class TestOrganizations:
    def test_organizations_methods_and_get_account_id_by_name(
        self, monkeypatch, aws_factory
    ):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(
                data={"Accounts": [{"Id": "111", "Name": "alpha"}]}
            )

        import importlib

        orgs_mod = importlib.import_module("infrastructure.clients.aws.organizations")
        monkeypatch.setattr(orgs_mod, "execute_aws_api_call", fake_execute)

        res = aws_factory.organizations.list_accounts()
        assert res.is_success
        assert captured["service"] == "organizations"
        assert captured["method"] == "list_accounts"

        captured.clear()
        res = aws_factory.organizations.describe_account("111")
        assert res.is_success
        assert captured["service"] == "organizations"
        assert captured["method"] == "describe_account"
        assert captured["AccountId"] == "111"

        # get_account_id_by_name - found
        captured.clear()
        res = aws_factory.organizations.get_account_id_by_name("alpha")
        assert res.is_success
        assert res.data.get("AccountId") == "111"

        # get_account_id_by_name - not found
        def fake_execute_no_accounts(service_name, method, **kwargs):
            return OperationResult.success(
                data={"Accounts": [{"Id": "222", "Name": "beta"}]}
            )

        monkeypatch.setattr(orgs_mod, "execute_aws_api_call", fake_execute_no_accounts)
        res = aws_factory.organizations.get_account_id_by_name("nope")

        assert not res.is_success
        assert res.status == OperationStatus.PERMANENT_ERROR
        assert res.error_code == "ACCOUNT_NOT_FOUND"
