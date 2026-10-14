"""Conditional-write store factory."""

import structlog

from contracts.coordination import ConditionalWriteStore
from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore
from infrastructure.coordination.settings import get_conditional_write_settings
from integrations.aws.client import get_aws_client

logger = structlog.get_logger().bind(component="coordination.factory")

_conditional_write_store_instance: ConditionalWriteStore | None = None


def get_conditional_write_store() -> ConditionalWriteStore:
    """Get application-scoped conditional-write store singleton."""
    global _conditional_write_store_instance

    if _conditional_write_store_instance is not None:
        return _conditional_write_store_instance

    dynamodb = get_aws_client("dynamodb")
    _conditional_write_store_instance = DynamoDBConditionalWriteStore(
        dynamodb,
        settings=get_conditional_write_settings(),
    )
    logger.info("initialized_conditional_write_store", backend="dynamodb")
    return _conditional_write_store_instance


def build_conditional_write_store(in_progress_ttl_seconds: int) -> ConditionalWriteStore:
    """Build a non-singleton conditional-write store with a custom in-progress TTL."""
    settings = get_conditional_write_settings().model_copy(
        update={"IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS": in_progress_ttl_seconds}
    )
    dynamodb = get_aws_client("dynamodb")
    logger.debug("built_conditional_write_store", backend="dynamodb", in_progress_ttl_seconds=in_progress_ttl_seconds)
    return DynamoDBConditionalWriteStore(dynamodb, settings=settings)


def reset_conditional_write_store() -> None:
    """Reset the conditional-write store singleton (for tests)."""
    global _conditional_write_store_instance
    _conditional_write_store_instance = None
    logger.debug("reset_conditional_write_store_singleton")
