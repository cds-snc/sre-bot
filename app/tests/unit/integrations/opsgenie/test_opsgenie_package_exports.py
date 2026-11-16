"""The Opsgenie vendor package exports only its client factory, its classifier and its settings.

Read from the package's ``__all__`` and attributes: no business operation and no write helper
remain in ``integrations.opsgenie`` (decisions/outbound-clients.md).
"""

import pytest

from integrations import opsgenie
from integrations.opsgenie import client

pytestmark = pytest.mark.unit


def test_the_package_exports_the_factory_the_classifier_and_the_settings() -> None:
    assert sorted(opsgenie.__all__) == [
        "OpsGenieSettings",
        "OpsGenieTenant",
        "build_opsgenie_client",
        "classify_opsgenie_error",
        "get_opsgenie_settings",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "get_on_call_users",
        "get_on_call_user_for_rotation",
        "healthcheck",
        "api_get_request",
        "OpsGenieAPIError",
        "create_alert",
        "api_post_request",
    ],
)
def test_no_business_operation_or_write_helper_remains(name: str) -> None:
    assert not hasattr(opsgenie, name)
    assert not hasattr(client, name)
