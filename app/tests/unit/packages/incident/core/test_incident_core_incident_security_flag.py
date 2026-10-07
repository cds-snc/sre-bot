"""Behavior tests for reading the security flag from the legacy incidents table.

A real boto3 dynamodb client built with static dummy credentials is wrapped in
botocore.stub.Stubber, which validates every request against the service model
and replays canned responses. Error cases use Stubber client errors (or an
EndpointConnectionError patched onto the get_item call) and assert the
classification plus a message free of provider text.
"""

from typing import Any
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from contracts.operations.status import OperationStatus
from integrations.aws.settings import get_aws_settings
from packages.incident.core.adapters import legacy_incidents
from packages.incident.core.adapters.legacy_incidents import LegacyIncidentTableLookup

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
PROVIDER_DETAIL = "provider detail that must not reach callers"


@pytest.fixture(autouse=True)
def _clear_aws_settings_cache():
    """Error classification reads the cached AWS settings; keep them per test."""
    get_aws_settings.cache_clear()
    yield
    get_aws_settings.cache_clear()


@pytest.fixture
def client() -> Any:
    """A real dynamodb client with dummy credentials, for Stubber to wrap."""
    return boto3.client(
        "dynamodb",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


def _get_item_params(incident_id: str) -> dict[str, Any]:
    """Expected params for a get_item call to fetch the security_incident attribute."""
    return {
        "TableName": "incidents",
        "Key": {"id": {"S": incident_id}},
        "ProjectionExpression": "#sec",
        "ExpressionAttributeNames": {"#sec": "security_incident"},
    }


def test_bool_true_returns_yes(client: Any) -> None:
    """A BOOL attribute with value true maps to IncidentSecurityFlag.YES."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response(
            "get_item",
            {"Item": {"security_incident": {"BOOL": True}}},
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert str(result.data) == "yes"


def test_bool_false_returns_no(client: Any) -> None:
    """A BOOL attribute with value false maps to IncidentSecurityFlag.NO."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response(
            "get_item",
            {"Item": {"security_incident": {"BOOL": False}}},
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert str(result.data) == "no"


def test_missing_attribute_returns_unknown(client: Any) -> None:
    """An item without the security_incident attribute maps to UNKNOWN."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response(
            "get_item",
            {"Item": {"id": {"S": INCIDENT_ID}}},
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert str(result.data) == "unknown"


def test_null_attribute_returns_unknown(client: Any) -> None:
    """A NULL attribute maps to UNKNOWN."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response(
            "get_item",
            {"Item": {"security_incident": {"NULL": True}}},
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert str(result.data) == "unknown"


def test_wrong_type_string_returns_unknown(client: Any) -> None:
    """A string (S) attribute instead of BOOL maps to UNKNOWN."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response(
            "get_item",
            {"Item": {"security_incident": {"S": "invalid"}}},
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert str(result.data) == "unknown"


def test_no_item_returns_not_found(client: Any) -> None:
    """When the item does not exist, return NOT_FOUND with NOT_AN_INCIDENT."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response(
            "get_item",
            {},
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == "NOT_AN_INCIDENT"
    assert result.data is None


def test_client_error_is_classified_with_generic_message(client: Any) -> None:
    """A ClientError is classified by code and returns a generic message free of provider text."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_client_error(
            "get_item",
            service_error_code="ThrottlingException",
            service_message=PROVIDER_DETAIL,
            http_status_code=400,
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "ThrottlingException"
    assert PROVIDER_DETAIL not in (result.message or "")


def test_endpoint_connection_error_is_transient(client: Any) -> None:
    """A BotoCoreError is classified as transient with a generic message."""
    lookup = LegacyIncidentTableLookup(client)
    endpoint_error = EndpointConnectionError(endpoint_url="https://dynamodb.ca-central-1.amazonaws.com")

    with Stubber(client) as stub, patch.object(client, "get_item", side_effect=endpoint_error):
        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "EndpointConnectionError"
    assert PROVIDER_DETAIL not in (result.message or "")


def test_missing_table_is_permanent_error(client: Any) -> None:
    """A ResourceNotFoundException (missing table) is PERMANENT_ERROR, never NOT_FOUND."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_client_error(
            "get_item",
            service_error_code="ResourceNotFoundException",
            service_message=PROVIDER_DETAIL,
            http_status_code=400,
            expected_params=_get_item_params(INCIDENT_ID),
        )

        result = lookup.read_security_flag(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "ResourceNotFoundException"


def test_blank_incident_id_returns_not_found_without_call(client: Any) -> None:
    """A blank incident id is refused without making a get_item call."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        result = lookup.read_security_flag("")

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == "NOT_AN_INCIDENT"


def test_builder_makes_one_in_account_dynamodb_client_at_call_time(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    """The builder asks the outbound AWS client factory for a standard-retry dynamodb client, with no role."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def record_get_aws_client(service_name: str, **kwargs: Any) -> Any:
        calls.append((service_name, kwargs))
        return client

    monkeypatch.setattr(legacy_incidents, "get_aws_client", record_get_aws_client)

    lookup = legacy_incidents.build_legacy_incident_security_reader()

    assert isinstance(lookup, LegacyIncidentTableLookup)
    assert calls == [("dynamodb", {"role_arn": None})]
