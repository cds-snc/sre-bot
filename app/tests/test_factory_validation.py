from integrations.google_workspace.schemas import GroupsResult, User, Member
from tests.factories.google import (
    make_google_groups,
    make_google_users,
    make_google_members,
)


def test_helpers_produce_valid_groups_and_users_and_members():
    # create dict outputs
    groups = make_google_groups(n=2, prefix="svc-", domain="example.com")
    users = make_google_users(n=2, prefix="svc-", domain="example.com")
    members = make_google_members(n=2, prefix="svc-", domain="example.com")

    # Validate GroupsResult wrapper
    sample = {"result": groups, "time": 0.1, "summary": "test"}
    parsed = GroupsResult.model_validate(sample)
    assert len(parsed.result) == 2

    # Validate individual user and member shapes
    u = User.model_validate(users[0])
    assert u.id is not None

    m = Member.model_validate(members[0])
    assert m.id is not None
