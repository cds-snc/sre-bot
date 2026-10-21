"""Conditional-write store and lease store providers."""

from functools import cache

import structlog

from contracts.coordination import ConditionalWriteStore, LeaseStore, ReadFailurePolicy
from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore
from infrastructure.coordination.settings import get_conditional_write_settings
from integrations.aws.client import get_aws_client

logger = structlog.get_logger().bind(component="coordination.factory")


def build_conditional_write_store(in_progress_ttl_seconds: int) -> ConditionalWriteStore:
    """Build a non-singleton conditional-write store with a custom in-progress TTL."""
    settings = get_conditional_write_settings().model_copy(
        update={"idempotency_in_progress_ttl_seconds": in_progress_ttl_seconds}
    )
    dynamodb = get_aws_client("dynamodb")
    logger.debug("built_conditional_write_store", backend="dynamodb", in_progress_ttl_seconds=in_progress_ttl_seconds)
    return DynamoDBConditionalWriteStore(dynamodb, settings=settings)


def build_lease_store(in_progress_ttl_seconds: int) -> LeaseStore:
    """Build a fail-closed lease store whose lease TTL is in_progress_ttl_seconds."""
    return LeaseStore(
        build_conditional_write_store(in_progress_ttl_seconds=in_progress_ttl_seconds),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )


@cache
def get_lease_store(ttl_seconds: int) -> LeaseStore:
    """Return a lease store singleton for the provided lease TTL."""
    return build_lease_store(in_progress_ttl_seconds=ttl_seconds)
