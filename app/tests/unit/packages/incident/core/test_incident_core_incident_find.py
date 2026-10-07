"""Behavior tests for the interim incident lookup over the legacy incidents table.

A real boto3 dynamodb client built with static dummy credentials is wrapped in
botocore.stub.Stubber, which validates every request against the service model
and replays canned scan pages. Two-page cases chain the pages through
LastEvaluatedKey and ExclusiveStartKey, which proves that the lookup reads
past the first page. Error cases use Stubber client errors (or an
EndpointConnectionError patched onto the scan call) and assert the
classification plus a message free of provider text.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from contracts.operations.status import OperationStatus
from integrations.aws.settings import get_aws_settings
from packages.incident.core.adapters import legacy_incidents
from packages.incident.core.adapters.legacy_incidents import LegacyIncidentTableLookup

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
OTHER_INCIDENT_ID = "1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9"
PROVIDER_DETAIL = "provider detail that must not reach callers"

FIRST_PAGE_PARAMS: dict[str, Any] = {
    "TableName": "incidents",
    "FilterExpression": "channel_id = :channel_id",
    "ExpressionAttributeValues": {":channel_id": {"S": CHANNEL_ID}},
    "ProjectionExpression": "#id",
    "ExpressionAttributeNames": {"#id": "id"},
}
PAGE_ONE_END = {"id": {"S": "a-scanned-incident"}}
SECOND_PAGE_PARAMS: dict[str, Any] = {**FIRST_PAGE_PARAMS, "ExclusiveStartKey": PAGE_ONE_END}


@pytest.fixture(autouse=True)
def _clear_aws_settings_cache() -> Iterator[None]:
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


def _items(*incident_ids: str) -> list[dict[str, Any]]:
    return [{"id": {"S": incident_id}} for incident_id in incident_ids]


def _add_two_pages(stub: Stubber, first: list[dict[str, Any]], second: list[dict[str, Any]]) -> None:
    stub.add_response("scan", {"Items": first, "LastEvaluatedKey": PAGE_ONE_END}, expected_params=FIRST_PAGE_PARAMS)
    stub.add_response("scan", {"Items": second}, expected_params=SECOND_PAGE_PARAMS)


def test_match_on_the_second_page_returns_the_incident_uuid(client: Any) -> None:
    """The first page matches nothing; the incident is found only by reading on with the page-one key."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        _add_two_pages(stub, first=[], second=_items(INCIDENT_ID))

        result = lookup.find_incident_for_conversation(CHANNEL_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == INCIDENT_ID


def test_no_match_across_two_pages_is_a_not_an_incident_refusal(client: Any) -> None:
    """Both pages are read and neither names the channel, so the refusal is NOT_FOUND with NOT_AN_INCIDENT."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        _add_two_pages(stub, first=[], second=[])

        result = lookup.find_incident_for_conversation(CHANNEL_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == "NOT_AN_INCIDENT"
    assert result.data is None


def test_a_match_on_each_page_is_refused_as_ambiguous(client: Any) -> None:
    """The scan does not stop at the first match: a second incident on page two makes the channel ambiguous."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        _add_two_pages(stub, first=_items(INCIDENT_ID), second=_items(OTHER_INCIDENT_ID))

        result = lookup.find_incident_for_conversation(CHANNEL_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "AMBIGUOUS_INCIDENT_CONVERSATION"
    assert result.data is None


@pytest.mark.parametrize("conversation_id", ["", "   "])
def test_a_blank_conversation_id_is_refused_without_a_scan(client: Any, conversation_id: str) -> None:
    """A blank id names no conversation; Stubber has no queued response, so any scan would fail the test."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        result = lookup.find_incident_for_conversation(conversation_id)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == "NOT_AN_INCIDENT"


def test_throttling_on_the_second_page_is_transient_with_a_retry_hint(client: Any) -> None:
    """A failure partway through the pages discards the partial read and reports a retryable error."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_response("scan", {"Items": [], "LastEvaluatedKey": PAGE_ONE_END}, expected_params=FIRST_PAGE_PARAMS)
        stub.add_client_error(
            "scan",
            service_error_code="ThrottlingException",
            service_message=PROVIDER_DETAIL,
            http_status_code=400,
            expected_params=SECOND_PAGE_PARAMS,
        )

        result = lookup.find_incident_for_conversation(CHANNEL_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "ThrottlingException"
    assert result.retry_after == get_aws_settings().TRANSIENT_RETRY_AFTER_SECONDS
    assert PROVIDER_DETAIL not in (result.message or "")


@pytest.mark.parametrize(
    ("error_code", "expected_status"),
    [
        # A missing table is a broken store, never "this channel is not an incident".
        ("ResourceNotFoundException", OperationStatus.PERMANENT_ERROR),
        ("AccessDeniedException", OperationStatus.UNAUTHORIZED),
    ],
)
def test_store_errors_keep_not_found_for_the_refusal_only(client: Any, error_code: str, expected_status: OperationStatus) -> None:
    """Store failures carry the botocore code and a generic message; NOT_FOUND stays reserved for not-an-incident."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_client_error(
            "scan",
            service_error_code=error_code,
            service_message=PROVIDER_DETAIL,
            http_status_code=400,
            expected_params=FIRST_PAGE_PARAMS,
        )

        result = lookup.find_incident_for_conversation(CHANNEL_ID)

        stub.assert_no_pending_responses()

    assert result.status is expected_status
    assert result.error_code == error_code
    assert PROVIDER_DETAIL not in (result.message or "")


def test_a_connection_failure_is_transient(client: Any) -> None:
    """A BotoCoreError never reaches the caller as an exception; it is a retryable error result."""
    lookup = LegacyIncidentTableLookup(client)
    endpoint_error = EndpointConnectionError(endpoint_url="https://dynamodb.ca-central-1.amazonaws.com")

    with Stubber(client) as stub, patch.object(client, "scan", side_effect=endpoint_error):
        result = lookup.find_incident_for_conversation(CHANNEL_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "EndpointConnectionError"


def test_an_unclassified_client_error_propagates(client: Any) -> None:
    """A malformed request is a programmer error, so it is raised rather than disguised as a store outage."""
    lookup = LegacyIncidentTableLookup(client)

    with Stubber(client) as stub:
        stub.add_client_error("scan", service_error_code="ValidationException", http_status_code=400)

        with pytest.raises(ClientError):
            lookup.find_incident_for_conversation(CHANNEL_ID)


def test_builder_makes_one_in_account_dynamodb_client_at_call_time(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    """The builder asks the outbound AWS client factory for a standard-retry dynamodb client, with no role."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def record_get_aws_client(service_name: str, **kwargs: Any) -> Any:
        calls.append((service_name, kwargs))
        return client

    monkeypatch.setattr(legacy_incidents, "get_aws_client", record_get_aws_client)

    lookup = legacy_incidents.build_legacy_incident_lookup()

    assert isinstance(lookup, LegacyIncidentTableLookup)
    assert calls == [("dynamodb", {"role_arn": None})]
