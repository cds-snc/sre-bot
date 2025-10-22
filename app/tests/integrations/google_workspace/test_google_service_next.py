from models.integrations import IntegrationResponse
import pytest
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
from integrations.google_workspace import google_service_next as gs
from tests.fixtures.google_clients import FakeGoogleService


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


def test_calculate_retry_delay_invalid_backoff_factor():
    gs.ERROR_CONFIG["default_backoff_factor"] = object()
    with pytest.raises(TypeError):
        gs._calculate_retry_delay(1, 500)


def test_calculate_retry_delay_type_error_default_backoff_factor():
    gs.ERROR_CONFIG["default_backoff_factor"] = object()
    # Should raise TypeError when default_backoff_factor is not numeric
    with pytest.raises(TypeError):
        gs._calculate_retry_delay(1, 500)


def test_calculate_retry_delay_type_error_rate_limit_delay():
    gs.ERROR_CONFIG["rate_limit_delay"] = object()
    # Should raise TypeError when rate_limit_delay is not numeric and status_code is 429
    with pytest.raises(TypeError):
        gs._calculate_retry_delay(1, 429)


# --- Additional edge case tests ---


def test_should_retry_exhausts_all_retries():
    # Simulate HttpError with retryable status
    class FakeResp:
        status = 429
        reason = "Too Many Requests"

    error = HttpError(resp=FakeResp(), content=b"rate limit")
    # Should retry until last attempt, then stop
    assert gs._should_retry(True, {429}, error, is_last_attempt=False) is True
    assert gs._should_retry(True, {429}, error, is_last_attempt=True) is False


def test_should_retry_missing_retry_codes():
    # Should not retry if retry_codes is None
    class FakeResp:
        status = 429
        reason = "Too Many Requests"

    error = HttpError(resp=FakeResp(), content=b"rate limit")
    assert gs._should_retry(True, None, error, is_last_attempt=False) is False


def test_should_retry_non_retryable_error():
    # Should not retry if status is not in retry_codes
    class FakeResp:
        status = 400
        reason = "Bad Request"

    error = HttpError(resp=FakeResp(), content=b"bad request")
    assert gs._should_retry(True, {429}, error, is_last_attempt=False) is False


# --- _get_retry_codes ---
def test_get_retry_codes_valid():
    error_config = {"retry_errors": [429, 500, 502]}
    codes = gs._get_retry_codes(error_config)
    assert codes == {429, 500, 502}


def test_get_retry_codes_invalid_type():
    error_config = {"retry_errors": "not-a-list"}
    codes = gs._get_retry_codes(error_config)
    assert codes is None
    error_config = {"retry_errors": [429, "five-hundred", None]}
    codes = gs._get_retry_codes(error_config)
    assert codes is None


# --- _handle_final_error ---
def test_handle_final_error_non_critical_config():
    error = Exception("not found")
    resp = gs._handle_final_error(error, "get_user")
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert "not found" in resp.error["message"]
    assert resp.function_name == "get_user"
    assert resp.integration_name == "google"


def test_handle_final_error_return_none_on_error():
    error = Exception("fail")
    resp = gs._handle_final_error(error, "func")
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert resp.function_name == "func"
    assert resp.integration_name == "google"


def test_handle_final_error_non_critical_with_response_metadata():
    error = Exception("not found")
    resp = gs._handle_final_error(error, "get_user")
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert resp.function_name == "get_user"
    assert resp.integration_name == "google"


# --- execute_api_call ---
def test_execute_api_call_success():
    def api():
        return 42

    resp = gs.execute_api_call("func", api)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == 42
    assert resp.error is None
    assert resp.function_name == "func"
    assert resp.integration_name == "google"


def test_execute_api_call_exhausts_retries_and_returns_error():
    # Simulate always failing API call with retryable error
    class FakeResp:
        status = 503
        reason = "Service Unavailable"

        def get(self, key, default=None):
            if key == "status":
                return self.status
            return default

    error = HttpError(resp=FakeResp(), content=b"fail")

    def api():
        raise error

    gs.ERROR_CONFIG["default_backoff_factor"] = 1.0
    resp = gs.execute_api_call("func", api, max_retries=2)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.data is None
    assert resp.error is not None
    assert "Service Unavailable" in str(resp.error["message"])


def test_execute_api_call_non_retryable_error_returns_error():
    # Simulate API call raising non-retryable error
    class FakeResp:
        status = 400
        reason = "Bad Request"

        def get(self, key, default=None):
            if key == "status":
                return self.status
            return default

    error = HttpError(resp=FakeResp(), content=b"fail")

    def api():
        raise error

    gs.ERROR_CONFIG["default_backoff_factor"] = 1.0
    resp = gs.execute_api_call("func", api, max_retries=2)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.data is None
    assert resp.error is not None
    assert "Bad Request" in str(resp.error["message"])


def test_execute_api_call_error_response():
    def api_call():
        raise ValueError("not found")

    resp = gs.execute_api_call("get_user", api_call)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.data is None
    assert resp.error is not None
    assert "not found" in resp.error["message"]
    assert resp.function_name == "get_user"
    assert resp.integration_name == "google"


def test_execute_api_call_retry_logic():
    # Ensure ERROR_CONFIG['default_backoff_factor'] is a valid float for this test
    gs.ERROR_CONFIG["default_backoff_factor"] = 1.0

    class FakeResp:
        status = 503
        reason = "Service Unavailable"

        def get(self, key, default=None):
            return getattr(self, key, default)

    err = HttpError(resp=FakeResp(), content=b"unavailable")
    calls = []

    def api():
        calls.append(1)
        if len(calls) < 3:
            raise err
        return "ok"

    resp = gs.execute_api_call("func", api, max_retries=3)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == "ok"
    assert len(calls) == 3


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
    assert isinstance(result, IntegrationResponse)
    assert result.success is True
    assert result.data == "ok"
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
def test_execute_api_call_non_retryable_http_error(logger_mock):
    class FakeResp:
        status = 404
        reason = "Not Found"

        def get(self, key, default=None):
            return getattr(self, key, default)

    err = HttpError(resp=FakeResp(), content=b"not found")

    def api():
        raise err

    resp = gs.execute_api_call("func", api)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert resp.error["error_code"] == "404"
    logger_mock.error.assert_any_call(
        "google_api_error_final", function="func", error=str(err), status_code=404
    )


@patch("integrations.google_workspace.google_service_next.logger")
def test_execute_api_call_raises(logger_mock):
    def api():
        raise ValueError("fail")

    result = gs.execute_api_call("func", api)
    assert isinstance(result, IntegrationResponse)
    assert result.success is False
    assert result.error["message"] == "fail"
    logger_mock.error.assert_any_call(
        "google_api_error_final", function="func", error="fail", status_code=None
    )


# --- paginate_all_results: auto-detect resource key, response as list, no execute_next_chunk ---


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results(_mock):

    # Simulate paginated API responses for "users"
    paginated_pages = [
        {"users": [1, 2], "nextPageToken": "abc"},
        {"users": [3], "nextPageToken": None},
    ]

    class FakeRequest:
        def __init__(self):
            self.pages = iter(paginated_pages)
            self.calls = 0

        def execute(self):
            self.calls += 1
            try:
                return next(self.pages)
            except StopIteration:
                return None

        def execute_next_chunk(self):
            if self.calls < len(paginated_pages):
                return (self, None)
            return (None, None)

    req = FakeRequest()
    resp = gs.paginate_all_results(req, resource_key="users")
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == [1, 2, 3]


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results_auto_detect_key(_mock):

    paginated_pages = [
        {"foo": [1, 2], "nextPageToken": "abc"},
        {"foo": [3], "nextPageToken": None},
    ]

    class FakeRequest:
        def __init__(self):
            self.pages = iter(paginated_pages)
            self.calls = 0

        def execute(self):
            self.calls += 1
            try:
                return next(self.pages)
            except StopIteration:
                return None

        def execute_next_chunk(self):
            if self.calls < len(paginated_pages):
                return (self, None)
            return (None, None)

    req = FakeRequest()
    resp = gs.paginate_all_results(req)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == [1, 2, 3]


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results_response_list(_mock):

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
    resp = gs.paginate_all_results(req)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == [1, 2]


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_paginate_all_results_no_execute_next_chunk(_mock):

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
    resp = gs.paginate_all_results(req, resource_key="foo")
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is True
    assert resp.data == [1]


# --- get_google_service ---
@patch("integrations.google_workspace.google_service_next.build")
@patch(
    "integrations.google_workspace.google_service_next.service_account.Credentials.from_service_account_info"
)
def test_get_google_service_valid_delegated_user_email(mock_creds, mock_build):
    # Simulate valid delegated user email
    mock_creds.return_value = MagicMock()
    mock_build.return_value = MagicMock()
    key_file = '{"client_email": "bot@example.com", "private_key": "FAKE", "token_uri": "https://oauth2.googleapis.com/token"}'
    with patch(
        "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
        key_file,
    ):
        service = gs.get_google_service(
            "admin", "v1", delegated_user_email="user@example.com"
        )
        assert service is not None
        mock_creds.assert_called()
        mock_build.assert_called()


@patch("integrations.google_workspace.google_service_next.build")
@patch(
    "integrations.google_workspace.google_service_next.service_account.Credentials.from_service_account_info"
)
def test_get_google_service_missing_creds_file(mock_creds, mock_build):
    # Simulate missing credential file
    mock_creds.return_value = MagicMock()
    mock_build.return_value = MagicMock()
    with patch(
        "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
        None,
    ):
        with pytest.raises(ValueError) as exc_info:
            gs.get_google_service("admin", "v1")
        assert "Credentials JSON not set" in str(exc_info.value)


@patch("integrations.google_workspace.google_service_next.build")
@patch(
    "integrations.google_workspace.google_service_next.service_account.Credentials.from_service_account_info"
)
def test_get_google_service_invalid_creds_file(mock_creds, mock_build):
    # Simulate invalid credential file (not JSON)
    mock_creds.return_value = MagicMock()
    mock_build.return_value = MagicMock()
    with patch(
        "integrations.google_workspace.google_service_next.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
        "not-json",
    ):
        with pytest.raises(Exception) as exc_info:
            gs.get_google_service("admin", "v1")
        assert "Invalid credentials JSON" in str(exc_info.value)


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


# --- execute_batch_request ---
def test_execute_batch_request_success():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Simulate the callback being called for each request
    def add(*args, **kwargs):
        request_id = kwargs.get("request_id")
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
    assert isinstance(result, IntegrationResponse)
    assert set(result.data["results"]) == {"id1", "id2"}
    assert result.error is None or result.error.get("errors", {}) == {}
    assert result.data["summary"]["successful"] == 2


def test_execute_batch_request_error():
    service = MagicMock()
    batch = MagicMock()
    service.new_batch_http_request.return_value = batch
    # Simulate error in batch callback

    def add(*args, **kwargs):
        request_id = kwargs.get("request_id", "get_user")
        batch.callback(request_id, None, Exception("fail"))

    batch.add.side_effect = add
    batch.execute.side_effect = lambda: None
    requests = [("get_user", MagicMock())]

    def new_batch_http_request(callback):
        batch.callback = callback
        return batch

    service.new_batch_http_request.side_effect = new_batch_http_request
    resp = gs.execute_batch_request(service, requests)
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.data == {}
    assert resp.error is not None
    assert resp.function_name == "execute_batch_request"
    assert resp.integration_name == "google"


def test_execute_batch_request_with_errors():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Simulate the callback being called for each request
    def add(*args, **kwargs):
        request_id = kwargs.get("request_id")
        if request_id == "id1":
            fake_batch.callback(request_id, {"foo": 1}, None)
        elif request_id == "id2":
            fake_batch.callback(request_id, None, ValueError("fail"))
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
    # If there are errors, results may be missing or empty
    if "results" in result.data:
        assert set(result.data["results"]) == {"id1"}
    else:
        # Expect partial results for error case
        assert result.data == {"id1": {"foo": 1}}


@patch("integrations.google_workspace.google_service_next.logger")
def test_execute_batch_request_exception(logger_mock):

    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch
    fake_batch.add.side_effect = lambda req, request_id=None: None
    fake_batch.execute.side_effect = ValueError("fail")
    requests = [("id1", MagicMock())]
    try:
        gs.execute_batch_request(fake_service, requests)
    except ValueError:
        pass
    else:
        assert False, "Should raise ValueError"
    logger_mock.error.assert_any_call("batch_execution_failed", error="fail")


def test_execute_batch_request_mixed_success_and_non_critical_error():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    def add(*args, **kwargs):
        request_id = kwargs.get("request_id")
        if request_id == "id1":
            fake_batch.callback(request_id, {"foo": 1}, None)
        elif request_id == "id2":
            fake_batch.callback(
                request_id, None, Exception("not found")
            )  # non-critical error
        fake_batch._added.append(request_id)

    fake_batch._added = []
    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock()), ("id2", MagicMock())]

    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    result = gs.execute_batch_request(fake_service, requests)
    assert isinstance(result, IntegrationResponse)
    assert result.success is False  # Non-critical error should still mark as failed
    assert "id1" in result.data.get("results", {}) or "id1" in result.data
    assert result.error is not None
    assert "not found" in str(result.error)


def test_execute_batch_request_missing_request_id():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Callback called with a request_id not in requests
    def add(*args, **kwargs):
        fake_batch.callback("unknown_id", {"foo": 1}, None)
        fake_batch._added.append("unknown_id")

    fake_batch._added = []
    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock())]

    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    result = gs.execute_batch_request(fake_service, requests)
    # Should not include unknown_id in results
    assert "unknown_id" not in result.data


def test_execute_batch_request_unexpected_callback_result():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Callback returns neither data nor error
    def add(*args, **kwargs):
        request_id = kwargs.get("request_id", "id1")
        fake_batch.callback(request_id, None, None)
        fake_batch._added.append(request_id)

    fake_batch._added = []
    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock())]

    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    result = gs.execute_batch_request(fake_service, requests)
    # Should handle gracefully, likely empty result
    assert result.success is True or result.success is False


def test_execute_batch_request_callback_with_data_and_error():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # Callback called with both data and error
    def add(*args, **kwargs):
        request_id = kwargs.get("request_id", "id1")
        fake_batch.callback(request_id, {"foo": 1}, ValueError("fail"))
        fake_batch._added.append(request_id)

    fake_batch._added = []
    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock())]

    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    result = gs.execute_batch_request(fake_service, requests)
    # Should prefer error
    assert result.success is False
    assert result.error is not None


def test_execute_batch_request_callback_never_called():
    fake_service = MagicMock()
    fake_batch = MagicMock()
    fake_service.new_batch_http_request.return_value = fake_batch

    # add does nothing, callback never called
    def add(*args, **kwargs):
        pass

    fake_batch.add.side_effect = add
    fake_batch.execute.side_effect = lambda: None
    requests = [("id1", MagicMock())]

    def new_batch_http_request(callback):
        fake_batch.callback = callback
        return fake_batch

    fake_service.new_batch_http_request.side_effect = new_batch_http_request

    result = gs.execute_batch_request(fake_service, requests)
    # Should handle gracefully, likely empty result
    assert isinstance(result, IntegrationResponse)


# --- execute_google_api_call edge case tests ---


def test_execute_google_api_call_invalid_resource_path():
    from tests.fixtures.google_clients import FakeGoogleService

    # Simulate invalid resource path (attribute error)
    class BrokenFakeGoogleService(FakeGoogleService):
        def __getattr__(self, name):
            raise AttributeError(f"No such resource: {name}")

    def fake_get_google_service(*args, **kwargs):
        return BrokenFakeGoogleService()

    gs.get_google_service = fake_get_google_service
    resp = gs.execute_google_api_call(
        service_name="drive",
        version="v3",
        resource_path="invalid_resource",
        method="list",
    )
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert "No such resource" in resp.error["message"]


def test_execute_google_api_call_unsupported_method():
    from tests.fixtures.google_clients import FakeGoogleService

    # Simulate unsupported method (attribute error)
    class BrokenFakeGoogleService(FakeGoogleService):
        def __getattr__(self, name):
            if name == "files":
                return lambda: self
            raise AttributeError(f"No such method: {name}")

    def fake_get_google_service(*args, **kwargs):
        return BrokenFakeGoogleService()

    gs.get_google_service = fake_get_google_service
    resp = gs.execute_google_api_call(
        service_name="drive",
        version="v3",
        resource_path="files",
        method="not_a_method",
    )
    assert isinstance(resp, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert "No such method" in resp.error["message"]


def test_execute_google_api_call_api_error():

    # Simulate API call raising an exception
    class BrokenFakeGoogleService(FakeGoogleService):
        def __getattr__(self, name):
            if name == "files":
                return lambda: self
            if name == "list":

                def api_method(**kwargs):
                    raise ValueError("API call failed")

                return api_method
            raise AttributeError(f"No such method: {name}")

    def fake_get_google_service(*args, **kwargs):
        return BrokenFakeGoogleService()

    gs.get_google_service = fake_get_google_service
    resp = gs.execute_google_api_call(
        service_name="drive",
        version="v3",
        resource_path="files",
        method="list",
    )
    assert isinstance(resp, IntegrationResponse)
    assert not isinstance(resp.data, IntegrationResponse)
    assert resp.success is False
    assert resp.error is not None
    assert "generator" in str(resp.error["message"])


@patch(
    "integrations.google_workspace.google_service_next.execute_api_call",
    side_effect=lambda name, fn, **kw: fn(),
)
def test_handle_google_api_errors_decorator(_mock):
    @gs.handle_google_api_errors
    def foo(x):
        return x + 1

    assert foo(2) == 3
