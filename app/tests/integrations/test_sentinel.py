import os

from integrations import sentinel

from unittest.mock import patch

customer_id = "customer_id"
log_type = "log_type"
shared_key = "dGVzdCBrZXk="


@patch.dict(
    os.environ, {"SENTINEL_LOG_TYPE": "foo", "SENTINEL_SHARED_KEY": "foo"}, clear=True
)
def test_send_event_customer_id_not_provided():
    event = {}
    assert sentinel.send_event(event) is False


@patch.dict(
    os.environ,
    {
        "SENTINEL_CUSTOMER_ID": "foo",
    },
    clear=True,
)
def test_send_event_shared_key_not_provided():
    event = {}
    assert sentinel.send_event(event) is False


@patch("integrations.sentinel.post_data")
def test_send_event(post_data_mock):
    event = {}
    assert sentinel.send_event(event) is True
    post_data_mock.assert_called_once_with(
        '"SENTINEL_CUSTOMER_ID"', '"SENTINEL_SHARED_KEY"', "{}", '"SENTINEL_LOG_TYPE"'
    )


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


@patch("integrations.sentinel.requests")
def test_post_data_success(mock_requests):
    body = "{}"
    log_type = "test_log_type"

    mock_requests.post.return_value.status_code = 200

    assert sentinel.post_data(customer_id, shared_key, body, log_type)


@patch("integrations.sentinel.requests")
def test_post_data_failure(mock_requests):
    body = "{}"
    log_type = "test_log_type"

    mock_requests.post.return_value.status_code = 400

    assert sentinel.post_data(customer_id, shared_key, body, log_type) is False


@patch("integrations.sentinel.send_event")
def test_log_to_sentinel(send_event_mock):
    sentinel.log_to_sentinel("foo", {"bar": "baz"})
    send_event_mock.assert_called_with({"event": "foo", "message": {"bar": "baz"}})


@patch("integrations.sentinel.send_event")
@patch("integrations.sentinel.logging")
def test_log_to_sentinel_logs_error(logging_mock, send_event_mock):
    send_event_mock.return_value = False
    sentinel.log_to_sentinel("foo", {"bar": "baz"})
    send_event_mock.assert_called_with({"event": "foo", "message": {"bar": "baz"}})
    logging_mock.error.assert_called_with(
        "Sentinel event failed: {'event': 'foo', 'message': {'bar': 'baz'}}"
    )
