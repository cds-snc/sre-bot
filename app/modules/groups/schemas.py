from typing import Any, Dict, List, Optional, Annotated
from datetime import datetime
from enum import Enum
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    model_validator,
)


class ProviderType(str, Enum):
    """Schema for provider types."""

    GOOGLE = "google"
    OKTA = "okta"
    AZURE = "azure"
    AWS = "aws"
    SLACK = "slack"


class OperationType(str, Enum):
    """Schema for operation types."""

    ADD_MEMBER = "add_member"
    REMOVE_MEMBER = "remove_member"


class PermissionAction(str, Enum):
    """Schema for permission actions."""

    VIEW = "view"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"


class AddMemberRequest(BaseModel):
    """Schema for adding a member to a group."""

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
        Optional[str],
        Field(
            default=None,
            max_length=500,
            description="Justification for adding member",
            json_schema_extra={"example": "Access required for project X"},
        ),
    ] = None
    requestor: Annotated[
        Optional[EmailStr],
        Field(
            default=None,
            description="Email of requestor",
            json_schema_extra={"example": "admin@example.com"},
        ),
    ] = None
    metadata: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Additional metadata",
            json_schema_extra={"example": {"ticket_id": "JIRA-123"}},
        ),
    ] = None


class RemoveMemberRequest(BaseModel):
    """Schema for removing a member from a group."""

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
        Optional[str],
        Field(
            default=None,
            max_length=500,
            description="Justification for removing member",
            json_schema_extra={"example": "No longer needed"},
        ),
    ] = None
    requestor: Annotated[
        Optional[EmailStr],
        Field(
            default=None,
            description="Email of requestor",
            json_schema_extra={"example": "admin@example.com"},
        ),
    ] = None
    metadata: Annotated[
        Optional[Dict[str, Any]],
        Field(
            default=None,
            description="Additional metadata",
            json_schema_extra={"example": {"ticket_id": "JIRA-456"}},
        ),
    ] = None


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
    """Schema for listing groups."""

    user_email: Annotated[
        EmailStr,
        Field(
            ...,
            description="User email",
            json_schema_extra={"example": "user@example.com"},
        ),
    ]
    provider: Annotated[
        Optional[ProviderType],
        Field(
            default=None,
            description="Provider type",
            json_schema_extra={"example": "google"},
        ),
    ] = None


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


class MemberResponse(BaseModel):
    """Pydantic representation of a normalized group member for API responses."""

    email: Annotated[Optional[EmailStr], Field(default=None)] = None
    id: Annotated[Optional[str], Field(default=None)] = None
    role: Annotated[Optional[str], Field(default=None)] = None
    provider_member_id: Annotated[Optional[str], Field(default=None)] = None
    first_name: Annotated[Optional[str], Field(default=None)] = None
    family_name: Annotated[Optional[str], Field(default=None)] = None
    raw: Annotated[Optional[Dict[str, Any]], Field(default=None)] = None


class GroupResponse(BaseModel):
    """Pydantic representation of a normalized group for API responses."""

    id: Annotated[Optional[str], Field(default=None)] = None
    name: Annotated[Optional[str], Field(default=None)] = None
    description: Annotated[Optional[str], Field(default=None)] = None
    provider: Annotated[str, Field(...)]
    members: Annotated[List[MemberResponse], Field(default_factory=list)]
    raw: Annotated[Optional[Dict[str, Any]], Field(default=None)] = None


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation response."""

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
