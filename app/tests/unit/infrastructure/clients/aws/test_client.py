from types import SimpleNamespace

import pytest

from botocore.exceptions import ClientError

from infrastructure.clients.aws import client as aws_client
from infrastructure.operations.status import OperationStatus


import pytest


@pytest.mark.unit
class TestClient:
    def test_calculate_retry_delay(self):
        assert aws_client._calculate_retry_delay(0) == pytest.approx(0.5)
        assert aws_client._calculate_retry_delay(1) == pytest.approx(1.0)
        assert aws_client._calculate_retry_delay(
            3, backoff_factor=1.0
        ) == pytest.approx(8.0)

    @staticmethod
    def make_client_with_method(result=None, raise_exc=None):
        class Dummy:
            def __init__(self):
                self._result = result

            def some_method(self, **kwargs):
                if raise_exc:
                    raise raise_exc
                return self._result

        return Dummy()

    def test_map_client_error_conflict_treated_as_success(self, monkeypatch):
        # Build a fake ClientError with ResourceAlreadyExistsException
        response = {
            "Error": {"Code": "ResourceAlreadyExistsException", "Message": "exists"}
        }
        e = ClientError(response, operation_name="Create")

        res = aws_client._map_client_error(e, "s3", "create_bucket", True, None)
        assert res.is_success

    def test_map_client_error_conflict_permanent(self, monkeypatch):
        response = {"Error": {"Code": "EntityAlreadyExists", "Message": "exists"}}
        e = ClientError(response, operation_name="Create")

        res = aws_client._map_client_error(e, "s3", "create_bucket", False, None)
        assert res.status == OperationStatus.PERMANENT_ERROR

    def test_map_client_error_throttling_returns_transient(self):
        response = {
            "Error": {"Code": "ThrottlingException", "Message": "throttle"},
            "RetryAfter": "2",
        }
        e = ClientError(response, operation_name="List")
        res = aws_client._map_client_error(e, "dynamodb", "query", False, None)
        assert res.status == OperationStatus.TRANSIENT_ERROR
        assert res.retry_after in (2, None)

    def test_map_client_error_unauthorized(self):
        response = {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}
        e = ClientError(response, operation_name="Get")
        res = aws_client._map_client_error(e, "iam", "get_user", False, None)
        assert res.status == OperationStatus.UNAUTHORIZED

    def test_execute_aws_api_call_success(self, monkeypatch):
        # Patch get_boto3_client to return a client with desired method
        dummy = SimpleNamespace()

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            obj = SimpleNamespace()

            def fake_method(**kwargs):
                return {"ok": True, "args": kwargs}

            setattr(obj, "describe_something", fake_method)
            return obj

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)

        res = aws_client.execute_aws_api_call(
            "service", "describe_something", max_retries=0
        )
        assert res.is_success
        assert res.data == {"ok": True, "args": {}}

    def test_execute_aws_api_call_clienterror_retry(self, monkeypatch):
        calls = {"count": 0}

        class FakeClient:
            def __init__(self):
                pass

            def flaky(self, **kwargs):
                calls["count"] += 1
                if calls["count"] < 2:
                    response = {
                        "Error": {"Code": "ThrottlingException", "Message": "throttle"}
                    }
                    raise ClientError(response, operation_name="Flaky")
                return {"ok": True}

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return FakeClient()

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)
        res = aws_client.execute_aws_api_call(
            "svc", "flaky", max_retries=2, backoff_factor=0
        )
        assert res.is_success
        assert calls["count"] >= 2

    def test_force_paginate_with_keys(self, monkeypatch):
        pages = [{"Items": [1, 2]}, {"Items": [3]}]

        class FakePaginator:
            def __init__(self, pages):
                self._pages = pages

            def paginate(self, **kwargs):
                yield from self._pages

        class FakeClient:
            def get_paginator(self, method_name):
                return FakePaginator(pages)

            def list(self, **kwargs):
                return None

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return FakeClient()

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)

        result = aws_client._call_api_once(
            service_name="svc",
            method="list",
            keys=["Items"],
            role_arn=None,
            session_config=None,
            client_config=None,
            force_paginate=True,
            kwargs={},
        )

        assert result == [1, 2, 3]

    def test_force_paginate_without_keys(self, monkeypatch):
        pages = [
            {"Items": [{"id": 1}], "Count": 1, "ResponseMetadata": {}},
            {"Items": [{"id": 2}], "Count": 1},
        ]

        class FakePaginator:
            def __init__(self, pages):
                self._pages = pages

            def paginate(self, **kwargs):
                yield from self._pages

        class FakeClient:
            def get_paginator(self, method_name):
                return FakePaginator(pages)

            def list(self, **kwargs):
                return None

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return FakeClient()

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)

        result = aws_client._call_api_once(
            service_name="svc",
            method="list",
            keys=None,
            role_arn=None,
            session_config=None,
            client_config=None,
            force_paginate=True,
            kwargs={},
        )

        assert result == [{"id": 1}, 1, {"id": 2}, 1]

    def test_conflict_callback_invoked_treat_as_success(self, monkeypatch):
        called = {"flag": False}

        class FakeClient:
            def create(self, **kwargs):
                response = {
                    "Error": {"Code": "EntityAlreadyExists", "Message": "exists"}
                }
                raise ClientError(response, operation_name="Create")

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return FakeClient()

        def conflict_cb(exc):
            called["flag"] = True

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)

        res = aws_client.execute_aws_api_call(
            "svc",
            "create",
            treat_conflict_as_success=True,
            conflict_callback=conflict_cb,
            max_retries=0,
        )

        assert called["flag"] is True
        assert res.is_success

    def test_conflict_callback_exception_handled(self, monkeypatch):
        # callback raises; execute_aws_api_call should not propagate
        class FakeClient:
            def create(self, **kwargs):
                response = {
                    "Error": {"Code": "ConflictException", "Message": "conflict"}
                }
                raise ClientError(response, operation_name="Create")

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return FakeClient()

        def conflict_cb(exc):
            raise RuntimeError("callback failed")

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)

        res = aws_client.execute_aws_api_call(
            "svc",
            "create",
            treat_conflict_as_success=True,
            conflict_callback=conflict_cb,
            max_retries=0,
        )

        assert res.is_success

    def test_conflict_callback_invoked_permanent_error(self, monkeypatch):
        called = {"flag": False}

        class FakeClient:
            def create(self, **kwargs):
                response = {
                    "Error": {"Code": "EntityAlreadyExists", "Message": "exists"}
                }
                raise ClientError(response, operation_name="Create")

        def get_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return FakeClient()

        def conflict_cb(exc):
            called["flag"] = True

        monkeypatch.setattr(aws_client, "get_boto3_client", get_boto3_client)

        res = aws_client.execute_aws_api_call(
            "svc",
            "create",
            treat_conflict_as_success=False,
            conflict_callback=conflict_cb,
            max_retries=0,
        )

        assert called["flag"] is True
        from infrastructure.operations.status import OperationStatus

        assert not res.is_success
        assert res.status == OperationStatus.PERMANENT_ERROR
