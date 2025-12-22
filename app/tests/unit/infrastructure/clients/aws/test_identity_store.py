import importlib
import pytest

from infrastructure.operations.result import OperationResult


@pytest.mark.unit
@pytest.mark.skip(reason="Deprecated tests, marked for deletion")
class TestIdentityStore:
    def test_identitystore_methods_call_execute(self, monkeypatch, aws_factory):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(data={})

        identity_mod = importlib.import_module(
            "infrastructure.clients.aws.identity_store"
        )
        monkeypatch.setattr(identity_mod, "execute_aws_api_call", fake_execute)

        # list_users - uses facade's configured identity_store_id
        res = aws_factory.identitystore.list_users()
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "list_users"
        assert captured["IdentityStoreId"] == "store-1234567890"

        # describe_user - uses facade's configured identity_store_id
        captured.clear()
        res = aws_factory.identitystore.describe_user("uid-1")
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "describe_user"
        assert captured["UserId"] == "uid-1"
        assert captured["IdentityStoreId"] == "store-1234567890"

        # create_user - uses facade's configured identity_store_id
        captured.clear()
        res = aws_factory.identitystore.create_user(
            UserName="jsmith", DisplayName="J Smith"
        )
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "create_user"
        assert captured["UserName"] == "jsmith"
        assert captured["DisplayName"] == "J Smith"
        assert captured["IdentityStoreId"] == "store-1234567890"

        # delete_user - uses facade's configured identity_store_id
        captured.clear()
        res = aws_factory.identitystore.delete_user("uid-1")
        assert res.is_success
        assert captured["service"] == "identitystore"
        assert captured["method"] == "delete_user"
        assert captured["UserId"] == "uid-1"
        assert captured["IdentityStoreId"] == "store-1234567890"
