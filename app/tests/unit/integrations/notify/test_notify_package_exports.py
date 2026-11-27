"""The GC Notify vendor package exports only its client factory, its classifier and its settings.

Read from the package's ``__all__`` and attributes: no business operation and no request helper
remain in ``integrations.notify`` (decisions/outbound-clients.md). That importing the package and
its legacy caller builds no settings is pinned by
tests/unit/server/test_server_app_import_vendor_settings_lazy.py.
"""

import pytest

from integrations import notify
from integrations.notify import client

pytestmark = pytest.mark.unit


def test_the_package_exports_the_factory_the_classifier_and_the_settings() -> None:
    assert sorted(notify.__all__) == [
        "NotifySettings",
        "NotifyTenant",
        "build_notify_client",
        "classify_notify_error",
        "get_notify_settings",
    ]


@pytest.mark.parametrize(
    "name",
    ["revoke_api_key", "post_event", "create_authorization_header", "create_jwt_token", "epoch_seconds"],
)
def test_no_business_operation_or_request_helper_remains(name: str) -> None:
    assert not hasattr(notify, name)
    assert not hasattr(client, name)
