"""Idempotency cache factory."""

import structlog

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore
from infrastructure.idempotency.protocol import IdempotencyStore
from infrastructure.idempotency.settings import (
    get_idempotency_settings,
)

logger = structlog.get_logger().bind(component="idempotency.factory")

_idempotency_store_instance: IdempotencyStore | None = None


def get_idempotency_store() -> IdempotencyStore:
    """Get application-scoped idempotency store singleton."""
    global _idempotency_store_instance

    if _idempotency_store_instance is not None:
        return _idempotency_store_instance

    _idempotency_store_instance = DynamoDBIdempotencyStore(idempotency_settings=get_idempotency_settings())
    logger.info("initialized_idempotency_store", backend="dynamodb")
    return _idempotency_store_instance


def build_idempotency_store(in_progress_ttl_seconds: int) -> IdempotencyStore:
    """Build a non-singleton idempotency store with a custom in-progress TTL."""
    settings = get_idempotency_settings().model_copy(update={"IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS": in_progress_ttl_seconds})
    return DynamoDBIdempotencyStore(idempotency_settings=settings)


def reset_idempotency_store() -> None:
    """Reset the idempotency store singleton (for tests)."""
    global _idempotency_store_instance
    _idempotency_store_instance = None
    logger.debug("reset_idempotency_store_singleton")
