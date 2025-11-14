"""API validation and response schemas using Pydantic.

This module defines all request and response models for the groups API.
All classes extend Pydantic BaseModel and provide:
  - Runtime input validation
  - OpenAPI/JSON schema generation
  - Type safety with Annotated field hints
  - Serialization/deserialization support

Key distinction from models.py:
  - schemas.py: API contracts with full Pydantic validation
  - models.py: Internal normalized structures (dataclasses, no validation)

Key distinction from types.py:
  - schemas.py: API validation contracts with Pydantic
  - types.py: Internal protocol hints (TypedDict, no validation)

Important relationships:
  - MemberResponse and GroupResponse are API serialization views of
    NormalizedMember and NormalizedGroup (see models.py)
  - ProviderType and OperationType enums are used by both APIs and
    internal orchestration for consistency
  - Request models (AddMemberRequest, RemoveMemberRequest, etc.) are
    validated here before passing to service layer

Usage:
  - Imported by: api.py, controllers.py, commands.py, idempotency.py
  - All API endpoints should accept/return these models
"""

from typing import Any, Dict, List, Optional, Annotated
from datetime import datetime
from enum import Enum
from uuid import uuid4
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    model_validator,
)


class ProviderType(str, Enum):
    """Schema for provider types.

    Enum of supported identity/group providers. Shared across API requests
    and internal business logic for consistency.
    """

    GOOGLE = "google"
    OKTA = "okta"
    AZURE = "azure"
    AWS = "aws"
    SLACK = "slack"


class OperationType(str, Enum):
    """Schema for operation types.

    Enum of supported group membership operations. Used in both API requests
    (BulkOperationsRequest) and internal responses (ActionResponse).
    """

    ADD_MEMBER = "add_member"
    REMOVE_MEMBER = "remove_member"


class PermissionAction(str, Enum):
    """Schema for permission actions.

    Enum of permission-related actions supported by the groups API.
    """

    VIEW = "view"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"


class AddMemberRequest(BaseModel):
    """Schema for adding a member to a group.

    All fields are required except requestor and metadata. Justification is
    required for audit and compliance purposes.
    """

    group_id: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            description="Target group ID",
            json_schema_extra={"example": "group-123"},
        ),
    ]
    member_email: Annotated[
        EmailStr,
        Field(
            ...,
            description="Email of member to add",
            json_schema_extra={"example": "user@example.com"},
        ),
    ]
    provider: Annotated[
        ProviderType,
        Field(
            ..., description="Provider type", json_schema_extra={"example": "google"}
        ),
    ]
    justification: Annotated[
        str,
        Field(
            ...,
            min_length=10,
            max_length=500,
            description="Justification for adding member (required, minimum 10 characters)",
            json_schema_extra={
                "example": "User joining engineering team to work on backend services"
            },
        ),
    ]
    requestor: Annotated[
        EmailStr,
        Field(
            default=None,
            description="Email of requestor",
            json_schema_extra={"example": "admin@example.com"},
        ),
    ]
    metadata: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Additional metadata",
            json_schema_extra={"example": {"ticket_id": "JIRA-123"}},
        ),
    ] = None
    idempotency_key: Annotated[
        str,
        Field(
            default_factory=lambda: str(uuid4()),
            description="Idempotency key for request deduplication (auto-generated if not provided)",
            json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
        ),
    ]


class RemoveMemberRequest(BaseModel):
    """Schema for removing a member from a group.

    All fields are required except requestor and metadata. Justification is
    required for audit and compliance purposes.
    """

    group_id: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            description="Target group ID",
            json_schema_extra={"example": "group-123"},
        ),
    ]
    member_email: Annotated[
        EmailStr,
        Field(
            ...,
            description="Email of member to remove",
            json_schema_extra={"example": "user@example.com"},
        ),
    ]
    provider: Annotated[
        ProviderType,
        Field(
            ..., description="Provider type", json_schema_extra={"example": "google"}
        ),
    ]
    justification: Annotated[
        str,
        Field(
            ...,
            min_length=10,
            max_length=500,
            description="Justification for removing member (required, minimum 10 characters)",
            json_schema_extra={
                "example": "User no longer requires access to this group"
            },
        ),
    ]
    requestor: Annotated[
        EmailStr,
        Field(
            default=None,
            description="Email of requestor",
            json_schema_extra={"example": "admin@example.com"},
        ),
    ]
    metadata: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Additional metadata",
            json_schema_extra={"example": {"ticket_id": "JIRA-456"}},
        ),
    ] = None
    idempotency_key: Annotated[
        str,
        Field(
            default_factory=lambda: str(uuid4()),
            description="Idempotency key for request deduplication (auto-generated if not provided)",
            json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
        ),
    ]


class OperationItem(BaseModel):
    """Schema for a single operation item."""

    operation: Annotated[
        OperationType,
        Field(
            ...,
            description="Operation type",
            json_schema_extra={"example": "add_member"},
        ),
    ]
    payload: Annotated[Dict[str, Any], Field(..., description="Operation payload")]

    @model_validator(mode="before")
    def validate_payload(cls, values):  # pylint: disable=no-self-argument
        try:
            op = values.get("operation")
            payload = values.get("payload")
        except Exception:
            # If values isn't a mapping, return it to allow Pydantic to
            # raise the appropriate error downstream.
            return values
        if op == OperationType.ADD_MEMBER:
            AddMemberRequest(**payload)
        elif op == OperationType.REMOVE_MEMBER:
            RemoveMemberRequest(**payload)
        else:
            raise ValueError("Invalid operation type")
        return values


class BulkOperationsRequest(BaseModel):
    """Schema for bulk operations request."""

    operations: Annotated[
        List[OperationItem],
        Field(
            ...,
            min_length=1,
            max_length=100,
            description="List of operations",
        ),
    ]


class ListGroupsRequest(BaseModel):
    """Schema for listing groups with flexible filtering options.

    This unified schema handles all four use cases:
    1. Simple list: target_member_email only (optional)
    2. User's groups: target_member_email + include_members=True
    3. Managed groups: target_member_email + include_members=True + filter_by_member_role with MANAGER/OWNER
    4. System sync: target_member_email + include_members=True + include_users_details=False
    """

    requestor: Annotated[
        EmailStr,
        Field(
            ...,
            description="Requestor email",
            json_schema_extra={"example": "requestor@example.com"},
        ),
    ]
    target_member_email: Annotated[
        Optional[EmailStr],
        Field(
            default=None,
            description="Email of the member whose groups are being queried",
            json_schema_extra={"example": "member@example.com"},
        ),
    ] = None
    provider: Annotated[
        Optional[ProviderType],
        Field(
            default=None,
            description="Provider type",
            json_schema_extra={"example": "google"},
        ),
    ] = None

    include_members: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to include group members in response",
            json_schema_extra={"example": True},
        ),
    ] = False

    include_users_details: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to enrich members with full user details (requires include_members=True)",
            json_schema_extra={"example": True},
        ),
    ] = False

    filter_by_member_email: Annotated[
        Optional[EmailStr],
        Field(
            default=None,
            description="Filter groups by member email (group included if member exists; requires include_members=True)",
            json_schema_extra={"example": "john@example.com"},
        ),
    ] = None

    filter_by_member_role: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Filter groups by member role (e.g., ['MANAGER', 'OWNER']; requires include_members=True)",
            json_schema_extra={"example": ["MANAGER", "OWNER"]},
        ),
    ] = None

    exclude_empty_groups: Annotated[
        bool,
        Field(
            default=True,
            description="Whether to exclude groups with no members (requires include_members=True)",
            json_schema_extra={"example": True},
        ),
    ] = True

    @model_validator(mode="after")
    def validate_filter_dependencies(self):
        """Ensure filter parameters are only used with include_members=True."""
        if self.target_member_email is None:
            self.target_member_email = self.requestor

        if not self.include_members:
            if self.filter_by_member_email is not None:
                raise ValueError("filter_by_member_email requires include_members=True")
            if self.filter_by_member_role is not None:
                raise ValueError("filter_by_member_role requires include_members=True")
            if not self.exclude_empty_groups:
                raise ValueError(
                    "include_empty_groups filtering requires include_members=True"
                )

        if not self.include_members and self.include_users_details:
            raise ValueError("include_users_details requires include_members=True")

        return self


class CheckPermissionsRequest(BaseModel):
    """Schema for checking permissions on a group."""

    user_email: Annotated[
        EmailStr,
        Field(
            ...,
            description="User email",
            json_schema_extra={"example": "user@example.com"},
        ),
    ]
    group_id: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            description="Group ID",
            json_schema_extra={"example": "group-123"},
        ),
    ]
    action: Annotated[
        PermissionAction,
        Field(
            ..., description="Permission action", json_schema_extra={"example": "view"}
        ),
    ]
    provider: Annotated[
        ProviderType,
        Field(
            ..., description="Provider type", json_schema_extra={"example": "google"}
        ),
    ]


class ActionResponse(BaseModel):
    """Schema for the response of an action."""

    success: Annotated[
        bool,
        Field(
            ...,
            description="Was the action successful?",
            json_schema_extra={"example": True},
        ),
    ]
    action: Annotated[
        OperationType,
        Field(
            ...,
            description="Operation performed",
            json_schema_extra={"example": "add_member"},
        ),
    ]
    group_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Group ID",
            json_schema_extra={"example": "group-123"},
        ),
    ] = None
    member_email: Annotated[
        Optional[EmailStr],
        Field(
            default=None,
            description="Member email",
            json_schema_extra={"example": "user@example.com"},
        ),
    ] = None
    provider: Annotated[
        Optional[ProviderType],
        Field(
            default=None,
            description="Provider type",
            json_schema_extra={"example": "google"},
        ),
    ] = None
    details: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Provider-specific details",
            json_schema_extra={"example": {"status": "completed"}},
        ),
    ] = None
    timestamp: Annotated[
        datetime,
        Field(
            ...,
            description="Timestamp of action",
            json_schema_extra={"example": "2024-06-01T12:00:00Z"},
        ),
    ]
    correlation_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Unique correlation ID for tracing this request",
            json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
        ),
    ] = None


class MemberResponse(BaseModel):
    """API response model for a group member.

    This is the Pydantic serialization view of NormalizedMember (see models.py).
    Used when returning member information in API responses. Provides validation
    and OpenAPI schema generation.

    Relationship: NormalizedMember → MemberResponse (for API)
    """

    email: Annotated[Optional[EmailStr], Field(default=None)] = None
    id: Annotated[Optional[str], Field(default=None)] = None
    role: Annotated[Optional[str], Field(default=None)] = None
    provider_member_id: Annotated[Optional[str], Field(default=None)] = None
    first_name: Annotated[Optional[str], Field(default=None)] = None
    family_name: Annotated[Optional[str], Field(default=None)] = None
    raw: Annotated[Optional[Dict[str, Any]], Field(default=None)] = None


class GroupResponse(BaseModel):
    """API response model for a group.

    This is the Pydantic serialization view of NormalizedGroup (see models.py).
    Used when returning group information in API responses. Provides validation
    and OpenAPI schema generation.

    Relationship: NormalizedGroup → GroupResponse (for API)
    Contains a list of MemberResponse for group members.
    """

    id: Annotated[Optional[str], Field(default=None)] = None
    name: Annotated[Optional[str], Field(default=None)] = None
    description: Annotated[Optional[str], Field(default=None)] = None
    provider: Annotated[str, Field(...)]
    members: Annotated[List[MemberResponse], Field(default_factory=list)]
    raw: Annotated[Optional[Dict[str, Any]], Field(default=None)] = None


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation response.

    Key distinction from types.OrchestrationResponseTypedDict:
      - This (schemas): API response contract with Pydantic validation
      - types: Internal orchestration contract (TypedDict, no validation)

    Used by API endpoints to return results of bulk operations with a
    summary of successes and failures.
    """

    results: Annotated[
        List[ActionResponse], Field(..., description="List of action responses")
    ]
    summary: Annotated[
        Dict[str, int],
        Field(
            ...,
            description="Summary of results by status",
            json_schema_extra={"example": {"success": 95, "failed": 5}},
        ),
    ]


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    success: Annotated[
        bool,
        Field(
            default=False,
            description="Always false for errors",
            json_schema_extra={"example": False},
        ),
    ] = False
    error_code: Annotated[
        str,
        Field(
            ...,
            description="Error code",
            json_schema_extra={"example": "GROUP_NOT_FOUND"},
        ),
    ]
    error_message: Annotated[
        str,
        Field(
            ...,
            description="Error message",
            json_schema_extra={"example": "Group not found"},
        ),
    ]
    details: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Additional error details",
            json_schema_extra={"example": {"group_id": "group-123"}},
        ),
    ] = None
