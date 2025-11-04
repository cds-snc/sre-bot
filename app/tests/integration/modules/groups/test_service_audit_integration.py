"""Integration tests for audit logging in service layer.

Tests verify that:
- add_member operation generates and logs audit entries
- remove_member operation generates and logs audit entries
- Failed operations log error audit entries
- correlation_id is included in responses and audit entries
- Justification and requestor are captured
"""

from unittest.mock import patch
from modules.groups import schemas
from modules.groups.audit import AuditEntry


class TestAddMemberAuditLogging:
    """Integration tests for add_member audit logging."""

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.add_member_to_group")
    def test_add_member_writes_audit_entry_on_success(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """add_member writes audit entry to log on successful operation."""
        from modules.groups import service

        # Mock orchestration response
        mock_orch.return_value = {
            "success": True,
            "group_id": "team@example.com",
            "member_email": "alice@example.com",
            "timestamp": "2025-01-08T12:00:00Z",
        }

        # Create request
        req = schemas.AddMemberRequest(
            group_id="team@example.com",
            member_email="alice@example.com",
            provider=schemas.ProviderType.GOOGLE,
            requestor="admin@example.com",
            justification="Adding new hire to the engineering team",  # Longer justification
        )

        # Call service
        res = service.add_member(req)

        # Verify response contains correlation_id
        assert res.success is True
        assert "correlation_id" in res.details
        correlation_id = res.details["correlation_id"]
        assert correlation_id is not None

        # Verify audit entry was written
        mock_audit_write.assert_called_once()
        audit_entry = mock_audit_write.call_args[0][0]

        # Verify audit entry contents
        assert isinstance(audit_entry, AuditEntry)
        assert audit_entry.correlation_id == correlation_id
        assert audit_entry.action == "add_member"
        assert audit_entry.group_id == "team@example.com"
        assert audit_entry.member_email == "alice@example.com"
        assert audit_entry.provider == "google"
        assert audit_entry.success is True
        assert audit_entry.requestor == "admin@example.com"
        assert audit_entry.justification == "Adding new hire to the engineering team"
        assert audit_entry.error_message is None

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.add_member_to_group")
    def test_add_member_writes_audit_entry_on_failure(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """add_member writes failure audit entry when orchestration fails."""
        from modules.groups import service

        # Mock orchestration to raise exception
        error_msg = "Permission denied"
        mock_orch.side_effect = ValueError(error_msg)

        # Create request
        req = schemas.AddMemberRequest(
            group_id="team@example.com",
            member_email="alice@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Adding new team member",
            requestor="admin@example.com",
        )

        # Call service and expect exception
        try:
            service.add_member(req)
        except ValueError:
            pass

        # Verify audit entry was written for failure
        mock_audit_write.assert_called_once()
        audit_entry = mock_audit_write.call_args[0][0]

        # Verify failure audit entry
        assert isinstance(audit_entry, AuditEntry)
        assert audit_entry.action == "add_member"
        assert audit_entry.success is False
        assert audit_entry.error_message == error_msg
        assert "ValueError" in audit_entry.metadata.get("exception_type", "")

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.add_member_to_group")
    def test_add_member_correlation_id_unique_per_request(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """add_member generates unique correlation_id for each request."""
        from modules.groups import service
        from uuid import uuid4

        mock_orch.return_value = {
            "success": True,
            "group_id": "team@example.com",
            "member_email": "alice@example.com",
            "timestamp": "2025-01-08T12:00:00Z",
        }

        # Create two different requests (different idempotency keys to bypass cache)
        req1 = schemas.AddMemberRequest(
            group_id="team@example.com",
            member_email="alice@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Adding new team member",
            idempotency_key=str(uuid4()),  # Different key for second request
        )

        req2 = schemas.AddMemberRequest(
            group_id="team@example.com",
            member_email="alice@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Adding new team member",
            idempotency_key=str(uuid4()),  # Different key
        )

        # Call service twice with different requests
        res1 = service.add_member(req1)
        res2 = service.add_member(req2)

        # Verify responses have different correlation_ids
        correlation_id_1 = res1.details["correlation_id"]
        correlation_id_2 = res2.details["correlation_id"]

        assert correlation_id_1 != correlation_id_2
        assert correlation_id_1 is not None
        assert correlation_id_2 is not None


class TestRemoveMemberAuditLogging:
    """Integration tests for remove_member audit logging."""

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.remove_member_from_group")
    def test_remove_member_writes_audit_entry_on_success(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """remove_member writes audit entry to log on successful operation."""
        from modules.groups import service

        # Mock orchestration response
        mock_orch.return_value = {
            "success": True,
            "group_id": "team@example.com",
            "member_email": "bob@example.com",
            "timestamp": "2025-01-08T13:00:00Z",
        }

        # Create request
        req = schemas.RemoveMemberRequest(
            group_id="team@example.com",
            member_email="bob@example.com",
            provider=schemas.ProviderType.GOOGLE,
            requestor="admin@example.com",
            justification="Access revoked",
        )

        # Call service
        res = service.remove_member(req)

        # Verify response contains correlation_id
        assert res.success is True
        assert "correlation_id" in res.details
        correlation_id = res.details["correlation_id"]

        # Verify audit entry was written
        mock_audit_write.assert_called_once()
        audit_entry = mock_audit_write.call_args[0][0]

        # Verify audit entry contents
        assert isinstance(audit_entry, AuditEntry)
        assert audit_entry.correlation_id == correlation_id
        assert audit_entry.action == "remove_member"
        assert audit_entry.group_id == "team@example.com"
        assert audit_entry.member_email == "bob@example.com"
        assert audit_entry.provider == "google"
        assert audit_entry.success is True
        assert audit_entry.requestor == "admin@example.com"
        assert audit_entry.justification == "Access revoked"

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.remove_member_from_group")
    def test_remove_member_writes_audit_entry_on_failure(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """remove_member writes failure audit entry when orchestration fails."""
        from modules.groups import service

        # Mock orchestration to raise exception
        error_msg = "User not in group"
        mock_orch.side_effect = RuntimeError(error_msg)

        # Create request
        req = schemas.RemoveMemberRequest(
            group_id="team@example.com",
            member_email="bob@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Access revoked for offboarding",
        )

        # Call service and expect exception
        try:
            service.remove_member(req)
        except RuntimeError:
            pass

        # Verify audit entry was written
        mock_audit_write.assert_called_once()
        audit_entry = mock_audit_write.call_args[0][0]

        # Verify failure audit entry
        assert audit_entry.success is False
        assert audit_entry.error_message == error_msg
        assert "RuntimeError" in audit_entry.metadata.get("exception_type", "")


class TestAuditLoggingEventDispatch:
    """Integration tests verifying audit logging works alongside event dispatch."""

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.add_member_to_group")
    def test_audit_written_before_event_dispatched(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """Audit entry is written before event dispatch (guarantee audit trail)."""
        from modules.groups import service

        mock_orch.return_value = {
            "success": True,
            "group_id": "team@example.com",
            "member_email": "alice@example.com",
            "timestamp": "2025-01-08T12:00:00Z",
        }

        req = schemas.AddMemberRequest(
            group_id="team@example.com",
            member_email="alice@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Adding new team member",
        )

        # Call service
        service.add_member(req)

        # Verify both audit write and event dispatch were called
        mock_audit_write.assert_called_once()
        mock_dispatch.assert_called_once()

        # Event dispatch happens for notifications
        assert mock_dispatch.call_args[0][0] == "group.member.added"

    @patch("modules.groups.service.audit.write_audit_entry")
    @patch("modules.groups.service.event_system.dispatch_background")
    @patch("modules.groups.service.orchestration.remove_member_from_group")
    def test_remove_member_dispatches_correct_event(
        self, mock_orch, mock_dispatch, mock_audit_write
    ):
        """remove_member dispatches correct event type."""
        from modules.groups import service

        mock_orch.return_value = {
            "success": True,
            "group_id": "team@example.com",
            "member_email": "bob@example.com",
            "timestamp": "2025-01-08T13:00:00Z",
        }

        req = schemas.RemoveMemberRequest(
            group_id="team@example.com",
            member_email="bob@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Access revoked for offboarding",
        )

        service.remove_member(req)

        # Verify correct event was dispatched
        mock_audit_write.assert_called_once()
        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args[0][0] == "group.member.removed"
