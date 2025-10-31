from modules.groups import service, schemas
import pytest


def test_add_member_invalid_group_id_raises():
    req = schemas.AddMemberRequest(
        group_id="bad",
        member_email="u@example.com",
        provider=schemas.ProviderType.AWS,
    )

    with pytest.raises(ValueError):
        service.add_member(req)


def test_remove_member_invalid_group_id_raises():
    req = schemas.RemoveMemberRequest(
        group_id="bad",
        member_email="u@example.com",
        provider=schemas.ProviderType.AWS,
    )

    with pytest.raises(ValueError):
        service.remove_member(req)
