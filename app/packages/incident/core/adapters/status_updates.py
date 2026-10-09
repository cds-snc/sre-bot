"""Interim ``StatusUpdateStore`` directly over DynamoDB.

Each update is its own item in ``sre_bot_incident_status_updates`` under
``PK = INCIDENT#<incident id>`` and ``SK = UPDATE#<sequence, zero-padded to 6>``,
so a newest-first query on the partition lists an incident's updates and a
one-item query reads the latest. The keys are permanent; this module moves onto
the storage contract with TASK-108/109 (decisions/incident-management.md).

Every write is one conditional put: an append only where no item exists, a
state change only while the stored state is the expected one. A failed
condition returns the stored item (``ALL_OLD``); when it equals the item being
written, the write is an SDK retry of one that already landed and is reported as
success. The adapter owns every SDK failure: expected botocore errors become
classified results with a generic message, and unclassified errors propagate as
programmer errors.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings
from packages.incident.core.domain import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)

if TYPE_CHECKING:
    from types_boto3_dynamodb.client import DynamoDBClient

logger = structlog.get_logger()

# Declared in terraform/dynamodb.tf.
STATUS_UPDATES_TABLE = "sre_bot_incident_status_updates"

_SK_PREFIX = "UPDATE#"
_STORE_FAILED_MESSAGE = "The status update store is unavailable."
_CONFLICT_MESSAGE = "The status update was changed or taken by another writer."
_UNREADABLE_MESSAGE = "A stored status update could not be read."

type _Item = dict[str, Any]


class _UnreadableItemError(Exception):
    """A stored item that does not deserialize into a ``StatusUpdate``."""


class DynamoDbStatusUpdateStore:
    """Store each incident status update as its own DynamoDB item."""

    def __init__(self, client: DynamoDBClient) -> None:
        self._client = client

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence; a different record already there is a conflict."""
        return self._put(update, operation="append", condition={"ConditionExpression": "attribute_not_exists(SK)"})

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Replace the stored update with ``update`` while its stored state is ``expected_state``.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        _check_transition(expected_state, update.state)
        return self._put(
            update,
            operation="transition",
            condition={
                "ConditionExpression": "attribute_exists(SK) AND #state = :expected",
                "ExpressionAttributeNames": {"#state": "state"},
                "ExpressionAttributeValues": {":expected": {"S": expected_state.value}},
            },
        )

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update, or success with ``None`` when it has none."""

        def read() -> StatusUpdate | None:
            items = self._client.query(**_query_params(incident_id), Limit=1).get("Items", [])
            return _from_item(items[0]) if items else None

        return self._read("latest", incident_id, read)

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""

        def read() -> Sequence[StatusUpdate]:
            pages = self._client.get_paginator("query").paginate(**_query_params(incident_id))
            return tuple(_from_item(item) for page in pages for item in page.get("Items", []))

        return self._read("list_for_incident", incident_id, read)

    def _put(self, update: StatusUpdate, *, operation: str, condition: Mapping[str, Any]) -> OperationResult[StatusUpdate]:
        item = _to_item(update)
        try:
            self._client.put_item(
                TableName=STATUS_UPDATES_TABLE, Item=item, ReturnValuesOnConditionCheckFailure="ALL_OLD", **condition
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                return _store_failed(exc, operation, update.incident_id)
            if exc.response.get("Item") == item:
                return OperationResult.success(data=update)
            logger.info("status_update_conflict", operation=operation, incident_id=update.incident_id, sequence=update.sequence)
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR, message=_CONFLICT_MESSAGE, error_code=ErrorCode.STATUS_UPDATE_CONFLICT
            )
        except BotoCoreError as exc:
            return _store_failed(exc, operation, update.incident_id)
        return OperationResult.success(data=update)

    def _read[T](self, operation: str, incident_id: str, read: Callable[[], T]) -> OperationResult[T]:
        try:
            return OperationResult.success(data=read())
        except (ClientError, BotoCoreError) as exc:
            return _store_failed(exc, operation, incident_id)
        except _UnreadableItemError as exc:
            logger.error("status_update_unreadable", operation=operation, incident_id=incident_id, reason=str(exc))
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR, message=_UNREADABLE_MESSAGE, error_code=ErrorCode.STATUS_UPDATE_UNREADABLE
            )


def _check_transition(current: StatusUpdateState, target: StatusUpdateState) -> None:
    if not current.can_move_to(target):
        raise ValueError(f"no status update transition from {current} to {target}")


def _store_failed[T](exc: ClientError | BotoCoreError, operation: str, incident_id: str) -> OperationResult[T]:
    status, error_code, retry_after = classify_aws_error(exc)
    if status is OperationStatus.NOT_FOUND:
        # A missing table is a broken store, not an incident without updates.
        status = OperationStatus.PERMANENT_ERROR
    logger.warning(
        "status_update_store_failed", operation=operation, incident_id=incident_id, status=status.value, error_code=error_code
    )
    return OperationResult.error(status, message=_STORE_FAILED_MESSAGE, error_code=error_code, retry_after=retry_after)


def _partition_key(incident_id: str) -> str:
    return f"INCIDENT#{incident_id}"


def _query_params(incident_id: str) -> dict[str, Any]:
    return {
        "TableName": STATUS_UPDATES_TABLE,
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :prefix)",
        "ExpressionAttributeValues": {":pk": {"S": _partition_key(incident_id)}, ":prefix": {"S": _SK_PREFIX}},
        "ScanIndexForward": False,
    }


def _to_item(update: StatusUpdate) -> _Item:
    item: _Item = {
        "PK": {"S": _partition_key(update.incident_id)},
        "SK": {"S": f"{_SK_PREFIX}{update.sequence:06d}"},
        "incident_id": {"S": update.incident_id},
        "sequence": {"N": str(update.sequence)},
        "state": {"S": update.state.value},
        "stage": {"S": update.stage.value},
        "en": _text_to_item(update.en),
        "fr": _text_to_item(update.fr),
        "next_update_at": _time_to_item(update.next_update_at),
        "author": {"S": update.author},
        "transcript_cutoff": _time_to_item(update.transcript_cutoff),
        "transcript_fingerprint": {"S": update.transcript_fingerprint},
        "created_at": _time_to_item(update.created_at),
    }
    if update.approver is not None:
        item["approver"] = {"S": update.approver}
    if update.approved_at is not None:
        item["approved_at"] = _time_to_item(update.approved_at)
    if update.published_at is not None:
        item["published_at"] = _time_to_item(update.published_at)
    if update.published_by is not None:
        item["published_by"] = {"S": update.published_by}
    if update.origin is not None:
        item["origin"] = {"S": update.origin.value}
    return item


def _text_to_item(text: StatusUpdateText) -> _Item:
    return {
        "M": {
            "affected_service": {"S": text.affected_service},
            "impact": {"S": text.impact},
            "current_action": {"S": text.current_action},
            "workaround": {"S": text.workaround},
        }
    }


def _time_to_item(value: datetime) -> _Item:
    return {"S": value.astimezone(UTC).isoformat()}


def _from_item(item: _Item) -> StatusUpdate:
    try:
        return StatusUpdate(
            incident_id=item["incident_id"]["S"],
            sequence=int(item["sequence"]["N"]),
            state=StatusUpdateState(item["state"]["S"]),
            stage=StatusUpdateStage(item["stage"]["S"]),
            en=_text_from_item(item["en"]),
            fr=_text_from_item(item["fr"]),
            next_update_at=datetime.fromisoformat(item["next_update_at"]["S"]),
            author=item["author"]["S"],
            transcript_cutoff=datetime.fromisoformat(item["transcript_cutoff"]["S"]),
            transcript_fingerprint=item["transcript_fingerprint"]["S"],
            created_at=datetime.fromisoformat(item["created_at"]["S"]),
            approver=item["approver"]["S"] if "approver" in item else None,
            approved_at=datetime.fromisoformat(item["approved_at"]["S"]) if "approved_at" in item else None,
            published_at=datetime.fromisoformat(item["published_at"]["S"]) if "published_at" in item else None,
            published_by=item["published_by"]["S"] if "published_by" in item else None,
            origin=StatusUpdateOrigin(item["origin"]["S"]) if "origin" in item else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise _UnreadableItemError(f"{type(exc).__name__}: {exc}") from exc


def _text_from_item(value: _Item) -> StatusUpdateText:
    fields = value["M"]
    return StatusUpdateText(
        affected_service=fields["affected_service"]["S"],
        impact=fields["impact"]["S"],
        current_action=fields["current_action"]["S"],
        workaround=fields["workaround"]["S"],
    )


def build_status_update_store() -> DynamoDbStatusUpdateStore:
    """Build the store on an in-account, standard-retry dynamodb client.

    Retries are safe: a replayed conditional put that finds its own item is
    reported as success.
    """
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("dynamodb") or None
    return DynamoDbStatusUpdateStore(get_aws_client("dynamodb", role_arn=role_arn))
