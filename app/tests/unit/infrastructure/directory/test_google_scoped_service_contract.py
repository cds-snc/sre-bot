"""Unit tests for GoogleDirectoryProvider scoped service usage.

These tests lock the provider contract to per-operation least-privilege
Google Admin SDK scope requests while preserving canonical payload mapping.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from infrastructure.directory.google import GoogleDirectoryProvider


def _request(payload: Any) -> MagicMock:
    request = MagicMock()
    request.execute.return_value = payload
    return request


def _build_service_stub() -> MagicMock:
    service = MagicMock()

    users = MagicMock()
    users.get.return_value = _request(
        {
            "primaryEmail": "user@example.com",
            "id": "user-1",
            "name": {"fullName": "User Example"},
        }
    )
    users.list.return_value = _request({"users": []})
    users.list_next.return_value = None

    groups = MagicMock()
    groups.get.return_value = _request(
        {
            "email": "sg-admin@example.com",
            "id": "group-1",
            "name": "Admins",
        }
    )
    groups.list.return_value = _request({"groups": []})
    groups.list_next.return_value = None

    members = MagicMock()
    members.list.return_value = _request({"members": []})
    members.list_next.return_value = None
    members.insert.return_value = _request(
        {
            "email": "user@example.com",
            "id": "member-1",
            "role": "MEMBER",
            "type": "USER",
        }
    )
    members.delete.return_value = _request({})
    members.hasMember.return_value = _request({"isMember": True})

    customers = MagicMock()
    customers.get.return_value = _request({"id": "customer-1"})

    service.users.return_value = users
    service.groups.return_value = groups
    service.members.return_value = members
    service.customers.return_value = customers
    return service


def _invoke_operation(provider: GoogleDirectoryProvider, operation: str) -> None:
    if operation == "warmup":
        provider.warmup()
        return
    if operation == "get_user":
        provider.get_user("user@example.com")
        return
    if operation == "list_users":
        provider.list_users(limit=10)
        return
    if operation == "get_group_members":
        provider.get_group_members("sg-admin@example.com")
        return
    if operation == "get_group":
        provider.get_group("sg-admin@example.com")
        return
    if operation == "add_group_member":
        provider.add_group_member("sg-admin@example.com", "user@example.com")
        return
    if operation == "remove_group_member":
        provider.remove_group_member("sg-admin@example.com", "user@example.com")
        return
    if operation == "check_membership":
        provider.check_membership("sg-admin@example.com", "user@example.com")
        return
    if operation == "list_groups":
        provider.list_groups("name:Admins")
        return
    if operation == "get_user_groups":
        provider.get_user_groups("user@example.com")
        return
    raise AssertionError(f"Unsupported operation in test matrix: {operation}")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("operation", "expected_scopes"),
    [
        ("warmup", ["https://www.googleapis.com/auth/admin.directory.customer.readonly"]),
        ("get_user", ["https://www.googleapis.com/auth/admin.directory.user.readonly"]),
        ("list_users", ["https://www.googleapis.com/auth/admin.directory.user.readonly"]),
        ("get_group_members", ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]),
        ("get_group", ["https://www.googleapis.com/auth/admin.directory.group.readonly"]),
        ("add_group_member", ["https://www.googleapis.com/auth/admin.directory.group.member"]),
        ("remove_group_member", ["https://www.googleapis.com/auth/admin.directory.group.member"]),
        ("check_membership", ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]),
        ("list_groups", ["https://www.googleapis.com/auth/admin.directory.group.readonly"]),
        ("get_user_groups", ["https://www.googleapis.com/auth/admin.directory.group.readonly"]),
    ],
)
def test_provider_requests_narrow_scopes_per_operation(
    operation: str,
    expected_scopes: list[str],
) -> None:
    service = _build_service_stub()
    observed_scopes: list[list[str]] = []

    def get_service(scopes: list[str]) -> Any:
        observed_scopes.append(scopes)
        return service

    settings = MagicMock()
    settings.managed_group_domain = "example.com"
    settings.managed_group_prefix = "sg-"
    settings.enforce_managed_group_email = True

    provider = GoogleDirectoryProvider(
        get_service=get_service,
        directory_settings=settings,
        customer_id="my_customer",
    )

    _invoke_operation(provider, operation)

    assert observed_scopes == [expected_scopes]
