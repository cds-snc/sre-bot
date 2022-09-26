from server import server

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import ANY, call, MagicMock, patch, PropertyMock


@patch("server.server.maxmind.geolocate")
def test_geolocate_success(mock_geolocate):
    mock_geolocate.return_value = "country", "city", "latitude", "longitude"
    client = TestClient(server.handler)
    response = client.get("/geolocate/111.111.111.111")
    assert response.status_code == 200
    assert response.json() == {
        "country": "country",
        "city": "city",
        "latitude": "latitude",
        "longitude": "longitude",
    }


@patch("server.server.maxmind.geolocate")
def test_geolocate_failure(mock_geolocate):
    mock_geolocate.return_value = "error"
    client = TestClient(server.handler)
    response = client.get("/geolocate/111")
    assert response.status_code == 404
    assert response.json() == {"detail": "error"}


@patch("server.server.append_incident_buttons")
@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
def test_handle_webhook_found(
    increment_invocation_count_mock, get_webhook_mock, append_incident_buttons_mock
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = {"channel": "channel"}
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert get_webhook_mock.call_count == 1
    assert increment_invocation_count_mock.call_count == 1
    assert append_incident_buttons_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_invalid_aws_json_payload(
    _log_ops_message_mock, _increment_invocation_count_mock, get_webhook_mock
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = "not a json payload"
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {"detail": ANY}


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_bad_aws_signature(
    _log_ops_message_mock, _increment_invocation_count_mock, get_webhook_mock
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = '{"Type": "foo"}'
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {"detail": ANY}


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
@patch("server.server.sns_message_validator.validate_message")
@patch("server.server.requests.get")
def test_handle_webhook_with_SubscriptionConfirmation_payload(
    get_mock,
    validate_message_mock,
    log_ops_message_mock,
    _increment_invocation_count_mock,
    get_webhook_mock,
):
    validate_message_mock.return_value = True
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = '{"Type": "SubscriptionConfirmation", "SubscribeURL": "SubscribeURL", "TopicArn": "TopicArn"}'
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert log_ops_message_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.sns_message_validator.validate_message")
def test_handle_webhook_with_UnsubscribeConfirmation_payload(
    validate_message_mock,
    _increment_invocation_count_mock,
    get_webhook_mock,
):
    validate_message_mock.return_value = True
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = '{"Type": "UnsubscribeConfirmation"}'
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.sns_message_validator.validate_message")
@patch("server.server.aws.parse")
def test_handle_webhook_with_Notification_payload(
    parse_mock,
    validate_message_mock,
    _increment_invocation_count_mock,
    get_webhook_mock,
):
    validate_message_mock.return_value = True
    parse_mock.return_value = ["foo", "bar"]
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = '{"Type": "Notification"}'
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("server.server.append_incident_buttons")
@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_found_but_exception(
    log_ops_message_mock,
    increment_invocation_count_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = MagicMock()
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    request = MagicMock()
    request.state.bot.client.api_call.side_effect = Exception("error")
    with pytest.raises(Exception):
        server.handle_webhook("id", payload, request)
        assert log_ops_message_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
def test_handle_webhook_not_found(get_webhook_mock):
    get_webhook_mock.return_value = None
    payload = {"channel": "channel"}
    client = TestClient(server.handler)
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not found"}
    assert get_webhook_mock.call_count == 1


def test_get_version_unkown():
    client = TestClient(server.handler)
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "unknown"}


@patch.dict(os.environ, {"GIT_SHA": "foo"}, clear=True)
def test_get_version_known():
    client = TestClient(server.handler)
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "foo"}


def test_append_incident_buttons():
    payload = MagicMock()
    attachments = PropertyMock(return_value=[])
    type(payload).attachments = attachments
    type(payload).text = PropertyMock(return_value="text")
    webhook_id = "bar"
    resp = server.append_incident_buttons(payload, webhook_id)
    assert payload == resp
    assert attachments.call_count == 2
    assert attachments.call_args_list == [
        call(),
        call(
            [
                {
                    "fallback": "Incident",
                    "callback_id": "handle_incident_action_buttons",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "call-incident",
                            "text": "🎉   Call incident ",
                            "type": "button",
                            "value": "text",
                            "style": "primary",
                        },
                        {
                            "name": "ignore-incident",
                            "text": "🙈   Acknowledge and ignore",
                            "type": "button",
                            "value": "bar",
                            "style": "default",
                        },
                    ],
                }
            ]
        ),
    ]
