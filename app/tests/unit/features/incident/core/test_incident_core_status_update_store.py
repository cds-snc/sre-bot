"""Behavior tests for the DynamoDB StatusUpdateStore adapter.

A real boto3 dynamodb client built with static dummy credentials is wrapped in
botocore.stub.Stubber, which validates every request against the service model
and pins the exact parameters: the table, the keys, the write conditions and
the newest-first query. Condition failures are stubbed with the old item that
ReturnValuesOnConditionCheckFailure=ALL_OLD returns, which is how the adapter
tells an SDK retry of its own write from a real conflict. Error cases assert
the classification plus a message free of provider text.
"""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from contracts.operations.status import OperationStatus
from features.incident.core.adapters import status_updates
from features.incident.core.adapters.status_updates import DynamoDbStatusUpdateStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)
from integrations.aws.settings import get_aws_settings

pytestmark = pytest.mark.unit

TABLE = "sre_bot_incident_status_updates"
INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
PK = f"INCIDENT#{INCIDENT_ID}"
PROVIDER_DETAIL = "provider detail that must not reach callers"
AT = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 7, 14, 20, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 10, 7, 14, 40, tzinfo=UTC)

EN = StatusUpdateText(
    affected_service="GC Notify", impact="Emails are delayed.", current_action="Restarting workers.", workaround=""
)
FR = StatusUpdateText(
    affected_service="Notification GC",
    impact="Les courriels sont retardés.",
    current_action="Redémarrage des processus.",
    workaround="",
)

DRAFT = StatusUpdate(
    incident_id=INCIDENT_ID,
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=EN,
    fr=FR,
    next_update_at=datetime(2026, 10, 7, 14, 30, tzinfo=UTC),
    author="U0AUTHOR",
    transcript_cutoff=datetime(2026, 10, 7, 13, 58, tzinfo=UTC),
    transcript_fingerprint="fp-1",
    created_at=AT,
)
APPROVED = StatusUpdate(
    incident_id=INCIDENT_ID,
    sequence=1,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    en=StatusUpdateText(affected_service="GC Notify", impact="Emails are delayed.", current_action="Edited.", workaround=""),
    fr=FR,
    next_update_at=datetime(2026, 10, 7, 14, 30, tzinfo=UTC),
    author="U0AUTHOR",
    transcript_cutoff=datetime(2026, 10, 7, 13, 58, tzinfo=UTC),
    transcript_fingerprint="fp-1",
    created_at=AT,
    approver="U0APPROVER",
    approved_at=LATER,
)


def _published(published_by: str | None = "U0PUBLISHER") -> StatusUpdate:
    """The approved record marked published at PUBLISHED_AT by ``published_by``."""
    return replace(APPROVED, state=StatusUpdateState.PUBLISHED, published_at=PUBLISHED_AT, published_by=published_by)


def _text_item(text: StatusUpdateText) -> dict[str, Any]:
    return {
        "M": {
            "affected_service": {"S": text.affected_service},
            "impact": {"S": text.impact},
            "current_action": {"S": text.current_action},
            "workaround": {"S": text.workaround},
        }
    }


DRAFT_ITEM: dict[str, Any] = {
    "PK": {"S": PK},
    "SK": {"S": "UPDATE#000001"},
    "incident_id": {"S": INCIDENT_ID},
    "sequence": {"N": "1"},
    "state": {"S": "draft"},
    "stage": {"S": "investigating"},
    "en": _text_item(EN),
    "fr": _text_item(FR),
    "next_update_at": {"S": "2026-10-07T14:30:00+00:00"},
    "author": {"S": "U0AUTHOR"},
    "transcript_cutoff": {"S": "2026-10-07T13:58:00+00:00"},
    "transcript_fingerprint": {"S": "fp-1"},
    "created_at": {"S": "2026-10-07T14:00:00+00:00"},
}
APPROVED_ITEM: dict[str, Any] = {
    **DRAFT_ITEM,
    "state": {"S": "approved"},
    "stage": {"S": "identified"},
    "en": _text_item(APPROVED.en),
    "approver": {"S": "U0APPROVER"},
    "approved_at": {"S": "2026-10-07T14:20:00+00:00"},
}
PUBLISHED_ITEM: dict[str, Any] = {
    **APPROVED_ITEM,
    "state": {"S": "published"},
    "published_at": {"S": "2026-10-07T14:40:00+00:00"},
    "published_by": {"S": "U0PUBLISHER"},
}
SECOND_ITEM: dict[str, Any] = {**DRAFT_ITEM, "SK": {"S": "UPDATE#000002"}, "sequence": {"N": "2"}}

APPEND_PARAMS: dict[str, Any] = {
    "TableName": TABLE,
    "Item": DRAFT_ITEM,
    "ConditionExpression": "attribute_not_exists(SK)",
    "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
}
TRANSITION_PARAMS: dict[str, Any] = {
    "TableName": TABLE,
    "Item": APPROVED_ITEM,
    "ConditionExpression": "attribute_exists(SK) AND #state = :expected",
    "ExpressionAttributeNames": {"#state": "state"},
    "ExpressionAttributeValues": {":expected": {"S": "draft"}},
    "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
}
PUBLISH_PARAMS: dict[str, Any] = {
    **TRANSITION_PARAMS,
    "Item": PUBLISHED_ITEM,
    "ExpressionAttributeValues": {":expected": {"S": "approved"}},
}
UNPUBLISH_PARAMS: dict[str, Any] = {
    **TRANSITION_PARAMS,
    "Item": APPROVED_ITEM,
    "ExpressionAttributeValues": {":expected": {"S": "published"}},
}
QUERY_PARAMS: dict[str, Any] = {
    "TableName": TABLE,
    "KeyConditionExpression": "PK = :pk AND begins_with(SK, :prefix)",
    "ExpressionAttributeValues": {":pk": {"S": PK}, ":prefix": {"S": "UPDATE#"}},
    "ScanIndexForward": False,
}
LATEST_PARAMS: dict[str, Any] = {**QUERY_PARAMS, "Limit": 1}
PAGE_ONE_END = {"PK": {"S": PK}, "SK": {"S": "UPDATE#000002"}}


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


def _condition_failed(stub: Stubber, expected_params: dict[str, Any], old_item: dict[str, Any] | None) -> None:
    stub.add_client_error(
        "put_item",
        service_error_code="ConditionalCheckFailedException",
        service_message=PROVIDER_DETAIL,
        http_status_code=400,
        expected_params=expected_params,
        modeled_fields={"Item": old_item} if old_item is not None else None,
    )


def test_append_puts_a_new_record_only_where_none_exists(client: Any) -> None:
    """The append is one conditional put of the whole record under INCIDENT#<uuid>/UPDATE#<seq>."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("put_item", {}, expected_params=APPEND_PARAMS)

        result = store.append(DRAFT)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == DRAFT


def test_latest_is_one_newest_first_query_that_round_trips_every_field(client: Any) -> None:
    """The stored attributes read back into an equal record, approver and approval time included."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": [APPROVED_ITEM]}, expected_params=LATEST_PARAMS)

        result = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == APPROVED


@pytest.mark.parametrize("origin", list(StatusUpdateOrigin))
def test_an_origin_is_written_as_its_own_attribute_and_read_back(client: Any, origin: StatusUpdateOrigin) -> None:
    """A record with an origin stores it as a plain string attribute; no key or index changes."""
    store = DynamoDbStatusUpdateStore(client)
    item = {**DRAFT_ITEM, "origin": {"S": origin.value}}

    with Stubber(client) as stub:
        stub.add_response("put_item", {}, expected_params={**APPEND_PARAMS, "Item": item})
        stub.add_response("query", {"Items": [item]}, expected_params=LATEST_PARAMS)

        appended = store.append(replace(DRAFT, origin=origin))
        latest = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert appended.is_success
    assert latest.data == replace(DRAFT, origin=origin)


def test_a_record_stored_without_an_origin_reads_back_with_none(client: Any) -> None:
    """Records written before origins existed load unchanged, origin None, and are never rewritten."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": [DRAFT_ITEM]}, expected_params=LATEST_PARAMS)

        result = store.latest(INCIDENT_ID)

    assert result.data is not None
    assert result.data.origin is None


def test_latest_for_an_incident_without_updates_is_success_with_nothing(client: Any) -> None:
    """No update yet is a normal answer, not a failure: the first draft reads the whole conversation."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": []}, expected_params=LATEST_PARAMS)

        result = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data is None


def test_list_reads_every_page_and_keeps_the_newest_first_order(client: Any) -> None:
    """The query runs descending by sort key; the second page is fetched with the first page's end key."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": [SECOND_ITEM], "LastEvaluatedKey": PAGE_ONE_END}, expected_params=QUERY_PARAMS)
        stub.add_response("query", {"Items": [DRAFT_ITEM]}, expected_params={**QUERY_PARAMS, "ExclusiveStartKey": PAGE_ONE_END})

        result = store.list_for_incident(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert [update.sequence for update in result.data or ()] == [2, 1]


def test_append_retry_of_the_same_record_is_success(client: Any) -> None:
    """An SDK retry after a lost response finds its own record; equal old and new items mean the write landed."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        _condition_failed(stub, APPEND_PARAMS, DRAFT_ITEM)

        result = store.append(DRAFT)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == DRAFT


def test_append_to_a_sequence_taken_by_another_record_is_a_conflict(client: Any) -> None:
    """Two writers claiming the same next sequence: the second is refused, not merged."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        _condition_failed(stub, APPEND_PARAMS, {**DRAFT_ITEM, "author": {"S": "U0OTHER"}})

        result = store.append(DRAFT)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "STATUS_UPDATE_CONFLICT"
    assert PROVIDER_DETAIL not in (result.message or "")


def test_transition_replaces_the_record_only_while_it_is_in_the_expected_state(client: Any) -> None:
    """Approval stores the edited text and approver in one write conditioned on the stored state."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("put_item", {}, expected_params=TRANSITION_PARAMS)

        result = store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == APPROVED


def test_transition_after_the_state_moved_on_is_a_conflict(client: Any) -> None:
    """Another responder approved first with different text; this approval is refused."""
    store = DynamoDbStatusUpdateStore(client)
    approved_by_someone_else = {**APPROVED_ITEM, "approver": {"S": "U0OTHER"}}

    with Stubber(client) as stub:
        _condition_failed(stub, TRANSITION_PARAMS, approved_by_someone_else)

        result = store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "STATUS_UPDATE_CONFLICT"


def test_transition_of_a_missing_record_is_a_conflict(client: Any) -> None:
    """With no stored record the condition fails and nothing is returned; nothing is created."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        _condition_failed(stub, TRANSITION_PARAMS, None)

        result = store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "STATUS_UPDATE_CONFLICT"


def test_transition_retry_of_the_same_write_is_success(client: Any) -> None:
    """The first attempt landed, so the retry's condition fails against the very record it wrote."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        _condition_failed(stub, TRANSITION_PARAMS, APPROVED_ITEM)

        result = store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

        stub.assert_no_pending_responses()

    assert result.is_success


@pytest.mark.parametrize(
    ("expected_state", "update"),
    [
        (StatusUpdateState.DRAFT, DRAFT),
        (StatusUpdateState.APPROVED, APPROVED),
        (StatusUpdateState.PUBLISHED, DRAFT),
        (StatusUpdateState.PUBLISHED, replace(APPROVED, state=StatusUpdateState.PUBLISHED, published_at=PUBLISHED_AT)),
    ],
)
def test_an_illegal_transition_raises_before_any_write(
    client: Any, expected_state: StatusUpdateState, update: StatusUpdate
) -> None:
    """Only draft->approved, approved->published and published->approved exist; anything else sends nothing."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        with pytest.raises(ValueError, match="transition"):
            store.transition(update, expected_state=expected_state)

        stub.assert_no_pending_responses()


def test_publishing_writes_who_published_it_while_the_record_is_approved(client: Any) -> None:
    """The publish is one put of the record with published_at and published_by, conditioned on the stored approved state."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("put_item", {}, expected_params=PUBLISH_PARAMS)

        result = store.transition(_published(), expected_state=StatusUpdateState.APPROVED)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == _published()


def test_marking_not_published_writes_the_approved_record_while_it_is_published(client: Any) -> None:
    """The undo puts the record back without published_at and published_by, conditioned on the stored published state."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("put_item", {}, expected_params=UNPUBLISH_PARAMS)

        result = store.transition(APPROVED, expected_state=StatusUpdateState.PUBLISHED)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == APPROVED


def test_marking_not_published_after_someone_else_did_is_a_conflict(client: Any) -> None:
    """The stored record is already approved with other data, so the published-state condition fails."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        _condition_failed(stub, UNPUBLISH_PARAMS, {**APPROVED_ITEM, "approver": {"S": "U0OTHER"}})

        result = store.transition(APPROVED, expected_state=StatusUpdateState.PUBLISHED)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "STATUS_UPDATE_CONFLICT"


def test_a_published_record_round_trips_who_published_it(client: Any) -> None:
    """A stored published_by reads back into the record with the publication time."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": [PUBLISHED_ITEM]}, expected_params=LATEST_PARAMS)

        result = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == _published()


def test_a_published_item_without_published_by_reads_as_nobody(client: Any) -> None:
    """An item stored before published_by existed reads with published_by None, not as unreadable."""
    store = DynamoDbStatusUpdateStore(client)
    legacy = {key: value for key, value in PUBLISHED_ITEM.items() if key != "published_by"}

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": [legacy]}, expected_params=LATEST_PARAMS)

        result = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.is_success
    assert result.data == _published(published_by=None)


def test_a_malformed_stored_item_is_unreadable(client: Any) -> None:
    """An item missing fields or holding an unknown state is reported, never half-parsed."""
    store = DynamoDbStatusUpdateStore(client)
    malformed = {**DRAFT_ITEM, "state": {"S": "archived"}}

    with Stubber(client) as stub:
        stub.add_response("query", {"Items": [malformed]}, expected_params=LATEST_PARAMS)

        result = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "STATUS_UPDATE_UNREADABLE"


def test_throttling_is_transient_with_a_retry_hint(client: Any) -> None:
    """A throttled query reports a retryable error with the configured hint."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_client_error(
            "query",
            service_error_code="ThrottlingException",
            service_message=PROVIDER_DETAIL,
            http_status_code=400,
            expected_params=LATEST_PARAMS,
        )

        result = store.latest(INCIDENT_ID)

        stub.assert_no_pending_responses()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.retry_after == get_aws_settings().TRANSIENT_RETRY_AFTER_SECONDS
    assert PROVIDER_DETAIL not in (result.message or "")


@pytest.mark.parametrize(
    ("error_code", "expected_status"),
    [
        # A missing table is a broken store, not an incident without updates.
        ("ResourceNotFoundException", OperationStatus.PERMANENT_ERROR),
        ("AccessDeniedException", OperationStatus.UNAUTHORIZED),
    ],
)
def test_store_errors_on_append_are_classified(client: Any, error_code: str, expected_status: OperationStatus) -> None:
    """Store failures carry the botocore code and a generic message."""
    store = DynamoDbStatusUpdateStore(client)

    with Stubber(client) as stub:
        stub.add_client_error(
            "put_item",
            service_error_code=error_code,
            service_message=PROVIDER_DETAIL,
            http_status_code=400,
            expected_params=APPEND_PARAMS,
        )

        result = store.append(DRAFT)

        stub.assert_no_pending_responses()

    assert result.status is expected_status
    assert result.error_code == error_code
    assert PROVIDER_DETAIL not in (result.message or "")


def test_a_connection_failure_is_transient(client: Any) -> None:
    """A BotoCoreError never reaches the caller as an exception; it is a retryable error result."""
    store = DynamoDbStatusUpdateStore(client)
    endpoint_error = EndpointConnectionError(endpoint_url="https://dynamodb.ca-central-1.amazonaws.com")

    with patch.object(client, "put_item", side_effect=endpoint_error):
        result = store.append(DRAFT)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "EndpointConnectionError"


@pytest.mark.parametrize(
    "params", [APPEND_PARAMS, TRANSITION_PARAMS, PUBLISH_PARAMS, UNPUBLISH_PARAMS, QUERY_PARAMS, LATEST_PARAMS]
)
def test_every_request_targets_only_the_status_update_table(params: dict[str, Any]) -> None:
    """Stubber matches these exact params, so no request reaches the legacy incidents item or its incident_updates list."""
    assert params["TableName"] == TABLE
    assert "incident_updates" not in repr(params)
    assert "incident_updates" not in Path(status_updates.__file__).read_text(encoding="utf-8")


def test_the_builder_asks_the_shared_factory_for_a_dynamodb_client_only_when_called(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is built at import; the builder uses the in-account client with standard retries."""
    factory = MagicMock()
    monkeypatch.setattr(status_updates, "get_aws_client", factory)

    store = status_updates.build_status_update_store()

    assert isinstance(store, DynamoDbStatusUpdateStore)
    factory.assert_called_once_with("dynamodb", role_arn=get_aws_settings().SERVICE_ROLE_MAP.get("dynamodb") or None)
