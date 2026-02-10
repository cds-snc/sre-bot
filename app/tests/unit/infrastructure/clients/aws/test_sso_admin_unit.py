import pytest
import importlib

from infrastructure.operations.result import OperationResult


@pytest.mark.unit
@pytest.mark.skip(reason="Deprecated tests, marked for deletion")
class TestSsoAdmin:
    def test_sso_admin_methods_call_execute(self, monkeypatch, aws_factory):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(data={})

        sso_mod = importlib.import_module("infrastructure.clients.aws.sso_admin")
        monkeypatch.setattr(sso_mod, "execute_aws_api_call", fake_execute)

        res = aws_factory.sso_admin.create_account_assignment(
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
        res = aws_factory.sso_admin.delete_account_assignment(
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
        res = aws_factory.sso_admin.list_account_assignments(
            instance_arn="arn:aws:sso:::instance/ins",
            principal_id="p1",
            principal_type="USER",
        )
        assert res.is_success
        assert captured["service"] == "sso-admin"
        assert captured["method"] == "list_account_assignments"
