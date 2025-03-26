from integrations import opsgenie

from unittest.mock import patch


@patch("integrations.opsgenie.api_get_request")
@patch("integrations.opsgenie.OPSGENIE_KEY", "OPSGENIE_KEY")
def test_get_on_call_users(api_get_request_mock):
    api_get_request_mock.return_value = (
        '{"data": {"onCallParticipants": [{"name": "test_user"}]}}'
    )
    assert opsgenie.get_on_call_users("test_schedule") == ["test_user"]
    api_get_request_mock.assert_called_once_with(
        "https://api.opsgenie.com/v2/schedules/test_schedule/on-calls",
        {"name": "GenieKey", "token": "OPSGENIE_KEY"},
    )


@patch("integrations.opsgenie.api_post_request")
@patch("integrations.opsgenie.OPSGENIE_KEY", "OPSGENIE_KEY")
def test_create_alert(api_post_request_mock):
    description = "test_description"
    api_post_request_mock.return_value = '{"result": "Request will be processed", "took": 0.302, "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120"}'
    assert opsgenie.create_alert(description) == "Request will be processed"
    api_post_request_mock.assert_called_once_with(
        "https://api.opsgenie.com/v2/alerts",
        {"name": "GenieKey", "token": "OPSGENIE_KEY"},
        {"message": "Notify API Key has been compromised!", "description": description},
    )


@patch("integrations.opsgenie.api_get_request")
def test_get_on_call_users_with_exception(api_get_request_mock):
    api_get_request_mock.return_value = "{]"
    assert opsgenie.get_on_call_users("test_schedule") == []


@patch("integrations.opsgenie.api_post_request")
def test_create_alert_with_exception(api_post_request_mock):
    description = "test_description"
    api_post_request_mock.return_value = "{]"
    assert opsgenie.create_alert(description) == "Could not issue alert to Opsgenie!"


@patch("integrations.opsgenie.Request")
@patch("integrations.opsgenie.urlopen")
def test_api_get_request(urlopen_mock, request_mock):
    urlopen_mock.return_value.read.return_value.decode.return_value = (
        '{"data": {"onCallParticipants": [{"name": "test_user"}]}}'
    )
    assert (
        opsgenie.api_get_request(
            "test_url", {"name": "GenieKey", "token": "OPSGENIE_KEY"}
        )
        == '{"data": {"onCallParticipants": [{"name": "test_user"}]}}'
    )

    request_mock.assert_called_once_with("test_url")
    request_mock.return_value.add_header.assert_called_once_with(
        "Authorization", "GenieKey OPSGENIE_KEY"
    )
    urlopen_mock.assert_called_once_with(request_mock.return_value)


@patch("integrations.opsgenie.Request")
@patch("integrations.opsgenie.urlopen")
def test_api_post_request(urlopen_mock, request_mock):
    urlopen_mock.return_value.read.return_value.decode.return_value = '{"result": "Request will be processed", "took": 0.302, "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120"}'
    assert (
        opsgenie.api_post_request(
            "test_url",
            {"name": "GenieKey", "token": "OPSGENIE_KEY"},
            {
                "message": "Notify API Key has been compromised!",
                "description": "test_description",
            },
        )
        == '{"result": "Request will be processed", "took": 0.302, "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120"}'
    )
    request_mock.assert_called_once_with(
        "test_url",
        data=b'{"message": "Notify API Key has been compromised!", "description": "test_description"}',
    )
    request_mock.return_value.add_header.assert_called_with(
        "Authorization",
        "GenieKey OPSGENIE_KEY",
    )
    urlopen_mock.assert_called_once_with(request_mock.return_value)


@patch("integrations.opsgenie.api_get_request")
def test_healthcheck_healthy(api_get_request_mock):
    api_get_request_mock.return_value = '{"data": {"name": "test_user"}}'
    assert opsgenie.healthcheck() is True


@patch("integrations.opsgenie.api_get_request")
def test_healthcheck_unhealthy(api_get_request_mock):
    api_get_request_mock.return_value = '{"error": "failed"}'
    assert opsgenie.healthcheck() is False


@patch("integrations.opsgenie.api_get_request")
def test_healthcheck_unhealthy_error(api_get_request_mock):
    api_get_request_mock.return_value = "{]"
    assert opsgenie.healthcheck() is False
