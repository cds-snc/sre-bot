import logging
import pytest
from types import SimpleNamespace

from botocore.exceptions import ClientError

from integrations.aws import client_next
from models.integrations import IntegrationResponse
from tests.fixtures.aws_clients import FakeClient


def test__can_paginate_method_fallback():
    class NoPaginate:
        pass

    client = NoPaginate()

    # Should return False and not raise
    assert client_next._can_paginate_method(client, "list_things") is False


def test__paginate_all_results_respects_keys():
    pages = [
        {"Items": [{"id": 1}], "ResponseMetadata": {"RequestId": "r1"}},
        {"Items": [{"id": 2}], "Other": ["x"]},
    ]
    # Provide a client that has paginator pages and also exposes the API method
    # name so getattr(client, method) doesn't raise when execute_aws_api_call
    # constructs api_method before deciding to paginate.
    client = FakeClient(
        paginated_pages=pages, api_responses={"list_items": lambda **kw: {}}
    )

    results = client_next._paginate_all_results(client, "list_items", keys=["Items"])
    assert results == [{"id": 1}, {"id": 2}]


def test_get_aws_client_assumes_role(monkeypatch):
    # Fake STS client that returns temporary credentials
    class FakeSTS:
        def assume_role(self, RoleArn, RoleSessionName):
            return {
                "Credentials": {
                    "AccessKeyId": "AK",
                    "SecretAccessKey": "SK",
                    "SessionToken": "TK",
                }
            }

    # Fake Session that captures provided credentials and returns an object with client()
    created = {}

    class FakeSession:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def client(self, service_name, **client_config):
            # Return a fake client so callers can call methods on it
            return FakeClient()

    class FakeBoto3:
        def client(self, svc_name):
            if svc_name == "sts":
                return FakeSTS()

        Session = FakeSession

    monkeypatch.setattr(client_next, "boto3", FakeBoto3())

    client = client_next.get_aws_client("svc", role_arn="arn:aws:iam::123:role/test")

    # Should return a client-like object
    assert isinstance(client, FakeClient)
    # Ensure our FakeSession received the temporary credentials keys
    assert created.get("aws_access_key_id") == "AK"
    assert created.get("aws_secret_access_key") == "SK"
    assert created.get("aws_session_token") == "TK"


def test_execute_aws_api_call_non_paginated_uses_api_method(monkeypatch):
    # Fake client where the api method returns a dict
    fake = FakeClient(api_responses={"get_item": {"item": 1}})

    def fake_get_aws_client(
        service_name,
        session_config=None,
        client_config=None,
        role_arn=None,
        session_name="DefaultSession",
    ):
        return fake

    monkeypatch.setattr(client_next, "get_aws_client", fake_get_aws_client)

    resp = client_next.execute_aws_api_call(service_name="svc", method="get_item")

    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == {"item": 1}


def test_execute_api_call_success():
    def api_call() -> dict:
        return {"items": [1, 2, 3]}

    resp = client_next.execute_api_call("test_service_method", api_call)

    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == {"items": [1, 2, 3]}


def test_paginate_all_results_aggregates_pages():
    pages = [
        {"Items": [{"id": 1}], "ResponseMetadata": {"RequestId": "r1"}},
        {"Items": [{"id": 2}]},
    ]
    # Provide a client that has paginator pages and exposes the API method name so
    # getattr(client, method) doesn't raise when execute_aws_api_call constructs
    # api_method before deciding to paginate.
    client = FakeClient(
        paginated_pages=pages, api_responses={"list_items": lambda **kw: {}}
    )

    # Monkeypatch get_aws_client to return our fake client so execute_aws_api_call
    # follows the paginated branch and uses _paginate_all_results internally.
    def fake_get_aws_client(
        service_name,
        session_config=None,
        client_config=None,
        role_arn=None,
        session_name="DefaultSession",
    ):
        return client

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(client_next, "get_aws_client", fake_get_aws_client)
        resp = client_next.execute_aws_api_call(service_name="svc", method="list_items", keys=["Items"])  # type: ignore[arg-type]
    finally:
        monkeypatch.undo()

    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == [{"id": 1}, {"id": 2}]


def test_execute_api_call_retries_on_retryable_error(monkeypatch, caplog):
    attempts = {"count": 0}

    def api_call() -> dict:
        if attempts["count"] < 2:
            attempts["count"] += 1
            raise ClientError(
                {"Error": {"Code": "Throttling", "Message": "throttle"}}, "Op"
            )
        return {"ok": True}

    sleeps: list[float] = []

    import time as _time

    def fake_sleep(seconds: float) -> None:
        sleeps.append(float(seconds))

    monkeypatch.setattr(_time, "sleep", fake_sleep)

    caplog.set_level(logging.WARNING)

    resp = client_next.execute_api_call("svc_method", api_call, max_retries=3)

    # Should succeed after retries
    assert resp.success is True
    assert resp.data == {"ok": True}

    # Ensure we retried (should have recorded sleeps for exponential backoff)
    assert len(sleeps) >= 1
    # Check exponential pattern for at least first two retries (1.0, 2.0) with default backoff 1.0
    assert pytest.approx(sleeps[0], rel=1e-3) == 1.0
    if len(sleeps) > 1:
        assert pytest.approx(sleeps[1], rel=1e-3) == 2.0


def test_execute_api_call_handles_non_retryable_error(monkeypatch, caplog):
    # api_call raises a non-retryable exception
    def api_call():
        raise ValueError("fatal")

    caplog.set_level(logging.ERROR)

    resp = client_next.execute_api_call("svc_fatal", api_call, max_retries=2)

    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert resp.error.get("function_name") == "svc_fatal"


def test_handle_final_error_logs_non_critical_and_critical(monkeypatch, caplog):
    # Prepare an error message that matches non_critical for a fake function
    err = Exception("user not found in directory")

    # Temporarily patch ERROR_CONFIG to classify svc_user as having 'not found' non-critical
    monkeypatch.setitem(
        client_next.ERROR_CONFIG,
        "non_critical_errors",
        {"svc_user": ["not found", "timed out"]},
    )

    caplog.set_level(logging.WARNING)
    resp = client_next._handle_final_error(err, "svc_user")
    assert resp.success is False
    # Non-critical should warn (not error)
    assert any("aws_api_non_critical_error" in rec.message for rec in caplog.records)

    # Now check critical path
    caplog.clear()
    resp2 = client_next._handle_final_error(Exception("unexpected failure"), "svc_user")
    assert resp2.success is False
    assert any("aws_api_error_final" in rec.message for rec in caplog.records)


def test_execute_aws_api_call_force_paginate_even_if_client_cant_paginate(monkeypatch):
    # Create a client that reports can_paginate False but has a paginator
    pages = [{"Items": [{"id": 10}]}, {"Items": [{"id": 11}]}]

    # Use centralized FakeClient fixture: it can be configured to report
    # can_paginate=False while still providing paginator pages.
    client = FakeClient(paginated_pages=pages, can_paginate=False)

    def fake_get_aws_client(*a, **kw):
        return client

    monkeypatch.setattr(client_next, "get_aws_client", fake_get_aws_client)

    resp = client_next.execute_aws_api_call(
        service_name="svc", method="list_items", keys=["Items"], force_paginate=True
    )

    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == [{"id": 10}, {"id": 11}]


def test__paginate_all_results_handles_non_list_values():
    pages = [{"Value": {"a": 1}, "ResponseMetadata": {}}, {"Value": {"b": 2}}]
    client = FakeClient(paginated_pages=pages)

    results = client_next._paginate_all_results(client, "some_method")
    assert results == [{"a": 1}, {"b": 2}]


def test_get_aws_client_no_role_uses_session_region(monkeypatch):
    created = {}

    class FakeSession:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def client(self, service_name, **client_config):
            return FakeClient()

    class FakeBoto3:
        Session = FakeSession

    monkeypatch.setattr(client_next, "boto3", FakeBoto3())

    client = client_next.get_aws_client("svc")
    assert isinstance(client, FakeClient)
    # default session_config should include the module AWS_REGION
    assert created.get("region_name") == client_next.AWS_REGION


def test_default_max_retries_honored(monkeypatch):
    # Ensure that when max_retries is None we use ERROR_CONFIG['default_max_retries']
    monkeypatch.setitem(client_next.ERROR_CONFIG, "default_max_retries", 1)

    attempts = {"count": 0}
    sleeps: list[float] = []

    def api_call():
        if attempts["count"] < 1:
            attempts["count"] += 1
            raise client_next.ClientError({"Error": {"Code": "Throttling"}}, "Op")
        return {"ok": True}

    import time as _time

    def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(_time, "sleep", fake_sleep)

    resp = client_next.execute_api_call("svc_retry_default", api_call)
    assert resp.success is True
    assert len(sleeps) == 1


def test_calculate_retry_delay_fallback_on_invalid_backoff(monkeypatch):
    monkeypatch.setitem(
        client_next.ERROR_CONFIG, "default_backoff_factor", "not-a-number"
    )
    # attempt 1 => backoff fallback 0.5 * 2**1 = 1.0
    val = client_next._calculate_retry_delay(1)
    assert pytest.approx(val, rel=1e-6) == 1.0


def test_execute_aws_api_call_with_non_iterable_key_returns_error(monkeypatch):
    # paginator yields a page where Items is None; with keys specified, _paginate_all_results
    # will attempt to extend None and raise; execute_aws_api_call should return an error IntegrationResponse
    pages = [{"Items": None}, {"Items": [{"id": 2}]}]
    client = FakeClient(paginated_pages=pages)

    def fake_get_aws_client(*a, **kw):
        return client

    monkeypatch.setattr(client_next, "get_aws_client", fake_get_aws_client)

    resp = client_next.execute_aws_api_call(service_name="svc", method="list_items", keys=["Items"])  # type: ignore[arg-type]
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None


def test__should_retry_detects_retryable_and_non_retryable():
    # Retryable
    e_retry = client_next.ClientError({"Error": {"Code": "Throttling"}}, "Op")
    assert client_next._should_retry(e_retry, attempt=0, max_attempts=2) is True

    # Non-retryable
    e_other = client_next.ClientError({"Error": {"Code": "Other"}}, "Op")
    assert client_next._should_retry(e_other, attempt=0, max_attempts=2) is False


def test_aws_api_error_properties():
    err = client_next.AWSAPIError("oops", error_code="E123", function_name="fn")
    assert err.message == "oops"
    assert err.error_code == "E123"
    assert err.function_name == "fn"


def test_should_retry_with_invalid_retry_errors_type(monkeypatch):
    # Temporarily set retry_errors to an invalid type (string) and ensure
    # the function falls back to an empty list and returns False.
    orig = client_next.ERROR_CONFIG.get("retry_errors")
    monkeypatch.setitem(client_next.ERROR_CONFIG, "retry_errors", "not-a-list")

    fake_error = SimpleNamespace(response={"Error": {"Code": "Throttling"}})

    try:
        assert client_next._should_retry(fake_error, attempt=0, max_attempts=3) is False
    finally:
        monkeypatch.setitem(client_next.ERROR_CONFIG, "retry_errors", orig)


def test_paginate_all_results_appends_non_list_values():
    pages = [
        {"Items": {"id": 1}, "ResponseMetadata": {"RequestId": "r1"}},
        {"Items": [{"id": 2}]},
    ]
    client = FakeClient(paginated_pages=pages)

    results = client_next._paginate_all_results(client, "list_items")
    # First page had a non-list value for Items, it should be appended as-is
    assert results == [{"id": 1}, {"id": 2}]


def test_execute_api_call_clienterror_non_retryable():
    # Create a ClientError with a code that's not retryable
    err = ClientError({"Error": {"Code": "OtherError", "Message": "bad"}}, "op")

    def api_call():
        raise err

    resp = client_next.execute_api_call("svc_method", api_call, max_retries=1)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    # Error info should include the ClientError message/code
    assert resp.error is not None
    assert (
        "OtherError" in str(resp.error.get("error_code"))
        or resp.error.get("error_code") == "OtherError"
    )


def test_execute_api_call_empty_loop_unknown_error():
    called = {"val": False}

    def api_call():
        called["val"] = True
        return {"ok": True}

    # max_retries = -1 will make range(max_retry_attempts + 1) empty and skip the loop
    resp = client_next.execute_api_call("svc_empty", api_call, max_retries=-1)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert "Unknown error after retries" in str(resp.error.get("message"))
    # Ensure the api_call was not invoked
    assert called["val"] is False
