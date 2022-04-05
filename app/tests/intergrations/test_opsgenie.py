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


@patch("integrations.opsgenie.api_get_request")
def test_get_on_call_users_with_exception(api_get_request_mock):
    api_get_request_mock.return_value = "{]"
    assert opsgenie.get_on_call_users("test_schedule") == []


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
