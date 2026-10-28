from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from integrations.sentinel import client as sentinel
from integrations.sentinel.settings import SentinelSettings

customer_id = "customer_id"
log_type = "log_type"
shared_key = "dGVzdCBrZXk="


@pytest.fixture
def configured(monkeypatch):
    """Sentinel configured through its slice, read by send_event at call time."""
    settings = SentinelSettings.model_construct(
        customer_id="SENTINEL_CUSTOMER_ID", shared_key=SecretStr("SENTINEL_SHARED_KEY"), log_type="SENTINEL_LOG_TYPE"
    )
    monkeypatch.setattr(sentinel, "get_sentinel_settings", lambda: settings)
    return settings


def test_send_event_customer_id_not_provided(configured):
    configured.customer_id = ""
    assert sentinel.send_event({}) is False


def test_send_event_shared_key_not_provided(configured):
    configured.shared_key = SecretStr("")
    assert sentinel.send_event({}) is False


@patch("integrations.sentinel.client.post_data")
def test_send_event(post_data_mock, configured):
    event = {}
    assert sentinel.send_event(event) is True
    post_data_mock.assert_called_once_with("SENTINEL_CUSTOMER_ID", "SENTINEL_SHARED_KEY", "{}", "SENTINEL_LOG_TYPE")


@patch("integrations.sentinel.client.post_data")
def test_send_event_serializes_datetime(post_data_mock, configured):
    event = {"created_at": datetime(2026, 3, 12, 16, 30, tzinfo=UTC)}

    assert sentinel.send_event(event) is True
    body = post_data_mock.call_args[0][2]
    assert "2026-03-12T16:30:00+00:00" in body


def test_build_signature():
    body = "{}"
    method = "POST"
    content_type = "application/json"
    resource = "/api/logs"
    date = "Sun, 21 Nov 2021 18:35:52 GMT"
    content_length = len(body)

    expected = "SharedKey customer_id:bSu2KGHkG5BkSq5WqYTlxfTlBpYFi+TgwYEQaZ/PwN8="
    assert (
        sentinel.build_signature(
            customer_id,
            shared_key,
            date,
            content_length,
            method,
            content_type,
            resource,
        )
        == expected
    )


@patch("integrations.sentinel.client.logger")
@patch("integrations.sentinel.client.requests")
def test_post_data_never_logs_the_workspace_id(mock_requests, logging_mock):
    """The workspace id is a non-public value: it is in the request host, never in a log binding."""
    mock_requests.post.return_value.status_code = 200

    sentinel.post_data(customer_id, shared_key, "{}", log_type)

    assert "customer_id" not in logging_mock.bind.call_args.kwargs


@patch("integrations.sentinel.client.requests")
def test_post_data_success(mock_requests):
    body = "{}"
    log_type = "test_log_type"

    mock_requests.post.return_value.status_code = 200

    assert sentinel.post_data(customer_id, shared_key, body, log_type)


@patch("integrations.sentinel.client.requests")
def test_post_data_failure(mock_requests):
    body = "{}"
    log_type = "test_log_type"

    mock_requests.post.return_value.status_code = 400

    assert sentinel.post_data(customer_id, shared_key, body, log_type) is False


@patch("integrations.sentinel.client.logger")
@patch("integrations.sentinel.client.send_event")
def test_log_to_sentinel(send_event_mock, logging_mock):
    bound_logger_mock = logging_mock.bind.return_value
    sentinel.log_to_sentinel("foo", {"bar": "baz"})
    send_event_mock.assert_called_with({"event": "foo", "message": {"bar": "baz"}})
    bound_logger_mock.info.assert_called_with("sentinel_event_sent")


@patch("integrations.sentinel.client.send_event")
@patch("integrations.sentinel.client.logger")
def test_log_to_sentinel_logs_error(logging_mock, send_event_mock):
    bound_logger_mock = logging_mock.bind.return_value
    send_event_mock.return_value = False
    sentinel.log_to_sentinel("foo", {"bar": "baz"})
    send_event_mock.assert_called_with({"event": "foo", "message": {"bar": "baz"}})
    bound_logger_mock.error.assert_called_once()
    args, kwargs = bound_logger_mock.error.call_args
    assert args[0] == "sentinel_event_error"
    assert kwargs["payload_message_type"] == "dict"
