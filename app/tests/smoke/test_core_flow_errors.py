import types

from modules.groups import service, schemas
from modules.groups.errors import IntegrationError


class FakeProvider:
    def __init__(self, raise_on_get=False, raise_on_add=False):
        self.raise_on_get = raise_on_get
        self.raise_on_add = raise_on_add
        self.raise_on_remove = False

    def get_user_managed_groups(self, user_email):
        if self.raise_on_get:
            raise IntegrationError(
                "downstream failure",
                response=types.SimpleNamespace(success=False, error="boom", meta={}),
            )
        return [{"id": "g-1", "name": "group1"}]

    def validate_permissions(self, user_email, group_id, action):
        return True

    def add_member(self, group_id, member_email, justification):
        if self.raise_on_add:
            raise IntegrationError(
                "add member failed",
                response=types.SimpleNamespace(
                    success=False, error="add-failed", meta={}
                ),
            )
        return {"member": member_email, "status": "added"}

    def remove_member(self, group_id, member_email, justification):
        if self.raise_on_remove:
            raise IntegrationError(
                "remove member failed",
                response=types.SimpleNamespace(
                    success=False, error="remove-failed", meta={}
                ),
            )
        return {"member": member_email, "status": "removed"}


def test_list_user_groups_integration_error(monkeypatch):
    fake_provider = FakeProvider(raise_on_get=True)

    # Patch the provider registry getter used by the base module to return our fake provider
    monkeypatch.setattr(
        "modules.groups.providers.get_active_providers",
        lambda provider_type=None: {"fake": fake_provider},
    )

    # Patch orchestration's get_primary_provider/get_primary_provider_name
    # (they were imported at module import time) so orchestration will use
    # our fake provider without requiring activate_providers().
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider", lambda: fake_provider
    )
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider_name", lambda: "fake"
    )

    # Call service list_groups which should surface provider errors as an empty
    # provider result for failing providers but still return a list.
    req = schemas.ListGroupsRequest(user_email="alice@example.com")
    res = service.list_groups(req)

    assert isinstance(res, list)


def test_add_member_integration_error(monkeypatch):
    fake_provider = FakeProvider(raise_on_add=True)

    monkeypatch.setattr(
        "modules.groups.providers.get_active_providers",
        lambda provider_type=None: {"aws": fake_provider},
    )

    # Ensure orchestration uses our fake provider functions
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider", lambda: fake_provider
    )
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider_name", lambda: "aws"
    )

    payload = {
        # valid-ish AWS group identifier (ARN-ish) so validation passes
        "group_id": "arn:aws:iam::123456789012:group/my-group",
        "member_email": "bob@example.com",
        "requestor_email": "admin@example.com",
        "provider_type": "aws",
        "justification": "test justification",
    }

    add_req = schemas.AddMemberRequest(
        group_id=payload["group_id"],
        member_email=payload["member_email"],
        provider=schemas.ProviderType(payload["provider_type"]),
        justification=payload.get("justification"),
        requestor=payload.get("requestor_email"),
    )

    res = service.add_member(add_req)

    # Service returns a Pydantic ActionResponse model; when integration fails
    # it should set success to False and include orchestration details.
    assert hasattr(res, "success")
    assert res.success is False
    assert isinstance(res.details, dict)


def test_remove_member_integration_error(monkeypatch):
    fake_provider = FakeProvider()
    fake_provider.raise_on_remove = True

    monkeypatch.setattr(
        "modules.groups.providers.get_active_providers",
        lambda provider_type=None: {"aws": fake_provider},
    )

    # Ensure orchestration uses our fake provider functions
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider", lambda: fake_provider
    )
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider_name", lambda: "aws"
    )

    payload = {
        # valid-ish AWS group identifier (ARN-ish) so validation passes
        "group_id": "arn:aws:iam::123456789012:group/my-group",
        "member_email": "charlie@example.com",
        "requestor_email": "admin@example.com",
        "provider_type": "aws",
        "justification": "removal test",
    }

    remove_req = schemas.RemoveMemberRequest(
        group_id=payload["group_id"],
        member_email=payload["member_email"],
        provider=schemas.ProviderType(payload["provider_type"]),
        justification=payload.get("justification"),
        requestor=payload.get("requestor_email"),
    )

    res = service.remove_member(remove_req)

    assert hasattr(res, "success")
    assert res.success is False
    assert isinstance(res.details, dict)
