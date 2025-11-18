"""Unit tests for the audit logging module.

Tests verify pure functionality of:
- AuditEntry model validation and serialization
- write_audit_entry() structured logging behavior
- create_audit_entry_from_operation() factory function
- All required fields are captured and logged correctly
"""

from unittest.mock import patch
from modules.groups.infrastructure.audit import (
    AuditEntry,
    write_audit_entry,
    create_audit_entry_from_operation,
)


class TestAuditEntryModel:
    """Unit tests for AuditEntry Pydantic model."""

    def test_audit_entry_creation_with_required_fields_only(self):
        """AuditEntry can be created with only required fields."""
        entry = AuditEntry(
            correlation_id="test-123",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
        )

        assert entry.correlation_id == "test-123"
        assert entry.action == "add_member"
        assert entry.group_id == "test-group@example.com"
        assert entry.provider == "google"
        assert entry.success is True
        assert entry.timestamp is not None
        assert entry.member_email is None
        assert entry.requestor is None
        assert entry.justification is None
        assert entry.error_message is None
        assert entry.metadata == {}

    def test_audit_entry_creation_with_all_fields(self):
        """AuditEntry can be created with all fields populated."""
        entry = AuditEntry(
            correlation_id="test-456",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
            requestor="admin@example.com",
            member_email="user@example.com",
            justification="Adding new team member",
            metadata={"ticket_id": "JIRA-123", "propagation_count": 2},
        )

        assert entry.correlation_id == "test-456"
        assert entry.requestor == "admin@example.com"
        assert entry.member_email == "user@example.com"
        assert entry.justification == "Adding new team member"
        assert entry.metadata == {"ticket_id": "JIRA-123", "propagation_count": 2}

    def test_audit_entry_failure_case(self):
        """AuditEntry captures failure details with error message."""
        entry = AuditEntry(
            correlation_id="test-fail",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=False,
            error_message="Member already exists in group",
            metadata={"exception_type": "ValueError"},
        )

        assert entry.success is False
        assert entry.error_message == "Member already exists in group"
        assert entry.metadata == {"exception_type": "ValueError"}

    def test_audit_entry_default_ttl(self):
        """AuditEntry has default TTL of 90 days (7776000 seconds)."""
        entry = AuditEntry(
            correlation_id="test-ttl",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
        )

        # 90 days = 7776000 seconds
        assert entry.ttl_seconds == 7776000

    def test_audit_entry_timestamp_is_iso8601(self):
        """AuditEntry timestamp is in ISO 8601 format."""
        entry = AuditEntry(
            correlation_id="test-ts",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
        )

        # Verify timestamp is ISO 8601 format (includes T and is datetime string)
        assert "T" in entry.timestamp  # ISO 8601 includes T
        assert isinstance(entry.timestamp, str)
        # Verify it contains date and time parts
        parts = entry.timestamp.split("T")
        assert len(parts) == 2

    def test_audit_entry_custom_timestamp(self):
        """AuditEntry can be created with custom timestamp."""
        custom_ts = "2025-01-08T12:30:45Z"
        entry = AuditEntry(
            correlation_id="custom-ts",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
            timestamp=custom_ts,
        )

        assert entry.timestamp == custom_ts

    def test_audit_entry_serialization_to_dict(self):
        """AuditEntry can be serialized to dict."""
        entry = AuditEntry(
            correlation_id="serial-test",
            action="remove_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
            requestor="admin@example.com",
            member_email="user@example.com",
        )

        entry_dict = entry.model_dump()

        assert entry_dict["correlation_id"] == "serial-test"
        assert entry_dict["action"] == "remove_member"
        assert entry_dict["success"] is True

    def test_audit_entry_serialization_to_json(self):
        """AuditEntry can be serialized to JSON string."""
        entry = AuditEntry(
            correlation_id="json-test",
            action="add_member",
            group_id="test-group@example.com",
            provider="google",
            success=True,
        )

        entry_json = entry.model_dump_json()

        assert isinstance(entry_json, str)
        assert "json-test" in entry_json
        assert "add_member" in entry_json


class TestCreateAuditEntryFactory:
    """Unit tests for create_audit_entry_from_operation factory function."""

    def test_factory_creates_audit_entry_with_all_fields(self):
        """Factory creates AuditEntry from operation with all fields."""
        entry = create_audit_entry_from_operation(
            correlation_id="op-123",
            action="add_member",
            group_id="team@example.com",
            provider="google",
            success=True,
            requestor="admin@example.com",
            member_email="alice@example.com",
            justification="New hire",
            metadata={"propagation_count": 2},
        )

        assert entry.correlation_id == "op-123"
        assert entry.action == "add_member"
        assert entry.group_id == "team@example.com"
        assert entry.provider == "google"
        assert entry.success is True
        assert entry.requestor == "admin@example.com"
        assert entry.member_email == "alice@example.com"
        assert entry.justification == "New hire"
        assert entry.metadata == {"propagation_count": 2}

    def test_factory_creates_entry_with_failure(self):
        """Factory creates AuditEntry for failed operation."""
        entry = create_audit_entry_from_operation(
            correlation_id="op-fail",
            action="remove_member",
            group_id="team@example.com",
            provider="google",
            success=False,
            error_message="Permission denied",
            metadata={"exception_type": "PermissionError"},
        )

        assert entry.success is False
        assert entry.error_message == "Permission denied"
        assert entry.metadata == {"exception_type": "PermissionError"}

    def test_factory_with_minimal_parameters(self):
        """Factory creates AuditEntry with only required parameters."""
        entry = create_audit_entry_from_operation(
            correlation_id="op-min",
            action="add_member",
            group_id="team@example.com",
            provider="google",
            success=True,
        )

        assert entry.correlation_id == "op-min"
        assert entry.requestor is None
        assert entry.member_email is None
        assert entry.justification is None
        assert entry.error_message is None
        assert entry.metadata == {}

    def test_factory_with_none_metadata_defaults_to_empty_dict(self):
        """Factory handles None metadata by creating empty dict."""
        entry = create_audit_entry_from_operation(
            correlation_id="op-meta",
            action="add_member",
            group_id="team@example.com",
            provider="google",
            success=True,
            metadata=None,
        )

        assert entry.metadata == {}


class TestWriteAuditEntry:
    """Unit tests for write_audit_entry function."""

    @patch("modules.groups.infrastructure.audit.logger")
    def test_write_audit_entry_logs_all_fields(self, mock_logger):
        """write_audit_entry logs entry with all fields to structured logger."""
        entry = AuditEntry(
            correlation_id="write-test",
            action="add_member",
            group_id="team@example.com",
            provider="google",
            success=True,
            requestor="admin@example.com",
            member_email="alice@example.com",
            justification="New hire",
            metadata={"ticket": "JIRA-123"},
        )

        write_audit_entry(entry)

        # Verify logger.info was called with correct structure
        mock_logger.info.assert_called_once()

        # Get the call arguments
        call_args = mock_logger.info.call_args

        # First argument should be event name
        assert call_args[0][0] == "audit_entry"

        # Check that keyword arguments include all required fields
        kwargs = call_args[1]
        assert kwargs["correlation_id"] == "write-test"
        assert kwargs["action"] == "add_member"
        assert kwargs["group_id"] == "team@example.com"
        assert kwargs["provider"] == "google"
        assert kwargs["success"] is True
        assert kwargs["requestor"] == "admin@example.com"
        assert kwargs["member_email"] == "alice@example.com"
        assert kwargs["justification"] == "New hire"
        assert kwargs["metadata"] == {"ticket": "JIRA-123"}

    @patch("modules.groups.infrastructure.audit.logger")
    def test_write_audit_entry_logs_failure(self, mock_logger):
        """write_audit_entry logs failure case with error message."""
        entry = AuditEntry(
            correlation_id="fail-test",
            action="add_member",
            group_id="team@example.com",
            provider="google",
            success=False,
            requestor="admin@example.com",
            member_email="alice@example.com",
            error_message="User already exists in group",
            metadata={"exception_type": "ValueError"},
        )

        write_audit_entry(entry)

        # Verify logger.info was called
        mock_logger.info.assert_called_once()

        # Check error_message is logged
        call_args = mock_logger.info.call_args
        kwargs = call_args[1]
        assert kwargs["success"] is False
        assert kwargs["error_message"] == "User already exists in group"

    @patch("modules.groups.infrastructure.audit.logger")
    def test_write_audit_entry_with_empty_metadata(self, mock_logger):
        """write_audit_entry logs with empty metadata correctly."""
        entry = AuditEntry(
            correlation_id="empty-meta",
            action="list_groups",
            group_id="team@example.com",
            provider="google",
            success=True,
            metadata={},
        )

        write_audit_entry(entry)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        kwargs = call_args[1]
        assert kwargs["metadata"] == {}

    @patch("modules.groups.infrastructure.audit.logger")
    def test_write_audit_entry_logs_sync_not_async(self, mock_logger):
        """write_audit_entry is synchronous - blocks until logged."""
        entry = AuditEntry(
            correlation_id="sync-test",
            action="add_member",
            group_id="team@example.com",
            provider="google",
            success=True,
        )

        # Call write_audit_entry
        write_audit_entry(entry)

        # Verify logger was called immediately (synchronous)
        mock_logger.info.assert_called_once()
