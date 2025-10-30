from modules.groups.schemas import member_from_dict, as_canonical_dict


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


def test_member_from_dict_handles_missing_fields():
    payload = {"something": "else"}
    m = member_from_dict(payload, "aws")
    assert m.email is None
    assert m.id is None
    assert m.first_name is None
    assert m.family_name is None
    d = as_canonical_dict(m)
    assert isinstance(d, dict)
