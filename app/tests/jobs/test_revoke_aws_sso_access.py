from jobs import revoke_aws_sso_access

from unittest.mock import call, MagicMock, patch


@patch("jobs.revoke_aws_sso_access.log_ops_message")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_aws_sso_access(
    logger_mock,
    aws_access_requests_mock,
    aws_sso_mock,
    identity_store_mock,
    log_ops_message_mock,
):
    client = MagicMock()
    aws_access_requests_mock.get_expired_requests.return_value = [
        {
            "account_id": {"S": "test_account_id"},
            "account_name": {"S": "test_account_name"},
            "user_id": {"S": "test_user_id"},
            "email": {"S": "test_email"},
            "access_type": {"S": "test_access_type"},
            "created_at": {"N": "test_created_at"},
        }
    ]
    identity_store_mock.get_user_id.return_value = "test_aws_user_id"
    aws_sso_mock.delete_account_assignment.return_value = True
    aws_access_requests_mock.expire_request.return_value = True
    revoke_aws_sso_access.revoke_aws_sso_access(client)
    assert log_ops_message_mock.call_count == 1
    assert log_ops_message_mock.call_args == call(
        client,
        "Revoked access to test_account_name (test_account_id) for <@test_user_id> (test_email) with access type: test_access_type",
    )
    assert identity_store_mock.get_user_id.call_count == 1
    assert identity_store_mock.get_user_id.call_args == call("test_email")
    assert aws_sso_mock.delete_account_assignment.call_count == 1
    assert aws_sso_mock.delete_account_assignment.call_args == call(
        "test_aws_user_id", "test_account_id", "test_access_type"
    )
    assert aws_access_requests_mock.expire_request.call_count == 1
    assert aws_access_requests_mock.expire_request.call_args == call(
        account_id="test_account_id", created_at="test_created_at"
    )
    client.chat_postEphemeral.assert_called_once_with(
        channel="test_user_id",
        user="test_user_id",
        text="Revoked access to test_account_name (test_account_id) for <@test_user_id> (test_email) with access type: test_access_type",
    )
    logger_mock.info.assert_called_once_with(
        "revoking_aws_sso_access",
        account_name="test_account_name",
        account_id="test_account_id",
        user_id="test_user_id",
        email="test_email",
        access_type="test_access_type",
        created_at="test_created_at",
    )


@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_aws_sso_access_with_exception(
    logger_mock, _aws_sso_mock, identity_store_mock, aws_access_requests_mock
):
    client = MagicMock()
    aws_access_requests_mock.get_expired_requests.return_value = [
        {
            "account_id": {"S": "test_account_id"},
            "account_name": {"S": "test_account_name"},
            "user_id": {"S": "test_user_id"},
            "email": {"S": "test_email"},
            "access_type": {"S": "test_access_type"},
            "created_at": {"N": "test_created_at"},
        }
    ]
    identity_store_mock.get_user_id.side_effect = Exception("test_exception")
    revoke_aws_sso_access.revoke_aws_sso_access(client)
    assert logger_mock.error.call_count == 1
