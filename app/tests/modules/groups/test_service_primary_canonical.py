from modules.groups import service, mappings


def test_primary_group_to_canonical_delegates(monkeypatch):
    called = {}

    def fake_primary_to_canonical(name, prefixes=None):
        called["name"] = name
        called["prefixes"] = prefixes
        return "canonical-name"

    monkeypatch.setattr(
        mappings, "primary_group_to_canonical", fake_primary_to_canonical
    )

    res = service.primary_group_to_canonical("aws-my-service", prefixes=["aws"])

    assert res == "canonical-name"
    assert called["name"] == "aws-my-service"
    assert called["prefixes"] == ["aws"]
