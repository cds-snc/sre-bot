"""Interim ``IncidentLookup`` over the legacy incidents DynamoDB table.

The legacy table is keyed by the incident's UUID ``id`` and has no index on
``channel_id``, so a conversation is resolved by scanning the whole table with
a filter, page by page. Every page is read even after a match, so a channel that
maps to two incidents is refused instead of resolved arbitrarily.

Tolerated until TASK-38.1's incident store serves the same interface
(decisions/incident-management.md Migration). The adapter owns every SDK
failure: expected botocore errors become classified results with a generic
message, and unclassified errors propagate as programmer errors.
"""

from typing import TYPE_CHECKING

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_dynamodb.client import DynamoDBClient

logger = structlog.get_logger()

# The legacy table declared in terraform/dynamodb.tf; deleted with this adapter.
_LEGACY_INCIDENTS_TABLE = "incidents"

_LOOKUP_FAILED_MESSAGE = "The incident lookup is unavailable."


class LegacyIncidentTableLookup:
    """Resolve a conversation to its incident UUID by scanning the legacy table."""

    def __init__(self, client: DynamoDBClient) -> None:
        self._client = client

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        """Return the UUID of the one incident whose channel is ``conversation_id``.

        Returns:
            Success with the UUID; NOT_FOUND with ``NOT_AN_INCIDENT`` when no
            incident names the conversation (or the id is blank);
            PERMANENT_ERROR with ``AMBIGUOUS_INCIDENT_CONVERSATION`` when more
            than one does; otherwise the classified store failure.
        """
        if not conversation_id.strip():
            return _not_an_incident()
        log = logger.bind(operation="find_incident_for_conversation", conversation_id=conversation_id)
        try:
            incident_ids = self._scan_incident_ids(conversation_id)
        except (ClientError, BotoCoreError) as exc:
            status, error_code, retry_after = classify_aws_error(exc)
            if status is OperationStatus.NOT_FOUND:
                # A missing table is a broken store; NOT_FOUND is reserved for "not an incident".
                status = OperationStatus.PERMANENT_ERROR
            log.warning("incident_lookup_failed", status=status.value, error_code=error_code)
            return OperationResult.error(status, message=_LOOKUP_FAILED_MESSAGE, error_code=error_code, retry_after=retry_after)
        if not incident_ids:
            return _not_an_incident()
        if len(incident_ids) > 1:
            log.warning("incident_lookup_ambiguous", match_count=len(incident_ids))
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="More than one incident is recorded for this conversation.",
                error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION,
            )
        return OperationResult.success(data=incident_ids[0])

    def _scan_incident_ids(self, channel_id: str) -> list[str]:
        paginator = self._client.get_paginator("scan")
        pages = paginator.paginate(
            TableName=_LEGACY_INCIDENTS_TABLE,
            FilterExpression="channel_id = :channel_id",
            ExpressionAttributeValues={":channel_id": {"S": channel_id}},
            ProjectionExpression="#id",
            ExpressionAttributeNames={"#id": "id"},
        )
        return [item["id"]["S"] for page in pages for item in page.get("Items", [])]


def _not_an_incident() -> OperationResult[str]:
    return OperationResult.error(
        OperationStatus.NOT_FOUND,
        message="No incident is recorded for this conversation.",
        error_code=ErrorCode.NOT_AN_INCIDENT,
    )


def build_legacy_incident_lookup() -> LegacyIncidentTableLookup:
    """Build the lookup on an in-account, standard-retry dynamodb client; reads are replay-safe."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("dynamodb") or None
    return LegacyIncidentTableLookup(get_aws_client("dynamodb", role_arn=role_arn))
