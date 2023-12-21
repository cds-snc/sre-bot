from unittest.mock import call, patch, MagicMock
from jobs import client_vpn_turn_off


@patch("jobs.client_vpn_turn_off.datetime.datetime")
@patch("jobs.client_vpn_turn_off.AWSClientVPN")
def test_client_vpn_turn_off_expired_session(mock_aws_client_vpn, mock_datetime):
    mock_session = {
        "SK": {"S": "some_session"},
        "vpn_id": {"S": "some_vpn_id"},
        "assume_role_arn": {"S": "some_assume_role_arn"},
        "expires_at": {"N": "1640092800"},
    }
    mock_vpn_sessions = [mock_session]

    mock_aws_client_vpn_instance = MagicMock()
    mock_aws_client_vpn_instance.get_vpn_sessions.return_value = mock_vpn_sessions
    mock_aws_client_vpn.return_value = mock_aws_client_vpn_instance

    mock_datetime.now.return_value.timestamp.return_value = 1640093800

    client_vpn_turn_off.client_vpn_turn_off()
    assert mock_aws_client_vpn.call_count == 2
    mock_aws_client_vpn.assert_has_calls(
        [
            call(),
            call().get_vpn_sessions(),
            call(
                name=mock_session["SK"]["S"],
                vpn_id=mock_session["vpn_id"]["S"],
                assume_role_arn=mock_session["assume_role_arn"]["S"],
            ),
            call().turn_off(),
        ]
    )


@patch("jobs.client_vpn_turn_off.datetime.datetime")
@patch("jobs.client_vpn_turn_off.AWSClientVPN")
def test_client_vpn_turn_off_valid_session(mock_aws_client_vpn, mock_datetime):
    mock_session = {
        "SK": {"S": "some_session"},
        "vpn_id": {"S": "some_vpn_id"},
        "assume_role_arn": {"S": "some_assume_role_arn"},
        "expires_at": {"N": "1640092800"},
    }
    mock_vpn_sessions = [mock_session]

    mock_aws_client_vpn_instance = MagicMock()
    mock_aws_client_vpn_instance.get_vpn_sessions.return_value = mock_vpn_sessions
    mock_aws_client_vpn.return_value = mock_aws_client_vpn_instance

    mock_datetime.now.return_value.timestamp.return_value = 1640082800

    client_vpn_turn_off.client_vpn_turn_off()
    assert mock_aws_client_vpn.call_count == 1
    mock_aws_client_vpn.assert_has_calls(
        [
            call(),
            call().get_vpn_sessions(),
        ]
    )


@patch("jobs.client_vpn_turn_off.datetime.datetime")
@patch("jobs.client_vpn_turn_off.AWSClientVPN")
def test_client_vpn_turn_off_no_session(mock_aws_client_vpn, mock_datetime):
    mock_vpn_sessions = []
    mock_aws_client_vpn_instance = MagicMock()
    mock_aws_client_vpn_instance.get_vpn_sessions.return_value = mock_vpn_sessions
    mock_aws_client_vpn.return_value = mock_aws_client_vpn_instance

    client_vpn_turn_off.client_vpn_turn_off()
    assert mock_aws_client_vpn.call_count == 1
    assert mock_datetime.now.call_count == 0
    mock_aws_client_vpn.assert_has_calls(
        [
            call(),
            call().get_vpn_sessions(),
        ]
    )
