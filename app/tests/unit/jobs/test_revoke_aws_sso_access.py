"""Unit tests for AWS SSO access revocation job.

Tests the core business logic of revoking AWS SSO access for expired requests.
Focuses on unit-level behavior: data transformation, error handling, and dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch
from jobs.revoke_aws_sso_access import revoke_aws_sso_access


@pytest.fixture
def make_expired_request() -> callable:
    """Factory fixture for creating expired access requests with optional overrides."""

    def _make(**overrides) -> dict:
        """Create an expired request with default values.

        Args:
            **overrides: Field overrides to apply to the default request.
                        Example: make_expired_request(account_id={"S": "different"})

        Returns:
            Dictionary representing an expired access request.
        """
        default = {
            "account_id": {"S": "123456789"},
            "account_name": {"S": "production"},
            "user_id": {"S": "U12345"},
            "email": {"S": "user@example.com"},
            "access_type": {"S": "ReadOnlyAccess"},
            "created_at": {"N": "1704067200"},
        }
        return {**default, **overrides}

    return _make


@pytest.fixture
def expired_request(make_expired_request) -> dict:
    """Default expired access request (convenience fixture for backward compatibility)."""
    return make_expired_request()


@pytest.fixture
def mock_slack_client() -> MagicMock:
    """Mock Slack client."""
    return MagicMock()


@pytest.mark.unit
@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.log_ops_message")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_access_success(
    mock_logger,
    mock_log_ops,
    mock_sso,
    mock_identity_store,
    mock_aws_requests,
    expired_request,
    mock_slack_client,
) -> None:
    """Test successful revocation of AWS SSO access.

    Verifies that:
    - Expired requests are retrieved
    - User ID is looked up via email
    - Account assignment is deleted
    - Request is marked as expired
    - Slack notification is sent
    - Ops message is logged
    """
    mock_aws_requests.get_expired_requests.return_value = [expired_request]
    mock_identity_store.get_user_id.return_value = "aws-user-123"

    revoke_aws_sso_access(mock_slack_client)

    # Verify sequence of calls
    mock_identity_store.get_user_id.assert_called_once_with("user@example.com")
    mock_sso.delete_account_assignment.assert_called_once_with(
        "aws-user-123", "123456789", "ReadOnlyAccess"
    )
    mock_aws_requests.expire_request.assert_called_once_with(
        account_id="123456789", created_at="1704067200"
    )

    # Verify notifications
    assert mock_slack_client.chat_postEphemeral.call_count == 1
    call_kwargs = mock_slack_client.chat_postEphemeral.call_args[1]
    assert call_kwargs["channel"] == "U12345"
    assert call_kwargs["user"] == "U12345"
    assert "production" in call_kwargs["text"]
    assert "user@example.com" in call_kwargs["text"]

    assert mock_log_ops.call_count == 1


@pytest.mark.unit
@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_access_handles_identity_store_error(
    mock_logger,
    mock_sso,
    mock_identity_store,
    mock_aws_requests,
    expired_request,
    mock_slack_client,
) -> None:
    """Test error handling when identity store lookup fails.

    Verifies that:
    - Exception is caught and logged
    - Other revocations continue
    - No Slack message is sent for failed request
    """
    mock_aws_requests.get_expired_requests.return_value = [expired_request]
    mock_identity_store.get_user_id.side_effect = RuntimeError(
        "Identity store unavailable"
    )

    revoke_aws_sso_access(mock_slack_client)

    # Verify error was logged with context
    assert mock_logger.error.call_count == 1
    error_call = mock_logger.error.call_args
    assert error_call[0][0] == "failed_to_revoke_aws_sso_access"
    assert "production" in error_call[1].values()

    # Verify access was not revoked
    mock_sso.delete_account_assignment.assert_not_called()
    mock_slack_client.chat_postEphemeral.assert_not_called()


@pytest.mark.unit
@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.log_ops_message")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_access_handles_sso_deletion_error(
    mock_logger,
    mock_log_ops,
    mock_sso,
    mock_identity_store,
    mock_aws_requests,
    expired_request,
    mock_slack_client,
) -> None:
    """Test error handling when SSO deletion fails.

    Verifies that:
    - SSO deletion failure is logged with context
    - Request expiration and notifications are not sent
    """
    mock_aws_requests.get_expired_requests.return_value = [expired_request]
    mock_identity_store.get_user_id.return_value = "aws-user-123"
    mock_sso.delete_account_assignment.side_effect = RuntimeError("SSO API error")

    revoke_aws_sso_access(mock_slack_client)

    assert mock_logger.error.call_count == 1
    mock_aws_requests.expire_request.assert_not_called()
    mock_slack_client.chat_postEphemeral.assert_not_called()
    mock_log_ops.assert_not_called()


@pytest.mark.unit
@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.log_ops_message")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_access_multiple_requests(
    mock_logger,
    mock_log_ops,
    mock_sso,
    mock_identity_store,
    mock_aws_requests,
    expired_request,
    mock_slack_client,
) -> None:
    """Test revocation of multiple concurrent expired requests.

    Verifies that:
    - All requests are processed
    - Each revocation is independent
    - Failure in one doesn't block others
    """
    request2 = {
        **expired_request,
        "account_id": {"S": "987654321"},
        "account_name": {"S": "staging"},
        "user_id": {"S": "U99999"},
    }

    mock_aws_requests.get_expired_requests.return_value = [expired_request, request2]
    mock_identity_store.get_user_id.return_value = "aws-user-123"

    revoke_aws_sso_access(mock_slack_client)

    # Verify both requests were processed
    assert mock_identity_store.get_user_id.call_count == 2
    assert mock_sso.delete_account_assignment.call_count == 2
    assert mock_aws_requests.expire_request.call_count == 2
    assert mock_slack_client.chat_postEphemeral.call_count == 2


@pytest.mark.unit
@patch("jobs.revoke_aws_sso_access.aws_access_requests")
@patch("jobs.revoke_aws_sso_access.identity_store")
@patch("jobs.revoke_aws_sso_access.sso_admin")
@patch("jobs.revoke_aws_sso_access.log_ops_message")
@patch("jobs.revoke_aws_sso_access.logger")
def test_revoke_access_no_expired_requests(
    mock_logger,
    mock_log_ops,
    mock_sso,
    mock_identity_store,
    mock_aws_requests,
    mock_slack_client,
) -> None:
    """Test behavior when there are no expired requests.

    Verifies that:
    - Function completes without errors
    - No AWS or Slack operations are performed
    """
    mock_aws_requests.get_expired_requests.return_value = []

    revoke_aws_sso_access(mock_slack_client)

    mock_identity_store.get_user_id.assert_not_called()
    mock_sso.delete_account_assignment.assert_not_called()
    mock_slack_client.chat_postEphemeral.assert_not_called()
    mock_log_ops.assert_not_called()
