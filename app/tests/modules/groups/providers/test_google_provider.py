import types


def _make_resp(success: bool, data=None, error=None):
    return types.SimpleNamespace(success=success, data=data, error=error)


def test_get_user_managed_groups_success(monkeypatch):
    from modules.groups.providers import get_provider

    sample_groups = [{"id": "group1@example.com", "name": "Eng", "members": []}]

    monkeypatch.setattr(
        "integrations.google_workspace.google_directory_next.list_groups",
        lambda **kwargs: _make_resp(True, data=sample_groups),
    )

    provider = get_provider("google")
    result = provider.get_user_managed_groups("alice@example.com")
    assert isinstance(result, list)
    assert result and result[0]["id"] == "group1@example.com"


def test_get_user_managed_groups_failure(monkeypatch):
    from modules.groups.providers import get_provider
    from modules.groups.errors import IntegrationError

    monkeypatch.setattr(
        "integrations.google_workspace.google_directory_next.list_groups",
        lambda **kwargs: _make_resp(False, data=None, error={"msg": "fail"}),
    )

    try:
        provider = get_provider("google")
        _ = provider.get_user_managed_groups("bob@example.com")
        assert False, "Expected IntegrationError"
    except IntegrationError as e:
        assert hasattr(e, "response")
        assert e.response.success is False
        assert e.response.success is False
