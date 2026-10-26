"""Unit tests for the access-request fallback approver slug requirement.

The requests settings are built only by the access.request plugin's provider,
which a disabled plugin never imports, so the slug is required unconditionally
on that class while the sync and config settings build without it. The
access-root conftest strips every ``ACCESS_*`` variable and the ``.env`` file.
"""

import pytest
from pydantic import ValidationError

from packages.access.common.settings import (
    AccessConfigSettings,
    AccessRequestsSettings,
    AccessSyncSettings,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", [None, "", "   "])
def test_requests_settings_without_a_slug_fail_naming_the_key(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """A missing, blank or whitespace slug fails with the env name in the message."""
    if value is not None:
        monkeypatch.setenv("ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG", value)

    with pytest.raises(ValidationError, match="ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG"):
        AccessRequestsSettings()


def test_requests_settings_with_a_slug_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured slug satisfies the requirement and keeps the other defaults."""
    monkeypatch.setenv("ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG", "sg-org-admins")

    s = AccessRequestsSettings()

    assert s.fallback_approver_slug == "sg-org-admins"
    assert s.min_approver_count == 1
    assert s.request_ttl_hours == 72
    assert s.table_name == "sre_bot_access_requests"


def test_sync_only_deployment_builds_without_a_slug() -> None:
    """The sync and config settings never validate the requests slug."""
    AccessSyncSettings()
    AccessConfigSettings()
