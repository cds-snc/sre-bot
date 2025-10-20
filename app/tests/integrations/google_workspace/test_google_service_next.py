from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from integrations.google_workspace import google_service_next as gs
import math


# --- _calculate_retry_delay ---
def test_calculate_retry_delay_rate_limit_numeric():
    gs.ERROR_CONFIG["rate_limit_delay"] = 60
    assert gs._calculate_retry_delay(1, 429) == 60.0


def test_calculate_retry_delay_rate_limit_string():
    gs.ERROR_CONFIG["rate_limit_delay"] = "30"
    assert gs._calculate_retry_delay(2, 429) == 30.0


def test_calculate_retry_delay_server_error():
    gs.ERROR_CONFIG["default_backoff_factor"] = 2
    assert math.isclose(
        gs._calculate_retry_delay(2, 500), 8.0
    )  # pylint: disable=protected-access


def test_calculate_retry_delay_invalid_type():
    gs.ERROR_CONFIG["rate_limit_delay"] = object()
    try:
        gs._calculate_retry_delay(1, 429)  # pylint: disable=protected-access
    except TypeError:
        pass
    else:
        assert False, "Should raise TypeError"


def test_calculate_retry_delay_invalid_backoff_factor():
    gs.ERROR_CONFIG["default_backoff_factor"] = object()
    try:
        gs._calculate_retry_delay(1, 500)  # Should raise TypeError
    except TypeError:
        pass
    else:
        assert False, "Should raise TypeError for invalid default_backoff_factor"


# --- _handle_final_error ---
def test_handle_final_error_return_none_on_error():
    error = Exception("fail")
    assert gs._handle_final_error(error, "func", False, True) is None


# --- execute_api_call generic retry branch ---
@patch(
    "integrations.google_workspace.google_service_next.time.sleep", return_value=None
)
@patch("integrations.google_workspace.google_service_next.logger")
def test_execute_api_call_generic_retry(logger_mock, _sleep_mock):
    gs.ERROR_CONFIG["default_backoff_factor"] = 1.0  # Ensure default value

    calls = []

    def api():
        calls.append(1)
        if len(calls) < 2:
            raise Exception("fail")
        return "ok"

    result = gs.execute_api_call("func", api)
    assert result == "ok"
    assert len(calls) == 2
    logger_mock.warning.assert_any_call(
        "google_api_retrying_generic",
        function="func",
        attempt=1,
        delay=1.0,
        error="fail",
    )


# --- execute_api_call final error after retries ---
def test_execute_api_call_final_error():

    def api():
        raise Exception("fail")

    with pytest.raises(gs.GoogleAPIError):
        gs.execute_api_call("func", api, max_retries=0)


# --- get_google_service: SRE_BOT_EMAIL None branch ---
@patch("integrations.google_workspace.google_service_next.build")
@patch(
    "integrations.google_workspace.google_service_next.service_account.Credentials.from_service_account_info"
)
@patch(
    "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    '{"client_email": "bot@example.com", "private_key": "FAKE", "token_uri": "https://oauth2.googleapis.com/token"}',
)
@patch("integrations.google_workspace.google_service_next.SRE_BOT_EMAIL", None)
def test_get_google_service_no_delegated_user_email(creds_mock, build_mock):

    build_mock.return_value = "service"
    creds_mock.return_value = MagicMock()
    service = gs.get_google_service("admin", "v1")
    assert service == "service"


# --- execute_batch_request exception branch ---
@patch("integrations.google_workspace.google_service_next.logger")
def test_execute_batch_request_exception(logger_mock):

    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch
    fake_batch.add.side_effect = lambda req, request_id=None: None
    fake_batch.execute.side_effect = Exception("fail")
    requests = [("id1", MagicMock())]
    try:
        gs.execute_batch_request(fake_service, requests)
    except Exception:
        pass
    else:
        assert False, "Should raise Exception"
    logger_mock.error.assert_any_call("batch_execution_failed", error="fail")


# --- paginate_all_results: auto-detect resource key, response as list, no execute_next_chunk ---
@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results_auto_detect_key(execute_api_call_mock):

    class FakeRequest:
        def __init__(self):
            self.calls = 0

        def execute(self):
            self.calls += 1
            if self.calls == 1:
                return {"foo": [1, 2], "nextPageToken": "abc"}
            elif self.calls == 2:
                return {"foo": [3], "nextPageToken": None}
            else:
                return None

        def execute_next_chunk(self):
            if self.calls < 2:
                return (self, None)
            return (None, None)

    req = FakeRequest()
    results = gs.paginate_all_results(req)
    assert results == [1, 2, 3]


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results_response_list(execute_api_call_mock):

    class FakeRequest:
        def __init__(self):
            self.calls = 0

        def execute(self):
            self.calls += 1
            if self.calls == 1:
                return [1, 2]
            else:
                return None

        # No execute_next_chunk

    req = FakeRequest()
    results = gs.paginate_all_results(req)
    assert results == [1, 2]


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results_no_execute_next_chunk(execute_api_call_mock):

    class FakeRequest:
        def __init__(self):
            self.calls = 0

        def execute(self):
            self.calls += 1
            if self.calls == 1:
                return {"foo": [1], "nextPageToken": "abc"}
            else:
                return None

        # No execute_next_chunk

    req = FakeRequest()
    results = gs.paginate_all_results(req, resource_key="foo")
    assert results == [1]


# --- Fixtures ---
@pytest.fixture
@patch("integrations.google_workspace.google_service_next.settings")
def fake_settings(settings_mock):
    class FakeGoogleWorkspace:
        GOOGLE_WORKSPACE_CUSTOMER_ID = "fake_customer_id"
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE = (
            '{"client_email": "bot@example.com", "private_key": "FAKE"}'
        )
        SRE_BOT_EMAIL = "bot@example.com"

    class FakeSettings:
        google_workspace = FakeGoogleWorkspace()

    settings_mock.google_workspace = FakeGoogleWorkspace()
    return FakeSettings()


# --- get_google_service ---
@patch(
    "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    '{"client_email": "bot@example.com", "private_key": "FAKE", "token_uri": "https://oauth2.googleapis.com/token"}',
)
@patch("integrations.google_workspace.google_service_next.build")
@patch(
    "integrations.google_workspace.google_service_next.service_account.Credentials.from_service_account_info"
)
def test_get_google_service_success(creds_mock, build_mock):
    build_mock.return_value = "service"
    creds_mock.return_value = MagicMock()
    service = gs.get_google_service("admin", "v1")
    assert service == "service"
    build_mock.assert_called_once()


@patch(
    "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    None,
)
def test_get_google_service_missing_creds():
    with pytest.raises(ValueError):
        gs.get_google_service("admin", "v1")


@patch(
    "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
    "not-json",
)
def test_get_google_service_invalid_json():
    with pytest.raises(Exception):
        gs.get_google_service("admin", "v1")


# --- execute_api_call ---
def test_execute_api_call_success():
    def api():
        return 42

    assert gs.execute_api_call("func", api) == 42


@patch(
    "integrations.google_workspace.google_service_next.ERROR_CONFIG",
    {
        "non_critical_errors": {
            "get_user": ["not found", "timed out"],
            "get_member": ["not found", "member not found"],
            "get_group": ["not found", "group not found"],
            "get_sheet": ["unable to parse range"],
        },
        "retry_errors": [429, 500, 502, 503, 504],
        "rate_limit_delay": 60,
        "default_max_retries": 3,
        "default_backoff_factor": 1.0,
    },
)
@patch("integrations.google_workspace.google_service_next.logger")
@patch(
    "integrations.google_workspace.google_service_next.time.sleep", return_value=None
)
def test_execute_api_call_http_error_retry(_sleep_mock, logger_mock):
    # Simulate HttpError with retryable status
    class FakeResp:
        status = 429
        reason = "Too Many Requests"

        def get(self, key, default=None):
            return getattr(self, key, default)

    err = HttpError(resp=FakeResp(), content=b"rate limit")
    calls = []

    def api():
        calls.append(1)
        if len(calls) < 2:
            raise err
        return "ok"

    result = gs.execute_api_call("func", api)
    assert result == "ok"
    assert len(calls) == 2
    logger_mock.warning.assert_any_call(
        "google_api_retrying",
        function="func",
        attempt=1,
        status_code=429,
        delay=60.0,
        error=str(err),
    )


@patch("integrations.google_workspace.google_service_next.logger")
def test_execute_api_call_non_critical(logger_mock):
    def api():
        raise Exception("not found")

    result = gs.execute_api_call("get_user", api, non_critical=True)
    assert result is None
    logger_mock.warning.assert_any_call(
        "google_api_non_critical_error",
        function="get_user",
        error="not found",
        status_code=None,
    )


@patch("integrations.google_workspace.google_service_next.logger")
def test_execute_api_call_raises(logger_mock):
    def api():
        raise Exception("fail")

    with pytest.raises(gs.GoogleAPIError):
        gs.execute_api_call("func", api)
    logger_mock.error.assert_any_call(
        "google_api_error_final", function="func", error="fail", status_code=None
    )


# --- execute_batch_request ---
def test_execute_batch_request_success():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Simulate the callback being called for each request
    def add(req, request_id=None):
        # Simulate success for both requests
        fake_batch.callback(request_id, fake_batch._results[request_id], None)
        fake_batch._added.append(request_id)

    fake_batch._added = []
    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock()), ("id2", MagicMock())]

    # Patch the callback attribute to match what the real batch expects
    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    fake_batch._results = {"id1": {"foo": 1}, "id2": {"bar": 2}}
    result = gs.execute_batch_request(fake_service, requests)
    assert set(result["results"]) == {"id1", "id2"}
    assert result["errors"] == {}
    assert result["summary"]["successful"] == 2


def test_execute_batch_request_with_errors():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Simulate the callback being called for each request
    def add(req, request_id=None):
        # Simulate error for id2, success for id1
        if request_id == "id1":
            fake_batch.callback(request_id, {"foo": 1}, None)
        elif request_id == "id2":
            fake_batch.callback(request_id, None, Exception("fail"))
        fake_batch._added.append(request_id)

    fake_batch._added = []
    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock()), ("id2", MagicMock())]

    # Patch the callback attribute to match what the real batch expects
    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    result = gs.execute_batch_request(fake_service, requests)
    assert set(result["results"]) == {"id1"}
    assert set(result["errors"]) == {"id2"}
    assert result["summary"]["failed"] == 1


# --- paginate_all_results ---
@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results(execute_api_call_mock):
    # Simulate paginated API
    class FakeRequest:
        def __init__(self):
            self.calls = 0

        def execute(self):
            self.calls += 1
            if self.calls == 1:
                return {"users": [1, 2], "nextPageToken": "abc"}
            elif self.calls == 2:
                return {"users": [3], "nextPageToken": None}
            else:
                return None

        def execute_next_chunk(self):
            if self.calls < 2:
                return (self, None)
            return (None, None)

    req = FakeRequest()
    results = gs.paginate_all_results(req, resource_key="users")
    assert results == [1, 2, 3]


# --- execute_google_api_call ---
@patch(
    "integrations.google_workspace.google_service_next.paginate_all_results",
    return_value=[1, 2, 3],
)
@patch("integrations.google_workspace.google_service_next.get_google_service")
def test_execute_google_api_call_list(
    get_google_service_mock, paginate_all_results_mock
):
    fake_service = MagicMock()
    get_google_service_mock.return_value = fake_service

    class FakeResource:
        def list(self, **kwargs):
            class Req:
                pass

            return Req()

    fake_service.users = lambda: FakeResource()
    result = gs.execute_google_api_call(
        "admin", "v1", "users", "list", scopes=["s"], delegated_user_email="e"
    )
    assert result == [1, 2, 3]


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
@patch("integrations.google_workspace.google_service_next.get_google_service")
def test_execute_google_api_call_get(get_google_service_mock, execute_api_call_mock):
    fake_service = MagicMock()
    get_google_service_mock.return_value = fake_service

    class FakeResource:
        def get(self, **kwargs):
            return MagicMock(execute=lambda: {"id": 1})

    fake_service.users = lambda: FakeResource()
    result = gs.execute_google_api_call(
        "admin",
        "v1",
        "users",
        "get",
        scopes=["s"],
        delegated_user_email="e",
        userKey="id",
    )
    assert result == {"id": 1}


# --- handle_google_api_errors ---
@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_handle_google_api_errors_decorator(execute_api_call_mock):
    @gs.handle_google_api_errors
    def foo(x):
        return x + 1

    assert foo(2) == 3
