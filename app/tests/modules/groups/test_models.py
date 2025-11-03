"""Legacy tests for groups module data models.

These tests have been migrated to tests/unit/modules/groups/test_models.py
but are retained here for verification during the transition period.
"""

from modules.groups.models import (
    member_from_dict,
    group_from_dict,
    as_canonical_dict,
)

import pytest


@pytest.mark.legacy
def test_normalized_member_from_dict_and_to_canonical():
    data = {
        "email": "user@example.com",
        "displayName": "User Example",
        "joined_at": "2024-01-01T12:00:00Z",
    }

    member = member_from_dict(data, "google")
    assert member.email == "user@example.com"
    assert member.first_name == "User"
    assert member.family_name == "Example"

    canon = as_canonical_dict(member)
    assert canon["email"] == "user@example.com"
    assert canon["first_name"] == "User"


@pytest.mark.legacy
def test_normalized_group_from_dict_and_as_canonical():
    data = {
        "id": "group-123",
        "name": "Engineering Team",
        "description": "All engineers",
        "members": [
            {"email": "a@example.com", "display_name": "A"},
            {"email": "b@example.com", "display_name": "B"},
        ],
        "created_at": "2023-06-01T00:00:00Z",
    }

    group = group_from_dict(data, "google")
    assert group.id == "group-123"
    assert group.name == "Engineering Team"
    assert len(group.members) == 2

    canon = as_canonical_dict(group)
    assert canon["id"] == "group-123"
    assert canon["name"] == "Engineering Team"
    assert isinstance(canon.get("members"), list)


@pytest.mark.legacy
def test_group_member_helpers_roundtrip():
    # Ensure helpers that convert between representations work as expected
    member = member_from_dict(
        {"email": "round@example.com", "displayName": "Round Tester"}, "google"
    )
    d = as_canonical_dict(member)
    m2 = member_from_dict(d, "google")
    assert m2.email == member.email
    assert m2.first_name in ("Round", None)


@pytest.mark.legacy
def test_member_from_dict_extracts_names_from_simple_payload():
    payload = {
        "email": "alice@example.com",
        "id": "user-123",
        "role": "MEMBER",
        "Name": {"GivenName": "Alice", "FamilyName": "Anderson"},
    }
    m = member_from_dict(payload, "aws")
    assert m.email == "alice@example.com"
    assert m.id == "user-123"
    assert m.first_name == "Alice"
    assert m.family_name == "Anderson"
    d = as_canonical_dict(m)
    assert isinstance(d, dict)
    assert d["first_name"] == "Alice"


@pytest.mark.legacy
def test_member_from_dict_fallback_display_name_split():
    payload = {
        "primaryEmail": "bob@example.com",
        "UserName": "bob",
        "displayName": "Bob Builder",
    }
    m = member_from_dict(payload, "google")
    assert m.email == "bob@example.com"
    assert m.first_name == "Bob"
    assert m.family_name == "Builder"


@pytest.mark.legacy
def test_member_from_dict_handles_missing_fields():
    payload = {"something": "else"}
    m = member_from_dict(payload, "aws")
    assert m.email is None
    assert m.id is None
    assert m.first_name is None
    assert m.family_name is None
    d = as_canonical_dict(m)
    assert isinstance(d, dict)
