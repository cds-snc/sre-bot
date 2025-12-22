import importlib
import pytest

from infrastructure.operations.result import OperationResult


@pytest.mark.unit
@pytest.mark.skip(reason="Deprecated tests, marked for deletion")
class TestDynamoDB:
    def test_build_client_kwargs_defaults(self, aws_factory):
        # aws_factory fixture already constructs with region us-east-1
        kwargs = aws_factory.dynamodb._session_provider.build_client_kwargs()
        assert "session_config" in kwargs
        assert "client_config" in kwargs
        assert kwargs["session_config"]["region_name"] == "us-east-1"

    def test_get_item_calls_execute(self, monkeypatch, aws_factory):
        captured = {}

        def fake_execute(service_name, method, **kwargs):
            captured["service"] = service_name
            captured["method"] = method
            captured.update(kwargs)
            return OperationResult.success(data={"Item": {"id": {"S": "1"}}})

        dynamodb_mod = importlib.import_module("infrastructure.clients.aws.dynamodb")
        monkeypatch.setattr(dynamodb_mod, "execute_aws_api_call", fake_execute)

        res = aws_factory.dynamodb.get_item("tbl", {"id": {"S": "1"}})
        assert res.is_success
        assert captured["service"] == "dynamodb"
        assert captured["method"] == "get_item"
        assert captured["TableName"] == "tbl"
