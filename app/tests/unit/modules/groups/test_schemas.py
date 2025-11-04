"""Unit tests for groups module Pydantic schemas.

Tests cover:
- Request schema validation (AddMember, RemoveMember, BulkOperations, ListGroups, CheckPermissions)
- Response schema validation (ActionResponse, BulkOperationResponse)
- Field validation (email format, enum values, length constraints)
- Default values and optional fields
- Error messages for invalid data
"""

import pytest
from datetime import datetime
from uuid import uuid4
from pydantic import ValidationError
from modules.groups import schemas


@pytest.mark.unit
class TestAddMemberRequest:
    """Tests for AddMemberRequest schema."""

    def test_valid_add_member_request_minimal(self):
        """AddMemberRequest accepts minimal required data."""
        request = schemas.AddMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="User joining engineering team",
        )

        assert request.group_id == "group-1"
        assert request.member_email == "user@example.com"
        assert request.provider == schemas.ProviderType.GOOGLE
        assert request.justification == "User joining engineering team"
        assert request.requestor is None
        assert request.metadata is None
        assert request.idempotency_key is not None

    def test_add_member_request_with_all_fields(self):
        """AddMemberRequest accepts all optional fields."""
        idempotency_key = str(uuid4())
        request = schemas.AddMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Access needed for project",
            requestor="admin@example.com",
            metadata={"ticket_id": "JIRA-123"},
            idempotency_key=idempotency_key,
        )

        assert request.justification == "Access needed for project"
        assert request.requestor == "admin@example.com"
        assert request.metadata == {"ticket_id": "JIRA-123"}
        assert request.idempotency_key == idempotency_key

    def test_add_member_request_invalid_email_raises(self):
        """AddMemberRequest rejects invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            schemas.AddMemberRequest(
                group_id="group-1",
                member_email="not-an-email",
                provider=schemas.ProviderType.GOOGLE,
                justification="User joining engineering team",
            )

        errors = exc_info.value.errors()
        assert any("member_email" in str(e) for e in errors)

    def test_add_member_request_empty_group_id_raises(self):
        """AddMemberRequest rejects empty group_id."""
        with pytest.raises(ValidationError) as exc_info:
            schemas.AddMemberRequest(
                group_id="",
                member_email="user@example.com",
                provider=schemas.ProviderType.GOOGLE,
                justification="User joining engineering team",
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_add_member_request_invalid_provider_raises(self):
        """AddMemberRequest rejects invalid provider value."""
        with pytest.raises(ValidationError):
            schemas.AddMemberRequest(
                group_id="group-1",
                member_email="user@example.com",
                provider="invalid_provider",
                justification="User joining engineering team",
            )

    def test_add_member_request_max_justification_length(self):
        """AddMemberRequest enforces maximum justification length."""
        long_justification = "x" * 501

        with pytest.raises(ValidationError) as exc_info:
            schemas.AddMemberRequest(
                group_id="group-1",
                member_email="user@example.com",
                provider=schemas.ProviderType.GOOGLE,
                justification=long_justification,
            )

        errors = exc_info.value.errors()
        assert any("justification" in str(e).lower() for e in errors)

    def test_add_member_request_accepts_max_valid_justification(self):
        """AddMemberRequest accepts justification at maximum length."""
        valid_justification = "x" * 500

        request = schemas.AddMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification=valid_justification,
        )

        assert len(request.justification) == 500


@pytest.mark.unit
class TestRemoveMemberRequest:
    """Tests for RemoveMemberRequest schema."""

    def test_valid_remove_member_request_minimal(self):
        """RemoveMemberRequest accepts minimal required data."""
        request = schemas.RemoveMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.AWS,
            justification="User no longer requires access",
        )

        assert request.group_id == "group-1"
        assert request.member_email == "user@example.com"
        assert request.provider == schemas.ProviderType.AWS
        assert request.justification == "User no longer requires access"

    def test_remove_member_request_with_justification(self):
        """RemoveMemberRequest accepts justification."""
        justification = "User left the team"
        request = schemas.RemoveMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification=justification,
        )

        assert request.justification == justification

    def test_remove_member_request_max_justification_length(self):
        """RemoveMemberRequest enforces maximum justification length."""
        long_justification = "x" * 501

        with pytest.raises(ValidationError) as exc_info:
            schemas.RemoveMemberRequest(
                group_id="group-1",
                member_email="user@example.com",
                provider=schemas.ProviderType.GOOGLE,
                justification=long_justification,
            )

        errors = exc_info.value.errors()
        assert any("justification" in str(e).lower() for e in errors)

    def test_remove_member_request_accepts_max_valid_justification(self):
        """RemoveMemberRequest accepts justification at maximum length."""
        valid_justification = "x" * 500

        request = schemas.RemoveMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification=valid_justification,
        )

        assert len(request.justification) == 500


@pytest.mark.unit
class TestOperationItem:
    """Tests for OperationItem schema."""

    def test_operation_item_add_member_valid(self):
        """OperationItem accepts valid ADD_MEMBER operation."""
        item = schemas.OperationItem(
            operation=schemas.OperationType.ADD_MEMBER,
            payload={
                "group_id": "g-1",
                "member_email": "u@example.com",
                "provider": "google",
                "justification": "User joining team project",
            },
        )

        assert item.operation == schemas.OperationType.ADD_MEMBER
        assert item.payload["group_id"] == "g-1"

    def test_operation_item_remove_member_valid(self):
        """OperationItem accepts valid REMOVE_MEMBER operation."""
        item = schemas.OperationItem(
            operation=schemas.OperationType.REMOVE_MEMBER,
            payload={
                "group_id": "g-1",
                "member_email": "u@example.com",
                "provider": "google",
                "justification": "User leaving team project",
            },
        )

        assert item.operation == schemas.OperationType.REMOVE_MEMBER

    def test_operation_item_invalid_payload_raises(self):
        """OperationItem rejects invalid payload for operation."""
        with pytest.raises(ValidationError):
            schemas.OperationItem(
                operation=schemas.OperationType.ADD_MEMBER,
                payload={"invalid": "payload"},
            )


@pytest.mark.unit
class TestBulkOperationsRequest:
    """Tests for BulkOperationsRequest schema."""

    def test_bulk_operations_request_valid(self):
        """BulkOperationsRequest accepts list of operations."""
        request = schemas.BulkOperationsRequest(
            operations=[
                schemas.OperationItem(
                    operation=schemas.OperationType.ADD_MEMBER,
                    payload={
                        "group_id": "g-1",
                        "member_email": "u1@example.com",
                        "provider": "google",
                        "justification": "User joining team project",
                    },
                ),
                schemas.OperationItem(
                    operation=schemas.OperationType.REMOVE_MEMBER,
                    payload={
                        "group_id": "g-1",
                        "member_email": "u2@example.com",
                        "provider": "google",
                        "justification": "User leaving team project",
                    },
                ),
            ]
        )

        assert len(request.operations) == 2
        assert request.operations[0].operation == schemas.OperationType.ADD_MEMBER
        assert request.operations[1].operation == schemas.OperationType.REMOVE_MEMBER

    def test_bulk_operations_empty_list_raises(self):
        """BulkOperationsRequest rejects empty operations list."""
        with pytest.raises(ValidationError):
            schemas.BulkOperationsRequest(operations=[])

    def test_bulk_operations_max_items(self):
        """BulkOperationsRequest enforces maximum operations limit."""
        # Create 101 operations (exceeding max of 100)
        operations = [
            schemas.OperationItem(
                operation=schemas.OperationType.ADD_MEMBER,
                payload={
                    "group_id": f"g-{i}",
                    "member_email": f"u{i}@example.com",
                    "provider": "google",
                    "justification": "User joining team project",
                },
            )
            for i in range(101)
        ]

        with pytest.raises(ValidationError):
            schemas.BulkOperationsRequest(operations=operations)


@pytest.mark.unit
class TestListGroupsRequest:
    """Tests for ListGroupsRequest schema."""

    def test_list_groups_request_with_email_only(self):
        """ListGroupsRequest accepts email address."""
        request = schemas.ListGroupsRequest(
            user_email="user@example.com",
        )

        assert request.user_email == "user@example.com"
        assert request.provider is None

    def test_list_groups_request_with_provider(self):
        """ListGroupsRequest accepts optional provider."""
        request = schemas.ListGroupsRequest(
            user_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
        )

        assert request.provider == schemas.ProviderType.GOOGLE

    def test_list_groups_request_invalid_email(self):
        """ListGroupsRequest rejects invalid email."""
        with pytest.raises(ValidationError):
            schemas.ListGroupsRequest(user_email="not-an-email")


@pytest.mark.unit
class TestCheckPermissionsRequest:
    """Tests for CheckPermissionsRequest schema."""

    def test_check_permissions_request_valid(self):
        """CheckPermissionsRequest accepts valid data."""
        request = schemas.CheckPermissionsRequest(
            user_email="user@example.com",
            group_id="g-1",
            action=schemas.PermissionAction.VIEW,
            provider=schemas.ProviderType.GOOGLE,
        )

        assert request.user_email == "user@example.com"
        assert request.group_id == "g-1"
        assert request.action == schemas.PermissionAction.VIEW
        assert request.provider == schemas.ProviderType.GOOGLE

    def test_check_permissions_request_different_actions(self):
        """CheckPermissionsRequest accepts different actions."""
        for action in [
            schemas.PermissionAction.VIEW,
            schemas.PermissionAction.EDIT,
            schemas.PermissionAction.DELETE,
            schemas.PermissionAction.APPROVE,
        ]:
            request = schemas.CheckPermissionsRequest(
                user_email="user@example.com",
                group_id="g-1",
                action=action,
                provider=schemas.ProviderType.GOOGLE,
            )
            assert request.action == action


@pytest.mark.unit
class TestActionResponse:
    """Tests for ActionResponse schema."""

    def test_valid_action_response_success(self):
        """ActionResponse accepts successful action."""
        ts = datetime.utcnow()
        response = schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            group_id="g-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            timestamp=ts,
        )

        assert response.success is True
        assert response.action == schemas.OperationType.ADD_MEMBER
        assert response.group_id == "g-1"
        assert isinstance(response.timestamp, datetime)

    def test_action_response_with_details(self):
        """ActionResponse accepts details information for errors or extended data."""
        ts = datetime.utcnow()
        response = schemas.ActionResponse(
            success=False,
            action=schemas.OperationType.REMOVE_MEMBER,
            group_id="g-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.AWS,
            timestamp=ts,
            details={"error": "Member not found", "code": "MEMBER_NOT_FOUND"},
        )

        assert response.success is False
        assert response.details == {
            "error": "Member not found",
            "code": "MEMBER_NOT_FOUND",
        }

    def test_action_response_timestamp_validation(self):
        """ActionResponse validates timestamp is datetime object."""
        # Valid datetime
        response = schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            group_id="g-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
        )

        assert response.timestamp.year == 2025

        # Invalid timestamp type should raise
        with pytest.raises(ValidationError):
            schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id="g-1",
                member_email="user@example.com",
                provider=schemas.ProviderType.GOOGLE,
                timestamp="not-a-datetime",
            )

    def test_action_response_optional_fields_default_to_none(self):
        """ActionResponse optional fields default to None."""
        response = schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            group_id="g-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            timestamp=datetime.utcnow(),
        )

        assert response.details is None


@pytest.mark.unit
class TestProviderType:
    """Tests for ProviderType enum."""

    def test_provider_type_enum_values(self):
        """ProviderType enum has expected values."""
        assert schemas.ProviderType.GOOGLE == "google"
        assert schemas.ProviderType.AWS == "aws"
        assert schemas.ProviderType.OKTA == "okta"
        assert schemas.ProviderType.AZURE == "azure"
        assert schemas.ProviderType.SLACK == "slack"

    def test_provider_type_in_request_validation(self):
        """Schemas validate provider against ProviderType enum."""
        # Valid provider
        request = schemas.AddMemberRequest(
            group_id="g-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="User joining team project",
        )
        assert request.provider == schemas.ProviderType.GOOGLE

        # String value works due to Pydantic coercion
        request2 = schemas.AddMemberRequest(
            group_id="g-1",
            member_email="user@example.com",
            provider="aws",
            justification="User joining team project",
        )
        assert request2.provider == schemas.ProviderType.AWS


@pytest.mark.unit
class TestOperationType:
    """Tests for OperationType enum."""

    def test_operation_type_enum_values(self):
        """OperationType enum has expected values."""
        assert schemas.OperationType.ADD_MEMBER == "add_member"
        assert schemas.OperationType.REMOVE_MEMBER == "remove_member"

    def test_operation_type_in_response(self):
        """ActionResponse uses OperationType enum."""
        response = schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            group_id="g-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            timestamp=datetime.utcnow(),
        )

        assert response.action == schemas.OperationType.ADD_MEMBER
        assert response.action.value == "add_member"


@pytest.mark.unit
class TestPermissionAction:
    """Tests for PermissionAction enum."""

    def test_permission_action_enum_values(self):
        """PermissionAction enum has expected values."""
        assert schemas.PermissionAction.VIEW == "view"
        assert schemas.PermissionAction.EDIT == "edit"
        assert schemas.PermissionAction.DELETE == "delete"
        assert schemas.PermissionAction.APPROVE == "approve"

    def test_permission_action_in_request(self):
        """CheckPermissionsRequest uses PermissionAction enum."""
        for action_val in [
            schemas.PermissionAction.VIEW,
            schemas.PermissionAction.EDIT,
            schemas.PermissionAction.DELETE,
            schemas.PermissionAction.APPROVE,
        ]:
            request = schemas.CheckPermissionsRequest(
                user_email="user@example.com",
                group_id="g-1",
                action=action_val,
                provider=schemas.ProviderType.GOOGLE,
            )
            assert request.action == action_val
