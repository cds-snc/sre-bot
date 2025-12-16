import pytest

from infrastructure.clients.aws import factory as aws_factory_module
from infrastructure.operations.result import OperationResult


@pytest.mark.unit
class TestDynamoDB:
    def test_build_client_kwargs_defaults(self, aws_factory):
        # aws_factory fixture already constructs with region us-east-1
        kwargs = aws_factory._build_client_kwargs()
        assert "session_config" in kwargs
        assert "client_config" in kwargs
        assert kwargs["session_config"]["region_name"] == "us-east-1"

    def test_factory_get_item_calls_execute(self, monkeypatch, aws_factory):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(data={"Item": {"id": {"S": "1"}}})

        monkeypatch.setattr(aws_factory_module, "execute_aws_api_call", fake_execute)

        res = aws_factory.get_item("tbl", {"id": {"S": "1"}})
        assert res.is_success
        assert captured["service"] == "dynamodb"
        assert captured["method"] == "get_item"
        assert captured["TableName"] == "tbl"


@pytest.mark.unit
class TestIdentityStore:
    def test_identitystore_methods_call_execute(self, monkeypatch, aws_factory):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(data={})

        monkeypatch.setattr(aws_factory_module, "execute_aws_api_call", fake_execute)

        # list_users
        res = aws_factory.list_users("sid-1")
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "list_users"
        assert captured["IdentityStoreId"] == "sid-1"

        # get_user
        captured.clear()
        res = aws_factory.get_user("sid-1", "uid-1")
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "describe_user"
        assert captured["UserId"] == "uid-1"

        # create_user
        captured.clear()
        res = aws_factory.create_user("sid-1", UserName="jsmith", DisplayName="J Smith")
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "create_user"
        assert captured["UserName"] == "jsmith"
        assert captured["DisplayName"] == "J Smith"

        # delete_user
        captured.clear()
        res = aws_factory.delete_user("sid-1", "uid-1")
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "delete_user"
        assert captured["UserId"] == "uid-1"


@pytest.mark.unit
class TestOrganizations:
    def test_organizations_methods_and_get_account_id_by_name(
        self, monkeypatch, aws_factory
    ):
        # list_organization_accounts / get_account_details
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(
                data={"Accounts": [{"Id": "111", "Name": "alpha"}]}
            )

        monkeypatch.setattr(aws_factory_module, "execute_aws_api_call", fake_execute)

        res = aws_factory.list_organization_accounts()
        assert res.is_success
        assert captured["service"] == "organizations"
        assert captured["method"] == "list_accounts"

        captured.clear()
        res = aws_factory.get_account_details("111")
        assert res.is_success
        assert captured["service"] == "organizations"
        assert captured["method"] == "describe_account"
        assert captured["AccountId"] == "111"

        # get_account_id_by_name - found
        captured.clear()
        # fake_execute already returns Accounts with Name 'alpha'
        res = aws_factory.get_account_id_by_name("alpha")
        assert res.is_success
        assert res.data.get("AccountId") == "111"

        # get_account_id_by_name - not found
        def fake_execute_no_accounts(service_name, method, **kwargs):
            return OperationResult.success(
                data={"Accounts": [{"Id": "222", "Name": "beta"}]}
            )

        monkeypatch.setattr(
            aws_factory_module, "execute_aws_api_call", fake_execute_no_accounts
        )
        res = aws_factory.get_account_id_by_name("nope")
        from infrastructure.operations.status import OperationStatus

        assert not res.is_success
        assert res.status == OperationStatus.PERMANENT_ERROR
        assert res.error_code == "ACCOUNT_NOT_FOUND"


@pytest.mark.unit
class TestSsoAdmin:
    def test_sso_admin_methods_call_execute(self, monkeypatch, aws_factory):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(data={})

        monkeypatch.setattr(aws_factory_module, "execute_aws_api_call", fake_execute)

        res = aws_factory.create_account_assignment(
            instance_arn="arn:aws:sso:::instance/ins",
            permission_set_arn="arn:permset",
            principal_id="p1",
            principal_type="USER",
            target_id="acct1",
        )
        assert res.is_success
        assert captured["service"] == "sso-admin"
        assert captured["method"] == "create_account_assignment"
        assert captured["InstanceArn"].startswith("arn:aws:sso")

        captured.clear()
        res = aws_factory.delete_account_assignment(
            instance_arn="arn:aws:sso:::instance/ins",
            permission_set_arn="arn:permset",
            principal_id="p1",
            principal_type="USER",
            target_id="acct1",
        )
        assert res.is_success
        assert captured["service"] == "sso-admin"
        assert captured["method"] == "delete_account_assignment"

        captured.clear()
        res = aws_factory.list_account_assignments_for_principal(
            instance_arn="arn:aws:sso:::instance/ins",
            principal_id="p1",
            principal_type="USER",
        )
        assert res.is_success
        assert captured["service"] == "sso-admin"
        assert captured["method"] == "list_account_assignments"
