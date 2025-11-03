import pytest
from pydantic import ValidationError

from modules.groups import schemas
from datetime import datetime


@pytest.mark.legacy
def test_add_member_request_valid():
    req = schemas.AddMemberRequest(
        group_id="group-123",
        member_email="user@example.com",
        provider=schemas.ProviderType.GOOGLE,
        justification="Needed for project X",
        requestor="admin@example.com",
    )
    assert req.group_id == "group-123"
    assert req.member_email == "user@example.com"
    assert req.provider == schemas.ProviderType.GOOGLE


@pytest.mark.legacy
def test_add_member_request_invalid_email():
    with pytest.raises(ValidationError):
        schemas.AddMemberRequest(
            group_id="group-123",
            member_email="not-an-email",
            provider=schemas.ProviderType.GOOGLE,
        )


@pytest.mark.legacy
def test_remove_member_request_max_justification_length():
    long_just = "a" * 501
    with pytest.raises(ValidationError):
        schemas.RemoveMemberRequest(
            group_id="group-1",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification=long_just,
        )


@pytest.mark.legacy
def test_operation_item_validates_payload():
    op_item = schemas.OperationItem(
        operation=schemas.OperationType.ADD_MEMBER,
        payload={
            "group_id": "g1",
            "member_email": "u@example.com",
            "provider": "google",
        },
    )
    assert op_item.operation == schemas.OperationType.ADD_MEMBER

    # Invalid payload for operation should raise
    with pytest.raises(ValidationError):
        schemas.OperationItem(
            operation=schemas.OperationType.ADD_MEMBER,
            payload={"invalid": "payload"},
        )


@pytest.mark.legacy
def test_action_response_timestamp_type():
    ts = datetime.utcnow()
    resp = schemas.ActionResponse(
        success=True,
        action=schemas.OperationType.ADD_MEMBER,
        timestamp=ts,
    )
    assert isinstance(resp.timestamp, datetime)
