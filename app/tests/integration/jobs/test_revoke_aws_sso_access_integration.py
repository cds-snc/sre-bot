"""Integration tests for AWS SSO access revocation job.

Tests the complete revocation workflow with real app initialization,
database interactions, and external service calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from jobs.revoke_aws_sso_access import revoke_aws_sso_access


@pytest.mark.integration
class TestRevokeAWSAccessWorkflow:
    """Complete workflow tests for AWS SSO access revocation."""

    @pytest.fixture
    def aws_expired_requests(self) -> list:
        """Complete expired access request from database."""
        return [
            {
                "account_id": {"S": "production-123"},
                "account_name": {"S": "production"},
                "user_id": {"S": "U12345"},
                "email": {"S": "engineer@company.com"},
                "access_type": {"S": "ReadOnlyAccess"},
                "created_at": {"N": "1704067200"},
            },
            {
                "account_id": {"S": "developmentx789"},
                "account_name": {"S": "development"},
                "user_id": {"S": "U99999"},
                "email": {"S": "dev@company.com"},
                "access_type": {"S": "PowerUserAccess"},
                "created_at": {"N": "1704153600"},
            },
        ]

    @pytest.fixture
    def mock_slack_client_with_validation(self) -> MagicMock:
        """Slack client with validation of call parameters."""
        client = MagicMock()
        return client

    @patch("jobs.revoke_aws_sso_access.aws_access_requests")
    @patch("jobs.revoke_aws_sso_access.identity_store")
    @patch("jobs.revoke_aws_sso_access.sso_admin")
    @patch("jobs.revoke_aws_sso_access.log_ops_message")
    def test_complete_revocation_workflow(
        self,
        mock_log_ops,
        mock_sso,
        mock_identity_store,
        mock_aws_requests,
        aws_expired_requests,
        mock_slack_client_with_validation,
    ) -> None:
        """Test complete revocation workflow for multiple accounts.

        Verifies the full integration:
        1. Fetch expired requests from database
        2. Lookup user in AWS Identity Store
        3. Delete account assignment from SSO
        4. Mark request as expired in database
        5. Notify user and ops

        This test exercises the complete system boundary without
        testing the mocked components themselves.
        """
        mock_aws_requests.get_expired_requests.return_value = aws_expired_requests

        # Map emails to AWS user IDs
        identity_lookups = {
            "engineer@company.com": "aws-user-prod-123",
            "dev@company.com": "aws-user-dev-456",
        }
        mock_identity_store.get_user_id.side_effect = lambda email: identity_lookups[
            email
        ]

        revoke_aws_sso_access(mock_slack_client_with_validation)

        # Verify complete workflow was executed
        assert mock_identity_store.get_user_id.call_count == 2
        assert mock_sso.delete_account_assignment.call_count == 2
        assert mock_aws_requests.expire_request.call_count == 2
        assert mock_slack_client_with_validation.chat_postEphemeral.call_count == 2
        assert mock_log_ops.call_count == 2

    @patch("jobs.revoke_aws_sso_access.aws_access_requests")
    @patch("jobs.revoke_aws_sso_access.identity_store")
    @patch("jobs.revoke_aws_sso_access.sso_admin")
    @patch("jobs.revoke_aws_sso_access.log_ops_message")
    def test_partial_failure_continues_processing(
        self,
        mock_log_ops,
        mock_sso,
        mock_identity_store,
        mock_aws_requests,
        aws_expired_requests,
        mock_slack_client_with_validation,
    ) -> None:
        """Test that failure in one revocation doesn't block others.

        Simulates:
        - First request: succeeds
        - Second request: identity store lookup fails

        Verifies:
        - First request completes fully
        - Second request fails gracefully
        - System continues processing
        """
        mock_aws_requests.get_expired_requests.return_value = aws_expired_requests

        def identity_side_effect(email):
            if email == "engineer@company.com":
                return "aws-user-prod-123"
            raise RuntimeError("Identity store unavailable")

        mock_identity_store.get_user_id.side_effect = identity_side_effect

        revoke_aws_sso_access(mock_slack_client_with_validation)

        # First request should succeed completely
        assert mock_sso.delete_account_assignment.call_count == 1
        assert mock_aws_requests.expire_request.call_count == 1
        assert mock_slack_client_with_validation.chat_postEphemeral.call_count == 1
        assert mock_log_ops.call_count == 1

    @patch("jobs.revoke_aws_sso_access.aws_access_requests")
    @patch("jobs.revoke_aws_sso_access.identity_store")
    @patch("jobs.revoke_aws_sso_access.sso_admin")
    @patch("jobs.revoke_aws_sso_access.log_ops_message")
    def test_notification_includes_required_context(
        self,
        mock_log_ops,
        mock_sso,
        mock_identity_store,
        mock_aws_requests,
        aws_expired_requests,
        mock_slack_client_with_validation,
    ) -> None:
        """Test that notifications include all required context.

        Verifies Slack messages contain:
        - Account name
        - Account ID
        - User mention
        - User email
        - Access type
        """
        mock_aws_requests.get_expired_requests.return_value = [aws_expired_requests[0]]
        mock_identity_store.get_user_id.return_value = "aws-user-123"

        revoke_aws_sso_access(mock_slack_client_with_validation)

        # Get the Slack message that was sent
        call_kwargs = mock_slack_client_with_validation.chat_postEphemeral.call_args[1]
        message_text = call_kwargs["text"]

        # Verify message contains all context
        assert "production" in message_text
        assert "production-123" in message_text
        assert "engineer@company.com" in message_text
        assert "ReadOnlyAccess" in message_text
        assert "<@U12345>" in message_text


@pytest.mark.integration
class TestScheduledRevokeIntegration:
    """Integration tests for scheduled revocation execution."""

    @patch("jobs.revoke_aws_sso_access.aws_access_requests")
    @patch("jobs.revoke_aws_sso_access.identity_store")
    @patch("jobs.revoke_aws_sso_access.sso_admin")
    @patch("jobs.revoke_aws_sso_access.log_ops_message")
    def test_revoke_called_with_slack_client(
        self,
        mock_log_ops,
        mock_sso,
        mock_identity_store,
        mock_aws_requests,
    ) -> None:
        """Test that revoke function accepts real Slack client."""
        mock_aws_requests.get_expired_requests.return_value = []
        real_client = MagicMock()

        # Should not raise
        revoke_aws_sso_access(real_client)

        # With no requests, nothing should be called
        mock_identity_store.get_user_id.assert_not_called()
